from typing import Any

from fastapi import HTTPException


def api_error(status_code: int, code: str, message: str, fields: dict[str, Any] | None = None):
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "fields": fields or {}},
    )


NOT_FOUND = "NOT_FOUND"
FORBIDDEN = "FORBIDDEN"
UNAUTHORIZED = "UNAUTHORIZED"
