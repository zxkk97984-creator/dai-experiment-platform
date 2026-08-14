"""TASK-028（F-22/F-23）：AI 输出与成本护栏。

- 各操作 completion 预算（评分 1500 / Rubric 2000 / 测试组 3000），未知操作 fail-closed
- usage/延迟/重试指标入结构化日志；usage 缺失不阻断；日志绝不出现学生原文
- 高成本生成限流在 Redis 故障时 fail-closed 返回 503（F-23）
- httpx 客户端不读环境代理变量（socks 代理注入不破坏出站调用）
"""
import json
import logging

import httpx
import pytest
from conftest import auth_header, create_user, login
from sqlalchemy import select

from app.config import Settings

API = "/api/v1"

# ── 客户端：预算与指标 ──────────────────────────────────────────


def _make_settings(**overrides):
    kwargs = {
        "ai_base_url": "https://aihub.codingpython.cn",
        "ai_model": "deepseek-v4-flash",
        "ai_api_key": "test-only-key-not-real",
        "ai_timeout_seconds": 10,
        "ai_max_retries": 2,
    }
    kwargs.update(overrides)
    return Settings(_env_file=None, **kwargs)


def _ok_response(**usage):
    body = {"choices": [{"message": {"content": '{"ok":true}'}}]}
    if usage:
        body["usage"] = usage
    return httpx.Response(200, json=body)


@pytest.mark.parametrize(
    ("operation", "expected"),
    [
        ("ai_grading", 1500),
        ("rubric_generation", 2000),
        ("test_group_generation", 3000),
    ],
)
def test_operation_budget_sent_as_max_tokens(operation, expected):
    """F-22：每个操作的 completion 预算写入请求体 max_tokens。"""
    from app.services.ai_client import DeepSeekClient

    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return _ok_response()

    client = DeepSeekClient(_make_settings(), transport=httpx.MockTransport(handler))
    client.chat_json([{"role": "user", "content": "x"}], operation=operation)
    assert seen["body"]["max_tokens"] == expected


def test_unknown_operation_fails_closed():
    """未登记预算的操作拒绝调用——不存在无预算出站路径。"""
    from app.services.ai_client import DeepSeekClient

    def handler(request):  # pragma: no cover - 不应发出请求
        raise AssertionError("未登记操作不得出站")

    client = DeepSeekClient(_make_settings(), transport=httpx.MockTransport(handler))
    with pytest.raises(ValueError, match="未登记"):
        client.chat_json([{"role": "user", "content": "x"}], operation="unregistered")


def test_usage_metrics_logged(caplog):
    """成功调用记录 operation/model/tokens/延迟/尝试次数。"""
    from app.services.ai_client import DeepSeekClient

    seen = {}

    def handler(request):
        return _ok_response(
            prompt_tokens=42, completion_tokens=7, total_tokens=49,
        )

    client = DeepSeekClient(_make_settings(), transport=httpx.MockTransport(handler))
    with caplog.at_level(logging.INFO, logger="dai.ai_client"):
        client.chat_json([{"role": "user", "content": "x"}], operation="ai_grading")

    completed = [r for r in caplog.records if r.getMessage() == "ai_chat_completed"]
    assert len(completed) == 1
    rec = completed[0]
    assert rec.operation == "ai_grading"
    assert rec.model == "deepseek-v4-flash"
    assert rec.prompt_tokens == 42
    assert rec.completion_tokens == 7
    assert rec.total_tokens == 49
    assert rec.max_tokens == 1500
    assert rec.attempts == 1
    assert rec.elapsed_ms >= 0


def test_usage_missing_tolerated(caplog):
    """usage 缺失不阻断调用，指标记录 None（可核算性由 TASK-029 聚合侧处理）。"""
    from app.services.ai_client import DeepSeekClient

    client = DeepSeekClient(
        _make_settings(),
        transport=httpx.MockTransport(lambda request: _ok_response()),
    )
    with caplog.at_level(logging.INFO, logger="dai.ai_client"):
        result = client.chat_json([{"role": "user", "content": "x"}], operation="ai_grading")
    assert result == {"ok": True}
    rec = next(r for r in caplog.records if r.getMessage() == "ai_chat_completed")
    assert rec.prompt_tokens is None
    assert rec.completion_tokens is None
    assert rec.total_tokens is None


def test_truncated_json_retries_then_succeeds(caplog):
    """JSON 截断（预算不足的典型表现）→ 可重试；attempts 计入指标。"""
    from app.services.ai_client import DeepSeekClient

    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            # 截断的 JSON：缺少闭合括号
            return httpx.Response(200, json={
                "choices": [{"message": {"content": '{"ok": true'}}],
            })
        return _ok_response()

    client = DeepSeekClient(_make_settings(), transport=httpx.MockTransport(handler))
    with caplog.at_level(logging.INFO, logger="dai.ai_client"):
        result = client.chat_json([{"role": "user", "content": "x"}], operation="ai_grading")

    assert result == {"ok": True}
    assert calls["n"] == 2
    # 每次响应都做用量核算（截断的那次也消耗 token）；最终成功记录 attempts=2
    completed = [r for r in caplog.records if r.getMessage() == "ai_chat_completed"]
    assert len(completed) == 2
    assert completed[-1].attempts == 2


def test_exhausted_retries_log_has_operation(caplog):
    """重试耗尽日志携带 operation（TASK-029 聚合判题失败/重试指标的依据）。"""
    from app.services.ai_client import AIServiceError, DeepSeekClient

    client = DeepSeekClient(
        _make_settings(),
        transport=httpx.MockTransport(lambda request: httpx.Response(500, text="boom")),
    )
    with caplog.at_level(logging.ERROR, logger="dai.ai_client"):
        with pytest.raises(AIServiceError):
            client.chat_json([{"role": "user", "content": "x"}], operation="rubric_generation")

    exhausted = [r for r in caplog.records if r.getMessage() == "ai_retries_exhausted"]
    assert len(exhausted) == 1
    assert exhausted[0].operation == "rubric_generation"
    assert exhausted[0].attempts == 3


def test_logs_never_contain_student_source(caplog):
    """日志脱敏：任何记录都不得包含学生原文/提示内容。"""
    from app.services.ai_client import DeepSeekClient

    secret = "SECRET_STUDENT_CODE_NEVER_LOG"
    client = DeepSeekClient(
        _make_settings(),
        transport=httpx.MockTransport(lambda request: _ok_response()),
    )
    with caplog.at_level(logging.DEBUG, logger="dai.ai_client"):
        client.chat_json(
            [{"role": "user", "content": f"学生的代码: {secret}"}],
            operation="ai_grading",
        )
    for record in caplog.records:
        assert secret not in record.getMessage()
        assert secret not in str(getattr(record, "exc_info", "") or "")


def test_proxy_env_ignored(monkeypatch):
    """trust_env=False：socks/http 代理环境变量不影响客户端构造与请求。"""
    from app.services.ai_client import DeepSeekClient

    monkeypatch.setenv("ALL_PROXY", "socks5://127.0.0.1:9999")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9999")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9999")

    client = DeepSeekClient(
        _make_settings(),
        transport=httpx.MockTransport(lambda request: _ok_response()),
    )
    assert client.chat_json([{"role": "user", "content": "x"}], operation="ai_grading") == {"ok": True}


# ── 端点：限流失效 fail-closed（F-23） ──────────────────────────


def _setup_teacher_question(client, db_session_factory, username):
    """建教师/课程/作业/题目，返回 (headers, question_id)。"""
    from app.models import User

    create_user(db_session_factory, username, "teacher")
    token, _ = login(client, username)
    headers = auth_header(token)
    course_id = client.post(
        f"{API}/courses", headers=headers, json={"title": f"{username}-course"},
    ).json()["id"]
    assignment_id = client.post(
        f"{API}/assignments", headers=headers,
        json={"title": f"{username}-assignment", "course_id": course_id},
    ).json()["id"]
    q = client.post(
        f"{API}/assignments/{assignment_id}/questions", headers=headers,
        json={
            "title": "两数相加", "function_name": "add", "signature": "def add(a, b)",
            "public_cases": [], "hidden_tests": "def t(): pass",
            "grading_mode": "active",
        },
    ).json()
    with db_session_factory() as db:
        user = db.scalar(select(User).where(User.username == username))
        user_id = user.id
    return headers, q["id"], user_id


@pytest.mark.parametrize(
    ("path", "scope_prefix"),
    [
        ("rubrics/generate", "rubric"),
        ("test-groups/generate", "testgroups"),
    ],
)
def test_generation_rate_limit_redis_failure_returns_503(
    client, db_session_factory, redis_client, monkeypatch, path, scope_prefix,
):
    """F-23：限流 Redis 故障 → 503，高成本生成不放行。"""
    headers, qid, user_id = _setup_teacher_question(
        client, db_session_factory, f"rl_fail_{scope_prefix}",
    )

    def broken_incr(key):
        raise RuntimeError("redis down")

    monkeypatch.setattr(redis_client, "incr", broken_incr)
    response = client.post(
        f"{API}/ai-grading/questions/assignment/{qid}/{path}",
        headers=headers, json={},
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "AI_RATE_LIMIT_UNAVAILABLE"


@pytest.mark.parametrize(
    ("path", "scope_prefix"),
    [
        ("rubrics/generate", "rubric"),
        ("test-groups/generate", "testgroups"),
    ],
)
def test_generation_rate_limit_over_limit_returns_429(
    client, db_session_factory, redis_client, path, scope_prefix,
):
    """同一 scope 60 秒内第 6 次调用 → 429。"""
    headers, qid, user_id = _setup_teacher_question(
        client, db_session_factory, f"rl_429_{scope_prefix}",
    )
    key = f"ai:gen:{scope_prefix}:assignment:{qid}:{user_id}"
    for _ in range(6):
        redis_client.incr(key)

    response = client.post(
        f"{API}/ai-grading/questions/assignment/{qid}/{path}",
        headers=headers, json={},
    )
    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "AI_RATE_LIMITED"
