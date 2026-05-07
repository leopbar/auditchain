import asyncio
from datetime import datetime

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from auditchain.api.limiter import limiter
from auditchain.auth import repository, schemas, service
from auditchain.auth.dependencies import get_current_user
from auditchain.data.database import get_async_session
from auditchain.core.config import get_settings

settings = get_settings()

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=schemas.UserOut)
@limiter.limit("5/15minutes")
async def login(
    request: Request,
    login_data: schemas.LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_async_session),
):
    """Authenticate user and set secure JWT cookies."""
    # Prevent timing attacks
    await asyncio.sleep(1)

    user = await repository.get_user_by_email(session, login_data.email)

    if not user or not service.verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated",
        )

    # Update last login time
    user.last_login_at = datetime.utcnow()

    # Generate tokens
    payload = {"sub": user.email, "role": user.role}
    access_token = service.create_access_token(payload)
    refresh_token = service.create_refresh_token(payload)

    # Set HTTP-only cookies for maximum security
    is_prod = settings.environment == "production"
    
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=is_prod,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        secure=is_prod,
    )

    return user


@router.post("/logout")
async def logout(response: Response):
    """Clear authentication cookies."""
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"message": "logged out"}


@router.post("/refresh")
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(None),
    session: AsyncSession = Depends(get_async_session),
):
    """Exchange a valid refresh token for a new access token."""
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token missing")

    payload = service.decode_token(refresh_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token"
        )

    email = payload.get("sub")
    user = await repository.get_user_by_email(session, email)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    new_access_token = service.create_access_token({"sub": user.email, "role": user.role})

    is_prod = settings.environment == "production"
    
    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        samesite="lax",
        secure=is_prod,
    )

    return {"message": "token refreshed"}


@router.get("/me", response_model=schemas.UserOut)
async def get_me(current_user: schemas.UserOut = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return current_user
