"""环境档位管理 API 测试（Phase 2：管理员端）

覆盖：
- 权限：管理端点仅 admin（teacher/student → 403，未认证 → 401）
- packages：创建/输入注入拒绝/重复拒绝/更新（分类与状态）/被引用包核心字段不可变/停用
- profiles：创建/slug 冲突/更新/列表（含最新可用版本）
- versions：创建草稿（版本号递增、FOR UPDATE）/停用档位拒绝/未知包拒绝
- builds：创建并入队/available 不可重建/已有任务拒绝/列表/详情/日志/重试/队列不可用
- available 教师端点：只返回 available 且不含 digest/tag/构建日志；teacher 可访问、student 拒绝
"""
from __future__ import annotations
import pytest
pytestmark = pytest.mark.no_auto_env_seed

from sqlalchemy import select

from app.models import (
    EnvironmentBuildJob,
    EnvironmentProfile,
    EnvironmentVersion,
    PackageCatalog,
    ProfileVersionPackage,
)
from conftest import auth_header, create_user, login

API = "/api/v1/environments"


# ═══════════════════════════════════════════════════════════════
# 辅助
# ═══════════════════════════════════════════════════════════════

def _login_admin(client, db_session_factory):
    create_user(db_session_factory, "env_admin", "admin")
    tok, _ = login(client, "env_admin")
    return tok


def _login_teacher(client, db_session_factory):
    create_user(db_session_factory, "env_teacher", "teacher")
    tok, _ = login(client, "env_teacher")
    return tok


def _login_student(client, db_session_factory):
    create_user(db_session_factory, "env_student", "student")
    tok, _ = login(client, "env_student")
    return tok


def _create_package(client, admin_tok, **overrides):
    body = {
        "pip_name": "numpy",
        "locked_version": "2.1.3",
        "import_names": ["numpy"],
        "category_tags": ["data"],
        "source_key": "pypi",
    }
    body.update(overrides)
    r = client.post(f"{API}/packages", headers=auth_header(admin_tok), json=body)
    assert r.status_code in (200, 201), r.text
    return r.json()


def _create_profile(client, admin_tok, **overrides):
    body = {"slug": "basic", "display_name": "Python 基础", "description": "测试档位"}
    body.update(overrides)
    r = client.post(f"{API}/profiles", headers=auth_header(admin_tok), json=body)
    assert r.status_code in (200, 201), r.text
    return r.json()


def _create_version(client, admin_tok, profile_id, **overrides):
    body = {"package_ids": [], "minimum_memory_mb": 256}
    body.update(overrides)
    r = client.post(f"{API}/profiles/{profile_id}/versions", headers=auth_header(admin_tok), json=body)
    assert r.status_code in (200, 201), r.text
    return r.json()


def _create_build(client, admin_tok, version_id):
    r = client.post(f"{API}/versions/{version_id}/builds", headers=auth_header(admin_tok), json={"note": "t"})
    assert r.status_code in (200, 201), r.text
    return r.json()


# ═══════════════════════════════════════════════════════════════
# 权限
# ═══════════════════════════════════════════════════════════════

def test_unauthenticated_rejected(client):
    r = client.get(f"{API}/packages")
    assert r.status_code == 401


def test_teacher_forbidden_on_admin_endpoints(client, db_session_factory):
    tok = _login_teacher(client, db_session_factory)
    endpoints = [
        ("get", f"{API}/packages"),
        ("post", f"{API}/packages"),
        ("get", f"{API}/profiles"),
        ("post", f"{API}/profiles"),
        ("post", f"{API}/profiles/1/versions"),
        ("post", f"{API}/versions/1/builds"),
        ("get", f"{API}/builds"),
        ("post", f"{API}/builds/1/retry"),
    ]
    for method, path in endpoints:
        kwargs = {"json": {}} if method == "post" else {}
        r = getattr(client, method)(path, headers=auth_header(tok), **kwargs)
        assert r.status_code == 403, f"{method.upper()} {path}: {r.status_code}"
        assert r.json()["detail"]["code"] == "FORBIDDEN"


def test_student_forbidden_on_admin_endpoints(client, db_session_factory):
    tok = _login_student(client, db_session_factory)
    for path in [f"{API}/packages", f"{API}/profiles", f"{API}/builds"]:
        r = client.get(path, headers=auth_header(tok))
        assert r.status_code == 403, f"GET {path}: {r.status_code}"


def test_student_forbidden_on_available(client, db_session_factory):
    """available 是教师端点，学生不可访问"""
    tok = _login_student(client, db_session_factory)
    r = client.get(f"{API}/available", headers=auth_header(tok))
    assert r.status_code == 403


# ═══════════════════════════════════════════════════════════════
# packages
# ═══════════════════════════════════════════════════════════════

def test_create_and_list_package(client, db_session_factory):
    admin_tok = _login_admin(client, db_session_factory)
    pkg = _create_package(client, admin_tok, pip_name="pandas", locked_version="2.2.3",
                          import_names=["pandas"], category_tags=["data"])
    assert pkg["normalized_name"] == "pandas"
    assert pkg["status"] == "active"
    r = client.get(f"{API}/packages", headers=auth_header(admin_tok))
    assert r.status_code == 200
    assert any(p["id"] == pkg["id"] for p in r.json())


def test_create_package_rejects_injection(client, db_session_factory):
    admin_tok = _login_admin(client, db_session_factory)
    bad_inputs = [
        {"pip_name": "numpy; rm -rf /"},
        {"pip_name": "numpy\nRUN echo x"},
        {"pip_name": "not a name"},
        {"locked_version": ">=1.0"},
        {"locked_version": "1.0 || 2.0"},
        {"locked_version": "1.0\n--extra-index-url http://evil"},
        {"import_names": ["bad-name!"]},
        {"import_names": ["a.b.c..d"]},
        {"pip_name": "https://evil.com/pkg"},
    ]
    for overrides in bad_inputs:
        r = client.post(f"{API}/packages", headers=auth_header(admin_tok), json={
            "pip_name": "numpy", "locked_version": "2.1.3",
            "import_names": ["numpy"], **overrides,
        })
        assert r.status_code == 422, f"{overrides} → {r.status_code}"


def test_create_package_duplicate_rejected(client, db_session_factory):
    admin_tok = _login_admin(client, db_session_factory)
    _create_package(client, admin_tok)
    r = client.post(f"{API}/packages", headers=auth_header(admin_tok), json={
        "pip_name": "numpy", "locked_version": "2.1.3",
        "import_names": ["numpy"], "source_key": "pypi",
    })
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "PACKAGE_INVALID"


def test_patch_package_category_and_status(client, db_session_factory):
    admin_tok = _login_admin(client, db_session_factory)
    pkg = _create_package(client, admin_tok)
    r = client.patch(f"{API}/packages/{pkg['id']}", headers=auth_header(admin_tok),
                     json={"category_tags": ["science"], "status": "inactive"})
    assert r.status_code == 200
    assert r.json()["category_tags"] == ["science"]
    assert r.json()["status"] == "inactive"


def test_patch_referenced_package_core_fields_immutable(client, db_session_factory):
    """被版本引用的包不能原地修改核心字段（PACKAGE_IMMUTABLE）"""
    admin_tok = _login_admin(client, db_session_factory)
    pkg = _create_package(client, admin_tok)
    prof = _create_profile(client, admin_tok)
    _create_version(client, admin_tok, prof["id"], package_ids=[pkg["id"]])
    r = client.patch(f"{API}/packages/{pkg['id']}", headers=auth_header(admin_tok),
                     json={"locked_version": "2.1.4"})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "PACKAGE_IMMUTABLE"


def test_patch_unreferenced_package_core_fields_ok(client, db_session_factory):
    admin_tok = _login_admin(client, db_session_factory)
    pkg = _create_package(client, admin_tok)
    r = client.patch(f"{API}/packages/{pkg['id']}", headers=auth_header(admin_tok),
                     json={"locked_version": "2.2.0"})
    assert r.status_code == 200
    assert r.json()["locked_version"] == "2.2.0"


def test_delete_package_means_deactivate(client, db_session_factory):
    admin_tok = _login_admin(client, db_session_factory)
    pkg = _create_package(client, admin_tok)
    r = client.delete(f"{API}/packages/{pkg['id']}", headers=auth_header(admin_tok))
    assert r.status_code == 200
    assert r.json()["status"] == "inactive"
    r = client.get(f"{API}/packages", headers=auth_header(admin_tok))
    assert r.status_code == 200
    assert any(p["id"] == pkg["id"] for p in r.json())  # 不物理删除


# ═══════════════════════════════════════════════════════════════
# profiles
# ═══════════════════════════════════════════════════════════════

def test_create_and_list_profiles(client, db_session_factory):
    admin_tok = _login_admin(client, db_session_factory)
    prof = _create_profile(client, admin_tok)
    assert prof["slug"] == "basic"
    assert prof["status"] == "active"
    r = client.get(f"{API}/profiles", headers=auth_header(admin_tok))
    assert r.status_code == 200
    assert any(p["id"] == prof["id"] for p in r.json())


def test_create_profile_slug_conflict(client, db_session_factory):
    admin_tok = _login_admin(client, db_session_factory)
    _create_profile(client, admin_tok, slug="data")
    r = client.post(f"{API}/profiles", headers=auth_header(admin_tok), json={
        "slug": "data", "display_name": "重复",
    })
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "PROFILE_SLUG_CONFLICT"


def test_create_profile_invalid_slug(client, db_session_factory):
    admin_tok = _login_admin(client, db_session_factory)
    for slug in ["Bad Slug", "UPPER", "a/b", ""]:
        r = client.post(f"{API}/profiles", headers=auth_header(admin_tok), json={
            "slug": slug, "display_name": "x",
        })
        assert r.status_code == 422, f"slug={slug!r} → {r.status_code}"


def test_patch_profile(client, db_session_factory):
    admin_tok = _login_admin(client, db_session_factory)
    prof = _create_profile(client, admin_tok)
    r = client.patch(f"{API}/profiles/{prof['id']}", headers=auth_header(admin_tok),
                     json={"display_name": "改名", "status": "inactive"})
    assert r.status_code == 200
    assert r.json()["display_name"] == "改名"
    assert r.json()["status"] == "inactive"


# ═══════════════════════════════════════════════════════════════
# versions
# ═══════════════════════════════════════════════════════════════

def test_create_version_draft_with_numbering(client, db_session_factory):
    admin_tok = _login_admin(client, db_session_factory)
    prof = _create_profile(client, admin_tok)
    v1 = _create_version(client, admin_tok, prof["id"])
    assert v1["version_number"] == 1
    assert v1["status"] == "draft"
    assert v1["minimum_memory_mb"] == 256
    assert len(v1["manifest_sha256"]) == 64
    v2 = _create_version(client, admin_tok, prof["id"])
    assert v2["version_number"] == 2


def test_create_version_with_packages(client, db_session_factory):
    admin_tok = _login_admin(client, db_session_factory)
    pkg = _create_package(client, admin_tok)
    prof = _create_profile(client, admin_tok)
    ver = _create_version(client, admin_tok, prof["id"], package_ids=[pkg["id"]])
    assert ver["version_number"] == 1
    with db_session_factory() as db:
        rows = list(db.scalars(select(ProfileVersionPackage).where(
            ProfileVersionPackage.environment_version_id == ver["id"])))
        assert len(rows) == 1
        assert rows[0].package_catalog_id == pkg["id"]


def test_create_version_unknown_package(client, db_session_factory):
    admin_tok = _login_admin(client, db_session_factory)
    prof = _create_profile(client, admin_tok)
    r = client.post(f"{API}/profiles/{prof['id']}/versions", headers=auth_header(admin_tok),
                    json={"package_ids": [99999], "minimum_memory_mb": 256})
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "PACKAGE_NOT_FOUND"


def test_create_version_on_inactive_profile(client, db_session_factory):
    admin_tok = _login_admin(client, db_session_factory)
    prof = _create_profile(client, admin_tok)
    client.patch(f"{API}/profiles/{prof['id']}", headers=auth_header(admin_tok), json={"status": "inactive"})
    r = client.post(f"{API}/profiles/{prof['id']}/versions", headers=auth_header(admin_tok),
                    json={"package_ids": [], "minimum_memory_mb": 256})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "PROFILE_INACTIVE"


def test_list_versions(client, db_session_factory):
    admin_tok = _login_admin(client, db_session_factory)
    prof = _create_profile(client, admin_tok)
    _create_version(client, admin_tok, prof["id"])
    _create_version(client, admin_tok, prof["id"])
    r = client.get(f"{API}/profiles/{prof['id']}/versions", headers=auth_header(admin_tok))
    assert r.status_code == 200
    versions = r.json()
    assert [v["version_number"] for v in versions] == [2, 1]


def test_profiles_list_has_latest_version(client, db_session_factory):
    admin_tok = _login_admin(client, db_session_factory)
    prof = _create_profile(client, admin_tok)
    ver = _create_version(client, admin_tok, prof["id"])
    with db_session_factory() as db:
        _mark_available(db, ver["id"])
    r = client.get(f"{API}/profiles", headers=auth_header(admin_tok))
    assert r.status_code == 200
    item = next(p for p in r.json() if p["id"] == prof["id"])
    assert item["latest_version"] is not None
    assert item["latest_version"]["version_number"] == 1


# ═══════════════════════════════════════════════════════════════
# builds
# ═══════════════════════════════════════════════════════════════

def test_create_build_job_enqueues_redis(client, db_session_factory, redis_client):
    admin_tok = _login_admin(client, db_session_factory)
    prof = _create_profile(client, admin_tok)
    ver = _create_version(client, admin_tok, prof["id"])
    job = _create_build(client, admin_tok, ver["id"])
    assert job["status"] == "queued"
    assert job["attempt_number"] == 1
    # Redis 只负责唤醒：DB 事实源，消息含 version_id
    queue = redis_client.lrange("environment:build:queue", 0, -1)
    assert len(queue) == 1
    assert f'"version_id": {ver["id"]}' in queue[0]


def test_create_build_available_version_rejected(client, db_session_factory, redis_client):
    admin_tok = _login_admin(client, db_session_factory)
    prof = _create_profile(client, admin_tok)
    ver = _create_version(client, admin_tok, prof["id"])
    with db_session_factory() as db:
        row = db.get(EnvironmentVersion, ver["id"])
        row.status = "available"
        row.image_digest = "sha256:" + "a" * 64
        db.commit()
    r = client.post(f"{API}/versions/{ver['id']}/builds", headers=auth_header(admin_tok), json={})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "VERSION_IMMUTABLE"


def test_create_build_already_active_rejected(client, db_session_factory, redis_client):
    admin_tok = _login_admin(client, db_session_factory)
    prof = _create_profile(client, admin_tok)
    ver = _create_version(client, admin_tok, prof["id"])
    _create_build(client, admin_tok, ver["id"])
    r = client.post(f"{API}/versions/{ver['id']}/builds", headers=auth_header(admin_tok), json={})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "BUILD_ALREADY_ACTIVE"


def test_list_and_get_builds(client, db_session_factory, redis_client):
    admin_tok = _login_admin(client, db_session_factory)
    prof = _create_profile(client, admin_tok)
    ver = _create_version(client, admin_tok, prof["id"])
    job = _create_build(client, admin_tok, ver["id"])
    r = client.get(f"{API}/builds", headers=auth_header(admin_tok))
    assert r.status_code == 200
    assert any(j["id"] == job["id"] for j in r.json())
    r = client.get(f"{API}/builds/{job['id']}", headers=auth_header(admin_tok))
    assert r.status_code == 200
    assert r.json()["status"] == "queued"


def test_get_build_log(client, db_session_factory, redis_client):
    """API 返回入库存储值——脱敏发生在 Worker 写库前（environment_builder.redact_build_log）"""
    from app.services.environment_builder import redact_build_log

    admin_tok = _login_admin(client, db_session_factory)
    prof = _create_profile(client, admin_tok)
    ver = _create_version(client, admin_tok, prof["id"])
    job = _create_build(client, admin_tok, ver["id"])
    raw_log = "STEP1\nhttps://user:secret@host/path\nAuthorization: Bearer abc123\n"
    redacted = redact_build_log(raw_log)
    assert "secret" not in redacted
    assert "abc123" not in redacted
    with db_session_factory() as db:
        row = db.get(EnvironmentBuildJob, job["id"])
        row.log_text = redacted  # 模拟 Worker 已脱敏入库
        db.commit()
    r = client.get(f"{API}/builds/{job['id']}/log", headers=auth_header(admin_tok))
    assert r.status_code == 200
    body = r.json()
    assert body["job_id"] == job["id"]
    assert body["log_text"] == redacted


def test_retry_failed_build(client, db_session_factory, redis_client):
    admin_tok = _login_admin(client, db_session_factory)
    prof = _create_profile(client, admin_tok)
    ver = _create_version(client, admin_tok, prof["id"])
    job = _create_build(client, admin_tok, ver["id"])
    with db_session_factory() as db:
        row = db.get(EnvironmentBuildJob, job["id"])
        row.status = "failed"
        row.error_code = "BUILD_FAILED"
        db.commit()
    r = client.post(f"{API}/builds/{job['id']}/retry", headers=auth_header(admin_tok))
    assert r.status_code in (200, 201)
    new_job = r.json()
    assert new_job["status"] == "queued"
    assert new_job["attempt_number"] == 2
    assert new_job["retry_of_id"] == job["id"]
    # 重试也会重新入队唤醒
    queue = redis_client.lrange("environment:build:queue", 0, -1)
    assert len(queue) == 2


def test_retry_non_retryable_status(client, db_session_factory, redis_client):
    admin_tok = _login_admin(client, db_session_factory)
    prof = _create_profile(client, admin_tok)
    ver = _create_version(client, admin_tok, prof["id"])
    job = _create_build(client, admin_tok, ver["id"])
    with db_session_factory() as db:
        row = db.get(EnvironmentBuildJob, job["id"])
        row.status = "succeeded"
        db.commit()
    r = client.post(f"{API}/builds/{job['id']}/retry", headers=auth_header(admin_tok))
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "BUILD_NOT_RETRYABLE"


def test_create_build_redis_unavailable(client, db_session_factory, redis_client, monkeypatch):
    """入队唤醒失败 → BUILD_QUEUE_UNAVAILABLE，但任务保留在 DB（queued 不丢失）"""
    import app.api.environments as env_api

    def boom(*a, **k):
        raise RuntimeError("redis down")

    monkeypatch.setattr(env_api, "enqueue_build_redis", boom)
    admin_tok = _login_admin(client, db_session_factory)
    prof = _create_profile(client, admin_tok)
    ver = _create_version(client, admin_tok, prof["id"])
    r = client.post(f"{API}/versions/{ver['id']}/builds", headers=auth_header(admin_tok), json={})
    assert r.status_code == 503
    assert r.json()["detail"]["code"] == "BUILD_QUEUE_UNAVAILABLE"
    with db_session_factory() as db:
        jobs = list(db.scalars(select(EnvironmentBuildJob).where(
            EnvironmentBuildJob.environment_version_id == ver["id"])))
        assert len(jobs) == 1
        assert jobs[0].status == "queued"


# ═══════════════════════════════════════════════════════════════
# available（教师端点）
# ═══════════════════════════════════════════════════════════════

def _mark_available(db, version_id):
    row = db.get(EnvironmentVersion, version_id)
    row.status = "available"
    row.image_digest = "sha256:" + "b" * 64
    row.python_version = "3.12"
    db.commit()


def test_available_returns_only_available_versions(client, db_session_factory):
    admin_tok = _login_admin(client, db_session_factory)
    teacher_tok = _login_teacher(client, db_session_factory)
    pkg = _create_package(client, admin_tok, pip_name="pandas", locked_version="2.2.3", import_names=["pandas"])
    prof = _create_profile(client, admin_tok)
    v1 = _create_version(client, admin_tok, prof["id"], package_ids=[pkg["id"]])
    with db_session_factory() as db:
        _mark_available(db, v1["id"])
    _create_version(client, admin_tok, prof["id"])  # v2 保持 draft

    r = client.get(f"{API}/available", headers=auth_header(teacher_tok))
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    item = items[0]
    assert item["environment_version_id"] == v1["id"]
    assert item["slug"] == "basic"
    assert item["version_number"] == 1
    assert item["minimum_memory_mb"] == 256
    assert [p["pip_name"] for p in item["packages"]] == ["pandas"]


def test_available_omits_sensitive_fields(client, db_session_factory):
    """教师响应绝不包含 digest、tag、基础镜像、构建日志"""
    admin_tok = _login_admin(client, db_session_factory)
    teacher_tok = _login_teacher(client, db_session_factory)
    prof = _create_profile(client, admin_tok)
    v1 = _create_version(client, admin_tok, prof["id"])
    with db_session_factory() as db:
        _mark_available(db, v1["id"])
    r = client.get(f"{API}/available", headers=auth_header(teacher_tok))
    assert r.status_code == 200
    body = r.text
    for forbidden in ["image_digest", "image_tag", "base_image_ref", "manifest_sha256", "log_text", "dockerfile"]:
        assert forbidden not in body, f"教师响应泄露字段: {forbidden}"


def test_available_excludes_inactive_profile(client, db_session_factory):
    admin_tok = _login_admin(client, db_session_factory)
    teacher_tok = _login_teacher(client, db_session_factory)
    prof = _create_profile(client, admin_tok)
    v1 = _create_version(client, admin_tok, prof["id"])
    with db_session_factory() as db:
        _mark_available(db, v1["id"])
    client.patch(f"{API}/profiles/{prof['id']}", headers=auth_header(admin_tok), json={"status": "inactive"})
    r = client.get(f"{API}/available", headers=auth_header(teacher_tok))
    assert r.status_code == 200
    assert r.json() == []


def test_available_admin_can_access(client, db_session_factory):
    admin_tok = _login_admin(client, db_session_factory)
    r = client.get(f"{API}/available", headers=auth_header(admin_tok))
    assert r.status_code == 200
