from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.dependencies import get_current_user, get_db, get_redis_client
from app.errors import api_error
from app.models import User
from app.schemas import LoginRequest, LogoutRequest, RefreshRequest, TokenResponse, UserRead
from app.security import decode_token
from app.services.auth_service import (
    LoginRateLimited,
    authenticate_user,
    check_login_rate_limit,
    clear_login_failures,
    issue_token_pair,
    record_login_failure,
    refresh_token_pair,
    resolve_client_ip,
    revoke_tokens,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Cookie 配置
REFRESH_COOKIE_KEY = "dai_refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def _validate_origin(request: Request, settings: Settings) -> None:
    """校验请求 Origin 在允许列表中。无 Origin 头（同源请求）放行。"""
    origin = request.headers.get("Origin", "")
    if not origin:
        return  # 同源请求没有 Origin 头，放行
    allowed = settings.cors_origin_list
    if origin not in allowed:
        raise api_error(403, "ORIGIN_NOT_ALLOWED", f"来源 {origin} 不被允许")


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


def _logout_access_payload(request: Request, settings: Settings) -> dict | None:
    """尽力解析 access token；退出本身不能依赖一个仍在有效期内的 access token。"""
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    try:
        payload = decode_token(
            token,
            settings.secret_key,
            settings.algorithm,
            verify_exp=False,
        )
    except ValueError:
        return None
    return payload if payload.get("type") == "access" else None


@router.post("/login")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    redis_client=Depends(get_redis_client),
    settings: Settings = Depends(get_settings),
):
    # ── 双维限流（TASK-005） ──
    # 用户名 15 分钟 10 次失败 / IP 15 分钟 30 次尝试，超限 429 + Retry-After。
    # Redis 不可用 → 503 失败关闭（认证事实依赖 Redis，绝不绕过限流放行）。
    client_ip = resolve_client_ip(request, settings)
    try:
        check_login_rate_limit(redis_client, settings, payload.username, client_ip)
    except RedisConnectionError:
        raise api_error(503, "AUTH_SERVICE_UNAVAILABLE", "认证服务暂不可用，请稍后重试")
    except LoginRateLimited as exc:
        raise api_error(
            429,
            "LOGIN_RATE_LIMITED",
            "尝试次数过多，请稍后再试",
            fields={"retry_after_seconds": exc.retry_after_seconds},
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )

    try:
        user = authenticate_user(db, payload.username, payload.password)
    except Exception:
        # 登录失败统一文案；失败计数（Redis 故障时静默跳过——失败原因优先于计数）
        try:
            record_login_failure(redis_client, settings, payload.username, client_ip)
        except RedisConnectionError:
            pass
        raise

    try:
        clear_login_failures(redis_client, payload.username)
    except RedisConnectionError:
        pass  # 计数清理失败不影响本次登录
    try:
        tokens = issue_token_pair(user, redis_client, settings)
    except RedisConnectionError:
        raise api_error(503, "AUTH_SERVICE_UNAVAILABLE", "认证服务暂不可用，请稍后重试")
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
    # Origin 校验：防止跨域 refresh 攻击
    _validate_origin(request, settings)

    # 优先从 Cookie 读取，兼容 JSON body
    refresh_token_value = dai_refresh_token or (payload.refresh_token if payload else None)
    if not refresh_token_value:
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
    request: Request,
    response: Response,
    payload: LogoutRequest | None = None,
    dai_refresh_token: str | None = Cookie(None, alias=REFRESH_COOKIE_KEY),
    redis_client=Depends(get_redis_client),
    settings: Settings = Depends(get_settings),
):
    # Origin 校验：防止跨域 logout 攻击
    _validate_origin(request, settings)
    access_payload = _logout_access_payload(request, settings)
    clear_refresh_cookie = revoke_tokens(
        access_payload,
        dai_refresh_token or (payload.refresh_token if payload else None),
        redis_client,
        settings,
    )
    if clear_refresh_cookie:
        _delete_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return None


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)):
    return current_user
