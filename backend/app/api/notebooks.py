"""Notebook API — 已终止的旧兼容入口。

新客户端请使用 /api/v1/experiments；教师上传功能请使用 /api/v1/studio。
"""
import json

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.dependencies import get_current_user
from app.models import User

router = APIRouter(prefix="/notebooks", tags=["notebooks"])


# ── catchall: 旧 notebooks 路由统一终止 ─────────────────────

@router.api_route("/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def catchall_deprecated(_: User = Depends(get_current_user)):
    return Response(
        content=json.dumps({"detail": {"code": "DEPRECATED", "message": "此 API 已废弃，请使用 /api/v1/experiments", "fields": {}}}),
        status_code=410,
        media_type="application/json",
        headers={"Deprecation": "true", "Sunset": "2026-09-01"},
    )
