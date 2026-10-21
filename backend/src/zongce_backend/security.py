"""密码哈希（Argon2id）与访问令牌（JWT）。"""

import secrets
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from .config import Settings
from .errors import UnauthorizedError

_hasher = PasswordHasher()
# 初始密码字符集：去掉易混淆的 0/O/o、1/l/I
_ALPHABET = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
# 用户不存在时也做一次哈希校验，避免通过响应时间判断账号是否存在
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def generate_password(length: int) -> str:
    """随机初始密码：至少含一个字母和一个数字。"""
    while True:
        password = "".join(secrets.choice(_ALPHABET) for _ in range(length))
        if any(c.isdigit() for c in password) and any(c.isalpha() for c in password):
            return password


def create_access_token(user_id: int, token_version: int, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "ver": token_version,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> tuple[int, int]:
    """返回 (user_id, token_version)；令牌无效或过期时抛出 UnauthorizedError。"""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp", "ver"]},
        )
        return int(payload["sub"]), int(payload["ver"])
    except (jwt.PyJWTError, ValueError, TypeError) as exc:
        raise UnauthorizedError("登录已失效，请重新登录") from exc
