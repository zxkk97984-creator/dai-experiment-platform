"""环境档位管理 API（Phase 2：管理员端）

管理端点（package/profile/version/build）全部仅 admin 角色；
教师可调用 GET /environments/available 查看可用的环境版本（不含 digest/tag/构建日志）。
管理员全程只填写包元数据和勾选包，无 Dockerfile/requirements 输入面。
"""
from __future__ import annotations

import re
import shutil
import json
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.dependencies import get_db, get_redis_client, require_roles
from app.errors import api_error
from app.models import (
    EnvironmentBuildJob,
    EnvironmentDraft,
    EnvironmentProfile,
    EnvironmentVersion,
    PackageCatalog,
    ProfileVersionPackage,
)
from app.schemas.environments import (
    BuildReadinessRead,
    EnvironmentBuildEditorRead,
    EnvironmentBuildListRead,
    EnvironmentBuildLogRead,
    EnvironmentBuildRead,
    EnvironmentCapabilities,
    EnvironmentDraftRead,
    EnvironmentDraftUpdate,
    EnvironmentEditorOptionsRead,
    EnvironmentOptionRead,
    EnvironmentProfileEditorListRead,
    EnvironmentProfileEditorRead,
    EnvironmentProfileCreate,
    EnvironmentProfileListRead,
    EnvironmentProfileRead,
    EnvironmentProfileUpdate,
    EnvironmentPublicationCreate,
    EnvironmentPublicationRead,
    EnvironmentVersionEditorRead,
    EnvironmentVersionCreate,
    EnvironmentVersionListRead,
    EnvironmentVersionRead,
    PackageCatalogAdminRead,
    PackageCatalogCreate,
    PackageCatalogUpdate,
    PackageCandidateRead,
)
from app.services.environment_service import (
    create_build_job,
    create_package,
    create_profile,
    create_profile_version,
    deactivate_package,
    enqueue_build_redis,
    is_package_referenced,
    list_available_options,
    list_build_jobs,
    list_packages,
    list_profiles_with_latest,
    list_versions,
    retry_build_job,
    update_package,
    update_profile,
)
from app.services.environment_editor_service import (
    abandon_draft,
    archive_profile,
    can_retry_build,
    create_or_get_draft,
    create_profile_with_draft,
    get_draft,
    list_current_available_options,
    publication_ids_for_profile,
    publish_version,
    retry_draft_build,
    save_draft,
    start_draft_build,
    teacher_option_for_version,
)
from app.services.environment_candidates import get_cached_apt_candidate, search_pip_candidates
from app.services.import_policy import normalize_pip_name
from app.services.environment_spec import (
    DEFAULT_MEMORY_MB,
    DEFAULT_PYTHON_VERSION,
    MAX_PYTHON_PACKAGES,
    MAX_SYSTEM_PACKAGES,
    MAX_MEMORY_MB,
    MIN_MEMORY_MB,
    SUPPORTED_PYTHON_VERSIONS,
    normalize_requested_spec,
    validate_apt_name,
)

router = APIRouter(prefix="/environments")


def _admin_only():
    return Depends(require_roles("admin"))


def _require_v2(settings: Settings) -> None:
    if not settings.environment_editor_v2_enabled:
        raise api_error(
            409,
            "LEGACY_ENVIRONMENT_API_DISABLED",
            "环境编辑器 V2 尚未启用",
            retryable=False,
        )


def _reject_legacy_write(settings: Settings) -> None:
    if settings.environment_editor_v2_enabled:
        raise api_error(
            409,
            "LEGACY_ENVIRONMENT_API_DISABLED",
            "V2 已启用，请使用环境编辑器草稿接口",
            retryable=False,
        )


def _v2_capabilities(db: Session, profile: EnvironmentProfile, draft=None) -> EnvironmentCapabilities:
    from app.models import EnvironmentPublication

    active = profile.status == "active"
    active_job = draft is not None and draft.active_build_job_id is not None and db.scalar(
        select(EnvironmentBuildJob.status).where(EnvironmentBuildJob.id == draft.active_build_job_id)
    ) in ("queued", "building")
    draft_busy = active_job or (draft is not None and draft.state == "building")
    candidate = db.get(EnvironmentVersion, draft.candidate_version_id) if draft and draft.candidate_version_id else None
    latest_job = None
    if candidate is not None:
        latest_job = db.scalar(
            select(EnvironmentBuildJob)
            .where(EnvironmentBuildJob.environment_version_id == candidate.id)
            .order_by(EnvironmentBuildJob.attempt_number.desc(), EnvironmentBuildJob.id.desc())
            .limit(1)
        )
    historical_available = db.scalar(
        select(EnvironmentVersion.id)
        .outerjoin(
            EnvironmentPublication,
            (EnvironmentPublication.profile_id == profile.id)
            & (EnvironmentPublication.version_id == EnvironmentVersion.id),
        )
        .where(
            EnvironmentVersion.profile_id == profile.id,
            EnvironmentVersion.status == "available",
            EnvironmentVersion.image_digest.is_not(None),
            EnvironmentVersion.id != profile.current_version_id,
            (EnvironmentVersion.first_published_at.is_not(None) | EnvironmentPublication.id.is_not(None)),
        )
        .limit(1)
    )
    return EnvironmentCapabilities(
        can_edit_profile=not draft_busy,
        can_create_draft=active and draft is None,
        can_edit_draft=active and draft is not None and not draft_busy and draft.state != "building",
        can_build=active and draft is not None and not draft_busy and draft.state in ("editing", "failed"),
        can_retry=latest_job is not None and can_retry_build(db, latest_job.id),
        can_publish=(
            active
            and draft is not None
            and candidate is not None
            and candidate.status == "available"
            and bool(candidate.image_digest)
            and not draft_busy
        ),
        can_abandon_draft=active and draft is not None and not draft_busy and draft.state != "building",
        can_rollback=active and draft is None and historical_available is not None,
        can_archive=active and not draft_busy,
        can_restore=(not active) and not draft_busy,
    )


def _v2_version_read(
    db: Session,
    version: EnvironmentVersion,
    *,
    current_version_id: int | None,
    published_ids: set[int],
) -> EnvironmentVersionEditorRead:
    def package_map(spec: dict | None, key: str) -> dict[str, dict]:
        value = spec.get(key) if isinstance(spec, dict) else None
        if not isinstance(value, list):
            return {}
        return {
            str(item["name"]): item
            for item in value
            if isinstance(item, dict) and item.get("name")
        }

    def package_diff(before: dict[str, dict], after: dict[str, dict]) -> dict:
        before_names = set(before)
        after_names = set(after)
        changed_names = sorted(
            name for name in before_names & after_names if before[name] != after[name]
        )
        return {
            "added": [after[name] for name in sorted(after_names - before_names)],
            "removed": [before[name] for name in sorted(before_names - after_names)],
            "changed": [
                {"name": name, "from": before[name], "to": after[name]}
                for name in changed_names
            ],
        }

    source = db.get(EnvironmentVersion, version.source_version_id) if version.source_version_id else None
    source_spec = source.requested_spec if source else {}
    target_spec = version.requested_spec if isinstance(version.requested_spec, dict) else {}
    diff = {
        "source_version_id": source.id if source else None,
        "python_version": {
            "from": source.python_version if source else None,
            "to": version.python_version,
        },
        "minimum_memory_mb": {
            "from": source.minimum_memory_mb if source else None,
            "to": version.minimum_memory_mb,
        },
        "python_packages": package_diff(
            package_map(source_spec, "python_packages"),
            package_map(target_spec, "python_packages"),
        ),
        "system_packages": package_diff(
            package_map(source_spec, "system_packages"),
            package_map(target_spec, "system_packages"),
        ),
    }
    source_resolved = source.resolved_spec if source and isinstance(source.resolved_spec, dict) else None
    target_resolved = version.resolved_spec if isinstance(version.resolved_spec, dict) else None
    if source_resolved is not None or target_resolved is not None:
        diff["resolved_python_packages"] = package_diff(
            package_map(source_resolved, "python_lock"),
            package_map(target_resolved, "python_lock"),
        )
    latest_job = db.scalar(
        select(EnvironmentBuildJob)
        .where(EnvironmentBuildJob.environment_version_id == version.id)
        .order_by(EnvironmentBuildJob.attempt_number.desc(), EnvironmentBuildJob.id.desc())
        .limit(1)
    )
    resolved = version.resolved_spec if isinstance(version.resolved_spec, dict) else None
    return EnvironmentVersionEditorRead(
        id=version.id,
        profile_id=version.profile_id,
        version_number=version.version_number,
        source_version_id=version.source_version_id,
        status=version.status,
        python_version=version.python_version,
        minimum_memory_mb=version.minimum_memory_mb,
        requested_spec=version.requested_spec,
        resolved_spec=resolved,
        image_digest=version.image_digest,
        image_size_bytes=(resolved or {}).get("image_size_bytes"),
        first_published_at=version.first_published_at,
        first_published_by_id=version.first_published_by_id,
        available_at=version.available_at,
        created_at=version.created_at,
        published=version.id in published_ids or version.first_published_at is not None,
        current=version.id == current_version_id,
        diff=diff,
        build_report=(latest_job.result_summary if latest_job else None),
    )


def _v2_draft_read(db: Session, profile: EnvironmentProfile, draft) -> EnvironmentDraftRead | None:
    if draft is None:
        return None
    return EnvironmentDraftRead(
        profile_id=draft.profile_id,
        source_version_id=draft.source_version_id,
        candidate_version_id=draft.candidate_version_id,
        active_build_job_id=draft.active_build_job_id,
        revision=draft.revision,
        state=draft.state,
        python_version=draft.python_version,
        minimum_memory_mb=draft.minimum_memory_mb,
        requested_spec=draft.requested_spec,
        capabilities=_v2_capabilities(db, profile, draft),
    )


def _v2_build_read(db: Session, job: EnvironmentBuildJob) -> EnvironmentBuildEditorRead:
    version = db.get(EnvironmentVersion, job.environment_version_id)
    profile = db.get(EnvironmentProfile, version.profile_id) if version else None
    return EnvironmentBuildEditorRead(
        id=job.id,
        environment_version_id=job.environment_version_id,
        profile_display_name=profile.display_name if profile else None,
        profile_slug=profile.slug if profile else None,
        version_number=version.version_number if version else None,
        version_status=version.status if version else None,
        image_digest_short=(version.image_digest[:12] + "…")
        if version and version.image_digest
        else None,
        status=job.status,
        phase=job.phase,
        attempt_number=job.attempt_number,
        retry_of_id=job.retry_of_id,
        worker_id=job.worker_id,
        error_code=job.error_code,
        error_message=job.error_message,
        error_detail=job.error_detail,
        result_summary=job.result_summary,
        started_at=job.started_at,
        finished_at=job.finished_at,
        created_at=job.created_at,
        capabilities=_v2_capabilities(db, profile, db.get(EnvironmentDraft, profile.id))
        if profile
        else EnvironmentCapabilities(),
    )


def _version_list_read(db: Session, version: EnvironmentVersion) -> EnvironmentVersionListRead:
    """版本管理端列表项——附加包摘要（PackageSummaryAdmin 含包目录 id 供复制预选）。"""
    from app.schemas.environments import PackageSummaryAdmin
    from app.services.environment_service import get_packages_for_version

    packages = [
        PackageSummaryAdmin(
            id=p.id,
            pip_name=p.pip_name,
            locked_version=p.locked_version,
            import_names=list(p.import_names or []),
        )
        for p in get_packages_for_version(db, version.id)
    ]
    return EnvironmentVersionListRead.model_validate(version).model_copy(update={"packages": packages})


# ═══════════════════════════════════════════════════════════════
# 包目录（管理端）
# ═══════════════════════════════════════════════════════════════


@router.get("/packages", response_model=list[PackageCatalogAdminRead])
def get_packages(
    status: Literal["active", "inactive"] | None = None,
    db: Session = Depends(get_db),
    current_user: PackageCatalog = _admin_only(),
):
    """包目录列表——默认全部（含 inactive），可选按状态过滤。"""
    pkgs = list_packages(db, status)
    referenced_ids = set(
        db.scalars(select(ProfileVersionPackage.package_catalog_id).distinct()).all()
    )
    return [
        PackageCatalogAdminRead.model_validate(pkg).model_copy(
            update={"referenced": pkg.id in referenced_ids}
        )
        for pkg in pkgs
    ]


@router.post("/packages", response_model=PackageCatalogAdminRead, status_code=201)
def post_package(
    body: PackageCatalogCreate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: PackageCatalog = _admin_only(),
):
    """创建受控包——输入严格校验（无 URL/requirements/pip 参数输入面）。"""
    _reject_legacy_write(settings)
    pkg = create_package(
        db,
        pip_name=body.pip_name,
        locked_version=body.locked_version,
        import_names=body.import_names,
        category_tags=body.category_tags,
        source_key=body.source_key,
        actor_id=current_user.id,
    )
    return PackageCatalogAdminRead.model_validate(pkg)


@router.patch("/packages/{package_id}", response_model=PackageCatalogAdminRead)
def patch_package(
    package_id: int,
    body: PackageCatalogUpdate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: PackageCatalog = _admin_only(),
):
    """更新包目录条目——被版本引用的包核心字段不可原地修改（PACKAGE_IMMUTABLE）。"""
    _reject_legacy_write(settings)
    patch = body.model_dump(exclude_unset=True)
    pkg = update_package(db, package_id, patch, actor_id=current_user.id)
    return PackageCatalogAdminRead.model_validate(pkg).model_copy(
        update={"referenced": is_package_referenced(db, pkg.id)}
    )


@router.delete("/packages/{package_id}", response_model=PackageCatalogAdminRead)
def delete_package(
    package_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: PackageCatalog = _admin_only(),
):
    """删除统一实现为停用——不物理删除，历史环境绑定不受影响。"""
    _reject_legacy_write(settings)
    pkg = deactivate_package(db, package_id, actor_id=current_user.id)
    return PackageCatalogAdminRead.model_validate(pkg)


# ═══════════════════════════════════════════════════════════════
# 环境档位（管理端）
# ═══════════════════════════════════════════════════════════════


@router.get("/profiles", response_model=None)
def get_profiles(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: PackageCatalog = _admin_only(),
):
    """档位列表——含最新可用版本摘要（版本号最大的 available）与包摘要。"""
    if settings.environment_editor_v2_enabled:
        profiles = list(db.scalars(select(EnvironmentProfile).order_by(EnvironmentProfile.slug)).all())
        result = []
        for profile in profiles:
            draft = db.get(EnvironmentDraft, profile.id)
            current = db.get(EnvironmentVersion, profile.current_version_id) if profile.current_version_id else None
            published_ids = publication_ids_for_profile(db, profile.id)
            recent = db.scalar(
                select(EnvironmentBuildJob)
                .join(EnvironmentVersion, EnvironmentVersion.id == EnvironmentBuildJob.environment_version_id)
                .where(EnvironmentVersion.profile_id == profile.id)
                .order_by(EnvironmentBuildJob.created_at.desc(), EnvironmentBuildJob.id.desc())
                .limit(1)
            )
            result.append(
                EnvironmentProfileEditorListRead(
                    id=profile.id,
                    slug=profile.slug,
                    display_name=profile.display_name,
                    description=profile.description,
                    status=profile.status,
                    current_version=_v2_version_read(
                        db, current, current_version_id=profile.current_version_id, published_ids=published_ids
                    )
                    if current
                    else None,
                    draft=_v2_draft_read(db, profile, draft),
                    recent_build=_v2_build_read(db, recent) if recent else None,
                    capabilities=_v2_capabilities(db, profile, draft),
                )
            )
        return result
    out = []
    for profile, ver in list_profiles_with_latest(db):
        latest = None
        if ver is not None:
            latest = _version_list_read(db, ver)
        out.append(
            EnvironmentProfileListRead.model_validate(profile).model_copy(
                update={"latest_version": latest}
            )
        )
    return out


@router.post("/profiles", response_model=None, status_code=201)
def post_profile(
    body: EnvironmentProfileCreate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: PackageCatalog = _admin_only(),
):
    """创建环境档位——slug 唯一。"""
    if settings.environment_editor_v2_enabled:
        profile, draft = create_profile_with_draft(
            db,
            display_name=body.display_name,
            description=body.description,
            slug=body.slug,
            actor_id=current_user.id,
            settings=settings,
        )
        return EnvironmentProfileEditorRead(
            id=profile.id,
            slug=profile.slug,
            display_name=profile.display_name,
            description=profile.description,
            status=profile.status,
            current_version=None,
            draft=_v2_draft_read(db, profile, draft),
            recent_build=None,
            capabilities=_v2_capabilities(db, profile, draft),
            versions=[],
        )
    if body.slug is None:
        raise api_error(422, "SLUG_REQUIRED", "旧环境接口需要填写 slug")
    return create_profile(
        db,
        slug=body.slug,
        display_name=body.display_name,
        description=body.description,
        actor_id=current_user.id,
    )


@router.patch("/profiles/{profile_id}", response_model=None)
def patch_profile(
    profile_id: int,
    body: EnvironmentProfileUpdate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: PackageCatalog = _admin_only(),
):
    """更新档位——展示名/描述/状态；slug 不可变。"""
    patch = body.model_dump(exclude_unset=True)
    if settings.environment_editor_v2_enabled:
        if "status" in patch:
            profile = archive_profile(db, profile_id, active=patch["status"] == "active")
            patch.pop("status", None)
        else:
            profile = db.get(EnvironmentProfile, profile_id)
            if profile is None:
                raise api_error(404, "NOT_FOUND", "环境不存在")
        if patch:
            profile = update_profile(db, profile_id, patch)
        draft = db.get(EnvironmentDraft, profile_id)
        return EnvironmentProfileEditorRead(
            id=profile.id,
            slug=profile.slug,
            display_name=profile.display_name,
            description=profile.description,
            status=profile.status,
            current_version=_v2_version_read(
                db,
                db.get(EnvironmentVersion, profile.current_version_id),
                current_version_id=profile.current_version_id,
                published_ids=publication_ids_for_profile(db, profile.id),
            )
            if profile.current_version_id
            else None,
            draft=_v2_draft_read(db, profile, draft),
            recent_build=None,
            capabilities=_v2_capabilities(db, profile, draft),
            versions=[],
        )
    return update_profile(db, profile_id, patch)


@router.get("/profiles/{profile_id}", response_model=None)
def get_profile_detail(
    profile_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: PackageCatalog = _admin_only(),
):
    _require_v2(settings)
    profile = db.get(EnvironmentProfile, profile_id)
    if profile is None:
        raise api_error(404, "NOT_FOUND", "环境不存在")
    draft = db.get(EnvironmentDraft, profile.id)
    published_ids = publication_ids_for_profile(db, profile.id)
    versions = list_versions(db, profile.id)
    recent = db.scalar(
        select(EnvironmentBuildJob)
        .join(EnvironmentVersion, EnvironmentVersion.id == EnvironmentBuildJob.environment_version_id)
        .where(EnvironmentVersion.profile_id == profile.id)
        .order_by(EnvironmentBuildJob.created_at.desc(), EnvironmentBuildJob.id.desc())
        .limit(1)
    )
    current = db.get(EnvironmentVersion, profile.current_version_id) if profile.current_version_id else None
    return EnvironmentProfileEditorRead(
        id=profile.id,
        slug=profile.slug,
        display_name=profile.display_name,
        description=profile.description,
        status=profile.status,
        current_version=_v2_version_read(
            db, current, current_version_id=profile.current_version_id, published_ids=published_ids
        )
        if current
        else None,
        draft=_v2_draft_read(db, profile, draft),
        recent_build=_v2_build_read(db, recent) if recent else None,
        capabilities=_v2_capabilities(db, profile, draft),
        versions=[
            _v2_version_read(
                db, version, current_version_id=profile.current_version_id, published_ids=published_ids
            )
            for version in versions
        ],
    )


@router.post("/profiles/{profile_id}/draft", response_model=None)
def post_draft(
    profile_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: PackageCatalog = _admin_only(),
):
    _require_v2(settings)
    draft = create_or_get_draft(db, profile_id, actor_id=current_user.id, settings=settings)
    profile = db.get(EnvironmentProfile, profile_id)
    return _v2_draft_read(db, profile, draft)


@router.get("/profiles/{profile_id}/draft", response_model=None)
def get_profile_draft(
    profile_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: PackageCatalog = _admin_only(),
):
    _require_v2(settings)
    profile = db.get(EnvironmentProfile, profile_id)
    if profile is None:
        raise api_error(404, "NOT_FOUND", "环境不存在")
    return _v2_draft_read(db, profile, get_draft(db, profile_id))


@router.put("/profiles/{profile_id}/draft", response_model=None)
def put_profile_draft(
    profile_id: int,
    body: EnvironmentDraftUpdate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: PackageCatalog = _admin_only(),
):
    _require_v2(settings)
    draft = save_draft(
        db,
        profile_id,
        revision=body.revision,
        python_version=body.python_version,
        minimum_memory_mb=body.minimum_memory_mb,
        requested_spec=body.requested_spec.model_dump(),
        actor_id=current_user.id,
    )
    profile = db.get(EnvironmentProfile, profile_id)
    return _v2_draft_read(db, profile, draft)


@router.delete("/profiles/{profile_id}/draft", status_code=204)
def delete_profile_draft(
    profile_id: int,
    expected_revision: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: PackageCatalog = _admin_only(),
):
    _require_v2(settings)
    abandon_draft(db, profile_id, expected_revision=expected_revision)
    return None


@router.post("/profiles/{profile_id}/draft/builds", response_model=None, status_code=202)
def post_draft_build(
    profile_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    redis_client=Depends(get_redis_client),
    current_user: PackageCatalog = _admin_only(),
):
    _require_v2(settings)
    _, job = start_draft_build(db, profile_id, actor_id=current_user.id, settings=settings)
    _enqueue_or_503(redis_client, job, settings)
    return _v2_build_read(db, job)


@router.get("/profiles/{profile_id}/versions", response_model=None)
def get_profile_versions(
    profile_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: PackageCatalog = _admin_only(),
):
    """档位全部版本（管理端可见全部状态）——版本号倒序，附包摘要。"""
    if settings.environment_editor_v2_enabled:
        profile = db.get(EnvironmentProfile, profile_id)
        if profile is None:
            raise api_error(404, "NOT_FOUND", "环境不存在")
        published_ids = publication_ids_for_profile(db, profile.id)
        return [
            _v2_version_read(
                db,
                version,
                current_version_id=profile.current_version_id,
                published_ids=published_ids,
            )
            for version in list_versions(db, profile_id)
        ]
    return [_version_list_read(db, ver) for ver in list_versions(db, profile_id)]


@router.post("/profiles/{profile_id}/versions", response_model=EnvironmentVersionRead, status_code=201)
def post_profile_version(
    profile_id: int,
    body: EnvironmentVersionCreate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: PackageCatalog = _admin_only(),
):
    """创建新版本（draft）——包集合从 package catalog 勾选，无 Dockerfile/requirements 输入。

    并发安全：profile 行 FOR UPDATE 后计算下一个版本号。
    """
    _reject_legacy_write(settings)
    package_ids = list(body.package_ids)
    if package_ids:
        existing_ids = set(
            db.scalars(select(PackageCatalog.id).where(PackageCatalog.id.in_(package_ids))).all()
        )
        missing = [pid for pid in package_ids if pid not in existing_ids]
        if missing:
            raise api_error(404, "PACKAGE_NOT_FOUND", f"包目录条目不存在: {missing}")
    return create_profile_version(
        db,
        profile_id=profile_id,
        package_ids=package_ids,
        actor_id=current_user.id,
        source_version_id=body.source_version_id,
        minimum_memory_mb=body.minimum_memory_mb,
        base_image_ref=settings.env_base_image,
        settings=settings,
    )


@router.post("/profiles/{profile_id}/publications", response_model=EnvironmentPublicationRead, status_code=201)
def post_publication(
    profile_id: int,
    body: EnvironmentPublicationCreate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: PackageCatalog = _admin_only(),
):
    _require_v2(settings)
    return publish_version(
        db,
        profile_id,
        version_id=body.environment_version_id,
        expected_current_version_id=body.expected_current_version_id,
        actor_id=current_user.id,
    )


@router.get("/editor-options", response_model=EnvironmentEditorOptionsRead)
def get_editor_options(
    settings: Settings = Depends(get_settings),
    current_user: PackageCatalog = _admin_only(),
):
    _require_v2(settings)
    return EnvironmentEditorOptionsRead(
        python_versions=list(SUPPORTED_PYTHON_VERSIONS),
        default_python_version=DEFAULT_PYTHON_VERSION,
        minimum_memory_mb=MIN_MEMORY_MB,
        maximum_memory_mb=MAX_MEMORY_MB,
        default_memory_mb=DEFAULT_MEMORY_MB,
        max_python_packages=MAX_PYTHON_PACKAGES,
        max_system_packages=MAX_SYSTEM_PACKAGES,
        source_display_names={"pypi": "平台 Python 镜像", "apt": "Debian 快照"},
    )


@router.get("/build-readiness", response_model=BuildReadinessRead)
def get_build_readiness(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: PackageCatalog = _admin_only(),
):
    _require_v2(settings)
    checks: dict[str, dict] = {}
    docker_ok = shutil.which("docker") is not None
    checks["docker"] = {
        "status": "healthy" if docker_ok else "unavailable",
        "message": "Docker CLI 可用" if docker_ok else "Worker 未发现 Docker CLI",
    }
    image_ok = set(settings.env_python_base_images) == set(SUPPORTED_PYTHON_VERSIONS) and all(
        bool(re.fullmatch(r"[^\s@]+@sha256:[0-9a-f]{64}", value))
        for value in settings.env_python_base_images.values()
    )
    checks["base_images"] = {
        "status": "configured" if image_ok else "misconfigured",
        "message": "已配置三个带 digest 的 Python 基础镜像" if image_ok else "基础镜像必须全部固定到 digest",
    }
    proxy = settings.env_build_http_proxy or ""
    loopback_proxy = bool(re.match(r"^https?://(?:127\.0\.0\.1|localhost|\[::1\])(?::\d+)?", proxy))
    proxy_ok = not loopback_proxy or settings.env_build_network_mode == "host"
    checks["proxy"] = {
        "status": "healthy" if proxy_ok else "unreachable",
        "code": None if proxy_ok else "BUILD_PROXY_UNREACHABLE",
        "message": "显式构建代理配置可用" if proxy_ok else "回环代理不能从默认 Docker 网络访问",
    }
    checks["worker"] = {
        "status": "unknown",
        "message": "Worker 心跳由后台任务更新；数据库补偿扫描仍可接管排队任务",
    }
    pip_source_ok = not settings.env_pip_index_url or bool(
        re.fullmatch(r"https?://[^\s/@]+(?:/[^\s]*)?", settings.env_pip_index_url)
    )
    checks["pip_source"] = {
        "status": "configured" if pip_source_ok else "misconfigured",
        "message": "Python 包源已配置" if pip_source_ok else "Python 包源 URL 无效或包含凭据",
    }
    apt_source_ok = all(
        isinstance(settings.env_apt_snapshot_sources.get(version), list)
        and bool(settings.env_apt_snapshot_sources.get(version))
        for version in SUPPORTED_PYTHON_VERSIONS
    )
    checks["apt_source"] = {
        "status": "configured" if apt_source_ok else "unconfigured",
        "message": "三个 Python 基础镜像均有 Debian 快照源"
        if apt_source_ok
        else "尚未配置 Debian 快照源；系统包构建会被阻止",
    }
    return BuildReadinessRead(
        ready=docker_ok and image_ok and proxy_ok and pip_source_ok and apt_source_ok,
        checks=checks,
    )


@router.get("/package-candidates", response_model=list[PackageCandidateRead])
def get_package_candidates(
    manager: Literal["pip", "apt"] = Query(...),
    q: str = Query("", min_length=0, max_length=128),
    python_version: str = Query(DEFAULT_PYTHON_VERSION),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    redis_client=Depends(get_redis_client),
    current_user: PackageCatalog = _admin_only(),
):
    _require_v2(settings)
    if python_version not in SUPPORTED_PYTHON_VERSIONS:
        raise api_error(422, "PYTHON_VERSION_UNSUPPORTED", "Python 版本不受支持", retryable=False)
    query = q.strip().lower()
    if manager == "pip":
        stmt = select(PackageCatalog).where(PackageCatalog.status == "active")
        if query:
            stmt = stmt.where(
                PackageCatalog.normalized_name.like(f"%{query}%")
                | PackageCatalog.pip_name.like(f"%{query}%")
            )
        packages = db.scalars(stmt.order_by(PackageCatalog.normalized_name, PackageCatalog.locked_version)).all()
        grouped: dict[str, dict] = {}
        for package in packages:
            item = grouped.setdefault(
                package.normalized_name,
                {"manager": "pip", "name": package.pip_name, "versions": [], "compatible": None, "denied": False, "indexing": False},
            )
            if package.locked_version not in item["versions"]:
                item["versions"].append(package.locked_version)
        if grouped or not query:
            return list(grouped.values())
        try:
            normalized = normalize_pip_name(query)
        except ValueError:
            raise api_error(422, "PACKAGE_NAME_INVALID", "Python 包名格式不合法", retryable=False)
        cache_key = f"environment:v2:pip-candidate:{python_version}:{normalized}"
        try:
            cached = redis_client.get(cache_key)
            if cached:
                return [json.loads(cached)]
        except Exception:  # noqa: BLE001 - cache is an optimization only
            pass
        try:
            candidate = search_pip_candidates(
                query=normalized,
                python_version=python_version,
                index_url=settings.env_pip_index_url,
            )
        except ValueError as exc:
            raise api_error(503, "BUILD_SERVICE_UNAVAILABLE", str(exc), retryable=True) from exc
        except Exception as exc:  # noqa: BLE001 - search must not block editing
            candidate = {
                "manager": "pip",
                "name": normalized,
                "versions": [],
                "compatible": None,
                "denied": False,
                "indexing": True,
                "deny_reason": "包源暂时不可用，构建时会再次权威验证",
            }
            # Do not expose upstream exception text; it may contain a URL or
            # proxy credentials.  Keep it in server logs only if needed.
            _ = exc
        try:
            redis_client.setex(cache_key, 300, json.dumps(candidate, ensure_ascii=False))
        except Exception:  # noqa: BLE001 - cache is an optimization only
            pass
        return [candidate]
    denied_pattern = next(
        (pattern for pattern in settings.env_apt_deny_patterns if query and re.fullmatch(pattern, query)),
        None,
    )
    if not query:
        return []
    try:
        validate_apt_name(query)
    except ValueError:
        raise api_error(422, "PACKAGE_NAME_INVALID", "系统包名格式不合法", retryable=False)
    cached = get_cached_apt_candidate(
        redis_client,
        python_version=python_version,
        normalized_name=query,
    )
    if cached is not None:
        cached = dict(cached)
        if denied_pattern:
            cached["denied"] = True
            cached["deny_reason"] = "平台安全策略禁止安装"
        return [cached]
    return [
        {
            "manager": "apt",
            "name": query,
            "versions": [],
            "compatible": None,
            "denied": denied_pattern is not None,
            "deny_reason": "平台安全策略禁止安装" if denied_pattern else None,
            "indexing": True,
        }
    ]


# ═══════════════════════════════════════════════════════════════
# 构建任务（管理端）
# ═══════════════════════════════════════════════════════════════


def _enqueue_or_503(redis_client, job: EnvironmentBuildJob, settings: Settings) -> None:
    """Redis list 只负责唤醒——入队失败不丢任务（DB queued 保留），返回队列不可用。"""
    try:
        enqueue_build_redis(redis_client, job, settings)
    except Exception:
        raise api_error(503, "BUILD_QUEUE_UNAVAILABLE", "构建队列暂不可用，请稍后重试")


@router.post("/versions/{version_id}/builds", response_model=EnvironmentBuildRead, status_code=201)
def post_build(
    version_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    redis_client=Depends(get_redis_client),
    current_user: PackageCatalog = _admin_only(),
):
    """为版本触发构建——available 不可重建；已有进行中任务不重复创建。"""
    _reject_legacy_write(settings)
    job = create_build_job(db, version_id, actor_id=current_user.id)
    _enqueue_or_503(redis_client, job, settings)
    return job


@router.get("/builds", response_model=None)
def get_builds(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: PackageCatalog = _admin_only(),
):
    """构建任务列表——创建时间倒序，附版本/档位摘要（UI 展示用）。"""
    jobs = list_build_jobs(db, limit)
    if settings.environment_editor_v2_enabled:
        return [_v2_build_read(db, job) for job in jobs]
    if not jobs:
        return []
    version_ids = {j.environment_version_id for j in jobs}
    versions = {
        v.id: v
        for v in db.scalars(
            select(EnvironmentVersion).where(EnvironmentVersion.id.in_(version_ids))
        ).all()
    }
    # 档位信息经版本查询
    from app.models import EnvironmentProfile

    profile_ids = {v.profile_id for v in versions.values()}
    profile_map = {
        p.id: p
        for p in db.scalars(select(EnvironmentProfile).where(EnvironmentProfile.id.in_(profile_ids))).all()
    }
    out = []
    for job in jobs:
        version = versions.get(job.environment_version_id)
        profile = profile_map.get(version.profile_id) if version else None
        digest_short = None
        if version and version.image_digest:
            digest_short = version.image_digest[:12] + "…"
        out.append(
            EnvironmentBuildListRead.model_validate(job).model_copy(
                update={
                    "profile_display_name": profile.display_name if profile else None,
                    "profile_slug": profile.slug if profile else None,
                    "version_number": version.version_number if version else None,
                    "version_status": version.status if version else None,
                    "image_digest_short": digest_short,
                }
            )
        )
    return out


@router.get("/builds/{job_id}", response_model=None)
def get_build_detail(
    job_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: PackageCatalog = _admin_only(),
):
    job = db.get(EnvironmentBuildJob, job_id)
    if job is None:
        raise api_error(404, "NOT_FOUND", "构建任务不存在")
    if settings.environment_editor_v2_enabled:
        return _v2_build_read(db, job)
    return job


@router.get("/builds/{job_id}/log", response_model=None)
def get_build_log(
    job_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: PackageCatalog = _admin_only(),
):
    """构建日志——入库前已脱敏并截断（60 KiB 尾部），仅 admin 可见。"""
    job = db.get(EnvironmentBuildJob, job_id)
    if job is None:
        raise api_error(404, "NOT_FOUND", "构建任务不存在")
    if settings.environment_editor_v2_enabled:
        return {
            "job_id": job.id,
            "status": job.status,
            "phase": job.phase,
            "log_text": job.log_text or "",
            "error_detail": job.error_detail,
        }
    return EnvironmentBuildLogRead(
        job_id=job.id,
        status=job.status,
        log_text=job.log_text or "",
    )


@router.post("/builds/{job_id}/retry", response_model=None, status_code=201)
def post_build_retry(
    job_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    redis_client=Depends(get_redis_client),
    current_user: PackageCatalog = _admin_only(),
):
    """重试失败/超时构建——创建新尝试（attempt+1、retry_of_id 关联）并入队。"""
    if settings.environment_editor_v2_enabled:
        _, new_job = retry_draft_build(
            db, job_id, actor_id=current_user.id, settings=settings
        )
        _enqueue_or_503(redis_client, new_job, settings)
        return _v2_build_read(db, new_job)
    return retry_build_job(db, job_id, actor_id=current_user.id, settings=settings, redis_client=redis_client)


# ═══════════════════════════════════════════════════════════════
# 教师可用环境（教师 + admin）
# ═══════════════════════════════════════════════════════════════


@router.get("/versions/{version_id}/summary", response_model=EnvironmentOptionRead)
def get_version_summary(
    version_id: int,
    db: Session = Depends(get_db),
    current_user: PackageCatalog = Depends(require_roles("teacher", "admin")),
):
    """Return a teacher-safe summary for a currently bound historical version.

    The normal picker only calls ``/available`` and therefore never exposes
    historical versions as new choices.  An existing assignment can still
    request this summary so its locked selection remains visible after a
    publication, rollback, or profile archive.
    """
    return teacher_option_for_version(
        db,
        version_id,
        actor_id=current_user.id,
        actor_role=current_user.role,
    )


@router.get("/available", response_model=list[EnvironmentOptionRead])
def get_available(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: PackageCatalog = Depends(require_roles("teacher", "admin")),
):
    """教师可用环境列表——active 档位下所有 available 版本。

    响应不含 digest、tag、基础镜像与构建日志；学生不需要直接调用该端点。
    """
    if settings.environment_editor_v2_enabled:
        return list_current_available_options(db)
    return list_available_options(db)
