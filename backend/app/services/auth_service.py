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


# ── 登录限流（TASK-005 / F-14） ────────────────────────────────
# 双维限流：用户名维度防单账户爆破（含 bcrypt CPU 放大），IP 维度防横向轮换用户名。
# 计数器存 Redis；窗口随失败滚动（仅在首次失败时设置 TTL）。
# Redis 不可用时登录必须失败关闭（503），绝不跳过限流放行。


class LoginRateLimited(Exception):
    """触发限流——携带剩余冷却秒数（Retry-After）。"""

    def __init__(self, retry_after_seconds: int):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"login rate limited, retry after {retry_after_seconds}s")


def _login_user_key(username: str) -> str:
    return f"login:fail:user:{username.strip().casefold()}"


def _login_ip_key(ip: str) -> str:
    return f"login:fail:ip:{ip}"


def resolve_client_ip(request, settings: Settings) -> str:
    """确定客户端 IP：仅当直连 peer 在可信代理列表内时才采用 X-Forwarded-For。

    伪造的 X-Forwarded-For 在直连客户端不可信时被忽略，防止攻击者通过
    自定义头绕过 IP 维度限流。
    """
    peer = (request.client.host if request.client else "") or ""
    if settings.trusted_proxy_list and peer in settings.trusted_proxy_list:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            first = forwarded.split(",")[0].strip()
            # 兼容 [IPv6]:port 与 ip:port 形态
            if first.startswith("["):
                first = first.split("]")[0].lstrip("[")
            elif first.count(":") == 1:
                first = first.rsplit(":", 1)[0]
            if first:
                return first
    return peer or "unknown"


def check_login_rate_limit(redis_client, settings: Settings, username: str, ip: str) -> None:
    """任一维度超限即抛 LoginRateLimited（含 Retry-After 秒数）。

    Redis 不可用抛 ConnectionError，由调用方转为 503 失败关闭。
    """
    user_key = _login_user_key(username)
    ip_key = _login_ip_key(ip)
    user_count = int(redis_client.get(user_key) or 0)
    ip_count = int(redis_client.get(ip_key) or 0)
    if user_count < settings.login_max_failures_per_username and ip_count < settings.login_max_attempts_per_ip:
        return
    ttls = [redis_client.ttl(key) for key in (user_key, ip_key) if redis_client.exists(key)]
    retry_after = max((t for t in ttls if t is not None and t > 0), default=settings.login_rate_limit_window_seconds)
    raise LoginRateLimited(int(retry_after))


def record_login_failure(redis_client, settings: Settings, username: str, ip: str) -> None:
    """登录失败后计数（窗口随首次失败起算；再次失败不刷新窗口）。"""
    window = settings.login_rate_limit_window_seconds
    for key in (_login_user_key(username), _login_ip_key(ip)):
        count = redis_client.incr(key)
        if count == 1:
            redis_client.expire(key, window)


def clear_login_failures(redis_client, username: str) -> None:
    """登录成功后清除账户维度的失败计数（IP 维度保留，防换用户名绕过）。"""
    redis_client.delete(_login_user_key(username))


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
    # 原子化消费 Refresh Token：GETDEL 同时读取并删除，防止并发重复使用
    user_id = redis_client.getdel(refresh_key)
    if not user_id:
        raise api_error(401, "REFRESH_TOKEN_REVOKED", "刷新 Token 已失效")
    # user_id 是 bytes，需要解码
    if isinstance(user_id, bytes):
        user_id = user_id.decode()
    user = db.get(User, int(user_id))
    if not user or user.status != "active":
        raise api_error(401, "USER_NOT_ACTIVE", "用户不存在或已禁用")
    return issue_token_pair(user, redis_client, settings)


def revoke_tokens(
    access_payload: dict | None,
    refresh_token: str | None,
    redis_client,
    settings: Settings,
) -> bool:
    """撤销同一会话的令牌；返回是否应清除请求携带的 refresh cookie。"""
    jti = access_payload.get("jti") if access_payload else None
    if jti:
        redis_client.setex(f"blacklist:{jti}", max(token_ttl_seconds(access_payload), 1), "1")
    if refresh_token:
        try:
            refresh_payload = decode_token(refresh_token, settings.secret_key, settings.algorithm)
        except ValueError:
            return True
        access_subject = access_payload.get("sub") if access_payload else None
        refresh_subject = refresh_payload.get("sub")
        if access_subject and refresh_subject and access_subject != refresh_subject:
            return False
        redis_client.delete(f"refresh:{refresh_payload.get('jti')}")
    return True
