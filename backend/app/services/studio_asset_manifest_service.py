"""Studio asset manifests over the single-object StorageService contract.

This module owns the collection/manifest layer only.  A manifest entry always
points at one concrete StorageObject; the storage backend never receives a
directory operation from here.  Legacy directory prefixes are read as a
compatibility fallback and are never exposed as host filesystem paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from mimetypes import guess_type
from pathlib import PurePosixPath
import logging
import uuid
import zipfile
from io import BytesIO

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import (
    NotebookTemplate,
    StorageObject,
    StudioAssetManifest,
    StudioAssetManifestEntry,
)
from app.services.storage_object_binding_service import (
    register_active_object,
    retire_bound_object,
)
from app.services.studio_asset_service import StudioAssetBundleService
from app.storage import (
    InvalidStorageKey,
    StorageArea,
    StorageConflict,
    StorageError,
    StorageService,
)


logger = logging.getLogger("studio_asset_manifest")


@dataclass(frozen=True)
class StudioAssetInfo:
    relative_path: str
    storage_object_id: int | None
    content_type: str | None
    size_bytes: int | None
    sha256: str | None
    object_key: str


@dataclass(frozen=True)
class StagedStudioAssetBundle:
    prefix: str | None
    entries: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class DraftAssetBindingPlan:
    staged: StagedStudioAssetBundle
    old_bindings: tuple[tuple[int, str], ...]
    old_legacy_prefix: str | None


@dataclass(frozen=True)
class VersionAssetBindingPlan:
    prefix: str | None
    manifest_id: int
    copied_keys: tuple[str, ...]


def validate_relative_asset_path(value: str) -> str:
    """Return a canonical relative POSIX path or raise InvalidStorageKey."""
    if not isinstance(value, str) or not value or "\x00" in value:
        raise InvalidStorageKey("asset path must be a non-empty string")
    if "\\" in value or value.startswith("/") or value.endswith("/"):
        raise InvalidStorageKey("asset path must use safe POSIX segments")
    parts = tuple(value.split("/"))
    if any(not part or part in {".", ".."} for part in parts):
        raise InvalidStorageKey("asset path contains an invalid path segment")
    if parts and ":" in parts[0]:
        raise InvalidStorageKey("asset path cannot contain a drive prefix")
    if len(value) > 500:
        raise InvalidStorageKey("asset path is too long")
    return PurePosixPath(value).as_posix()


def _content_type(path: str) -> str:
    return guess_type(path)[0] or "application/octet-stream"


class StudioAssetManifestService:
    """Manage draft/version manifests and their concrete object rows."""

    area = StorageArea.STUDIO
    namespace = "studio-assets"

    def __init__(self, storage: StorageService) -> None:
        self.storage = storage
        self.bundles = StudioAssetBundleService(storage)

    @classmethod
    def from_settings(cls, settings: Settings) -> "StudioAssetManifestService":
        return cls(StorageService.from_settings(settings))

    @staticmethod
    def public_legacy_prefix(value: str | None) -> str | None:
        if not value:
            return None
        try:
            return validate_relative_asset_path(value)
        except InvalidStorageKey:
            # A corrupt historical value must never leak to an API response.
            return None

    def stage_bundle(
        self,
        template_id: int,
        revision: int,
        assets: tuple[tuple[str, bytes], ...] | list[tuple[str, bytes]],
    ) -> StagedStudioAssetBundle:
        normalized: list[tuple[str, bytes]] = []
        seen: set[str] = set()
        try:
            for relative_path, content in assets:
                relative_path = validate_relative_asset_path(relative_path)
                if relative_path in seen:
                    raise StorageConflict(f"duplicate asset path: {relative_path}")
                if not isinstance(content, bytes):
                    raise TypeError("asset content must be bytes")
                seen.add(relative_path)
                normalized.append((relative_path, content))
        except InvalidStorageKey:
            raise

        if not normalized:
            return StagedStudioAssetBundle(prefix=None, entries=())

        prefix = (
            PurePosixPath("templates")
            / str(template_id)
            / f"draft-r{revision}-{uuid.uuid4().hex[:12]}"
        ).as_posix()
        self.bundles.put(prefix, normalized)
        return StagedStudioAssetBundle(
            prefix=prefix,
            entries=tuple((relative, f"{prefix}/{relative}") for relative, _ in normalized),
        )

    def cleanup_staged_bundle(self, staged: StagedStudioAssetBundle) -> None:
        if not staged.prefix:
            return
        try:
            self.bundles.delete(staged.prefix)
        except StorageError:
            logger.error("failed to clean staged Studio asset bundle: %s", staged.prefix, exc_info=True)

    def bind_draft_assets(
        self,
        db: Session,
        template: NotebookTemplate,
        *,
        revision: int,
        staged: StagedStudioAssetBundle,
        created_by_id: int,
    ) -> DraftAssetBindingPlan:
        manifest = db.scalar(
            select(StudioAssetManifest).where(
                StudioAssetManifest.template_id == template.id
            )
        )
        if manifest is None:
            manifest = StudioAssetManifest(template_id=template.id, revision=revision)
            db.add(manifest)
            db.flush()

        old_rows = db.execute(
            select(StudioAssetManifestEntry, StorageObject)
            .join(StorageObject, StorageObject.id == StudioAssetManifestEntry.storage_object_id)
            .where(StudioAssetManifestEntry.manifest_id == manifest.id)
        ).all()
        old_bindings = tuple(
            (entry.storage_object_id, obj.object_key) for entry, obj in old_rows
        )
        db.execute(
            delete(StudioAssetManifestEntry).where(
                StudioAssetManifestEntry.manifest_id == manifest.id
            )
        )
        db.flush()

        manifest.revision = revision
        for relative_path, object_key in staged.entries:
            physical = self.storage.head(self.area, object_key)
            obj = register_active_object(
                db,
                self.storage,
                area=self.area,
                namespace=self.namespace,
                object_key=object_key,
                original_filename=PurePosixPath(relative_path).name,
                content_type=_content_type(relative_path),
                size_bytes=physical.size,
                created_by_id=created_by_id,
            )
            db.add(
                StudioAssetManifestEntry(
                    manifest_id=manifest.id,
                    storage_object_id=obj.id,
                    relative_path=relative_path,
                )
            )

        old_legacy_prefix = self.public_legacy_prefix(template.draft_assets_dir)
        template.draft_assets_dir = staged.prefix
        return DraftAssetBindingPlan(
            staged=staged,
            old_bindings=old_bindings,
            old_legacy_prefix=old_legacy_prefix,
        )

    def touch_draft_revision(self, db: Session, template_id: int, revision: int) -> None:
        manifest = db.scalar(
            select(StudioAssetManifest).where(
                StudioAssetManifest.template_id == template_id
            )
        )
        if manifest is not None:
            manifest.revision = revision

    def finalize_draft_assets(
        self,
        db: Session,
        plan: DraftAssetBindingPlan,
    ) -> None:
        for object_id, object_key in plan.old_bindings:
            retire_bound_object(
                db,
                self.storage,
                object_id=object_id,
                area=self.area,
                legacy_key=object_key,
                logger_name="studio_asset_manifest",
            )
        if plan.old_legacy_prefix and plan.old_legacy_prefix != plan.staged.prefix:
            try:
                self.bundles.delete(plan.old_legacy_prefix)
            except StorageError:
                logger.error(
                    "failed to clean legacy Studio asset bundle: %s",
                    plan.old_legacy_prefix,
                    exc_info=True,
                )

    def manifest_for_template(
        self, db: Session, template_id: int
    ) -> StudioAssetManifest | None:
        return db.scalar(
            select(StudioAssetManifest).where(
                StudioAssetManifest.template_id == template_id
            )
        )

    def manifest_for_version(
        self, db: Session, version_id: int
    ) -> StudioAssetManifest | None:
        return db.scalar(
            select(StudioAssetManifest).where(
                StudioAssetManifest.version_id == version_id
            )
        )

    def _manifest_assets(
        self, db: Session, manifest_id: int
    ) -> tuple[StudioAssetInfo, ...]:
        rows = db.execute(
            select(StudioAssetManifestEntry, StorageObject)
            .join(StorageObject, StorageObject.id == StudioAssetManifestEntry.storage_object_id)
            .where(StudioAssetManifestEntry.manifest_id == manifest_id)
            .order_by(StudioAssetManifestEntry.relative_path)
        ).all()
        return tuple(
            StudioAssetInfo(
                relative_path=entry.relative_path,
                storage_object_id=obj.id,
                content_type=obj.content_type,
                size_bytes=obj.size_bytes,
                sha256=obj.sha256,
                object_key=obj.object_key,
            )
            for entry, obj in rows
        )

    def _legacy_assets(self, prefix: str | None) -> tuple[StudioAssetInfo, ...]:
        prefix = self.public_legacy_prefix(prefix)
        if not prefix:
            return ()
        try:
            objects = self.storage.list_objects(self.area, prefix)
        except StorageError:
            return ()
        root = f"{prefix}/"
        assets: list[StudioAssetInfo] = []
        for obj in objects:
            if not obj.key.startswith(root):
                continue
            relative = validate_relative_asset_path(obj.key[len(root) :])
            assets.append(
                StudioAssetInfo(
                    relative_path=relative,
                    storage_object_id=None,
                    content_type=_content_type(relative),
                    size_bytes=obj.size,
                    sha256=None,
                    object_key=obj.key,
                )
            )
        return tuple(assets)

    def draft_assets(
        self, db: Session, template: NotebookTemplate
    ) -> tuple[int | None, tuple[StudioAssetInfo, ...]]:
        manifest = self.manifest_for_template(db, template.id)
        if manifest is not None:
            return manifest.id, self._manifest_assets(db, manifest.id)
        return None, self._legacy_assets(template.draft_assets_dir)

    def version_assets(
        self, db: Session, version_id: int, legacy_prefix: str | None
    ) -> tuple[int | None, tuple[StudioAssetInfo, ...]]:
        manifest = self.manifest_for_version(db, version_id)
        if manifest is not None:
            return manifest.id, self._manifest_assets(db, manifest.id)
        return None, self._legacy_assets(legacy_prefix)

    def _source_assets(
        self,
        db: Session,
        template_id: int,
        legacy_prefix: str | None,
    ) -> tuple[StudioAssetInfo, ...]:
        manifest = self.manifest_for_template(db, template_id)
        if manifest is not None:
            return self._manifest_assets(db, manifest.id)
        return self._legacy_assets(legacy_prefix)

    def create_version_snapshot(
        self,
        db: Session,
        *,
        template_id: int,
        version_id: int,
        version_number: int,
        legacy_prefix: str | None,
        created_by_id: int,
    ) -> VersionAssetBindingPlan:
        source_assets = self._source_assets(db, template_id, legacy_prefix)
        manifest = StudioAssetManifest(version_id=version_id, revision=version_number)
        db.add(manifest)
        db.flush()

        if not source_assets:
            return VersionAssetBindingPlan(
                prefix=None,
                manifest_id=manifest.id,
                copied_keys=(),
            )

        prefix = (
            PurePosixPath("templates")
            / str(template_id)
            / "versions"
            / str(version_number)
        ).as_posix()
        copied_keys: list[str] = []
        try:
            for source in source_assets:
                relative_path = validate_relative_asset_path(source.relative_path)
                destination_key = f"{prefix}/{relative_path}"
                self.storage.copy(self.area, source.object_key, destination_key)
                copied_keys.append(destination_key)
                physical = self.storage.head(self.area, destination_key)
                obj = register_active_object(
                    db,
                    self.storage,
                    area=self.area,
                    namespace=self.namespace,
                    object_key=destination_key,
                    original_filename=PurePosixPath(relative_path).name,
                    content_type=source.content_type or _content_type(relative_path),
                    size_bytes=physical.size,
                    created_by_id=created_by_id,
                )
                db.add(
                    StudioAssetManifestEntry(
                        manifest_id=manifest.id,
                        storage_object_id=obj.id,
                        relative_path=relative_path,
                    )
                )
        except Exception:
            self.cleanup_version_snapshot(
                VersionAssetBindingPlan(
                    prefix=prefix,
                    manifest_id=manifest.id,
                    copied_keys=tuple(copied_keys),
                )
            )
            raise

        return VersionAssetBindingPlan(
            prefix=prefix,
            manifest_id=manifest.id,
            copied_keys=tuple(copied_keys),
        )

    def cleanup_version_snapshot(self, plan: VersionAssetBindingPlan | None) -> None:
        if plan is None:
            return
        for key in reversed(plan.copied_keys):
            try:
                self.storage.delete(self.area, key)
            except StorageError:
                logger.error("failed to clean version Studio asset: %s", key, exc_info=True)

    def export_zip(
        self,
        notebook: bytes,
        assets: tuple[StudioAssetInfo, ...],
    ) -> bytes:
        names = {"notebook.ipynb"}
        output = BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("notebook.ipynb", notebook)
            for asset in assets:
                relative_path = validate_relative_asset_path(asset.relative_path)
                if relative_path in names:
                    raise StorageConflict(f"duplicate export asset: {relative_path}")
                names.add(relative_path)
                archive.writestr(relative_path, self.storage.read(self.area, asset.object_key))
        return output.getvalue()
