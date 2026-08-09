"""环境档位管理 API（Phase 2：管理员端）

管理端点（package/profile/version/build）全部仅 admin 角色；
教师可调用 GET /environments/available 查看可用的环境版本（不含 digest/tag/构建日志）。
管理员全程只填写包元数据和勾选包，无 Dockerfile/requirements 输入面。
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.dependencies import get_db, get_redis_client, require_roles
from app.errors import api_error
from app.models import EnvironmentBuildJob, EnvironmentVersion, PackageCatalog, ProfileVersionPackage
from app.schemas.environments import (
    EnvironmentBuildListRead,
    EnvironmentBuildLogRead,
    EnvironmentBuildRead,
    EnvironmentOptionRead,
    EnvironmentProfileCreate,
    EnvironmentProfileListRead,
    EnvironmentProfileRead,
    EnvironmentProfileUpdate,
    EnvironmentVersionCreate,
    EnvironmentVersionListRead,
    EnvironmentVersionRead,
    PackageCatalogAdminRead,
    PackageCatalogCreate,
    PackageCatalogUpdate,
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

router = APIRouter(prefix="/environments")


def _admin_only():
    return Depends(require_roles("admin"))


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
    current_user: PackageCatalog = _admin_only(),
):
    """创建受控包——输入严格校验（无 URL/requirements/pip 参数输入面）。"""
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
    current_user: PackageCatalog = _admin_only(),
):
    """更新包目录条目——被版本引用的包核心字段不可原地修改（PACKAGE_IMMUTABLE）。"""
    patch = body.model_dump(exclude_unset=True)
    pkg = update_package(db, package_id, patch, actor_id=current_user.id)
    return PackageCatalogAdminRead.model_validate(pkg).model_copy(
        update={"referenced": is_package_referenced(db, pkg.id)}
    )


@router.delete("/packages/{package_id}", response_model=PackageCatalogAdminRead)
def delete_package(
    package_id: int,
    db: Session = Depends(get_db),
    current_user: PackageCatalog = _admin_only(),
):
    """删除统一实现为停用——不物理删除，历史环境绑定不受影响。"""
    pkg = deactivate_package(db, package_id, actor_id=current_user.id)
    return PackageCatalogAdminRead.model_validate(pkg)


# ═══════════════════════════════════════════════════════════════
# 环境档位（管理端）
# ═══════════════════════════════════════════════════════════════


@router.get("/profiles", response_model=list[EnvironmentProfileListRead])
def get_profiles(
    db: Session = Depends(get_db),
    current_user: PackageCatalog = _admin_only(),
):
    """档位列表——含最新可用版本摘要（版本号最大的 available）与包摘要。"""
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


@router.post("/profiles", response_model=EnvironmentProfileRead, status_code=201)
def post_profile(
    body: EnvironmentProfileCreate,
    db: Session = Depends(get_db),
    current_user: PackageCatalog = _admin_only(),
):
    """创建环境档位——slug 唯一。"""
    return create_profile(
        db,
        slug=body.slug,
        display_name=body.display_name,
        description=body.description,
        actor_id=current_user.id,
    )


@router.patch("/profiles/{profile_id}", response_model=EnvironmentProfileRead)
def patch_profile(
    profile_id: int,
    body: EnvironmentProfileUpdate,
    db: Session = Depends(get_db),
    current_user: PackageCatalog = _admin_only(),
):
    """更新档位——展示名/描述/状态；slug 不可变。"""
    patch = body.model_dump(exclude_unset=True)
    return update_profile(db, profile_id, patch)


@router.get("/profiles/{profile_id}/versions", response_model=list[EnvironmentVersionListRead])
def get_profile_versions(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: PackageCatalog = _admin_only(),
):
    """档位全部版本（管理端可见全部状态）——版本号倒序，附包摘要。"""
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
    job = create_build_job(db, version_id, actor_id=current_user.id)
    _enqueue_or_503(redis_client, job, settings)
    return job


@router.get("/builds", response_model=list[EnvironmentBuildListRead])
def get_builds(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: PackageCatalog = _admin_only(),
):
    """构建任务列表——创建时间倒序，附版本/档位摘要（UI 展示用）。"""
    jobs = list_build_jobs(db, limit)
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


@router.get("/builds/{job_id}", response_model=EnvironmentBuildRead)
def get_build_detail(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: PackageCatalog = _admin_only(),
):
    job = db.get(EnvironmentBuildJob, job_id)
    if job is None:
        raise api_error(404, "NOT_FOUND", "构建任务不存在")
    return job


@router.get("/builds/{job_id}/log", response_model=EnvironmentBuildLogRead)
def get_build_log(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: PackageCatalog = _admin_only(),
):
    """构建日志——入库前已脱敏并截断（60 KiB 尾部），仅 admin 可见。"""
    job = db.get(EnvironmentBuildJob, job_id)
    if job is None:
        raise api_error(404, "NOT_FOUND", "构建任务不存在")
    return EnvironmentBuildLogRead(
        job_id=job.id,
        status=job.status,
        log_text=job.log_text or "",
    )


@router.post("/builds/{job_id}/retry", response_model=EnvironmentBuildRead, status_code=201)
def post_build_retry(
    job_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    redis_client=Depends(get_redis_client),
    current_user: PackageCatalog = _admin_only(),
):
    """重试失败/超时构建——创建新尝试（attempt+1、retry_of_id 关联）并入队。"""
    return retry_build_job(db, job_id, actor_id=current_user.id, settings=settings, redis_client=redis_client)


# ═══════════════════════════════════════════════════════════════
# 教师可用环境（教师 + admin）
# ═══════════════════════════════════════════════════════════════


@router.get("/available", response_model=list[EnvironmentOptionRead])
def get_available(
    db: Session = Depends(get_db),
    current_user: PackageCatalog = Depends(require_roles("teacher", "admin")),
):
    """教师可用环境列表——active 档位下所有 available 版本。

    响应不含 digest、tag、基础镜像与构建日志；学生不需要直接调用该端点。
    """
    return list_available_options(db)
