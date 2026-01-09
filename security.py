# security.py

import os
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
JWT_ALGORITHM = "HS256"


class PasswordTooLongError(ValueError):
    """Raised when password exceeds bcrypt's 72-byte limit."""


def _get_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET", "")
    if not secret:
        raise RuntimeError("Missing required env var: JWT_SECRET")
    return secret


def hash_password(password: str) -> str:
    # bcrypt only supports up to 72 BYTES (not characters).
    if len(password.encode("utf-8")) > 72:
        raise PasswordTooLongError(
            "Password is too long. Please use 72 characters or fewer (ASCII), "
            "or a shorter password overall."
        )
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, tenant_id: str, expires_in_hours: int = 24) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "tenant_id": tenant_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=expires_in_hours)).timestamp()),
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=JWT_ALGORITHM)
