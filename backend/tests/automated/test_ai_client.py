"""Task 4: DeepSeek 客户端测试——MockTransport 覆盖各种场景"""
import json

import httpx
import pytest

from app.config import Settings


def make_test_settings(**overrides):
    """构建测试用 Settings"""
    kwargs = {
        "ai_base_url": "https://aihub.codingpython.cn",
        "ai_model": "deepseek-v4-flash",
        "ai_api_key": "test-only-key-not-real",
        "ai_timeout_seconds": 10,
        "ai_max_retries": 2,
    }
    kwargs.update(overrides)
    return Settings(_env_file=None, **kwargs)


# ── 端点与认证 ──


def test_chat_uses_configured_endpoint_and_model():
    """验证客户端使用配置的端点、模型和认证头"""
    from app.services.ai_client import DeepSeekClient

    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '{"ok":true}'}}]
        })

    client = DeepSeekClient(
        make_test_settings(),
        transport=httpx.MockTransport(handler),
    )
    result = client.chat_json([{"role": "user", "content": "hello"}], operation="ai_grading")
    assert result == {"ok": True}
    assert seen["url"] == "https://aihub.codingpython.cn/v1/chat/completions"
    assert seen["auth"].startswith("Bearer ")
    assert seen["auth"] == "Bearer test-only-key-not-real"
    assert seen["body"]["model"] == "deepseek-v4-flash"
    assert seen["body"]["temperature"] == 0


def test_chat_passes_messages_correctly():
    """验证消息正确传递"""
    from app.services.ai_client import DeepSeekClient

    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '{"ok":true}'}}]
        })

    client = DeepSeekClient(
        make_test_settings(),
        transport=httpx.MockTransport(handler),
    )
    messages = [
        {"role": "system", "content": "You are a code grader."},
        {"role": "user", "content": "Grade this code."},
    ]
    client.chat_json(messages, operation="ai_grading")
    assert seen["body"]["messages"] == messages
    assert seen["body"]["response_format"] == {"type": "json_object"}


# ── Base URL 处理 ──


def test_base_url_with_trailing_slash():
    """带尾部斜杠的 Base URL 正确处理"""
    from app.services.ai_client import DeepSeekClient

    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '{"ok":true}'}}]
        })

    client = DeepSeekClient(
        make_test_settings(ai_base_url="https://aihub.codingpython.cn/"),
        transport=httpx.MockTransport(handler),
    )
    client.chat_json([{"role": "user", "content": "x"}], operation="ai_grading")
    assert seen["url"] == "https://aihub.codingpython.cn/v1/chat/completions"


def test_base_url_already_contains_v1():
    """Base URL 已含 /v1 时不重复添加"""
    from app.services.ai_client import DeepSeekClient

    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '{"ok":true}'}}]
        })

    client = DeepSeekClient(
        make_test_settings(ai_base_url="https://aihub.codingpython.cn/v1"),
        transport=httpx.MockTransport(handler),
    )
    client.chat_json([{"role": "user", "content": "x"}], operation="ai_grading")
    assert seen["url"] == "https://aihub.codingpython.cn/v1/chat/completions"


# ── 重试与错误处理 ──


def test_retry_on_429():
    """429 错误后重试成功"""
    from app.services.ai_client import DeepSeekClient

    call_count = [0]

    def handler(request):
        call_count[0] += 1
        if call_count[0] < 2:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '{"ok":true}'}}]
        })

    client = DeepSeekClient(
        make_test_settings(ai_max_retries=2),
        transport=httpx.MockTransport(handler),
    )
    result = client.chat_json([{"role": "user", "content": "x"}], operation="ai_grading")
    assert result == {"ok": True}
    assert call_count[0] == 2


def test_retry_on_5xx():
    """5xx 错误后重试成功"""
    from app.services.ai_client import DeepSeekClient

    call_count = [0]

    def handler(request):
        call_count[0] += 1
        if call_count[0] < 3:
            return httpx.Response(503, json={"error": "service unavailable"})
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '{"ok":true}'}}]
        })

    client = DeepSeekClient(
        make_test_settings(ai_max_retries=3),
        transport=httpx.MockTransport(handler),
    )
    result = client.chat_json([{"role": "user", "content": "x"}], operation="ai_grading")
    assert result == {"ok": True}
    assert call_count[0] == 3


def test_exhausted_retries_raise():
    """重试耗尽后抛出 AIServiceError"""
    from app.services.ai_client import AIServiceError, DeepSeekClient

    def handler(request):
        return httpx.Response(503, json={"error": "down"})

    client = DeepSeekClient(
        make_test_settings(ai_max_retries=1),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(AIServiceError) as exc_info:
        client.chat_json([{"role": "user", "content": "x"}], operation="ai_grading")
    assert exc_info.value.retryable is True


def test_401_fails_immediately():
    """401/403 不重试直接失败"""
    from app.services.ai_client import AIServiceError, DeepSeekClient

    call_count = [0]

    def handler(request):
        call_count[0] += 1
        return httpx.Response(401, json={"error": "unauthorized"})

    client = DeepSeekClient(
        make_test_settings(ai_max_retries=3),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(AIServiceError) as exc_info:
        client.chat_json([{"role": "user", "content": "x"}], operation="ai_grading")
    assert exc_info.value.retryable is False
    assert call_count[0] == 1  # 一次都不重试


def test_timeout_raises_retryable():
    """超时错误可重试"""
    from app.services.ai_client import AIServiceError, DeepSeekClient

    def handler(request):
        raise httpx.TimeoutException("timeout")

    client = DeepSeekClient(
        make_test_settings(ai_timeout_seconds=1),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(AIServiceError) as exc_info:
        client.chat_json([{"role": "user", "content": "x"}], operation="ai_grading")
    assert exc_info.value.retryable is True


# ── JSON 提取 ──


def test_markdown_json_fence_extraction():
    """从 markdown 代码块中提取 JSON"""
    from app.services.ai_client import DeepSeekClient

    def handler(request):
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '```json\n{"ok":true}\n```'}}]
        })

    client = DeepSeekClient(
        make_test_settings(),
        transport=httpx.MockTransport(handler),
    )
    result = client.chat_json([{"role": "user", "content": "x"}], operation="ai_grading")
    assert result == {"ok": True}


def test_pure_json_without_fence():
    """无 markdown 包裹的纯 JSON"""
    from app.services.ai_client import DeepSeekClient

    def handler(request):
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '{"ok":true}'}}]
        })

    client = DeepSeekClient(
        make_test_settings(),
        transport=httpx.MockTransport(handler),
    )
    result = client.chat_json([{"role": "user", "content": "x"}], operation="ai_grading")
    assert result == {"ok": True}


def test_invalid_json_raises():
    """非法 JSON 抛出异常"""
    from app.services.ai_client import DeepSeekClient

    def handler(request):
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "not valid json at all"}}]
        })

    client = DeepSeekClient(
        make_test_settings(),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(Exception):
        client.chat_json([{"role": "user", "content": "x"}], operation="ai_grading")


def test_empty_choices_raises():
    """空 choices 抛出异常"""
    from app.services.ai_client import DeepSeekClient

    def handler(request):
        return httpx.Response(200, json={"choices": []})

    client = DeepSeekClient(
        make_test_settings(),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(Exception):
        client.chat_json([{"role": "user", "content": "x"}], operation="ai_grading")


def test_sanitize_ai_error_removes_secrets():
    """错误脱敏：不包含 Authorization 头和 Key"""
    from app.services.ai_client import sanitize_ai_error

    error_text = "HTTP 401: Bearer sk-1234567890abcdef"
    sanitized = sanitize_ai_error(error_text)
    assert "sk-1234567890abcdef" not in sanitized
    # "Bearer" 词本身是正常描述，不强制移除


def test_sanitize_ai_error_passes_safe_text():
    """脱敏函数不过滤普通错误消息"""
    from app.services.ai_client import sanitize_ai_error

    safe = sanitize_ai_error("Connection timeout after 30s")
    assert safe == "Connection timeout after 30s"


def test_api_key_not_in_repr():
    """客户端 repr 不泄露 API Key"""
    from app.services.ai_client import DeepSeekClient

    client = DeepSeekClient(
        make_test_settings(ai_api_key="sk-very-secret-do-not-leak")
    )
    client_repr = repr(client)
    assert "sk-very-secret-do-not-leak" not in client_repr
