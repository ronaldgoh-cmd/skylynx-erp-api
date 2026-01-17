import os
import secrets
import string
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
JWT_ALGORITHM = "HS256"


class PasswordTooLongError(ValueError):
    pass


def _get_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET", "")
    if not secret:
        raise RuntimeError("Missing required env var: JWT_SECRET")
    return secret


def hash_password(password: str) -> str:
    # bcrypt supports max 72 BYTES (not characters)
    if len(password.encode("utf-8")) > 72:
        raise PasswordTooLongError("Password too long (max 72 characters).")
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, tenant_id: str, expires_in: timedelta | None = None) -> str:
    now = datetime.now(timezone.utc)
    if expires_in is None:
        expires_in = timedelta(hours=12)
    payload = {
        "sub": subject,
        "tenant_id": tenant_id,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_in).timestamp()),
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=JWT_ALGORITHM)


def generate_temporary_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))
