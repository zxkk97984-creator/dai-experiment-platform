"""结构化日志配置——统一 request_id / job_id 透传"""
import logging
import sys
import uuid


class RequestIDFilter(logging.Filter):
    """将 request_id 注入日志记录"""
    _request_id = None

    @classmethod
    def set_request_id(cls, request_id: str):
        cls._request_id = request_id

    @classmethod
    def get_request_id(cls) -> str:
        return cls._request_id or "-"

    def filter(self, record):
        record.request_id = self.get_request_id()
        return True


def setup_logging():
    """配置根日志——JSON 格式（生产）或人类可读（开发）"""
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    fmt = "%(asctime)s [%(levelname)s] %(name)s rid=%(request_id)s: %(message)s"
    handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%dT%H:%M:%S"))

    # 清除已有 handler 避免重复
    root.handlers = []
    root.addHandler(handler)

    # 抑制 noisy 库
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("fakeredis").setLevel(logging.WARNING)

    root.addFilter(RequestIDFilter())
