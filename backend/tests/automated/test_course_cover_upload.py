"""课程封面：上传 / 权限 / 校验 / 生命周期 / 公开读取 端到端测试

- 存储目录由 conftest 指向 tmp_path，绝不写入真实 backend/storage/covers/
- 公开媒体端点直接使用 TestClient（无需登录、Cookie、Token 或签名）
- 服务层单测直接调用 course_cover_service（控制字符文件名无法经 HTTP 传输）
"""
from __future__ import annotations

import asyncio
import re
from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile

from app import models
from app.services import course_cover_service as svc
from conftest import auth_header, create_user, login

API = "/api/v1"

# 封面存储 key 的逻辑前缀
COVER_KEY_PREFIX = "covers/"

# 稳定错误码
COVER_FILE_EMPTY = "COVER_FILE_EMPTY"
COVER_FILENAME_INVALID = "COVER_FILENAME_INVALID"
COVER_TYPE_UNSUPPORTED = "COVER_TYPE_UNSUPPORTED"
COVER_CONTENT_INVALID = "COVER_CONTENT_INVALID"
COVER_TOO_LARGE = "COVER_TOO_LARGE"
COVER_NOT_FOUND = "COVER_NOT_FOUND"


# ── 合法图片文件头 ──────────────────────────────────────────────────
def jpeg_bytes(size: int = 200) -> bytes:
    head = b"\xff\xd8\xff\xe0"
    return head + b"x" * max(0, size - len(head))


def png_bytes(size: int = 200) -> bytes:
    head = b"\x89PNG\r\n\x1a\n"
    return head + b"x" * max(0, size - len(head))


def gif_bytes(size: int = 200, version: str = "89a") -> bytes:
    head = f"GIF{version}".encode("ascii")
    return head + b"x" * max(0, size - len(head))


def webp_bytes(size: int = 200) -> bytes:
    head = b"RIFF" + (size - 8).to_bytes(4, "little") + b"WEBP"
    return head + b"x" * max(0, size - len(head))


def _store(upload: UploadFile, course_id: int, settings):
    """同步调用异步存储服务（服务层单测用）"""
    return asyncio.run(svc.store_upload(upload, course_id, settings))


def _upload_file(name: str, content: bytes, mime: str) -> UploadFile:
    return UploadFile(
        filename=name,
        file=BytesIO(content),
        headers={"content-type": mime},
    )


def _error_code(exc: HTTPException) -> str:
    return exc.detail["code"]


def _cover_keys(test_settings):
    """封面根目录下所有最终文件 key（逻辑 key 形式，含 covers/ 前缀，不含 .staging）"""
    root = test_settings.cover_storage_path
    if not root.exists():
        return []
    return sorted(
        COVER_KEY_PREFIX + str(p.relative_to(root)).replace("\\", "/")
        for p in root.rglob("*")
        if p.is_file() and ".staging" not in p.parts
    )


def _staging_files(test_settings):
    staging = test_settings.cover_storage_path / ".staging"
    if not staging.exists():
        return []
    return list(staging.iterdir())


# ══════════════════════════════════════════════════════════════════
# 服务层校验（Task 2）
# ══════════════════════════════════════════════════════════════════

def test_service_rejects_svg_and_exe_extensions(test_settings):
    for name, mime in [("evil.svg", "image/svg+xml"), ("evil.exe", "application/octet-stream")]:
        upload = _upload_file(name, b"<svg></svg>" if name.endswith(".svg") else b"MZ" + b"x" * 100, mime)
        with pytest.raises(HTTPException) as exc:
            _store(upload, 1, test_settings)
        assert _error_code(exc.value) == COVER_TYPE_UNSUPPORTED, name


def test_service_rejects_mime_not_in_whitelist(test_settings):
    upload = _upload_file("a.jpg", jpeg_bytes(), "application/pdf")
    with pytest.raises(HTTPException) as exc:
        _store(upload, 1, test_settings)
    assert _error_code(exc.value) == COVER_TYPE_UNSUPPORTED


def test_service_rejects_extension_mime_mismatch(test_settings):
    upload = _upload_file("a.jpg", jpeg_bytes(), "image/png")
    with pytest.raises(HTTPException) as exc:
        _store(upload, 1, test_settings)
    assert _error_code(exc.value) == COVER_TYPE_UNSUPPORTED


def test_service_rejects_fake_magic_numbers(test_settings):
    cases = [
        ("fake.jpg", png_bytes(), "image/jpeg"),       # 假 JPEG：PNG 头
        ("fake.png", jpeg_bytes(), "image/png"),       # 假 PNG：JPEG 头
        ("fake.gif", png_bytes(), "image/gif"),        # 假 GIF：PNG 头
        ("fake.webp", jpeg_bytes(), "image/webp"),     # 假 WebP：JPEG 头
        ("fake.jpg", b"\xff\xd8\x00notjpeg", "image/jpeg"),  # 魔数开头但不完整
    ]
    for name, content, mime in cases:
        upload = _upload_file(name, content, mime)
        with pytest.raises(HTTPException) as exc:
            _store(upload, 1, test_settings)
        assert _error_code(exc.value) == COVER_CONTENT_INVALID, name
    assert _cover_keys(test_settings) == []


def test_service_rejects_empty_file(test_settings):
    upload = _upload_file("a.jpg", b"", "image/jpeg")
    with pytest.raises(HTTPException) as exc:
        _store(upload, 1, test_settings)
    assert _error_code(exc.value) == COVER_FILE_EMPTY


def test_service_too_large_413_no_residue(test_settings):
    test_settings.cover_max_upload_bytes = 512
    upload = _upload_file("big.jpg", jpeg_bytes(2048), "image/jpeg")
    with pytest.raises(HTTPException) as exc:
        _store(upload, 1, test_settings)
    assert _error_code(exc.value) == COVER_TOO_LARGE
    # staging 与最终目录均无残留
    assert _staging_files(test_settings) == []
    assert _cover_keys(test_settings) == []


def test_service_rejects_bad_filenames(test_settings):
    cases = [
        "../escape.jpg",
        "a\\b.jpg",
        "a/b.jpg",
        "a" * 300 + ".jpg",
        "..jpg",
        ".",
        "..",
    ]
    for name in cases:
        upload = _upload_file(name, jpeg_bytes(), "image/jpeg")
        with pytest.raises(HTTPException) as exc:
            _store(upload, 1, test_settings)
        assert _error_code(exc.value) == COVER_FILENAME_INVALID, repr(name)
    # NUL 与控制字符（HTTP 层无法传输，服务层直接拒绝）
    for name in ("x\x00y.jpg", "x\x01y.jpg", "x\x1fy.jpg"):
        upload = _upload_file(name, jpeg_bytes(), "image/jpeg")
        with pytest.raises(HTTPException) as exc:
            _store(upload, 1, test_settings)
        assert _error_code(exc.value) == COVER_FILENAME_INVALID, repr(name)
    assert _cover_keys(test_settings) == []


def test_service_stored_key_is_uuid_without_original_name(test_settings):
    stored = _store(_upload_file("秘密封面.png", png_bytes(300), "image/png"), 42, test_settings)
    assert re.fullmatch(
        rf"covers/42/[0-9a-f]{{32}}\.png",
        stored.storage_key,
    ), stored.storage_key
    assert "秘密封面" not in stored.storage_key
    assert stored.content_type == "image/png"
    assert stored.size == 300
    # 磁盘上只有这一个文件，且位于封面根目录内
    keys = _cover_keys(test_settings)
    assert keys == [stored.storage_key]


def test_service_resolve_rejects_non_covers_key_and_traversal(test_settings):
    # 非 covers/ 前缀一律拒绝
    for bad in ("videos/1/x.mp4", "lessons/1/x.mp4", "covers2/1/x.jpg"):
        with pytest.raises(HTTPException) as exc:
            svc.resolve_storage_path(test_settings, bad)
        assert _error_code(exc.value) == COVER_NOT_FOUND, bad
    # 目录穿越一律拒绝
    for bad in ("../escape.jpg", "covers/../escape.jpg", "covers/1/../../etc/passwd"):
        with pytest.raises(HTTPException) as exc:
            svc.resolve_storage_path(test_settings, bad)
        assert _error_code(exc.value) == COVER_NOT_FOUND, bad
    # None 与空串同样拒绝
    for bad in (None, ""):
        with pytest.raises(HTTPException) as exc:
            svc.resolve_storage_path(test_settings, bad)
        assert _error_code(exc.value) == COVER_NOT_FOUND


def test_service_accepts_all_formats(test_settings):
    expected = [
        ("a.jpg", jpeg_bytes(), "image/jpeg", ".jpg"),
        ("a.jpeg", jpeg_bytes(), "image/jpeg", ".jpeg"),
        ("a.png", png_bytes(), "image/png", ".png"),
        ("a.gif", gif_bytes(200, "87a"), "image/gif", ".gif"),
        ("a.gif", gif_bytes(200, "89a"), "image/gif", ".gif"),
        ("a.webp", webp_bytes(), "image/webp", ".webp"),
    ]
    for i, (name, content, mime, ext) in enumerate(expected):
        stored = _store(_upload_file(name, content, mime), 7, test_settings)
        assert stored.storage_key.startswith(f"covers/7/"), name
        assert stored.storage_key.endswith(ext), name
        assert stored.content_type == mime, name
    assert len(_cover_keys(test_settings)) == len(expected)


# ══════════════════════════════════════════════════════════════════
# 接口与生命周期（Task 4）
# ══════════════════════════════════════════════════════════════════

def _setup(client, db_session_factory, visibility="public", archived=False, tag=""):
    """教师 owner + 其他教师 + 学生 + 管理员；可创建 archived 课程。

    tag 用于同一测试内多次调用时避免用户名冲突。
    """
    prefix = f"{tag}_" if tag else ""
    create_user(db_session_factory, f"{prefix}t_own", "teacher")
    create_user(db_session_factory, f"{prefix}t_other", "teacher")
    create_user(db_session_factory, f"{prefix}s_yes", "student")
    create_user(db_session_factory, f"{prefix}admin", "admin")
    tok = {u: login(client, f"{prefix}{u}")[0] for u in ["t_own", "t_other", "s_yes", "admin"]}
    c = client.post(f"{API}/courses", headers=auth_header(tok["t_own"]), json={
        "title": "封面课程", "status": "published", "visibility": visibility,
    })
    cid = c.json()["id"]
    if archived:
        r = client.delete(f"{API}/courses/{cid}", headers=auth_header(tok["t_own"]))
        assert r.status_code == 204
    return {"tok": tok, "cid": cid}


def _put_cover(client, tok, cid, filename, content, mime):
    return client.put(
        f"{API}/courses/{cid}/cover",
        headers=auth_header(tok),
        files={"file": (filename, content, mime)},
    )


def _get_course(client, tok, cid):
    r = client.get(f"{API}/courses/{cid}", headers=auth_header(tok))
    assert r.status_code == 200, r.text
    return r.json()


# ── 上传权限 ──────────────────────────────────────────────────────

def test_owner_teacher_uploads_cover(client, db_session_factory, test_settings):
    d = _setup(client, db_session_factory)
    r = _put_cover(client, d["tok"]["t_own"], d["cid"], "cover.png", png_bytes(300), "image/png")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["id"] == d["cid"]
    assert re.fullmatch(
        rf"covers/{d['cid']}/[0-9a-f]{{32}}\.png", data["cover"]
    ), data["cover"]
    assert len(_cover_keys(test_settings)) == 1


def test_admin_uploads_cover(client, db_session_factory):
    d = _setup(client, db_session_factory)
    r = _put_cover(client, d["tok"]["admin"], d["cid"], "a.jpg", jpeg_bytes(), "image/jpeg")
    assert r.status_code == 200, r.text


def test_other_teacher_and_student_forbidden(client, db_session_factory, test_settings):
    d = _setup(client, db_session_factory)
    for role in ("t_other", "s_yes"):
        r = _put_cover(client, d["tok"][role], d["cid"], "a.jpg", jpeg_bytes(), "image/jpeg")
        assert r.status_code == 403, f"{role}: {r.status_code}"
        assert r.json()["detail"]["code"] == "FORBIDDEN", role
    assert _cover_keys(test_settings) == []


def test_upload_requires_login(client, db_session_factory):
    d = _setup(client, db_session_factory)
    r = client.put(
        f"{API}/courses/{d['cid']}/cover",
        files={"file": ("a.jpg", jpeg_bytes(), "image/jpeg")},
    )
    assert r.status_code == 401


def test_upload_missing_course_404(client, db_session_factory):
    d = _setup(client, db_session_factory)
    r = _put_cover(client, d["tok"]["t_own"], 99999, "a.jpg", jpeg_bytes(), "image/jpeg")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "COURSE_NOT_FOUND"


def test_put_cover_returns_courseread(client, db_session_factory):
    d = _setup(client, db_session_factory)
    r = _put_cover(client, d["tok"]["t_own"], d["cid"], "a.webp", webp_bytes(150), "image/webp")
    assert r.status_code == 200, r.text
    data = r.json()
    # CourseRead 完整字段：id / title / status / visibility / cover
    assert data["title"] == "封面课程"
    assert data["status"] == "published"
    assert data["cover"].startswith(f"covers/{d['cid']}/")
    # 数据库值就是逻辑 key
    course = _get_course(client, d["tok"]["t_own"], d["cid"])
    assert course["cover"] == data["cover"]


# ── 生命周期 ──────────────────────────────────────────────────────

def test_replace_cover_deletes_old_file_after_commit(client, db_session_factory, test_settings):
    d = _setup(client, db_session_factory)
    r1 = _put_cover(client, d["tok"]["t_own"], d["cid"], "a.png", png_bytes(), "image/png")
    assert r1.status_code == 200
    first_key = r1.json()["cover"]
    assert first_key in _cover_keys(test_settings)

    r2 = _put_cover(client, d["tok"]["t_own"], d["cid"], "b.jpg", jpeg_bytes(250), "image/jpeg")
    assert r2.status_code == 200
    second_key = r2.json()["cover"]
    assert second_key != first_key
    # 数据库指向新 key，旧文件在提交成功后已被删除
    keys = _cover_keys(test_settings)
    assert keys == [second_key], "替换后旧文件应被删除"


def test_db_commit_failure_removes_new_file_keeps_old(
    client, app, db_session_factory, test_settings, monkeypatch
):
    d = _setup(client, db_session_factory)
    r1 = _put_cover(client, d["tok"]["t_own"], d["cid"], "a.png", png_bytes(), "image/png")
    assert r1.status_code == 200
    first_key = r1.json()["cover"]

    # 使用不抛出异常的 TestClient 以接收 500 响应体
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session as ORMSession

    quiet_client = TestClient(app, raise_server_exceptions=False)

    def _fail_commit(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(ORMSession, "commit", _fail_commit)
    r = _put_cover(quiet_client, d["tok"]["t_own"], d["cid"], "b.jpg", jpeg_bytes(), "image/jpeg")
    assert r.status_code == 500
    # 新文件被清理，旧文件与旧数据库值保留
    assert _cover_keys(test_settings) == [first_key]
    course = _get_course(client, d["tok"]["t_own"], d["cid"])
    assert course["cover"] == first_key


def test_delete_cover_clears_field_and_file(client, db_session_factory, test_settings):
    d = _setup(client, db_session_factory)
    assert _put_cover(client, d["tok"]["t_own"], d["cid"], "a.png", png_bytes(), "image/png").status_code == 200
    assert len(_cover_keys(test_settings)) == 1

    r = client.delete(f"{API}/courses/{d['cid']}/cover", headers=auth_header(d["tok"]["t_own"]))
    assert r.status_code == 204
    course = _get_course(client, d["tok"]["t_own"], d["cid"])
    assert course["cover"] is None
    assert _cover_keys(test_settings) == []


def test_delete_cover_idempotent_no_cover(client, db_session_factory, test_settings):
    d = _setup(client, db_session_factory)
    r = client.delete(f"{API}/courses/{d['cid']}/cover", headers=auth_header(d["tok"]["t_own"]))
    assert r.status_code == 204
    course = _get_course(client, d["tok"]["t_own"], d["cid"])
    assert course["cover"] is None


def test_delete_legacy_external_cover_only_clears_field(client, db_session_factory, test_settings):
    d = _setup(client, db_session_factory)
    # 历史外链封面（直接写入数据库，模拟旧数据）
    with db_session_factory() as db:
        course = db.get(models.Course, d["cid"])
        course.cover = "https://legacy.example.com/old-cover.jpg"
        db.commit()
    r = client.delete(f"{API}/courses/{d['cid']}/cover", headers=auth_header(d["tok"]["t_own"]))
    assert r.status_code == 204
    course = _get_course(client, d["tok"]["t_own"], d["cid"])
    assert course["cover"] is None
    assert _cover_keys(test_settings) == [], "历史外链不操作磁盘"


def test_concurrent_replace_uses_locked_latest_old_key(client, db_session_factory, test_settings):
    """替换时以行锁内读取的最新旧 key 为准，不误删锁外并发写入的文件"""
    d = _setup(client, db_session_factory)
    r1 = _put_cover(client, d["tok"]["t_own"], d["cid"], "a.png", png_bytes(), "image/png")
    assert r1.status_code == 200
    first_key = r1.json()["cover"]

    # 模拟锁外并发：另一事务把 cover 改成磁盘上不存在的 key
    with db_session_factory() as db:
        course = db.get(models.Course, d["cid"])
        course.cover = f"covers/{d['cid']}/ffffffffffffffffffffffffffffffff.png"
        db.commit()

    r2 = _put_cover(client, d["tok"]["t_own"], d["cid"], "b.jpg", jpeg_bytes(), "image/jpeg")
    assert r2.status_code == 200
    second_key = r2.json()["cover"]
    assert second_key != first_key
    # 旧 key（锁内读到的）磁盘不存在 → 安全跳过；第一个文件不得被误删
    assert first_key in _cover_keys(test_settings)
    assert second_key in _cover_keys(test_settings)
    course = _get_course(client, d["tok"]["t_own"], d["cid"])
    assert course["cover"] == second_key


# ══════════════════════════════════════════════════════════════════
# 公开读取（Task 4）
# ══════════════════════════════════════════════════════════════════

def _uploaded_setup(client, db_session_factory, visibility="public", archived=False, tag=""):
    d = _setup(client, db_session_factory, visibility=visibility, archived=archived, tag=tag)
    r = _put_cover(client, d["tok"]["t_own"], d["cid"], "a.png", png_bytes(500), "image/png")
    assert r.status_code == 200, r.text
    d["cover"] = r.json()["cover"]
    return d


def test_media_readable_without_auth_for_all_visibilities(client, db_session_factory):
    # public / private / whitelist / archived 课程的封面均可匿名读取
    for i, (visibility, archived) in enumerate([
        ("public", False),
        ("private", False),
        ("whitelist", False),
        ("public", True),
    ]):
        d = _uploaded_setup(client, db_session_factory, visibility=visibility, archived=archived, tag=f"v{i}")
        r = client.get(f"{API}/media/course-covers/{d['cid']}")
        assert r.status_code == 200, f"{visibility} archived={archived}: {r.status_code}"


def test_media_404_cases(client, db_session_factory, test_settings):
    d = _uploaded_setup(client, db_session_factory)
    # 无课程
    r = client.get(f"{API}/media/course-covers/99999")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "COVER_NOT_FOUND"
    # 有课程无封面
    d2 = _setup(client, db_session_factory, tag="d2")
    r = client.get(f"{API}/media/course-covers/{d2['cid']}")
    assert r.status_code == 404
    # 非受管 key（历史外链）不当作磁盘 key
    with db_session_factory() as db:
        course = db.get(models.Course, d["cid"])
        course.cover = "https://legacy.example.com/old.jpg"
        db.commit()
    r = client.get(f"{API}/media/course-covers/{d['cid']}")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "COVER_NOT_FOUND"
    # 磁盘文件丢失
    with db_session_factory() as db:
        course = db.get(models.Course, d2["cid"])
        course.cover = "covers/99999/missing.png"
        db.commit()
    r = client.get(f"{API}/media/course-covers/{d2['cid']}")
    assert r.status_code == 404


def test_media_returns_content_type_and_nosniff(client, db_session_factory):
    d = _uploaded_setup(client, db_session_factory)
    r = client.get(f"{API}/media/course-covers/{d['cid']}", params={"v": d["cover"]})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/png")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert len(r.content) == 500


def test_media_v_matching_returns_immutable_cache(client, db_session_factory):
    d = _uploaded_setup(client, db_session_factory)
    r = client.get(f"{API}/media/course-covers/{d['cid']}", params={"v": d["cover"]})
    assert r.status_code == 200
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_media_no_v_returns_short_cache(client, db_session_factory):
    d = _uploaded_setup(client, db_session_factory)
    r = client.get(f"{API}/media/course-covers/{d['cid']}")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "public, max-age=300"


def test_media_v_mismatch_returns_404(client, db_session_factory):
    d = _uploaded_setup(client, db_session_factory)
    r = client.get(
        f"{API}/media/course-covers/{d['cid']}",
        params={"v": f"covers/{d['cid']}/00000000000000000000000000000000.png"},
    )
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "COVER_NOT_FOUND"


def test_media_ignores_signature_params_and_enrollment(client, db_session_factory):
    """公开媒体端点不依赖签名参数，也不依赖用户或选课状态"""
    d = _uploaded_setup(client, db_session_factory)
    r = client.get(
        f"{API}/media/course-covers/{d['cid']}",
        params={"v": d["cover"], "uid": 1, "expires": 9999999999, "sig": "0" * 64},
    )
    assert r.status_code == 200
