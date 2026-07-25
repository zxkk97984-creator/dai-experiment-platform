from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import asyncio
from contextlib import asynccontextmanager

from app.api import api_router
from app.config import Settings, get_settings
from app.database import SessionLocal
from app.services.exam_service import scan_expired_exams


def _normalize_detail(detail):
    if isinstance(detail, dict) and set(detail.keys()) == {"code", "message", "fields"}:
        return detail
    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        return {"code": detail["code"], "message": detail["message"], "fields": detail.get("fields", {})}
    if isinstance(detail, str):
        return {"code": "ERROR", "message": detail, "fields": {}}
    return {"code": "ERROR", "message": str(detail), "fields": {}}


async def _expiry_scanner():
    while True:
        try:
            await asyncio.sleep(15)
            from datetime import datetime, timezone
            with SessionLocal() as db:
                scan_expired_exams(db, datetime.now(timezone.utc))
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(_expiry_scanner())
    yield
    task.cancel()


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
        return JSONResponse(status_code=500, content={"detail": {"code": "INTERNAL_ERROR", "message": "服务器内部错误", "fields": {}}})

    @app.get("/health", tags=["health"])
    def health():
        return {"status": "ok", "app": settings.app_name}

    app.include_router(api_router)
    return app


app = create_app()
