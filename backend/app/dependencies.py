from collections.abc import Callable

import redis
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import get_db_session
from .errors import api_error
from .models import User
from .security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_db():
    yield from get_db_session()


def get_redis_client(settings: Settings = Depends(get_settings)):
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


def get_current_payload(
    token: str = Depends(oauth2_scheme),
    settings: Settings = Depends(get_settings),
    redis_client=Depends(get_redis_client),
) -> dict:
    try:
        payload = decode_token(token, settings.secret_key, settings.algorithm)
    except ValueError:
        raise api_error(401, "INVALID_TOKEN", "Token 无效")
    if payload.get("type") != "access":
        raise api_error(401, "INVALID_TOKEN_TYPE", "Token 类型无效")
    jti = payload.get("jti")
    if jti and redis_client.exists(f"blacklist:{jti}"):
        raise api_error(401, "TOKEN_REVOKED", "Token 已失效")
    payload["_raw_token"] = token
    return payload


def get_current_user(
    payload: dict = Depends(get_current_payload),
    db: Session = Depends(get_db),
) -> User:
    user_id = payload.get("sub")
    user = db.get(User, int(user_id)) if user_id else None
    if not user or user.status != "active":
        raise api_error(401, "USER_NOT_ACTIVE", "用户不存在或已禁用")
    return user


def require_roles(*roles: str) -> Callable:
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise api_error(403, "FORBIDDEN", "没有权限执行该操作")
        return current_user

    return dependency
