"""结构化日志配置——统一 request_id / job_id 透传"""
import contextvars
import logging
import sys

# ContextVar 替代全局类变量，避免并发请求相互覆盖
_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


def set_request_id(rid: str) -> None:
    _request_id_var.set(rid)


def get_request_id() -> str:
    return _request_id_var.get()


class RequestIDFilter(logging.Filter):
    """将 request_id 注入日志记录——挂在 handler 而非 root logger"""

    def filter(self, record):
        record.request_id = get_request_id()
        return True


def setup_logging():
    """配置根日志——人类可读格式（开发）/ JSON（生产）"""
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
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
