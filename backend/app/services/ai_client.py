"""DeepSeek OpenAI 兼容客户端——重试、脱敏、JSON 提取"""
from __future__ import annotations

import json
import logging
import re
import time
import uuid
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger("dai.ai_client")

_RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}
_NON_RETRYABLE_HTTP_STATUS = {401, 403}


class AIServiceError(RuntimeError):
    """AI 服务异常，含可重试标记"""

    def __init__(self, code: str, message: str, *, retryable: bool):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def sanitize_ai_error(text: str) -> str:
    """删除错误文本中的 Bearer token 和疑似 API Key"""
    # 删除 Authorization header 值
    text = re.sub(r"Bearer\s+\S+", "Bearer ***", text)
    # 删除 sk- 开头的 key
    text = re.sub(r"sk-[a-zA-Z0-9]+", "sk-***", text)
    # 截断过长文本
    if len(text) > 1000:
        text = text[:1000]
    return text


def normalize_chat_endpoint(base_url: str) -> str:
    """规范化聊天补全端点"""
    url = base_url.rstrip("/")
    if url.endswith("/v1"):
        return f"{url}/chat/completions"
    return f"{url}/v1/chat/completions"


def extract_json_object(text: str) -> dict:
    """从文本中提取 JSON 对象——支持 markdown fence 和纯 JSON"""
    text = text.strip()
    # 尝试 markdown fence ```json ... ```
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    # 尝试提取最外层 {...}
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        text = brace_match.group(0)
    return json.loads(text)


class DeepSeekClient:
    """DeepSeek OpenAI 兼容聊天客户端"""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.BaseTransport | None = None,
    ):
        self._settings = settings
        self._endpoint = normalize_chat_endpoint(settings.ai_base_url)
        self._client = httpx.Client(
            timeout=httpx.Timeout(settings.ai_timeout_seconds),
            transport=transport,
        )

    def __repr__(self) -> str:
        return (
            f"DeepSeekClient(endpoint={self._endpoint!r}, "
            f"model={self._settings.ai_model!r})"
        )

    def chat_json(self, messages: list[dict[str, str]]) -> dict:
        """发送聊天请求并返回解析后的 JSON 对象"""
        request_id = uuid.uuid4().hex[:12]
        payload = {
            "model": self._settings.ai_model,
            "messages": messages,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self._settings.ai_api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        max_attempts = 1 + self._settings.ai_max_retries

        for attempt in range(1, max_attempts + 1):
            start = time.monotonic()
            try:
                response = self._client.post(
                    self._endpoint,
                    headers=headers,
                    json=payload,
                )
                elapsed = time.monotonic() - start

                # 400 且使用了 response_format：降级重试一次（无 response_format）
                if response.status_code == 400 and payload.get("response_format") is not None:
                    logger.warning("AI 不支持 response_format，降级重试")
                    del payload["response_format"]
                    continue

                if response.status_code in _NON_RETRYABLE_HTTP_STATUS:
                    body = sanitize_ai_error(response.text[:500])
                    raise AIServiceError(
                        f"http_{response.status_code}",
                        f"AI 认证失败: {body}",
                        retryable=False,
                    )

                if response.status_code in _RETRYABLE_HTTP_STATUS:
                    body = sanitize_ai_error(response.text[:500])
                    raise AIServiceError(
                        f"http_{response.status_code}",
                        f"AI 服务暂时不可用 ({response.status_code}): {body}",
                        retryable=True,
                    )

                response.raise_for_status()
                data = response.json()

                logger.info(
                    "ai_chat_completed",
                    extra={
                        "request_id": request_id,
                        "model": self._settings.ai_model,
                        "status": response.status_code,
                        "elapsed_ms": round(elapsed * 1000),
                    },
                )

                choices = data.get("choices", [])
                if not choices:
                    raise AIServiceError(
                        "empty_choices",
                        "AI 返回空的 choices 列表",
                        retryable=True,
                    )

                content = choices[0]["message"]["content"]
                return extract_json_object(content)

            except AIServiceError as exc:
                if not exc.retryable:
                    raise
                last_error = exc
                logger.warning(
                    "ai_retryable_error",
                    extra={
                        "request_id": request_id,
                        "attempt": attempt,
                        "code": exc.code,
                    },
                )
            except httpx.TimeoutException:
                last_error = AIServiceError(
                    "timeout",
                    f"AI 请求超时 (尝试 {attempt}/{max_attempts})",
                    retryable=True,
                )
                logger.warning(
                    "ai_timeout",
                    extra={"request_id": request_id, "attempt": attempt},
                )
            except httpx.NetworkError as exc:
                last_error = AIServiceError(
                    "network_error",
                    f"AI 网络错误: {exc}",
                    retryable=True,
                )
                logger.warning(
                    "ai_network_error",
                    extra={"request_id": request_id, "attempt": attempt},
                )
            except (json.JSONDecodeError, ValueError) as exc:
                last_error = AIServiceError(
                    "bad_json",
                    f"AI 返回非 JSON 内容: {exc}",
                    retryable=True,
                )
                logger.warning(
                    "ai_bad_json",
                    extra={"request_id": request_id, "attempt": attempt},
                )
            except Exception as exc:
                last_error = AIServiceError(
                    "unknown",
                    f"AI 未知错误: {exc}",
                    retryable=False,
                )
                logger.error(
                    "ai_unknown_error",
                    extra={"request_id": request_id, "attempt": attempt},
                )
                raise last_error

            if attempt < max_attempts:
                backoff = min(2 ** (attempt - 1), 8)
                logger.info(
                    "ai_retrying",
                    extra={
                        "request_id": request_id,
                        "attempt": attempt,
                        "backoff_s": backoff,
                    },
                )
                time.sleep(backoff)

        # 重试耗尽
        logger.error(
            "ai_retries_exhausted",
            extra={"request_id": request_id, "attempts": max_attempts},
        )
        raise last_error  # type: ignore[misc]
