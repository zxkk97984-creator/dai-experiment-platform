from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.dependencies import get_current_payload, get_current_user, get_db, get_redis_client
from app.models import User
from app.schemas import LoginRequest, LogoutRequest, RefreshRequest, TokenResponse, UserRead
from app.services.auth_service import authenticate_user, issue_token_pair, refresh_token_pair, revoke_tokens

router = APIRouter(prefix="/auth", tags=["auth"])

# Cookie 配置
REFRESH_COOKIE_KEY = "dai_refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def _set_refresh_cookie(response: Response, refresh_token: str, settings: Settings, max_age_days: int = 7):
    """设置 HttpOnly refresh token Cookie"""
    secure = settings.environment == "production"
    response.set_cookie(
        key=REFRESH_COOKIE_KEY,
        value=refresh_token,
        max_age=max_age_days * 86400,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=secure,
        samesite="lax",
    )


def _delete_refresh_cookie(response: Response):
    """删除 refresh token Cookie"""
    response.delete_cookie(
        key=REFRESH_COOKIE_KEY,
        path=REFRESH_COOKIE_PATH,
    )


@router.post("/login")
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    redis_client=Depends(get_redis_client),
    settings: Settings = Depends(get_settings),
):
    user = authenticate_user(db, payload.username, payload.password)
    tokens = issue_token_pair(user, redis_client, settings)
    # Refresh token 仅存入 HttpOnly Cookie，不在 JSON body 返回
    _set_refresh_cookie(response, tokens.refresh_token, settings)
    return {
        "access_token": tokens.access_token,
        "token_type": "bearer",
        "expires_in": tokens.expires_in,
        "user": tokens.user,
    }


@router.post("/refresh")
def refresh(
    request: Request,
    response: Response,
    payload: RefreshRequest | None = None,
    dai_refresh_token: str | None = Cookie(None, alias=REFRESH_COOKIE_KEY),
    db: Session = Depends(get_db),
    redis_client=Depends(get_redis_client),
    settings: Settings = Depends(get_settings),
):
    # 优先从 Cookie 读取，兼容 JSON body
    refresh_token_value = dai_refresh_token or (payload.refresh_token if payload else None)
    if not refresh_token_value:
        from app.errors import api_error
        raise api_error(401, "NO_REFRESH_TOKEN", "缺少刷新令牌")

    tokens = refresh_token_pair(db, refresh_token_value, redis_client, settings)
    _set_refresh_cookie(response, tokens.refresh_token, settings)
    return {
        "access_token": tokens.access_token,
        "token_type": "bearer",
        "expires_in": tokens.expires_in,
        "user": tokens.user,
    }


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    payload: LogoutRequest | None = None,
    dai_refresh_token: str | None = Cookie(None, alias=REFRESH_COOKIE_KEY),
    access_payload: dict = Depends(get_current_payload),
    redis_client=Depends(get_redis_client),
    settings: Settings = Depends(get_settings),
):
    revoke_tokens(access_payload, dai_refresh_token or (payload.refresh_token if payload else None), redis_client, settings)
    _delete_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return None


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)):
    return current_user
