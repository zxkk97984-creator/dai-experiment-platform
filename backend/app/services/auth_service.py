from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import api_error
from app.models import User
from app.schemas import TokenResponse
from app.security import create_token, decode_token, token_ttl_seconds, verify_password


def authenticate_user(db: Session, username: str, password: str) -> User:
    user = db.scalar(select(User).where(User.username == username))
    if not user or user.status != "active" or not verify_password(password, user.password_hash):
        raise api_error(401, "INVALID_CREDENTIALS", "用户名或密码错误")
    return user


def issue_token_pair(user: User, redis_client, settings: Settings) -> TokenResponse:
    access_token = create_token(
        subject=user.id,
        role=user.role,
        token_type="access",
        secret_key=settings.secret_key,
        algorithm=settings.algorithm,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    refresh_token = create_token(
        subject=user.id,
        role=user.role,
        token_type="refresh",
        secret_key=settings.secret_key,
        algorithm=settings.algorithm,
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )
    refresh_payload = decode_token(refresh_token, settings.secret_key, settings.algorithm)
    redis_client.setex(
        f"refresh:{refresh_payload['jti']}",
        settings.refresh_token_expire_days * 24 * 60 * 60,
        str(user.id),
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
        user=user,
    )


def refresh_token_pair(db: Session, refresh_token: str, redis_client, settings: Settings) -> TokenResponse:
    try:
        payload = decode_token(refresh_token, settings.secret_key, settings.algorithm)
    except ValueError:
        raise api_error(401, "INVALID_REFRESH_TOKEN", "刷新 Token 无效")
    if payload.get("type") != "refresh":
        raise api_error(401, "INVALID_TOKEN_TYPE", "Token 类型无效")
    refresh_key = f"refresh:{payload['jti']}"
    user_id = redis_client.get(refresh_key)
    if not user_id:
        raise api_error(401, "REFRESH_TOKEN_REVOKED", "刷新 Token 已失效")
    redis_client.delete(refresh_key)
    user = db.get(User, int(user_id))
    if not user or user.status != "active":
        raise api_error(401, "USER_NOT_ACTIVE", "用户不存在或已禁用")
    return issue_token_pair(user, redis_client, settings)


def revoke_tokens(access_payload: dict, refresh_token: str | None, redis_client, settings: Settings) -> None:
    jti = access_payload.get("jti")
    if jti:
        redis_client.setex(f"blacklist:{jti}", max(token_ttl_seconds(access_payload), 1), "1")
    if refresh_token:
        try:
            refresh_payload = decode_token(refresh_token, settings.secret_key, settings.algorithm)
        except ValueError:
            return
        redis_client.delete(f"refresh:{refresh_payload.get('jti')}")
