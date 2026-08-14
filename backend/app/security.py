from datetime import UTC, datetime, timedelta
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext


password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_context.verify(password, password_hash)


def validate_password_rules(password: str, username: str | None = None) -> None:
    """校验所有密码入口共享的 TASK-011 边界。"""
    if len(password) < 8:
        raise ValueError("密码至少需要 8 个字符")
    if len(password.encode("utf-8")) > 72:
        raise ValueError("密码 UTF-8 字节数超过上限 72")
    if not password.strip():
        raise ValueError("密码不能为全空白")
    if username is not None and password.strip().casefold() == username.strip().casefold():
        raise ValueError("密码不能与用户名相同")


def create_token(
    *,
    subject: int,
    role: str,
    token_type: str,
    secret_key: str,
    algorithm: str,
    expires_delta: timedelta,
    session_version: int,
) -> str:
    expires_at = datetime.now(UTC) + expires_delta
    payload = {
        "sub": str(subject),
        "role": role,
        "type": token_type,
        "jti": str(uuid4()),
        "exp": expires_at,
        "sv": session_version,
    }
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def decode_token(
    token: str,
    secret_key: str,
    algorithm: str,
    *,
    verify_exp: bool = True,
) -> dict:
    try:
        return jwt.decode(
            token,
            secret_key,
            algorithms=[algorithm],
            options={"verify_exp": verify_exp},
        )
    except JWTError as exc:
        raise ValueError("Invalid token") from exc


def token_ttl_seconds(payload: dict) -> int:
    exp = payload.get("exp")
    if not exp:
        return 0
    return max(int(exp - datetime.now(UTC).timestamp()), 0)
