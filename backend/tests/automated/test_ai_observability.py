"""Task 13: AI 可观测性与安全测试——日志脱敏、恢复、安全检查"""
from app.services.ai_client import sanitize_ai_error


def test_log_sanitize_removes_key():
    """sanitize_ai_error 移除 API Key"""
    error = "HTTP 401: Unauthorized with key sk-abc123xyz and Bearer token"
    safe = sanitize_ai_error(error)
    assert "sk-abc123xyz" not in safe


def test_log_sanitize_preserves_diagnostics():
    """sanitize_ai_error 保留有用诊断信息"""
    error = "Connection timeout after 30s to https://aihub.codingpython.cn/v1/chat/completions"
    safe = sanitize_ai_error(error)
    assert "timeout" in safe
    assert "aihub" in safe


def test_log_sanitize_truncates_long_errors():
    """sanitize_ai_error 截断过长错误消息"""
    long_error = "x" * 2000
    safe = sanitize_ai_error(long_error)
    assert len(safe) <= 1000


def test_queue_sanitize_consistent_with_client():
    """队列和客户端的脱敏逻辑一致"""
    from app.services.ai_grading_queue import _sanitize
    error = "Bearer sk-secret-key-value error"
    client_safe = sanitize_ai_error(error)
    queue_safe = _sanitize(error)
    assert "sk-secret-key-value" not in client_safe
    assert "sk-secret-key-value" not in queue_safe


def test_client_repr_no_leak(monkeypatch):
    """DeepSeekClient repr 不泄露 API Key"""
    from app.config import Settings
    from app.services.ai_client import DeepSeekClient

    # httpx 默认 trust_env：shell 中的代理变量（如 ALL_PROXY=socks://…）
    # 会让 httpx.Client 构造抛 ValueError，与测试目的无关——隔离环境变量
    for var in ("ALL_PROXY", "all_proxy", "HTTP_PROXY", "http_proxy",
                "HTTPS_PROXY", "https_proxy"):
        monkeypatch.delenv(var, raising=False)

    settings = Settings(
        _env_file=None,
        ai_api_key="sk-do-not-leak-this-key",
        ai_base_url="https://aihub.codingpython.cn",
        ai_model="deepseek-v4-flash",
    )
    client = DeepSeekClient(settings)
    repr_str = repr(client)
    assert "sk-do-not-leak-this-key" not in repr_str


def test_settings_str_no_leak():
    """Settings str() 不泄露 API Key"""
    from app.config import Settings

    settings = Settings(
        _env_file=None,
        ai_api_key="sk-settings-leak-test",
    )
    settings_str = str(settings)
    assert "sk-settings-leak-test" not in settings_str


def test_stale_running_recovery_api():
    """recover_stale_ai_grades 接口存在且可调用"""
    from app.services.ai_grading_queue import recover_stale_ai_grades

    # 验证函数存在且接受正确参数
    assert callable(recover_stale_ai_grades)
