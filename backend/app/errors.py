from typing import Any

from fastapi import HTTPException


def api_error(
    status_code: int,
    code: str,
    message: str,
    fields: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    *,
    field_errors: list[dict[str, Any]] | None = None,
    retryable: bool | None = None,
):
    detail: dict[str, Any] = {"code": code, "message": message, "fields": fields or {}}
    # Keep the legacy ``fields`` member for existing clients while allowing
    # V2 endpoints to expose the structured contract without changing old
    # error payloads unexpectedly.
    if field_errors is not None:
        detail["field_errors"] = field_errors
    if retryable is not None:
        detail["retryable"] = retryable
    return HTTPException(
        status_code=status_code,
        detail=detail,
        headers=headers,
    )


NOT_FOUND = "NOT_FOUND"
FORBIDDEN = "FORBIDDEN"
UNAUTHORIZED = "UNAUTHORIZED"
