import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import api_router
from app.config import Settings, get_settings
from app.database import SessionLocal
from app.dependencies import get_db, get_redis_client, require_roles
from app.services.exam_service import scan_expired_exams
from app.services.op_metrics import http_metrics_recorder

logger = logging.getLogger("dai.main")

# TASK-029：HTTP 状态类别/延迟指标记录器（Redis 故障时内部 no-op，不阻断请求）
_http_metrics = http_metrics_recorder()


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

    # Request ID 中间件 + 访问指标（TASK-029：状态类别/延迟，低基数路径模板）
    from app.logging_config import set_request_id, setup_logging
    setup_logging(settings.environment)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        from app.logging_config import _request_id_var
        rid = request.headers.get("X-Request-ID", "") or str(uuid.uuid4())[:8]
        token = set_request_id(rid)
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            _request_id_var.reset(token)  # 请求结束后重置，避免泄漏到下一个请求
            latency_ms = (time.perf_counter() - start) * 1000
            status_class = f"{status_code // 100}xx"
            # 路径模板（路由匹配后 scope 提供，如 /api/v1/courses/{course_id}）——
            # 绝不记录带资源 id 的原始路径（防高基数与内容泄露）
            path_template = ""
            route = request.scope.get("route")
            if route is not None:
                path_template = getattr(route, "path", "") or ""
            log_method = logger.warning if status_code >= 500 else logger.info
            log_method(
                "http_request",
                extra={
                    "method": request.method,
                    "path": path_template or "unmatched",
                    "status_code": status_code,
                    "latency_ms": round(latency_ms, 1),
                },
            )
            _http_metrics(status_class, latency_ms)

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
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": _normalize_detail(exc.detail)},
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(HTTPException)
    async def fastapi_http_exception_handler(_: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": _normalize_detail(exc.detail)},
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(_: Request, exc: Exception):
        logger.exception("未处理的服务器异常: %s", exc)
        return JSONResponse(status_code=500, content={"detail": {"code": "INTERNAL_ERROR", "message": "服务器内部错误", "fields": {}}})

    @app.get("/api/v1/health/live", tags=["health"])
    def health_live():
        """存活检查——总是返回 ok"""
        return {"status": "ok", "app": settings.app_name}

    @app.get("/api/v1/health/ready", tags=["health"])
    def health_ready(db=Depends(get_db), redis_client=Depends(get_redis_client)):
        """就绪检查——MySQL 与 Redis 均为关键依赖，任一不可用返回 503。

        响应不回显底层异常详情（只返回 ok/unavailable），细节仅记录服务端日志；
        liveness（/api/v1/health/live）只判断进程存活，不检查任何依赖。
        """
        ready = True
        details = {}

        # MySQL
        try:
            db.execute(select(1))
            details["mysql"] = "ok"
        except Exception:
            ready = False
            details["mysql"] = "unavailable"
            logger.warning("健康检查：MySQL 不可用", exc_info=True)

        # Redis（认证、限流与队列唤醒的关键依赖，故障时实例必须摘流）
        try:
            redis_client.ping()
            details["redis"] = "ok"
        except Exception:
            ready = False
            details["redis"] = "unavailable"
            logger.warning("健康检查：Redis 不可用", exc_info=True)

        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=200 if ready else 503,
            content={"status": "ready" if ready else "degraded", "checks": details},
        )

    @app.get("/health", tags=["health"])
    def health():
        return {"status": "ok", "app": settings.app_name}

    @app.get("/api/v1/metrics", tags=["metrics"])
    def metrics(
        current_user=Depends(require_roles("admin")),
        db: Session = Depends(get_db),
        redis_client=Depends(get_redis_client),
    ):
        """内部指标——仅管理员可访问（Nginx 代理后 IP 检查不可靠，改用认证）。

        TASK-029：除队列计数外，增加当前小时 op_metrics 快照、Redis 队列深度、
        最老排队年龄与 DB/Redis 健康；不包含任何提交内容。
        """
        from app.models import CodeGrade, ExamAnswer, Submission
        from app.services.op_metrics import queue_depth, snapshot
        stats = {}
        try:
            db.execute(select(1))
            stats["db_ok"] = True
        except Exception:
            stats["db_ok"] = False
            return {"metrics": stats}
        try:
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
            # 判题队列：DB 事实源（最老 queued 年龄）+ Redis 实际深度
            oldest = db.query(func.min(CodeGrade.queued_at)).filter(
                CodeGrade.status == "queued").scalar()
            if oldest is not None:
                stats["judge_queue_oldest_age_seconds"] = int(
                    (datetime.now(timezone.utc) - oldest).total_seconds()
                )
        except Exception as e:
            stats["db_error"] = str(e)[:100]
            return {"metrics": stats}

        # Redis 侧：队列深度 + 健康 + 当前小时指标快照
        try:
            stats["judge_queue_depth"] = queue_depth(redis_client, settings.ai_queue_name)
            redis_client.ping()
            stats["redis_ok"] = True
        except Exception:
            stats["redis_ok"] = False
        stats["window"] = "current_hour_utc"
        stats["op_metrics"] = snapshot(redis_client)
        return {"metrics": stats}

    app.include_router(api_router)
    return app


app = create_app()
