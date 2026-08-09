"""环境档位种子（Phase 1：seed）——幂等，全部数据来自内置常量。

规则（计划 7.3）：
- 已存在同 slug/profile/version/package 时不重复插入
- 已 available 的版本不重建
- draft/failed 且无 active build job 时才入队
- 无任意 requirements 或 Dockerfile 参数
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from sqlalchemy import select

from app.config import Settings
from app.models import (
    EnvironmentBuildJob,
    EnvironmentProfile,
    EnvironmentVersion,
    PackageCatalog,
    ProfileVersionPackage,
)
from app.services.environment_builder import canonical_build_spec, spec_manifest_sha256
from app.services.import_policy import normalize_pip_name

# v1 固定基线（计划第 3 章）——首次正式构建前必须执行全量 import smoke test
SEED_PACKAGES: list[dict] = [
    {"pip_name": "pytest", "locked_version": "8.3.4", "import_names": ["pytest"], "category_tags": ["testing"], "source_key": "pypi"},
    {"pip_name": "numpy", "locked_version": "2.1.3", "import_names": ["numpy"], "category_tags": ["data"], "source_key": "pypi"},
    {"pip_name": "pandas", "locked_version": "2.2.3", "import_names": ["pandas"], "category_tags": ["data"], "source_key": "pypi"},
    {"pip_name": "scipy", "locked_version": "1.14.1", "import_names": ["scipy"], "category_tags": ["data"], "source_key": "pypi"},
    {"pip_name": "scikit-learn", "locked_version": "1.6.0", "import_names": ["sklearn"], "category_tags": ["machine-learning"], "source_key": "pypi"},
    {"pip_name": "matplotlib", "locked_version": "3.10.0", "import_names": ["matplotlib"], "category_tags": ["visualization"], "source_key": "pypi"},
    {"pip_name": "torch", "locked_version": "2.6.0+cpu", "import_names": ["torch"], "category_tags": ["machine-learning"], "source_key": "pytorch_cpu"},
]

SEED_PROFILES: list[dict] = [
    {
        "slug": "basic", "display_name": "Python 基础",
        "description": "基础 Python 判题环境（pytest）", "minimum_memory_mb": 256,
        "packages": ["pytest"],
    },
    {
        "slug": "data", "display_name": "数据分析",
        "description": "数据分析与科学计算环境（numpy/pandas/scipy/scikit-learn/matplotlib）",
        "minimum_memory_mb": 768,
        "packages": ["pytest", "numpy", "pandas", "scipy", "scikit-learn", "matplotlib"],
    },
    {
        "slug": "torch-cpu", "display_name": "PyTorch CPU",
        "description": "PyTorch CPU 机器学习环境（data + torch CPU）",
        "minimum_memory_mb": 2048,
        "packages": ["pytest", "numpy", "pandas", "scipy", "scikit-learn", "matplotlib", "torch"],
    },
]


@dataclass
class SeedResult:
    profiles_created: list[str] = field(default_factory=list)
    packages_created: list[str] = field(default_factory=list)
    versions_created: list[int] = field(default_factory=list)
    enqueued: list[int] = field(default_factory=list)
    already_available: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def seed_environment_catalog(
    db,
    settings: Settings,
    *,
    enqueue: bool = False,
    redis_client=None,
) -> SeedResult:
    """幂等种子：创建包目录 / 档位 / v1 草稿版本；--enqueue 时入队构建。"""
    result = SeedResult()

    # ── 包目录（按 (normalized_name, locked_version, source_key) 唯一） ──
    pkg_map: dict[str, PackageCatalog] = {}
    for spec_pkg in SEED_PACKAGES:
        normalized = normalize_pip_name(spec_pkg["pip_name"])
        existing = db.scalar(
            select(PackageCatalog).where(
                PackageCatalog.normalized_name == normalized,
                PackageCatalog.locked_version == spec_pkg["locked_version"],
                PackageCatalog.source_key == spec_pkg["source_key"],
            )
        )
        if existing is None:
            existing = PackageCatalog(
                normalized_name=normalized,
                pip_name=spec_pkg["pip_name"],
                locked_version=spec_pkg["locked_version"],
                import_names=spec_pkg["import_names"],
                category_tags=spec_pkg["category_tags"],
                source_key=spec_pkg["source_key"],
                status="active",
            )
            db.add(existing)
            db.flush()
            result.packages_created.append(spec_pkg["pip_name"])
        pkg_map[spec_pkg["pip_name"]] = existing

    # ── 档位与 v1 版本 ──
    for prof_spec in SEED_PROFILES:
        slug = prof_spec["slug"]
        profile = db.scalar(select(EnvironmentProfile).where(EnvironmentProfile.slug == slug))
        if profile is None:
            profile = EnvironmentProfile(
                slug=slug,
                display_name=prof_spec["display_name"],
                description=prof_spec["description"],
                status="active",
            )
            db.add(profile)
            db.flush()
            result.profiles_created.append(slug)

        version = db.scalar(
            select(EnvironmentVersion).where(
                EnvironmentVersion.profile_id == profile.id,
                EnvironmentVersion.version_number == 1,
            )
        )
        if version is None:
            packages = [pkg_map[name] for name in prof_spec["packages"]]
            spec = canonical_build_spec(
                base_image_ref=settings.env_base_image,
                profile_slug=slug,
                version_number=1,
                packages=packages,
                settings=settings,
            )
            version = EnvironmentVersion(
                profile_id=profile.id,
                version_number=1,
                status="draft",
                base_image_ref=settings.env_base_image,
                minimum_memory_mb=prof_spec["minimum_memory_mb"],
                manifest_sha256=spec_manifest_sha256(spec),
            )
            db.add(version)
            db.flush()
            for order, pkg in enumerate(packages):
                db.add(ProfileVersionPackage(
                    environment_version_id=version.id,
                    package_catalog_id=pkg.id,
                    display_order=order,
                ))
            result.versions_created.append(version.id)
        elif version.status == "available":
            result.already_available.append(slug)
            continue
        else:
            result.skipped.append(slug)

        # ── 入队：draft/failed 且无 active build job 时才入队 ──
        if enqueue and version.status in ("draft", "failed"):
            active = db.scalar(
                select(EnvironmentBuildJob).where(
                    EnvironmentBuildJob.environment_version_id == version.id,
                    EnvironmentBuildJob.status.in_(["queued", "building"]),
                ).limit(1)
            )
            if active is None:
                job = EnvironmentBuildJob(
                    environment_version_id=version.id,
                    status="queued",
                    attempt_number=1,
                )
                db.add(job)
                db.flush()
                version.status = "queued"
                if redis_client is not None:
                    redis_client.rpush(
                        settings.env_build_queue_name,
                        json.dumps({"type": "env_build", "version_id": version.id}),
                    )
                result.enqueued.append(version.id)

    db.commit()
    return result
