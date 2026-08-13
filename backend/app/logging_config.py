"""结构化日志配置——统一 request_id / job_id 透传；生产输出 JSON（含 extra 字段，脱敏）。"""
import contextvars
import json
import logging
import sys
from datetime import datetime, timezone

# ContextVar 替代全局类变量，避免并发请求相互覆盖
_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

# TASK-029：JSON 输出时剔除的敏感 extra 键（防未来误把密钥/学生原文打进日志）。
# *_tokens 是指标键（prompt/completion/total/max），必须放行——不在此列。
_SENSITIVE_KEY_PATTERN = ("api_key", "apikey", "password", "secret", "authorization", "cookie", "bearer")
_SAFE_TOKEN_KEYS = {"prompt_tokens", "completion_tokens", "total_tokens", "max_tokens"}


def set_request_id(rid: str):
    """设置当前请求 ID，返回 ContextVar token 用于请求结束后 reset"""
    return _request_id_var.set(rid)


def get_request_id() -> str:
    return _request_id_var.get()


class RequestIDFilter(logging.Filter):
    """将 request_id 注入日志记录——挂在 handler 而非 root logger"""

    def filter(self, record):
        record.request_id = get_request_id()
        return True


def _is_sensitive_key(name: str) -> bool:
    lowered = name.lower()
    if lowered in _SAFE_TOKEN_KEYS:
        return False
    return any(part in lowered for part in _SENSITIVE_KEY_PATTERN)


class JsonFormatter(logging.Formatter):
    """生产 JSON 行格式：标准字段 + extra 字段；敏感键剔除。"""

    _BASE_FIELDS = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "taskName", "message", "asctime",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "rid": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in self._BASE_FIELDS or key.startswith("_"):
                continue
            if _is_sensitive_key(key):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(environment: str = "development"):
    """配置根日志——人类可读格式（开发）/ JSON（生产，含 extra 字段与脱敏）"""
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    if environment == "production":
        handler.setFormatter(JsonFormatter())
    else:
        fmt = "%(asctime)s [%(levelname)s] %(name)s rid=%(request_id)s: %(message)s"
        handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%dT%H:%M:%S"))
    # Filter 加到 handler 而非 root logger，确保子 logger 记录也能获得 request_id
    handler.addFilter(RequestIDFilter())

    # 清除已有 handler 避免重复
    root.handlers = []
    root.addHandler(handler)

    # 抑制 noisy 库
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("fakeredis").setLevel(logging.WARNING)
