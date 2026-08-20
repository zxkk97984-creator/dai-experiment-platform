"""环境控制面数据模型测试（Phase 1 + V2）

覆盖：控制面表的建表、唯一约束、外键、状态默认值与版本关联。
注意：SQLite 下 BigInteger 主键不是 rowid 别名，插入时必须显式传 id。
"""
from __future__ import annotations
import pytest
pytestmark = pytest.mark.no_auto_env_seed

import sqlalchemy as sa
from sqlalchemy import select

from app.models import (
    EnvironmentBuildJob,
    EnvironmentProfile,
    EnvironmentVersion,
    PackageCatalog,
    ProfileVersionPackage,
)

CONTROL_TABLES = [
    "package_catalog",
    "environment_profiles",
    "environment_versions",
    "profile_version_packages",
    "environment_build_jobs",
    "environment_drafts",
    "environment_publications",
]


def _make_package(db, **overrides):
    values = dict(
        id=overrides.pop("id", 1),
        normalized_name=overrides.pop("normalized_name", "numpy"),
        pip_name=overrides.pop("pip_name", "numpy"),
        locked_version=overrides.pop("locked_version", "2.1.3"),
        import_names=overrides.pop("import_names", ["numpy"]),
        category_tags=overrides.pop("category_tags", ["data"]),
        source_key=overrides.pop("source_key", "pypi"),
    )
    values.update(overrides)
    pkg = PackageCatalog(**values)
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    return pkg


def _make_profile(db, **overrides):
    values = dict(
        id=overrides.pop("id", 1),
        slug=overrides.pop("slug", "basic"),
        display_name=overrides.pop("display_name", "Python 基础"),
    )
    values.update(overrides)
    prof = EnvironmentProfile(**values)
    db.add(prof)
    db.commit()
    db.refresh(prof)
    return prof


def _make_version(db, profile_id, **overrides):
    values = dict(
        id=overrides.pop("id", 1),
        profile_id=profile_id,
        version_number=overrides.pop("version_number", 1),
        status=overrides.pop("status", "available"),
        base_image_ref=overrides.pop("base_image_ref", "python:3.12-slim@sha256:0000000000000000000000000000000000000000000000000000000000000000"),
        minimum_memory_mb=overrides.pop("minimum_memory_mb", 256),
        manifest_sha256=overrides.pop("manifest_sha256", "m" * 64),
    )
    values.update(overrides)
    ver = EnvironmentVersion(**values)
    db.add(ver)
    db.commit()
    db.refresh(ver)
    return ver


# ═══════════════════════════════════════════════════════════════
# 建表与基础字段
# ═══════════════════════════════════════════════════════════════

def test_all_control_tables_created(db_session_factory):
    with db_session_factory() as db:
        inspector = sa.inspect(db.get_bind())
        tables = set(inspector.get_table_names())
    for t in CONTROL_TABLES:
        assert t in tables, f"缺少控制面表: {t}"


def test_package_catalog_columns_and_defaults(db_session_factory):
    with db_session_factory() as db:
        pkg = _make_package(db)
        assert pkg.status == "active"
        assert pkg.import_names == ["numpy"]
        assert pkg.category_tags == ["data"]
        assert pkg.created_at is not None


def test_version_columns_and_defaults(db_session_factory):
    with db_session_factory() as db:
        prof = _make_profile(db)
        ver = _make_version(db, prof.id)
        assert ver.status == "available"
        assert ver.version_number == 1
        assert ver.minimum_memory_mb == 256
        assert ver.image_digest is None
        assert ver.python_version == "3.12"
        assert ver.requested_spec == {
            "schema_version": 1,
            "python_packages": [],
            "system_packages": [],
        }
        assert ver.available_at is None


def test_build_job_defaults(db_session_factory):
    with db_session_factory() as db:
        prof = _make_profile(db)
        ver = _make_version(db, prof.id)
        job = EnvironmentBuildJob(
            id=1, environment_version_id=ver.id, status="queued", attempt_number=1
        )
        db.add(job)
        db.commit()
        assert job.attempt_number == 1
        assert job.phase == "queued"
        assert job.worker_id is None
        assert job.error_message is None


# ═══════════════════════════════════════════════════════════════
# 唯一约束
# ═══════════════════════════════════════════════════════════════

def test_package_unique_name_version_source(db_session_factory):
    with db_session_factory() as db:
        _make_package(db, id=1)
        with pytest_raises_integrity(db):
            _make_package(db, id=2)
        # 不同版本或不同来源允许并存
        _make_package(db, id=2, locked_version="2.0.0")
        _make_package(db, id=3, source_key="pytorch_cpu")


def test_profile_slug_unique(db_session_factory):
    with db_session_factory() as db:
        _make_profile(db, id=1, slug="basic")
        with pytest_raises_integrity(db):
            _make_profile(db, id=2, slug="basic")


def test_version_unique_profile_number(db_session_factory):
    with db_session_factory() as db:
        prof = _make_profile(db)
        _make_version(db, prof.id, id=1, version_number=1)
        with pytest_raises_integrity(db):
            _make_version(db, prof.id, id=2, version_number=1)


def test_version_image_digest_unique(db_session_factory):
    with db_session_factory() as db:
        prof = _make_profile(db)
        digest = "sha256:" + "a" * 64
        _make_version(db, prof.id, id=1, version_number=1, image_digest=digest)
        with pytest_raises_integrity(db):
            _make_version(db, prof.id, id=2, version_number=2, image_digest=digest)


# ═══════════════════════════════════════════════════════════════
# 外键与关系
# ═══════════════════════════════════════════════════════════════

def test_version_belongs_to_profile(db_session_factory):
    with db_session_factory() as db:
        prof = _make_profile(db, id=1, slug="data", display_name="数据分析")
        ver = _make_version(db, prof.id)
        db.refresh(prof)
        assert ver.profile_id == prof.id
        assert prof.versions[0].id == ver.id


def test_supersedes_self_reference(db_session_factory):
    with db_session_factory() as db:
        old = _make_package(db, id=1)
        new = _make_package(db, id=2, locked_version="2.2.0", supersedes_id=old.id)
        assert new.supersedes_id == old.id


def test_profile_version_packages_association(db_session_factory):
    with db_session_factory() as db:
        prof = _make_profile(db)
        ver = _make_version(db, prof.id)
        p1 = _make_package(db, id=1, normalized_name="numpy", locked_version="2.1.3")
        p2 = _make_package(db, id=2, normalized_name="pandas", locked_version="2.2.3")
        db.add_all([
            ProfileVersionPackage(environment_version_id=ver.id, package_catalog_id=p1.id, display_order=0),
            ProfileVersionPackage(environment_version_id=ver.id, package_catalog_id=p2.id, display_order=1),
        ])
        db.commit()
        links = db.scalars(
            select(ProfileVersionPackage).where(
                ProfileVersionPackage.environment_version_id == ver.id
            ).order_by(ProfileVersionPackage.display_order)
        ).all()
        assert [l.package_catalog_id for l in links] == [p1.id, p2.id]
        assert links[0].display_order == 0


def test_build_job_retry_chain(db_session_factory):
    with db_session_factory() as db:
        prof = _make_profile(db)
        ver = _make_version(db, prof.id)
        job1 = EnvironmentBuildJob(id=1, environment_version_id=ver.id, status="failed", attempt_number=1)
        db.add(job1)
        db.commit()
        job2 = EnvironmentBuildJob(
            id=2, environment_version_id=ver.id, status="queued", attempt_number=2, retry_of_id=job1.id
        )
        db.add(job2)
        db.commit()
        assert job2.retry_of_id == job1.id


def test_build_job_status_index_exists(db_session_factory):
    with db_session_factory() as db:
        inspector = sa.inspect(db.get_bind())
        indexes = inspector.get_indexes("environment_build_jobs")
        assert any("status" in ix["column_names"] and "created_at" in ix["column_names"] for ix in indexes), \
            "缺少 (status, created_at) 复合索引"


def pytest_raises_integrity(db):
    from contextlib import contextmanager

    @contextmanager
    def _cm():
        try:
            yield
            raise AssertionError("应触发唯一约束/完整性错误")
        except Exception as exc:  # noqa: BLE001
            from sqlalchemy.exc import IntegrityError

            if not isinstance(exc, IntegrityError):
                raise
        finally:
            db.rollback()

    return _cm()
