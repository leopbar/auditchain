"""Security services for password hashing and JWT management."""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from auditchain.auth.config import get_auth_settings

# Setup password context
pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")
auth_settings = get_auth_settings()


def hash_password(plain: str) -> str:
    """Return a hashed version of the plain text password."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Check if the plain text password matches the hash."""
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict[str, Any]) -> str:
    """Generate a JWT access token with a short expiration."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=auth_settings.access_token_expire_minutes
    )
    to_encode.update({"exp": expire})
    return jwt.encode(
        to_encode,
        auth_settings.secret_key.get_secret_value(),
        algorithm=auth_settings.algorithm,
    )


def create_refresh_token(data: dict[str, Any]) -> str:
    """Generate a JWT refresh token with a long expiration."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=auth_settings.refresh_token_expire_days)
    to_encode.update({"exp": expire})
    return jwt.encode(
        to_encode,
        auth_settings.secret_key.get_secret_value(),
        algorithm=auth_settings.algorithm,
    )


def decode_token(token: str) -> dict[str, Any] | None:
    """Decode a JWT token and return the payload. 
    
    Returns None if the token is invalid or expired.
    """
    try:
        payload = jwt.decode(
            token,
            auth_settings.secret_key.get_secret_value(),
            algorithms=[auth_settings.algorithm],
        )
        return payload
    except JWTError:
        return None
