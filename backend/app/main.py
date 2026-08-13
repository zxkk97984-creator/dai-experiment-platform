import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from sqlalchemy import select

from app.api import api_router
from app.config import Settings, get_settings
from app.database import SessionLocal
from app.dependencies import require_roles
from app.services.exam_service import scan_expired_exams

logger = logging.getLogger("dai.main")


def _normalize_detail(detail):
    if isinstance(detail, dict) and set(detail.keys()) == {"code", "message", "fields"}:
        return detail
    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        return {"code": detail["code"], "message": detail["message"], "fields": detail.get("fields", {})}
    if isinstance(detail, str):
        return {"code": "ERROR", "message": detail, "fields": {}}
    return {"code": "ERROR", "message": str(detail), "fields": {}}


async def _expiry_scanner():
    """定期扫描：过期考试自动交卷 + grading finalize（约 5 秒一轮）。

    多 API 实例下通过 exam-expiry DB 租约保证同一时刻只有一个实例执行；
    judge/AI stale recovery 由 Judge Worker 在 grading-recovery 租约下负责，
    此处不再重复做判题恢复。
    """
    import os
    import socket
    import uuid
    # owner 每进程唯一：hostname + pid + 随机实例 ID
    # （同机多 API 进程若只含 hostname 会共享 owner，导致同时续租同时扫描）
    _instance_id = uuid.uuid4().hex[:8]
    owner_id = f"api:{socket.gethostname()}:{os.getpid()}:{_instance_id}"
    while True:
        try:
            await asyncio.sleep(5)
            with SessionLocal() as db:
                from app.services.scheduler_lease import try_acquire_lease
                if not try_acquire_lease(db, "exam-expiry", owner_id, ttl_seconds=20):
                    continue  # 其他实例持有租约
                from app.services.time_utils import utc_now
                metrics = scan_expired_exams(db, utc_now())
                if any(v > 0 for v in metrics.values()):
                    logger.info("考试扫描: %s", metrics)
        except Exception:
            logger.exception("过期考试扫描异常")


async def _kernel_cleanup():
    """定期清理空闲 Kernel session"""
    while True:
        try:
            await asyncio.sleep(300)  # 每 5 分钟清理一次
            from app.services.kernel_manager import get_kernel_manager
            km = get_kernel_manager()
            km.cleanup_idle(max_idle_seconds=900)  # 15 分钟无活动则销毁
        except Exception:
            logger.exception("Kernel 清理异常")


@asynccontextmanager
async def lifespan(app):
    expiry_task = asyncio.create_task(_expiry_scanner())
    cleanup_task = asyncio.create_task(_kernel_cleanup())
    yield
    expiry_task.cancel()
    cleanup_task.cancel()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    # Request ID 中间件
    from app.logging_config import set_request_id, setup_logging
    setup_logging()

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        from app.logging_config import _request_id_var
        rid = request.headers.get("X-Request-ID", "") or str(uuid.uuid4())[:8]
        token = set_request_id(rid)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            _request_id_var.reset(token)  # 请求结束后重置，避免泄漏到下一个请求

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"detail": {"code": "VALIDATION_ERROR", "message": "请求参数校验失败", "fields": {"errors": [str(e) for e in exc.errors()]}}},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_: Request, exc: StarletteHTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": _normalize_detail(exc.detail)})

    @app.exception_handler(HTTPException)
    async def fastapi_http_exception_handler(_: Request, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": _normalize_detail(exc.detail)})

    @app.exception_handler(Exception)
    async def general_exception_handler(_: Request, exc: Exception):
        logger.exception("未处理的服务器异常: %s", exc)
        return JSONResponse(status_code=500, content={"detail": {"code": "INTERNAL_ERROR", "message": "服务器内部错误", "fields": {}}})

    @app.get("/api/v1/health/live", tags=["health"])
    def health_live():
        """存活检查——总是返回 ok"""
        return {"status": "ok", "app": settings.app_name}

    @app.get("/api/v1/health/ready", tags=["health"])
    def health_ready():
        """就绪检查——验证 MySQL + Redis 可达。

        Redis 承载 Refresh Token、黑名单与队列唤醒，是认证关键依赖；
        任一依赖故障即返回 503，且不回显底层异常详情。
        """
        import redis as _redis
        ready = True
        details = {}

        # MySQL
        try:
            from app.database import SessionLocal
            db = SessionLocal()
            db.execute(select(1)) if True else None  # simplified check
            db.close()
            details["mysql"] = "ok"
        except Exception:
            ready = False
            details["mysql"] = "unavailable"

        # Redis
        try:
            r = _redis.Redis.from_url(settings.redis_url, socket_connect_timeout=2)
            r.ping()
            details["redis"] = "ok"
        except Exception:
            ready = False
            details["redis"] = "unavailable"

        status_code = 200 if ready else 503
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=status_code,
            content={"status": "ready" if ready else "degraded", "checks": details},
        )

    @app.get("/health", tags=["health"])
    def health():
        return {"status": "ok", "app": settings.app_name}

    @app.get("/api/v1/metrics", tags=["metrics"])
    def metrics(current_user=Depends(require_roles("admin"))):
        """内部指标——仅管理员可访问（Nginx 代理后 IP 检查不可靠，改用认证）"""
        from app.database import SessionLocal
        from app.models import ExamAnswer, Submission
        stats = {}
        try:
            db = SessionLocal()
            stats["assignment_queued"] = db.query(Submission).filter(
                Submission.grading_status == "queued").count()
            stats["assignment_running"] = db.query(Submission).filter(
                Submission.grading_status == "running").count()
            stats["assignment_pending"] = db.query(Submission).filter(
                Submission.grading_status == "pending").count()
            stats["exam_queued"] = db.query(ExamAnswer).filter(
                ExamAnswer.grading_status == "queued").count()
            stats["exam_running"] = db.query(ExamAnswer).filter(
                ExamAnswer.grading_status == "running").count()
            stats["exam_pending"] = db.query(ExamAnswer).filter(
                ExamAnswer.grading_status == "pending").count()
            db.close()
        except Exception as e:
            stats["error"] = str(e)[:100]
        return {"metrics": stats}

    app.include_router(api_router)
    return app


app = create_app()
