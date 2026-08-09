"""环境档位服务（Phase 1：控制面）

- list_available_options：教师可选的 available 版本（不含 digest/tag/构建日志）
- create_profile_version：并发安全地创建下一个版本号（SELECT ... FOR UPDATE）
- require_available_version：运行链路校验版本可用且已构建
- Phase 5：resolve_run_image_ref / installed_imports_for_version / public_environment_summary
  供判题、Kernel 运行链路解析不可变镜像引用与学生可见环境摘要
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import api_error
from app.models import (
    EnvironmentBuildJob,
    EnvironmentProfile,
    EnvironmentVersion,
    PackageCatalog,
    ProfileVersionPackage,
)
from app.schemas.environments import EnvironmentOptionRead, EnvironmentSummaryRead, PackageSummary


def get_packages_for_version(db: Session, version_id: int) -> list[PackageCatalog]:
    """版本关联的包（按 display_order 排序）——包集合必须关联版本，不可关联 profile"""
    return list(
        db.scalars(
            select(PackageCatalog)
            .join(ProfileVersionPackage, ProfileVersionPackage.package_catalog_id == PackageCatalog.id)
            .where(ProfileVersionPackage.environment_version_id == version_id)
            .order_by(ProfileVersionPackage.display_order)
        ).all()
    )


def current_available_version(db: Session, profile_slug: str) -> EnvironmentVersion | None:
    """档位当前可用版本——版本号最大的 available 版本（不引入循环 current_version_id 外键）"""
    return db.scalar(
        select(EnvironmentVersion)
        .join(EnvironmentProfile, EnvironmentProfile.id == EnvironmentVersion.profile_id)
        .where(
            EnvironmentProfile.slug == profile_slug,
            EnvironmentVersion.status == "available",
        )
        .order_by(EnvironmentVersion.version_number.desc())
        .limit(1)
    )


def require_available_version(db: Session, version_id: int) -> EnvironmentVersion:
    """运行链路校验：版本必须存在、available、所属档位未停用。

    版本缺失/未构建/档位停用 → VERSION_NOT_AVAILABLE。
    """
    version = db.get(EnvironmentVersion, version_id)
    if version is None:
        raise api_error(404, "VERSION_NOT_AVAILABLE", "环境版本不存在")
    if version.status != "available" or not version.image_digest:
        raise api_error(409, "VERSION_NOT_AVAILABLE", "环境版本尚未构建完成，暂不可用")
    profile = db.get(EnvironmentProfile, version.profile_id)
    if profile is None or profile.status != "active":
        raise api_error(409, "VERSION_NOT_AVAILABLE", "环境档位已停用")
    return version


def list_available_options(db: Session) -> list[EnvironmentOptionRead]:
    """教师可用环境列表——active profile 下所有 available 版本，按档位排序。"""
    versions = db.scalars(
        select(EnvironmentVersion)
        .join(EnvironmentProfile, EnvironmentProfile.id == EnvironmentVersion.profile_id)
        .where(
            EnvironmentProfile.status == "active",
            EnvironmentVersion.status == "available",
        )
        .order_by(EnvironmentProfile.slug, EnvironmentVersion.version_number.desc())
    ).all()

    options: list[EnvironmentOptionRead] = []
    for version in versions:
        profile = db.get(EnvironmentProfile, version.profile_id)
        packages = get_packages_for_version(db, version.id)
        options.append(
            EnvironmentOptionRead(
                profile_id=version.profile_id,
                environment_version_id=version.id,
                slug=profile.slug,
                display_name=profile.display_name,
                description=profile.description,
                version_number=version.version_number,
                packages=[
                    PackageSummary(
                        pip_name=p.pip_name,
                        locked_version=p.locked_version,
                        import_names=list(p.import_names or []),
                    )
                    for p in packages
                ],
                minimum_memory_mb=version.minimum_memory_mb,
            )
        )
    return options


def create_profile_version(
    db: Session,
    profile_id: int,
    package_ids: list[int],
    actor_id: int | None,
    *,
    source_version_id: int | None,
    minimum_memory_mb: int,
    base_image_ref: str,
    settings: Settings,
) -> EnvironmentVersion:
    """并发安全地创建档位新版本。

    对 profile 行加 FOR UPDATE 锁后计算下一个版本号，避免并发创建撞 UNIQUE(profile_id, version_number)。
    新版本创建为 draft；包集合通过 profile_version_packages 关联。
    """
    profile = db.execute(
        select(EnvironmentProfile).where(EnvironmentProfile.id == profile_id).with_for_update()
    ).scalar_one_or_none()
    if profile is None:
        raise api_error(404, "NOT_FOUND", "环境档位不存在")
    if profile.status != "active":
        raise api_error(409, "PROFILE_INACTIVE", "环境档位已停用，不能创建新版本")

    max_number = db.scalar(
        select(func.max(EnvironmentVersion.version_number)).where(
            EnvironmentVersion.profile_id == profile_id
        )
    )
    next_number = (max_number or 0) + 1

    from app.services.environment_builder import canonical_build_spec, spec_manifest_sha256

    # 先算 manifest 再落库：manifest_sha256 为 NOT NULL
    packages = (
        list(db.scalars(select(PackageCatalog).where(PackageCatalog.id.in_(package_ids))).all())
        if package_ids
        else []
    )
    spec = canonical_build_spec(
        base_image_ref=base_image_ref,
        profile_slug=profile.slug,
        version_number=next_number,
        packages=packages,
        settings=settings,
    )
    version = EnvironmentVersion(
        profile_id=profile_id,
        version_number=next_number,
        source_version_id=source_version_id,
        status="draft",
        base_image_ref=base_image_ref,
        minimum_memory_mb=minimum_memory_mb,
        manifest_sha256=spec_manifest_sha256(spec),
        created_by_id=actor_id,
    )
    db.add(version)
    db.flush()  # 拿到 version.id 供关联表使用

    for order, package_id in enumerate(package_ids):
        db.add(ProfileVersionPackage(
            environment_version_id=version.id,
            package_catalog_id=package_id,
            display_order=order,
        ))
    db.commit()
    db.refresh(version)
    return version


def create_build_job(
    db: Session,
    version_id: int,
    actor_id: int | None,
) -> EnvironmentBuildJob:
    """为版本创建构建任务（attempt_number 取该版本已有任务的最大尝试号 + 1）。

    - available 版本不可重建（VERSION_IMMUTABLE）
    - 已有 queued/building 任务时不重复创建（BUILD_ALREADY_ACTIVE）
    """
    version = db.get(EnvironmentVersion, version_id)
    if version is None:
        raise api_error(404, "NOT_FOUND", "环境版本不存在")
    if version.status == "available":
        raise api_error(409, "VERSION_IMMUTABLE", "环境版本已可用，不能重新构建")
    active = db.scalar(
        select(EnvironmentBuildJob)
        .where(
            EnvironmentBuildJob.environment_version_id == version_id,
            EnvironmentBuildJob.status.in_(["queued", "building"]),
        )
        .limit(1)
    )
    if active is not None:
        raise api_error(409, "BUILD_ALREADY_ACTIVE", "该环境版本已有进行中的构建任务")

    last_attempt = db.scalar(
        select(func.max(EnvironmentBuildJob.attempt_number)).where(
            EnvironmentBuildJob.environment_version_id == version_id
        )
    )
    job = EnvironmentBuildJob(
        environment_version_id=version_id,
        status="queued",
        attempt_number=(last_attempt or 0) + 1,
        created_by_id=actor_id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def enqueue_build_redis(redis_client, job: EnvironmentBuildJob, settings: Settings) -> None:
    """Redis list 只负责唤醒——DB 是任务事实源，消息内容为版本 ID。"""
    import json as _json

    redis_client.rpush(
        settings.env_build_queue_name,
        _json.dumps({"type": "env_build", "version_id": job.environment_version_id}),
    )


# ═══════════════════════════════════════════════════════════════
# Phase 2：管理端 CRUD（仅 admin API 调用）
# ═══════════════════════════════════════════════════════════════

CORE_PACKAGE_FIELDS = ("pip_name", "locked_version", "import_names", "source_key")


def list_packages(db: Session, status: str | None = None) -> list[PackageCatalog]:
    """包目录列表——默认全部（管理员可见 inactive），可选按状态过滤。"""
    stmt = select(PackageCatalog).order_by(PackageCatalog.normalized_name, PackageCatalog.id)
    if status:
        stmt = stmt.where(PackageCatalog.status == status)
    return list(db.scalars(stmt).all())


def create_package(
    db: Session,
    *,
    pip_name: str,
    locked_version: str,
    import_names: list[str],
    category_tags: list[str],
    source_key: str,
    actor_id: int | None,
) -> PackageCatalog:
    """创建受控包——(normalized_name, locked_version, source_key) 唯一，重复 → PACKAGE_INVALID。"""
    from app.services.import_policy import normalize_pip_name

    normalized = normalize_pip_name(pip_name)
    existing = db.scalar(
        select(PackageCatalog).where(
            PackageCatalog.normalized_name == normalized,
            PackageCatalog.locked_version == locked_version,
            PackageCatalog.source_key == source_key,
        )
    )
    if existing is not None:
        raise api_error(409, "PACKAGE_INVALID", "该包（名称/版本/来源）已存在，不能重复创建")
    pkg = PackageCatalog(
        normalized_name=normalized,
        pip_name=pip_name,
        locked_version=locked_version,
        import_names=import_names,
        category_tags=category_tags,
        source_key=source_key,
        status="active",
        created_by_id=actor_id,
        updated_by_id=actor_id,
    )
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    return pkg


def is_package_referenced(db: Session, package_id: int) -> bool:
    """包是否被任何环境版本引用——被引用则核心字段不可原地修改。"""
    return (
        db.scalar(
            select(func.count(ProfileVersionPackage.package_catalog_id)).where(
                ProfileVersionPackage.package_catalog_id == package_id
            )
        )
        or 0
    ) > 0


def update_package(
    db: Session,
    package_id: int,
    patch: dict,
    actor_id: int | None,
) -> PackageCatalog:
    """更新包目录条目。

    - 核心字段（包名/版本/import 名/来源）在包被引用时不可原地修改 → PACKAGE_IMMUTABLE；
      未被引用时允许，normalized_name 随 pip_name 重算。
    - 分类/状态随时可改。
    """
    from app.services.import_policy import normalize_pip_name

    pkg = db.get(PackageCatalog, package_id)
    if pkg is None:
        raise api_error(404, "NOT_FOUND", "包目录条目不存在")

    core_changed = any(patch.get(f) is not None for f in CORE_PACKAGE_FIELDS)
    if core_changed and is_package_referenced(db, package_id):
        raise api_error(
            409,
            "PACKAGE_IMMUTABLE",
            "该包已被环境版本引用，不能原地修改；请创建新目录条目并关联旧条目",
        )

    for field in ("pip_name", "locked_version", "import_names", "source_key"):
        if patch.get(field) is not None:
            setattr(pkg, field, patch[field])
    if patch.get("pip_name") is not None:
        pkg.normalized_name = normalize_pip_name(patch["pip_name"])
    if patch.get("category_tags") is not None:
        pkg.category_tags = patch["category_tags"]
    if patch.get("status") is not None:
        pkg.status = patch["status"]
    pkg.updated_by_id = actor_id
    db.commit()
    db.refresh(pkg)
    return pkg


def deactivate_package(db: Session, package_id: int, actor_id: int | None) -> PackageCatalog:
    """删除统一实现为停用——不物理删除历史条目，已绑定版本不受影响。"""
    pkg = db.get(PackageCatalog, package_id)
    if pkg is None:
        raise api_error(404, "NOT_FOUND", "包目录条目不存在")
    pkg.status = "inactive"
    pkg.updated_by_id = actor_id
    db.commit()
    db.refresh(pkg)
    return pkg


def create_profile(
    db: Session,
    *,
    slug: str,
    display_name: str,
    description: str | None,
    actor_id: int | None,
) -> EnvironmentProfile:
    """创建环境档位——slug 唯一，冲突 → PROFILE_SLUG_CONFLICT。"""
    existing = db.scalar(select(EnvironmentProfile).where(EnvironmentProfile.slug == slug))
    if existing is not None:
        raise api_error(409, "PROFILE_SLUG_CONFLICT", "档位 slug 已存在")
    profile = EnvironmentProfile(
        slug=slug,
        display_name=display_name,
        description=description,
        status="active",
        created_by_id=actor_id,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def update_profile(db: Session, profile_id: int, patch: dict) -> EnvironmentProfile:
    """更新档位——仅展示名/描述/状态；slug 不可变。"""
    profile = db.get(EnvironmentProfile, profile_id)
    if profile is None:
        raise api_error(404, "NOT_FOUND", "环境档位不存在")
    for field in ("display_name", "description", "status"):
        if patch.get(field) is not None:
            setattr(profile, field, patch[field])
    db.commit()
    db.refresh(profile)
    return profile


def list_profiles_with_latest(db: Session) -> list[tuple[EnvironmentProfile, EnvironmentVersion | None]]:
    """档位列表（含最新可用版本摘要）——按 slug 排序。"""
    profiles = list(db.scalars(select(EnvironmentProfile).order_by(EnvironmentProfile.slug)).all())
    return [(p, current_available_version(db, p.slug)) for p in profiles]


def list_versions(db: Session, profile_id: int) -> list[EnvironmentVersion]:
    """档位全部版本（管理端可见 draft/failed/available 等全部状态）——版本号倒序。"""
    profile = db.get(EnvironmentProfile, profile_id)
    if profile is None:
        raise api_error(404, "NOT_FOUND", "环境档位不存在")
    return list(
        db.scalars(
            select(EnvironmentVersion)
            .where(EnvironmentVersion.profile_id == profile_id)
            .order_by(EnvironmentVersion.version_number.desc())
        ).all()
    )


def list_build_jobs(db: Session, limit: int = 50) -> list[EnvironmentBuildJob]:
    """构建任务列表——创建时间倒序。"""
    return list(
        db.scalars(
            select(EnvironmentBuildJob).order_by(EnvironmentBuildJob.created_at.desc()).limit(limit)
        ).all()
    )


def retry_build_job(
    db: Session,
    job_id: int,
    actor_id: int | None,
    settings: Settings,
    redis_client,
) -> EnvironmentBuildJob:
    """重试构建任务：failed/timed_out → 新 job（attempt+1、retry_of_id 关联）+ Redis 唤醒。

    - 非失败终态不可重试 → BUILD_NOT_RETRYABLE
    - 版本已 available 不可重试 → VERSION_IMMUTABLE
    - Redis 唤醒失败 → BUILD_QUEUE_UNAVAILABLE（任务保留 queued，DB 事实源不丢）
    """
    job = db.get(EnvironmentBuildJob, job_id)
    if job is None:
        raise api_error(404, "NOT_FOUND", "构建任务不存在")
    if job.status not in ("failed", "timed_out"):
        raise api_error(409, "BUILD_NOT_RETRYABLE", f"构建任务当前状态（{job.status}）不可重试")
    version = db.get(EnvironmentVersion, job.environment_version_id)
    if version is None:
        raise api_error(404, "NOT_FOUND", "环境版本不存在")
    if version.status == "available":
        raise api_error(409, "VERSION_IMMUTABLE", "环境版本已可用，不能重新构建")

    last_attempt = db.scalar(
        select(func.max(EnvironmentBuildJob.attempt_number)).where(
            EnvironmentBuildJob.environment_version_id == version.id
        )
    )
    new_job = EnvironmentBuildJob(
        environment_version_id=version.id,
        status="queued",
        attempt_number=(last_attempt or 0) + 1,
        retry_of_id=job.id,
        created_by_id=actor_id,
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    try:
        enqueue_build_redis(redis_client, new_job, settings)
    except Exception:
        # 唤醒失败：任务保留 queued，管理员可稍后再次重试
        raise api_error(503, "BUILD_QUEUE_UNAVAILABLE", "构建队列暂不可用，请稍后重试")
    return new_job


# ═══════════════════════════════════════════════════════════════
# Phase 4：教师端环境解析与发布门禁
# ═══════════════════════════════════════════════════════════════

ENV_FIELDS = ("environment_version_id", "import_policy_mode", "allowed_imports")


def resolve_basic_available_version(db: Session) -> EnvironmentVersion | None:
    """basic 档位当前可用版本——创建路径未显式指定环境时的服务层解析。

    Phase 3 模型层 default 仅作存量兼容；Phase 4 起创建路径由服务层显式解析并写入。
    """
    return current_available_version(db, "basic")


def validate_environment_selection(db: Session, env_id: int | None) -> None:
    """教师选择环境时的可用性校验——非 None 时必须是 available（VERSION_NOT_AVAILABLE）。"""
    if env_id is not None:
        require_available_version(db, env_id)


def validate_publish_gate(
    db: Session,
    assignment,
    questions: list,
) -> None:
    """作业发布门禁（Phase 4）：

    - 作业默认环境必须 available；
    - 题目覆盖环境必须 available；
    - 题目 memory_limit_mb 不得低于有效环境 minimum_memory_mb（MEMORY_BELOW_ENV_MIN）。
    未绑定环境（存量/测试库无种子）的记录跳过校验，保持既有发布行为不变。
    """
    if assignment.environment_version_id is not None:
        require_available_version(db, assignment.environment_version_id)
    for question in questions:
        env_id = (
            question.environment_version_id
            if question.environment_version_id is not None
            else assignment.environment_version_id
        )
        if env_id is None:
            continue
        version = require_available_version(db, env_id)
        if question.memory_limit_mb < version.minimum_memory_mb:
            raise api_error(
                409,
                "MEMORY_BELOW_ENV_MIN",
                f"题目「{question.title}」内存上限 {question.memory_limit_mb} MB 低于环境最低内存 {version.minimum_memory_mb} MB，请调高或更换环境",
            )


# ═══════════════════════════════════════════════════════════════
# Phase 5：运行链路（判题 / Kernel / 学生摘要）
# ═══════════════════════════════════════════════════════════════

def resolve_run_image_ref(db: Session, version_id: int) -> str:
    """运行链路解析不可变镜像引用——必须 available 且 image_digest 非空。

    返回 version.image_digest（单机为本地 image ID `sha256:...`；配置 Registry 后
    为 `repository@sha256:...`），运行容器直接以该值作为镜像参数启动，
    禁止回退到 `dai-env-<slug>:vN` 标签（计划 2.3 Digest 语义）。
    版本缺失 / 未构建 / 档位停用 → ENVIRONMENT_IMAGE_MISSING（fail closed，不扣分）。
    """
    version = db.get(EnvironmentVersion, version_id)
    if version is None or version.status != "available" or not version.image_digest:
        raise api_error(
            503,
            "ENVIRONMENT_IMAGE_MISSING",
            "运行环境暂不可用，本次提交不会扣分，请稍后重试",
        )
    profile = db.get(EnvironmentProfile, version.profile_id)
    if profile is None or profile.status != "active":
        raise api_error(503, "ENVIRONMENT_IMAGE_MISSING", "运行环境暂不可用，本次提交不会扣分，请稍后重试")
    return version.image_digest


def installed_imports_for_version(db: Session, version_id: int) -> set[str]:
    """环境版本安装的 import 名集合——从版本关联包目录的 import_names 汇总。

    用于 classify_imports 的 installed_imports 参数（教学反馈，不是安全边界）。
    """
    return {
        name
        for pkg in get_packages_for_version(db, version_id)
        for name in (pkg.import_names or [])
    }


def resolve_effective_policy(assignment, question) -> "ImportPolicy":
    """解析题目的最终 import 策略：inherit → 作业策略；否则题目自己的（计划 2.4）。"""
    from app.services.import_policy import ImportPolicy

    if getattr(question, "import_policy_mode", "inherit") in ("inherit", None):
        mode = assignment.import_policy_mode
        allowed = list(assignment.allowed_imports or [])
    else:
        mode = question.import_policy_mode
        allowed = list(question.allowed_imports or [])
    return ImportPolicy.from_mode(mode, allowed)


def public_environment_summary(
    db: Session,
    version_id: int | None,
    policy: "ImportPolicy | None" = None,
) -> EnvironmentSummaryRead | None:
    """学生可见的环境摘要（计划 6.1 EnvironmentSummaryRead）。

    - 只含展示名 / 版本号 / Python 版本 / 可用 import / 策略；绝不包含 digest、tag、
      基础镜像或构建日志。
    - 版本缺失、未构建、档位停用 → 返回 None（不泄露内部状态）。
    """
    if version_id is None:
        return None
    version = db.get(EnvironmentVersion, version_id)
    if version is None or version.status != "available":
        return None
    profile = db.get(EnvironmentProfile, version.profile_id)
    if profile is None or profile.status != "active":
        return None
    if policy is None:
        from app.services.import_policy import ImportPolicy

        policy = ImportPolicy(mode="unrestricted")
    return EnvironmentSummaryRead(
        display_name=profile.display_name,
        version_label=f"v{version.version_number}",
        python_version=version.python_version or "",
        imports=sorted(installed_imports_for_version(db, version.id)),
        import_policy_mode=policy.mode if policy.mode != "inherit" else "unrestricted",
        allowed_imports=sorted(policy.allowed_imports),
    )
