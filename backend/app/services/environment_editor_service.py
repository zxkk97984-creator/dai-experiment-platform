"""Domain services for the V2 administrator environment editor.

The module owns the draft/version state machine.  HTTP handlers should only
translate request/response DTOs and enqueue the returned job; they must not
mutate a published version directly.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from collections.abc import Mapping

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import api_error
from app.models import (
    Assignment,
    Course,
    EnvironmentBuildJob,
    EnvironmentDraft,
    EnvironmentProfile,
    EnvironmentVersion,
    EnvironmentPublication,
    ExperimentModule,
    ExperimentRecord,
    NotebookTemplate,
    NotebookTemplateVersion,
    JudgeQuestion,
    PackageCatalog,
    ProfileVersionPackage,
)
from app.services.environment_spec import (
    DEFAULT_MEMORY_MB,
    DEFAULT_PYTHON_VERSION,
    canonical_requested_spec,
    normalize_requested_spec,
    apt_snapshot_key,
    pip_source_key,
    validate_memory_mb,
    validate_python_version,
)
from app.services.environment_builder_v2 import build_config_fingerprint


_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_ACTIVE_JOB_STATUSES = ("queued", "building")
_FAILED_JOB_STATUSES = ("failed", "timed_out")
_DISPLAY_NAME_CONFLICT_CODE = "PROFILE_DISPLAY_NAME_CONFLICT"
_DISPLAY_NAME_CONFLICT_MESSAGE = "环境名称已存在，请使用其他名称"


def _empty_spec() -> dict:
    return {"schema_version": 1, "python_packages": [], "system_packages": []}


def _error(
    status: int,
    code: str,
    message: str,
    *,
    fields: dict | None = None,
    field_errors: list[dict] | None = None,
    retryable: bool | None = None,
):
    if retryable is None:
        retryable = False
    return api_error(
        status,
        code,
        message,
        fields=fields,
        field_errors=field_errors,
        retryable=retryable,
    )


def _new_slug(db: Session, requested: str | None) -> str:
    if requested is not None:
        slug = requested.strip()
        if not _SLUG_RE.fullmatch(slug):
            raise _error(422, "SLUG_INVALID", "slug 只允许小写字母、数字和短横线")
        if db.scalar(select(EnvironmentProfile.id).where(EnvironmentProfile.slug == slug)) is not None:
            raise _error(409, "PROFILE_SLUG_CONFLICT", "环境 slug 已存在")
        return slug

    for _ in range(8):
        slug = f"env-{secrets.token_hex(4)}"
        if db.scalar(select(EnvironmentProfile.id).where(EnvironmentProfile.slug == slug)) is None:
            return slug
    raise _error(503, "SLUG_GENERATION_FAILED", "暂时无法生成唯一环境标识，请稍后重试")


def _normalize_display_name(display_name: str) -> str:
    normalized = display_name.strip()
    if not normalized:
        raise _error(422, "DISPLAY_NAME_REQUIRED", "环境名称不能为空")
    return normalized


def _display_name_exists(
    db: Session,
    display_name: str,
    *,
    exclude_profile_id: int | None = None,
) -> bool:
    statement = select(EnvironmentProfile.id).where(
        func.lower(func.trim(EnvironmentProfile.display_name)) == display_name.lower()
    )
    if exclude_profile_id is not None:
        statement = statement.where(EnvironmentProfile.id != exclude_profile_id)
    return db.scalar(statement) is not None


def _ensure_unique_display_name(
    db: Session,
    display_name: str,
    *,
    exclude_profile_id: int | None = None,
) -> str:
    normalized = _normalize_display_name(display_name)
    if _display_name_exists(db, normalized, exclude_profile_id=exclude_profile_id):
        raise _error(409, _DISPLAY_NAME_CONFLICT_CODE, _DISPLAY_NAME_CONFLICT_MESSAGE)
    return normalized


def _validate_draft_inputs(
    python_version: str, minimum_memory_mb: int, requested_spec: Mapping
) -> tuple[str, int, dict]:
    try:
        python_version = validate_python_version(python_version)
        minimum_memory_mb = validate_memory_mb(minimum_memory_mb)
        requested_spec = normalize_requested_spec(requested_spec)
    except ValueError as exc:
        message = str(exc)
        if "Python 版本" in message:
            code = "PYTHON_VERSION_UNSUPPORTED"
        elif any(token in message for token in ("pip 包", "锁定版本", "Python 包", "import 名")):
            code = "PACKAGE_NAME_INVALID"
        elif "系统包" in message:
            code = "PACKAGE_NAME_INVALID"
        else:
            code = "DRAFT_INPUT_INVALID"
        raise _error(
            422,
            code,
            message,
        ) from exc
    return python_version, minimum_memory_mb, requested_spec


def _active_job(db: Session, draft: EnvironmentDraft) -> EnvironmentBuildJob | None:
    if draft.active_build_job_id is None:
        return None
    job = db.get(EnvironmentBuildJob, draft.active_build_job_id)
    if job is not None and job.status in _ACTIVE_JOB_STATUSES:
        return job
    return None


def _direct_spec_from_version(db: Session, version: EnvironmentVersion) -> dict:
    """Clone resolved direct versions; fall back to the legacy catalog links."""

    resolved = version.resolved_spec if isinstance(version.resolved_spec, dict) else {}
    direct = resolved.get("direct_python_packages")
    system_direct = resolved.get("direct_system_packages")
    if isinstance(direct, list):
        python_packages = []
        for item in direct:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            python_packages.append(
                {
                    "name": item["name"],
                    "version": item.get("resolved_version") or item.get("requested_version"),
                    "import_names": list(item.get("import_names") or []),
                }
            )
        system_packages = []
        if isinstance(system_direct, list):
            for item in system_direct:
                if isinstance(item, dict) and item.get("name"):
                    system_packages.append(
                        {
                            "name": item["name"],
                            "version": item.get("resolved_version") or item.get("version"),
                        }
                    )
        try:
            return normalize_requested_spec(
                {
                    "schema_version": 1,
                    "python_packages": python_packages,
                    "system_packages": system_packages,
                }
            )
        except ValueError:
            # A legacy inferred result may contain a version string that the
            # stricter V2 validator rejects.  The old catalog fallback below is
            # safer than copying an unverifiable declaration into a new draft.
            pass

    packages = list(
        db.scalars(
            select(PackageCatalog)
            .join(ProfileVersionPackage, ProfileVersionPackage.package_catalog_id == PackageCatalog.id)
            .where(ProfileVersionPackage.environment_version_id == version.id)
            .order_by(ProfileVersionPackage.display_order, PackageCatalog.id)
        ).all()
    )
    python_packages = []
    seen = set()
    for package in packages:
        name = package.normalized_name
        if name in seen:
            continue
        seen.add(name)
        python_packages.append(
            {
                "name": package.pip_name,
                "version": package.locked_version,
                "import_names": list(package.import_names or []),
            }
        )
    return normalize_requested_spec(
        {"schema_version": 1, "python_packages": python_packages, "system_packages": []}
    )


def create_profile_with_draft(
    db: Session,
    *,
    display_name: str,
    description: str | None,
    slug: str | None,
    actor_id: int | None,
    settings: Settings,
) -> tuple[EnvironmentProfile, EnvironmentDraft]:
    """Create the long-lived Profile and its initial editable Draft together."""

    if not settings.environment_editor_v2_enabled:
        raise _error(409, "LEGACY_ENVIRONMENT_API_DISABLED", "环境编辑器 V2 尚未启用")
    display_name = _ensure_unique_display_name(db, display_name)
    slug = _new_slug(db, slug)
    profile = EnvironmentProfile(
        slug=slug,
        display_name=display_name,
        description=description,
        status="active",
        created_by_id=actor_id,
    )
    db.add(profile)
    db.flush()
    draft = EnvironmentDraft(
        profile_id=profile.id,
        revision=1,
        state="editing",
        python_version=DEFAULT_PYTHON_VERSION,
        minimum_memory_mb=DEFAULT_MEMORY_MB,
        requested_spec=_empty_spec(),
        created_by_id=actor_id,
        updated_by_id=actor_id,
    )
    db.add(draft)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _error(409, "PROFILE_SLUG_CONFLICT", "环境 slug 已存在") from exc
    db.refresh(profile)
    db.refresh(draft)
    return profile, draft


def create_or_get_draft(
    db: Session,
    profile_id: int,
    *,
    actor_id: int | None,
    settings: Settings,
) -> EnvironmentDraft:
    """Return the single draft, cloning the current published version if needed."""

    if not settings.environment_editor_v2_enabled:
        raise _error(409, "LEGACY_ENVIRONMENT_API_DISABLED", "环境编辑器 V2 尚未启用")
    profile = db.execute(
        select(EnvironmentProfile).where(EnvironmentProfile.id == profile_id).with_for_update()
    ).scalar_one_or_none()
    if profile is None:
        raise _error(404, "NOT_FOUND", "环境不存在")
    existing = db.get(EnvironmentDraft, profile_id)
    if existing is not None:
        return existing
    if profile.status != "active":
        raise _error(409, "PROFILE_INACTIVE", "已归档环境不能创建草稿")

    source = db.get(EnvironmentVersion, profile.current_version_id) if profile.current_version_id else None
    if source is None:
        python_version = DEFAULT_PYTHON_VERSION
        minimum_memory_mb = DEFAULT_MEMORY_MB
        requested_spec = _empty_spec()
        source_id = None
    else:
        python_version = source.python_version
        minimum_memory_mb = source.minimum_memory_mb
        requested_spec = _direct_spec_from_version(db, source)
        source_id = source.id
    draft = EnvironmentDraft(
        profile_id=profile.id,
        source_version_id=source_id,
        revision=1,
        state="editing",
        python_version=python_version,
        minimum_memory_mb=minimum_memory_mb,
        requested_spec=requested_spec,
        created_by_id=actor_id,
        updated_by_id=actor_id,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


def get_draft(db: Session, profile_id: int) -> EnvironmentDraft:
    draft = db.execute(
        select(EnvironmentDraft).where(EnvironmentDraft.profile_id == profile_id).with_for_update()
    ).scalar_one_or_none()
    if draft is None:
        raise _error(404, "DRAFT_NOT_FOUND", "环境草稿不存在")
    return draft


def save_draft(
    db: Session,
    profile_id: int,
    *,
    revision: int,
    python_version: str,
    minimum_memory_mb: int,
    requested_spec: Mapping,
    actor_id: int | None,
) -> EnvironmentDraft:
    """Atomically replace editable fields using optimistic locking."""

    profile = db.execute(
        select(EnvironmentProfile).where(EnvironmentProfile.id == profile_id).with_for_update()
    ).scalar_one_or_none()
    if profile is None:
        raise _error(404, "NOT_FOUND", "环境不存在")
    draft = db.execute(
        select(EnvironmentDraft).where(EnvironmentDraft.profile_id == profile_id).with_for_update()
    ).scalar_one_or_none()
    if draft is None:
        raise _error(404, "DRAFT_NOT_FOUND", "环境草稿不存在")
    if draft.revision != revision:
        raise _error(
            409,
            "DRAFT_REVISION_CONFLICT",
            "环境草稿已被其他管理员修改",
            fields={"expected_revision": revision, "actual_revision": draft.revision},
            field_errors=[
                {
                    "path": "revision",
                    "code": "DRAFT_REVISION_CONFLICT",
                    "message": f"服务器当前 revision 为 {draft.revision}",
                }
            ],
        )
    if _active_job(db, draft) is not None or draft.state == "building":
        raise _error(409, "DRAFT_BUILD_ACTIVE", "构建进行中，暂不能编辑草稿")

    python_version, minimum_memory_mb, requested_spec = _validate_draft_inputs(
        python_version, minimum_memory_mb, requested_spec
    )
    changed = (
        draft.python_version != python_version
        or draft.minimum_memory_mb != minimum_memory_mb
        or canonical_requested_spec(draft.requested_spec) != canonical_requested_spec(requested_spec)
    )
    if not changed:
        return draft

    draft.python_version = python_version
    draft.minimum_memory_mb = minimum_memory_mb
    draft.requested_spec = requested_spec
    draft.revision += 1
    draft.updated_by_id = actor_id
    draft.state = "editing"
    # Any material edit invalidates the failed/ready candidate.  Keeping the
    # old EnvironmentVersion preserves its number and logs, while a new build
    # will receive the next version number.
    draft.candidate_version_id = None
    draft.active_build_job_id = None
    db.commit()
    db.refresh(draft)
    return draft


def abandon_draft(db: Session, profile_id: int, *, expected_revision: int) -> None:
    profile = db.execute(
        select(EnvironmentProfile).where(EnvironmentProfile.id == profile_id).with_for_update()
    ).scalar_one_or_none()
    if profile is None:
        raise _error(404, "NOT_FOUND", "环境不存在")
    draft = db.execute(
        select(EnvironmentDraft).where(EnvironmentDraft.profile_id == profile_id).with_for_update()
    ).scalar_one_or_none()
    if draft is None:
        raise _error(404, "DRAFT_NOT_FOUND", "环境草稿不存在")
    if draft.revision != expected_revision:
        raise _error(409, "DRAFT_REVISION_CONFLICT", "环境草稿已被其他管理员修改")
    if _active_job(db, draft) is not None or draft.state == "building":
        raise _error(409, "DRAFT_BUILD_ACTIVE", "构建进行中，暂不能放弃草稿")
    db.delete(draft)
    db.commit()


def _base_image_ref(settings: Settings, python_version: str) -> str:
    try:
        validate_python_version(python_version)
    except ValueError as exc:
        raise _error(422, "PYTHON_VERSION_UNSUPPORTED", str(exc)) from exc
    if settings.environment_editor_v2_enabled:
        image_ref = settings.env_python_base_images.get(python_version)
        if not image_ref:
            raise _error(503, "BUILD_SERVICE_UNAVAILABLE", "该 Python 版本没有配置基础镜像")
        return image_ref
    return settings.env_base_image


def _manifest_sha256(
    *,
    base_image_ref: str,
    python_version: str,
    minimum_memory_mb: int,
    requested_spec: dict,
    settings: Settings,
) -> str:
    from app.services.environment_builder_v2 import platform_runner_sha256

    try:
        source_key = pip_source_key(settings.env_pip_index_url)
    except ValueError as exc:
        raise _error(503, "BUILD_SERVICE_UNAVAILABLE", "Python 包源配置无效", retryable=True) from exc
    payload = {
        "schema_version": 1,
        "base_image_ref": base_image_ref,
        "python_version": python_version,
        "minimum_memory_mb": minimum_memory_mb,
        "requested_spec": requested_spec,
        "platform_python_packages": dict(sorted(settings.env_platform_python_packages.items())),
        "platform_bundle_version": settings.env_platform_bundle_version,
        "platform_runner_sha256": platform_runner_sha256(),
        "pip_source_key": source_key,
        "apt_snapshot_key": apt_snapshot_key(
            python_version, settings.env_apt_snapshot_sources.get(python_version)
        ),
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _latest_job(db: Session, version_id: int) -> EnvironmentBuildJob | None:
    return db.scalar(
        select(EnvironmentBuildJob)
        .where(EnvironmentBuildJob.environment_version_id == version_id)
        .order_by(EnvironmentBuildJob.attempt_number.desc(), EnvironmentBuildJob.id.desc())
        .limit(1)
    )


def _candidate_is_unchanged(draft: EnvironmentDraft, version: EnvironmentVersion) -> bool:
    try:
        return canonical_requested_spec(draft.requested_spec) == canonical_requested_spec(
            version.requested_spec
        )
    except ValueError:
        return False


def _draft_matches_source(
    db: Session,
    draft: EnvironmentDraft,
    *,
    python_version: str,
    minimum_memory_mb: int,
    requested_spec: dict,
) -> bool:
    """Detect a cloned draft with no material change from its source image."""

    if draft.source_version_id is None:
        return False
    source = db.get(EnvironmentVersion, draft.source_version_id)
    if source is None or source.python_version != python_version or source.minimum_memory_mb != minimum_memory_mb:
        return False
    try:
        return canonical_requested_spec(requested_spec) == canonical_requested_spec(
            _direct_spec_from_version(db, source)
        )
    except ValueError:
        return False


def _new_build_attempt(
    db: Session,
    *,
    version: EnvironmentVersion,
    draft: EnvironmentDraft,
    actor_id: int | None,
    settings: Settings,
    retry_of: EnvironmentBuildJob | None = None,
) -> EnvironmentBuildJob:
    last_attempt = db.scalar(
        select(func.max(EnvironmentBuildJob.attempt_number)).where(
            EnvironmentBuildJob.environment_version_id == version.id
        )
    )
    job = EnvironmentBuildJob(
        environment_version_id=version.id,
        status="queued",
        phase="queued",
        build_mode=version.build_mode,
        attempt_number=(last_attempt or 0) + 1,
        retry_of_id=retry_of.id if retry_of else None,
        build_config_fingerprint=(
            retry_of.build_config_fingerprint
            if retry_of is not None
            else (
                build_config_fingerprint(version.python_version, settings)
                if version.build_mode == "v2"
                else None
            )
        ),
        created_by_id=actor_id,
    )
    db.add(job)
    db.flush()
    version.status = "queued"
    draft.candidate_version_id = version.id
    draft.active_build_job_id = job.id
    draft.state = "building"
    return job


def start_draft_build(
    db: Session,
    profile_id: int,
    *,
    actor_id: int | None,
    settings: Settings,
) -> tuple[EnvironmentVersion, EnvironmentBuildJob]:
    """Snapshot a draft into a version, or retry its unchanged failed candidate."""

    profile = db.execute(
        select(EnvironmentProfile).where(EnvironmentProfile.id == profile_id).with_for_update()
    ).scalar_one_or_none()
    if profile is None:
        raise _error(404, "NOT_FOUND", "环境不存在")
    if profile.status != "active":
        raise _error(409, "PROFILE_INACTIVE", "已归档环境不能构建")
    draft = db.execute(
        select(EnvironmentDraft).where(EnvironmentDraft.profile_id == profile_id).with_for_update()
    ).scalar_one_or_none()
    if draft is None:
        raise _error(404, "DRAFT_NOT_FOUND", "环境草稿不存在")
    if _active_job(db, draft) is not None or draft.state == "building":
        raise _error(409, "DRAFT_BUILD_ACTIVE", "该环境已有进行中的构建")

    python_version, minimum_memory_mb, requested_spec = _validate_draft_inputs(
        draft.python_version, draft.minimum_memory_mb, draft.requested_spec
    )
    candidate = db.get(EnvironmentVersion, draft.candidate_version_id) if draft.candidate_version_id else None
    if candidate is not None and _candidate_is_unchanged(draft, candidate):
        latest = _latest_job(db, candidate.id)
        if (
            latest is not None
            and latest.status in _FAILED_JOB_STATUSES
            and candidate.status == "failed"
            and draft.state == "failed"
        ):
            job = _new_build_attempt(
                db,
                version=candidate,
                draft=draft,
                actor_id=actor_id,
                settings=settings,
                retry_of=latest,
            )
            db.commit()
            db.refresh(candidate)
            db.refresh(job)
            return candidate, job
        if candidate.status == "available":
            raise _error(409, "NO_ENVIRONMENT_CHANGES", "当前草稿已经生成可发布版本")

    if _draft_matches_source(
        db,
        draft,
        python_version=python_version,
        minimum_memory_mb=minimum_memory_mb,
        requested_spec=requested_spec,
    ):
        raise _error(409, "NO_ENVIRONMENT_CHANGES", "草稿与当前发布版本没有实际变化")

    base_image_ref = _base_image_ref(settings, python_version)
    max_number = db.scalar(
        select(func.max(EnvironmentVersion.version_number)).where(
            EnvironmentVersion.profile_id == profile_id
        )
    )
    version = EnvironmentVersion(
        profile_id=profile_id,
        version_number=(max_number or 0) + 1,
        source_version_id=draft.source_version_id,
        status="queued",
        build_mode="v2" if settings.environment_editor_v2_enabled else "legacy",
        base_image_ref=base_image_ref,
        python_version=python_version,
        minimum_memory_mb=minimum_memory_mb,
        requested_spec=requested_spec,
        manifest_sha256=_manifest_sha256(
            base_image_ref=base_image_ref,
            python_version=python_version,
            minimum_memory_mb=minimum_memory_mb,
            requested_spec=requested_spec,
            settings=settings,
        ),
        created_by_id=actor_id,
    )
    db.add(version)
    db.flush()
    job = _new_build_attempt(
        db, version=version, draft=draft, actor_id=actor_id, settings=settings
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _error(409, "VERSION_NUMBER_CONFLICT", "环境版本号发生并发冲突，请刷新后重试") from exc
    db.refresh(version)
    db.refresh(job)
    return version, job


def can_retry_build(db: Session, job_id: int) -> bool:
    """Single server-side capability predicate used by API and admin UI."""

    job = db.get(EnvironmentBuildJob, job_id)
    if job is None or job.status not in _FAILED_JOB_STATUSES:
        return False
    version = db.get(EnvironmentVersion, job.environment_version_id)
    if version is None or version.status == "available":
        return False
    profile = db.get(EnvironmentProfile, version.profile_id)
    draft = db.get(EnvironmentDraft, version.profile_id) if profile else None
    if draft is None or draft.candidate_version_id != version.id:
        return False
    if draft.state != "failed" or _active_job(db, draft) is not None:
        return False
    latest = _latest_job(db, version.id)
    if latest is None or latest.id != job.id:
        return False
    return _candidate_is_unchanged(draft, version)


def retry_draft_build(
    db: Session,
    job_id: int,
    *,
    actor_id: int | None,
    settings: Settings,
) -> tuple[EnvironmentVersion, EnvironmentBuildJob]:
    job = db.execute(
        select(EnvironmentBuildJob).where(EnvironmentBuildJob.id == job_id).with_for_update()
    ).scalar_one_or_none()
    if job is None:
        raise _error(404, "NOT_FOUND", "构建任务不存在")
    version = db.get(EnvironmentVersion, job.environment_version_id)
    if version is None:
        raise _error(404, "NOT_FOUND", "环境版本不存在")
    profile = db.execute(
        select(EnvironmentProfile).where(EnvironmentProfile.id == version.profile_id).with_for_update()
    ).scalar_one_or_none()
    draft = db.execute(
        select(EnvironmentDraft).where(EnvironmentDraft.profile_id == version.profile_id).with_for_update()
    ).scalar_one_or_none()
    if profile is None or draft is None:
        raise _error(409, "BUILD_NOT_RETRYABLE", "该构建任务当前不可重试")
    # The public capability is only advisory.  Re-evaluate the whole
    # predicate after locking Job, Profile, and Draft so a concurrent save
    # cannot rebind an old failed candidate.
    latest = _latest_job(db, version.id)
    if (
        job.status not in _FAILED_JOB_STATUSES
        or version.status == "available"
        or draft.candidate_version_id != version.id
        or draft.state != "failed"
        or _active_job(db, draft) is not None
        or latest is None
        or latest.id != job.id
        or not _candidate_is_unchanged(draft, version)
    ):
        raise _error(409, "BUILD_NOT_RETRYABLE", "该构建任务当前不可重试")
    if _active_job(db, draft) is not None:
        raise _error(409, "DRAFT_BUILD_ACTIVE", "该环境已有进行中的构建")
    new_job = _new_build_attempt(
        db,
        version=version,
        draft=draft,
        actor_id=actor_id,
        settings=settings,
        retry_of=job,
    )
    db.commit()
    db.refresh(version)
    db.refresh(new_job)
    return version, new_job


def mark_build_failed(db: Session, job_id: int, *, error_code: str, detail: dict | None = None) -> None:
    """Transition a V2 job to a terminal failure and release the draft lock."""

    job = db.get(EnvironmentBuildJob, job_id)
    if job is None:
        return
    job.status = "failed"
    job.phase = "done"
    job.error_code = error_code
    job.error_detail = detail
    version = db.get(EnvironmentVersion, job.environment_version_id)
    if version is not None:
        version.status = "failed"
        draft = db.get(EnvironmentDraft, version.profile_id)
        if draft is not None and draft.active_build_job_id == job.id:
            draft.active_build_job_id = None
            draft.state = "failed"
    db.commit()


def archive_profile(db: Session, profile_id: int, *, active: bool) -> EnvironmentProfile:
    profile = db.execute(
        select(EnvironmentProfile).where(EnvironmentProfile.id == profile_id).with_for_update()
    ).scalar_one_or_none()
    if profile is None:
        raise _error(404, "NOT_FOUND", "环境不存在")
    draft = db.execute(
        select(EnvironmentDraft).where(EnvironmentDraft.profile_id == profile_id).with_for_update()
    ).scalar_one_or_none()
    if draft is not None and (_active_job(db, draft) is not None or draft.state == "building"):
        raise _error(409, "DRAFT_BUILD_ACTIVE", "构建进行中，暂不能归档环境")
    profile.status = "active" if active else "inactive"
    db.commit()
    db.refresh(profile)
    return profile


def publish_version(
    db: Session,
    profile_id: int,
    *,
    version_id: int,
    expected_current_version_id: int | None,
    actor_id: int | None,
) -> EnvironmentPublication:
    """Publish a ready candidate or roll back to an already published image."""

    profile = db.execute(
        select(EnvironmentProfile).where(EnvironmentProfile.id == profile_id).with_for_update()
    ).scalar_one_or_none()
    if profile is None:
        raise _error(404, "NOT_FOUND", "环境不存在")
    if profile.status != "active":
        raise _error(409, "PROFILE_INACTIVE", "已归档环境不能发布或回滚")
    if profile.current_version_id != expected_current_version_id:
        raise _error(
            409,
            "CURRENT_VERSION_CONFLICT",
            "当前发布版本已变化，请刷新后重试",
            fields={"current_version_id": profile.current_version_id},
        )
    version = db.get(EnvironmentVersion, version_id)
    if version is None or version.profile_id != profile_id:
        raise _error(404, "NOT_FOUND", "环境版本不存在")
    if version.status != "available" or not version.image_digest:
        raise _error(409, "VERSION_NOT_PUBLISHABLE", "只有构建成功且镜像可用的版本才能发布")

    draft = db.execute(
        select(EnvironmentDraft).where(EnvironmentDraft.profile_id == profile_id).with_for_update()
    ).scalar_one_or_none()
    candidate = draft is not None and draft.candidate_version_id == version.id
    historical = db.scalar(
        select(EnvironmentPublication.id).where(
            EnvironmentPublication.profile_id == profile_id,
            EnvironmentPublication.version_id == version.id,
        )
    )
    if not candidate and historical is None and version.first_published_at is None:
        raise _error(409, "VERSION_NOT_PUBLISHABLE", "目标版本不是当前草稿候选，也没有历史发布记录")
    if draft is not None and not candidate:
        raise _error(409, "DRAFT_BUILD_ACTIVE", "存在未处理草稿，请先发布或放弃草稿")
    if draft is not None and (_active_job(db, draft) is not None or draft.state == "building"):
        raise _error(409, "DRAFT_BUILD_ACTIVE", "构建进行中，暂不能发布")

    previous_id = profile.current_version_id
    if previous_id == version.id:
        existing = db.scalar(
            select(EnvironmentPublication)
            .where(
                EnvironmentPublication.profile_id == profile_id,
                EnvironmentPublication.version_id == version.id,
            )
            .order_by(EnvironmentPublication.created_at.desc(), EnvironmentPublication.id.desc())
            .limit(1)
        )
        if existing is not None:
            return existing

    if version.first_published_at is None:
        from datetime import datetime, timezone

        version.first_published_at = datetime.now(timezone.utc)
        version.first_published_by_id = actor_id
    profile.current_version_id = version.id
    action = "publish" if previous_id is None or candidate else "rollback"
    publication = EnvironmentPublication(
        profile_id=profile_id,
        version_id=version.id,
        previous_version_id=previous_id,
        action=action,
        published_by_id=actor_id,
    )
    db.add(publication)
    if candidate:
        db.delete(draft)
    db.commit()
    db.refresh(publication)
    return publication


def publication_ids_for_profile(db: Session, profile_id: int) -> set[int]:
    return set(
        db.scalars(
            select(EnvironmentPublication.version_id).where(
                EnvironmentPublication.profile_id == profile_id
            )
        ).all()
    )


def _public_option_for_version(
    db: Session,
    profile: EnvironmentProfile,
    version: EnvironmentVersion,
):
    """Build the teacher-safe summary for either a current or historical image."""

    from app.schemas.environments import (
        EnvironmentOptionRead,
        PackageSummary,
        SystemPackageSummary,
    )
    from app.services.environment_service import get_packages_for_version

    resolved = version.resolved_spec if isinstance(version.resolved_spec, dict) else {}
    direct = resolved.get("direct_python_packages")
    if isinstance(direct, list):
        packages = [
            PackageSummary(
                pip_name=str(item.get("name")),
                locked_version=str(item.get("resolved_version") or item.get("requested_version") or ""),
                import_names=list(item.get("import_names") or []),
            )
            for item in direct
            if isinstance(item, dict) and item.get("name")
        ]
    else:
        packages = [
            PackageSummary(
                pip_name=p.pip_name,
                locked_version=p.locked_version,
                import_names=list(p.import_names or []),
            )
            for p in get_packages_for_version(db, version.id)
        ]
    direct_system = resolved.get("direct_system_packages")
    system_packages = [
        SystemPackageSummary(
            name=str(item.get("name")),
            version=item.get("version") or item.get("resolved_version"),
        )
        for item in (
            direct_system if isinstance(direct_system, list) else resolved.get("system_packages") or []
        )
        if isinstance(item, dict) and item.get("name")
    ]
    return EnvironmentOptionRead(
        profile_id=profile.id,
        environment_version_id=version.id,
        slug=profile.slug,
        display_name=profile.display_name,
        description=profile.description,
        version_number=version.version_number,
        packages=packages,
        system_packages=system_packages,
        minimum_memory_mb=version.minimum_memory_mb,
    )


def _teacher_has_environment_binding(
    db: Session,
    version_id: int,
    actor_id: int,
) -> bool:
    """Check that a teacher owns a business object bound to this version.

    This is deliberately an allow-list of immutable binding tables.  A
    publication record alone is not enough to disclose a historical version
    summary to an arbitrary teacher.
    """

    assignment = db.scalar(
        select(Assignment.id)
        .join(Course, Course.id == Assignment.course_id)
        .where(
            Assignment.environment_version_id == version_id,
            Course.teacher_id == actor_id,
        )
        .limit(1)
    )
    if assignment is not None:
        return True
    question = db.scalar(
        select(JudgeQuestion.id)
        .join(Assignment, Assignment.id == JudgeQuestion.assignment_id)
        .join(Course, Course.id == Assignment.course_id)
        .where(
            JudgeQuestion.environment_version_id == version_id,
            Course.teacher_id == actor_id,
        )
        .limit(1)
    )
    if question is not None:
        return True
    notebook_version = db.scalar(
        select(NotebookTemplateVersion.id)
        .join(NotebookTemplate, NotebookTemplate.id == NotebookTemplateVersion.template_id)
        .where(
            NotebookTemplateVersion.environment_version_id == version_id,
            NotebookTemplate.owner_id == actor_id,
        )
        .limit(1)
    )
    if notebook_version is not None:
        return True
    experiment_record = db.scalar(
        select(ExperimentRecord.id)
        .join(ExperimentModule, ExperimentModule.id == ExperimentRecord.module_id)
        .where(
            ExperimentRecord.environment_version_id == version_id,
            ExperimentModule.owner_id == actor_id,
        )
        .limit(1)
    )
    return experiment_record is not None


def teacher_option_for_version(
    db: Session,
    version_id: int,
    *,
    actor_id: int | None = None,
    actor_role: str = "admin",
):
    """Return a safe summary for a bound version, including archived history.

    ``actor_role=admin`` is retained for internal migration/audit callers.
    Teacher requests must prove an actual business binding owned by them.
    """

    version = db.get(EnvironmentVersion, version_id)
    profile = db.get(EnvironmentProfile, version.profile_id) if version else None
    if (
        version is None
        or profile is None
        or version.status != "available"
        or not version.image_digest
    ):
        raise api_error(404, "VERSION_NOT_AVAILABLE", "环境版本不存在或镜像不可用")
    published = db.scalar(
        select(EnvironmentPublication.id).where(
            EnvironmentPublication.profile_id == profile.id,
            EnvironmentPublication.version_id == version.id,
        )
    )
    if actor_role != "admin" and (
        actor_id is None
        or not _teacher_has_environment_binding(db, version.id, actor_id)
    ):
        raise api_error(404, "VERSION_NOT_AVAILABLE", "该环境版本不是已发布的历史版本")
    if published is None and version.first_published_at is None and actor_role != "admin":
        raise api_error(404, "VERSION_NOT_AVAILABLE", "该环境版本不是已发布的历史版本")
    return _public_option_for_version(db, profile, version)


def list_current_available_options(db: Session):
    """Teacher picker view: exactly one current published version per profile."""

    profiles = list(
        db.scalars(
            select(EnvironmentProfile)
            .where(
                EnvironmentProfile.status == "active",
                EnvironmentProfile.current_version_id.is_not(None),
            )
            .order_by(EnvironmentProfile.slug)
        ).all()
    )
    options = []
    for profile in profiles:
        version = db.get(EnvironmentVersion, profile.current_version_id)
        if version is None or version.status != "available" or not version.image_digest:
            continue
        options.append(_public_option_for_version(db, profile, version))
    return options
