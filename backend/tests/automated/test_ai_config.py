"""Task 1: AI 配置安全测试——默认值、密钥保护、ai_ready 判定"""
import os

import pytest

from app.config import Settings


def test_ai_defaults_are_safe():
    """默认值安全：Base URL、模型名、空密钥、repr 不含 secret"""
    settings = Settings(_env_file=None)
    assert settings.ai_base_url == "https://aihub.codingpython.cn"
    assert settings.ai_model == "deepseek-v4-flash"
    assert settings.ai_api_key.get_secret_value() == ""
    # SecretStr 默认用 ****** 遮蔽真实值
    api_key_repr = repr(settings.ai_api_key)
    assert "******" in api_key_repr or settings.ai_api_key.get_secret_value() == ""


def test_active_ai_requires_key():
    """ai_ready 属性：enabled 但 Key 为空时返回 False"""
    settings = Settings(_env_file=None, ai_enabled=True, ai_api_key="")
    assert settings.ai_ready is False


def test_ai_ready_true_with_key():
    """ai_ready 属性：enabled 且有 Key 时返回 True"""
    settings = Settings(_env_file=None, ai_enabled=True, ai_api_key="test-only-key-not-real")
    assert settings.ai_ready is True


def test_ai_disabled_means_not_ready():
    """ai_enabled=False 时无论 Key 是否存在都返回 False"""
    settings = Settings(_env_file=None, ai_enabled=False, ai_api_key="test-only-key-not-real")
    assert settings.ai_ready is False


def test_ai_timeout_in_range():
    """超时设置必须在 1-180 秒范围内"""
    with pytest.raises(Exception):  # pydantic ValidationError
        Settings(_env_file=None, ai_timeout_seconds=0)

    with pytest.raises(Exception):
        Settings(_env_file=None, ai_timeout_seconds=200)


def test_ai_max_retries_in_range():
    """重试次数必须在 0-8 范围内"""
    with pytest.raises(Exception):
        Settings(_env_file=None, ai_max_retries=-1)

    with pytest.raises(Exception):
        Settings(_env_file=None, ai_max_retries=10)


def test_ai_env_prefix_works(monkeypatch):
    """DAI_ 前缀环境变量正确映射到 Settings 字段"""
    monkeypatch.setenv("DAI_AI_BASE_URL", "https://custom.example.com")
    monkeypatch.setenv("DAI_AI_MODEL", "custom-model")
    monkeypatch.setenv("DAI_AI_API_KEY", "env-key-test")

    settings = Settings(_env_file=None)
    assert settings.ai_base_url == "https://custom.example.com"
    assert settings.ai_model == "custom-model"
    assert settings.ai_api_key.get_secret_value() == "env-key-test"


def test_key_not_in_error_or_repr():
    """Settings 的 repr/str 不泄露密钥明文"""
    settings = Settings(_env_file=None, ai_api_key="sk-secret-do-not-leak")
    settings_str = str(settings)
    settings_repr = repr(settings)
    assert "sk-secret-do-not-leak" not in settings_str
    assert "sk-secret-do-not-leak" not in settings_repr
