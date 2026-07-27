import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

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

    @app.get("/health", tags=["health"])
    def health():
        return {"status": "ok", "app": settings.app_name}

    app.include_router(api_router)
    return app


app = create_app()
