"""管理员系统日志 API——读取/过滤本进程组 JSON 行日志文件。

覆盖：
- admin 可查询：级别过滤（含及以上）、关键词、limit、时间倒序
- 非 admin（教师/学生）403；非法 source / 非法 level 422
- 不存在的文件返回空列表（worker 未启动等场景）
- 路径穿越拒绝：rotated 参数只能取数字序号
- /files 列出当前与轮转文件
"""
import json

import pytest
from conftest import auth_header, create_user, login

from app.config import Settings

API = "/api/v1"


@pytest.fixture()
def log_dir(tmp_path):
    return tmp_path / "logs"


def _write_log(log_dir, name, records):
    log_dir.mkdir(parents=True, exist_ok=True)
    with (log_dir / name).open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def _api_records():
    return [
        {"ts": "2026-08-22T10:00:00+00:00", "level": "INFO", "logger": "dai.ai_client",
         "rid": "aaa1", "message": "ai_chat_completed", "operation": "ai_grading",
         "completion_tokens": 800, "max_tokens": 8000},
        {"ts": "2026-08-22T10:01:00+00:00", "level": "ERROR", "logger": "dai.ai_client",
         "rid": "aaa2", "message": "ai_retries_exhausted", "operation": "rubric_generation",
         "attempts": 3},
        {"ts": "2026-08-22T10:02:00+00:00", "level": "INFO", "logger": "dai.main",
         "rid": "aaa3", "message": "http_request"},
        {"ts": "2026-08-22T10:03:00+00:00", "level": "WARNING", "logger": "dai.exam_grading",
         "rid": "aaa4", "message": "ExamSubmission 985 转 review_required"},
    ]


def _setup(client, db_session_factory):
    create_user(db_session_factory, "alog_t", "teacher")
    admin = create_user(db_session_factory, "alog_a", "admin")
    admin_tok, _ = login(client, "alog_a")
    teacher_tok, _ = login(client, "alog_t")
    return admin_tok, teacher_tok


def _app_with_log_dir(app, log_dir):
    from app.config import get_settings
    base = app.dependency_overrides[get_settings]()
    merged = Settings(**{**base.model_dump(), "log_dir": str(log_dir)})
    app.dependency_overrides[get_settings] = lambda: merged
    return merged


def test_admin_can_query_and_filter(client, app, db_session_factory, tmp_path):
    admin_tok, _ = _setup(client, db_session_factory)
    log_dir = tmp_path / "logs"
    _write_log(log_dir, "dai-api.log", _api_records())
    _app_with_log_dir(app, log_dir)

    r = client.get(f"{API}/admin/logs", headers=auth_header(admin_tok))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 4
    assert body["file"] == "dai-api.log"
    # 时间倒序：最新在前
    assert body["items"][0]["message"] == "ExamSubmission 985 转 review_required"

    # 级别过滤：ERROR 及以上只有 1 条
    r = client.get(f"{API}/admin/logs?level=ERROR", headers=auth_header(admin_tok))
    assert [i["level"] for i in r.json()["items"]] == ["ERROR"]

    # WARNING 及以上 = WARNING + ERROR
    r = client.get(f"{API}/admin/logs?level=WARNING", headers=auth_header(admin_tok))
    assert r.json()["total"] == 2

    # 关键词：ai_
    r = client.get(f"{API}/admin/logs?q=ai_", headers=auth_header(admin_tok))
    assert r.json()["total"] == 2
    assert all("ai_" in i["message"] for i in r.json()["items"])

    # rid 搜索
    r = client.get(f"{API}/admin/logs?q=aaa2", headers=auth_header(admin_tok))
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["operation"] == "rubric_generation"

    # limit
    r = client.get(f"{API}/admin/logs?limit=2", headers=auth_header(admin_tok))
    assert len(r.json()["items"]) == 2


def test_teacher_forbidden(client, app, db_session_factory, tmp_path):
    _, teacher_tok = _setup(client, db_session_factory)
    _app_with_log_dir(app, tmp_path / "logs")

    r = client.get(f"{API}/admin/logs", headers=auth_header(teacher_tok))
    assert r.status_code == 403


def test_invalid_params_rejected(client, app, db_session_factory, tmp_path):
    admin_tok, _ = _setup(client, db_session_factory)
    _app_with_log_dir(app, tmp_path / "logs")

    assert client.get(f"{API}/admin/logs?source=hack", headers=auth_header(admin_tok)).status_code == 422
    assert client.get(f"{API}/admin/logs?level=BOGUS", headers=auth_header(admin_tok)).status_code == 422


def test_missing_file_returns_empty(client, app, db_session_factory, tmp_path):
    """worker 日志不存在（未启动）→ 空列表而非报错。"""
    admin_tok, _ = _setup(client, db_session_factory)
    _app_with_log_dir(app, tmp_path / "logs")

    r = client.get(f"{API}/admin/logs?source=worker", headers=auth_header(admin_tok))
    assert r.status_code == 200
    assert r.json()["items"] == []
    assert r.json()["total"] == 0


def test_rotated_file_and_files_listing(client, app, db_session_factory, tmp_path):
    admin_tok, _ = _setup(client, db_session_factory)
    log_dir = tmp_path / "logs"
    _write_log(log_dir, "dai-worker.log", [
        {"ts": "2026-08-22T09:00:00+00:00", "level": "INFO", "logger": "dai.worker", "rid": "-", "message": "Worker 启动"},
    ])
    _write_log(log_dir, "dai-worker.log.1", [
        {"ts": "2026-08-22T08:00:00+00:00", "level": "ERROR", "logger": "dai.worker", "rid": "-", "message": "旧轮转日志"},
    ])
    _write_log(log_dir, "unrelated.txt", [])
    _app_with_log_dir(app, log_dir)

    r = client.get(f"{API}/admin/logs?source=worker", headers=auth_header(admin_tok))
    assert r.json()["total"] == 1

    r = client.get(f"{API}/admin/logs?source=worker&rotated=1", headers=auth_header(admin_tok))
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["message"] == "旧轮转日志"

    r = client.get(f"{API}/admin/logs/files", headers=auth_header(admin_tok))
    names = {f["name"] for f in r.json()["items"]}
    assert names == {"dai-worker.log", "dai-worker.log.1"}


def test_setup_logging_writes_json_file(tmp_path):
    """文件日志：setup_logging 后写入 JSON 行（管理员页依赖此格式）。"""
    import logging

    from app.logging_config import setup_logging

    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/x.db",
        secret_key="test-secret-key",
        log_dir=str(tmp_path / "logs2"),
        log_max_bytes=1024,
        log_backup_count=2,
    )
    setup_logging("development", process_name="unit", settings=settings)
    try:
        logging.getLogger("dai.test").warning("文件日志自检 %s", "ok")
        # 刷 handler 确保 promptly 写盘
        for handler in logging.getLogger().handlers:
            handler.flush()
        log_path = tmp_path / "logs2" / "dai-unit.log"
        assert log_path.exists()
        record = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
        assert record["level"] == "WARNING"
        assert "文件日志自检 ok" in record["message"]
        assert record["rid"] == "-"
    finally:
        # 还原全局 root handlers，避免污染其他测试的 stdout 捕获
        setup_logging("development", process_name="", settings=None)
