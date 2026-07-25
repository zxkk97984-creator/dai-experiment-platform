"""Notebook API — 已废弃，应用内薄转发到 /api/v1/experiments。

使用 ASGITransport 进行进程内路由，所有响应注入 Deprecation: true 头。
新客户端请直接使用 /api/v1/experiments。
教师上传功能已迁移至 /api/v1/studio。
"""
import json

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from app.dependencies import get_current_user
from app.models import User

router = APIRouter(prefix="/notebooks", tags=["notebooks"])


async def _forward(request: Request, target_method: str, target_path: str) -> Response:
    """使用 ASGITransport 对同一 app 实例进行进程内请求转发"""
    body = await request.body()
    headers = {k: v for k, v in request.headers.items()
               if k.lower() not in ("host", "content-length", "transfer-encoding")}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=request.app),
        base_url="http://testserver",
    ) as client:
        resp = await client.request(
            method=target_method,
            url=f"/api/v1/experiments{target_path}",
            headers=headers,
            content=body,
        )

    response_headers = dict(resp.headers)
    response_headers["Deprecation"] = "true"
    response_headers["Sunset"] = "2026-09-01"

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=response_headers,
        media_type=resp.headers.get("content-type"),
    )


# ── 映射路由 ─────────────────────────────────────────────────

@router.get("/{lesson_id}")
async def get_notebook(lesson_id: int, request: Request, _: User = Depends(get_current_user)):
    """GET /notebooks/{lesson_id} → POST /experiments/records/ensure-for-lesson/{lesson_id}"""
    return await _forward(request, "POST", f"/records/ensure-for-lesson/{lesson_id}")


@router.put("/records/{record_id}/cells")
async def save_cells(record_id: int, request: Request, _: User = Depends(get_current_user)):
    return await _forward(request, "PUT", f"/records/{record_id}/cells")


@router.post("/records/{record_id}/cells/{cell_id}/execute")
async def execute_cell(record_id: int, cell_id: str, request: Request, _: User = Depends(get_current_user)):
    return await _forward(request, "POST", f"/records/{record_id}/cells/{cell_id}/execute")


@router.post("/records/{record_id}/interrupt")
async def interrupt(record_id: int, request: Request, _: User = Depends(get_current_user)):
    return await _forward(request, "POST", f"/records/{record_id}/interrupt")


@router.post("/records/{record_id}/restart-kernel")
async def restart_kernel(record_id: int, request: Request, _: User = Depends(get_current_user)):
    return await _forward(request, "POST", f"/records/{record_id}/restart")


# ── catchall: 未映射的旧 notebooks 路由 ──────────────────────

@router.api_route("/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def catchall_deprecated(_: User = Depends(get_current_user)):
    return Response(
        content=json.dumps({"detail": {"code": "DEPRECATED", "message": "此 API 已废弃，请使用 /api/v1/experiments", "fields": {}}}),
        status_code=410,
        media_type="application/json",
        headers={"Deprecation": "true", "Sunset": "2026-09-01"},
    )
