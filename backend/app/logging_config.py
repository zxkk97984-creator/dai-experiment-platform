"""结构化日志配置——统一 request_id / job_id 透传；生产输出 JSON（含 extra 字段，脱敏）。

文件日志：无论环境如何都写 JSON 行（按大小轮转），供管理员日志页直读；
控制台保持开发人类可读 / 生产 JSON。API 与 worker 写不同文件，避免多进程轮转冲突。
"""
import contextvars
import json
import logging
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

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


def _build_file_handler(log_path: Path, max_bytes: int, backup_count: int) -> RotatingFileHandler:
    """JSON 行格式文件 handler（轮转）；目录自动创建，权限收紧到 0o640。"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8",
    )
    handler.setFormatter(JsonFormatter())
    try:
        log_path.chmod(0o640)
    except OSError:
        pass  # 容器/受限环境下静默降级
    return handler


def setup_logging(environment: str = "development", *, process_name: str = "api", settings=None):
    """配置根日志。

    - 控制台：开发人类可读 / 生产 JSON
    - 文件：始终 JSON 行 + 按大小轮转（settings.log_dir 为空时禁用），
      文件名 dai-{process_name}.log——管理员日志页依赖此格式直读。
    """
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
    root.handlers = []
    root.addHandler(handler)

    # 文件日志（可选）：日志页读取的就是这些文件
    if settings is None:
        from app.config import get_settings
        try:
            settings = get_settings()
        except Exception:
            settings = None
    log_dir = getattr(settings, "log_dir", "") or ""
    if log_dir and process_name:
        try:
            file_handler = _build_file_handler(
                Path(log_dir) / f"dai-{process_name}.log",
                max_bytes=int(getattr(settings, "log_max_bytes", 20 * 1024 * 1024)),
                backup_count=int(getattr(settings, "log_backup_count", 10)),
            )
            file_handler.addFilter(RequestIDFilter())
            root.addHandler(file_handler)
        except OSError:
            # 文件系统不可写等场景不阻断服务启动
            root.warning("文件日志初始化失败（跳过）", exc_info=True)

    # 抑制 noisy 库
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("fakeredis").setLevel(logging.WARNING)
