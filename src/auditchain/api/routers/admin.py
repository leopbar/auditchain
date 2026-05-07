"""Admin-only router for user management and system control."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from auditchain.auth import repository, schemas, service
from auditchain.auth.dependencies import require_admin
from auditchain.data.database import get_async_session

router = APIRouter(
    prefix="/api/admin", 
    tags=["admin"], 
    dependencies=[Depends(require_admin)]
)


@router.get("/users", response_model=list[schemas.UserOut])
async def list_users(session: AsyncSession = Depends(get_async_session)):
    """List all registered users in the system."""
    return await repository.get_all_users(session)


@router.post("/users", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
async def create_new_user(
    user_data: schemas.UserCreate,
    session: AsyncSession = Depends(get_async_session),
):
    """Create a new user with hashed password."""
    hashed = service.hash_password(user_data.password)
    return await repository.create_user(session, user_data, hashed)


@router.delete("/users/{user_id}/deactivate")
async def deactivate(user_id: UUID, session: AsyncSession = Depends(get_async_session)):
    """Deactivate a user account without deleting it."""
    success = await repository.deactivate_user(session, user_id)
    if not success:
        return {"message": "User not found or already inactive"}
    return {"message": "user deactivated"}


@router.delete("/users/{user_id}")
async def delete(user_id: UUID, session: AsyncSession = Depends(get_async_session)):
    """Permanently delete a user from the system."""
    success = await repository.delete_user(session, user_id)
    if not success:
        return {"message": "User not found"}
    return {"message": "user deleted"}
