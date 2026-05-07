"""FastAPI dependencies for authentication and authorization."""

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from auditchain.auth.repository import get_user_by_email
from auditchain.auth.schemas import UserOut
from auditchain.auth.service import decode_token
from auditchain.data.database import get_async_session


async def get_current_user(
    access_token: str | None = Cookie(None),
    session: AsyncSession = Depends(get_async_session),
) -> UserOut:
    """Dependency to retrieve the currently logged-in user from a cookie.
    
    Raises 401 Unauthorized if the token is missing, invalid, or the user 
    doesn't exist.
    """
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    payload = decode_token(access_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    email = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload invalid",
        )

    user = await get_user_by_email(session, email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated",
        )

    # Convert ORM to Pydantic
    return UserOut.model_validate(user)


async def require_admin(
    current_user: UserOut = Depends(get_current_user),
) -> UserOut:
    """Dependency to restrict access to admin users only.
    
    Raises 403 Forbidden if the user is not an admin.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user
