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
    """统一密码校验（TASK-011 / F-15）——所有密码入口共享：

    - 至少 8 个字符
    - UTF-8 编码不超过 bcrypt 的 72 字节上限
    - 不得全为空白字符
    - 不得等同于规范化用户名（strip + casefold 比较）
    不增加字符组合规则或 HIBP 外部查询。
    """
    if len(password) < 8:
        raise ValueError("密码至少需要 8 个字符")
    if len(password.encode("utf-8")) > 72:
        raise ValueError("密码过长（UTF-8 编码后不能超过 72 字节）")
    if not password.strip():
        raise ValueError("密码不能全为空白字符")
    if username is not None and password.strip().casefold() == (username or "").strip().casefold():
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
        # TASK-012：会话撤销版本——认证/刷新时与 users.session_version 比对
        "sv": session_version,
        "exp": expires_at,
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
