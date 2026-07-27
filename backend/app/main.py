import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from sqlalchemy import select

from app.api import api_router
from app.config import Settings, get_settings
from app.database import SessionLocal
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
    """定期扫描：过期考试自动交卷 + 判题任务恢复"""
    while True:
        try:
            await asyncio.sleep(15)
            with SessionLocal() as db:
                # 考试过期扫描
                from app.services.time_utils import utc_now
                count = scan_expired_exams(db, utc_now())
                if count > 0:
                    logger.info("过期考试扫描：自动交卷 %d 份", count)
        except Exception:
            logger.exception("过期考试扫描异常")

        try:
            await asyncio.sleep(15)
            with SessionLocal() as db:
                # 判题任务恢复扫描（作业 + 考试）
                from app.services.judge_queue import requeue_stale_jobs
                stats = requeue_stale_jobs(db)
                if any(v > 0 for v in stats.values()):
                    logger.info("判题任务恢复扫描：%s", stats)
        except Exception:
            logger.exception("判题任务恢复扫描异常")


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
        rid = request.headers.get("X-Request-ID", "") or str(uuid.uuid4())[:8]
        set_request_id(rid)
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

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
        """就绪检查——验证 MySQL + Redis 可达"""
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
        except Exception as e:
            ready = False
            details["mysql"] = str(e)[:100]

        # Redis
        try:
            r = _redis.Redis.from_url(settings.redis_url, socket_connect_timeout=2)
            r.ping()
            details["redis"] = "ok"
        except Exception as e:
            details["redis"] = str(e)[:100]
            # Redis 不可用不影响 ready（判题暂时无法入队但不阻塞 API）

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
    def metrics(request: Request):
        """内部指标——仅内网或鉴权访问"""
        # 简单的内网检查：仅允许 localhost/内网 IP 或无鉴权时返回 403
        host = request.client.host if request.client else "unknown"
        if host not in ("127.0.0.1", "localhost", "::1") and not host.startswith("10.") and not host.startswith("172.") and not host.startswith("192.168."):
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=403, content={"detail": "仅限内网访问"})
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
