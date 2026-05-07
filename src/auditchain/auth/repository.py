"""Repository layer for user management using asynchronous database access.

This module encapsulates all database operations for the UserORM model.
Each function requires an active AsyncSession to be passed as an argument.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auditchain.auth.models import UserORM
from auditchain.auth.schemas import UserCreate


async def get_user_by_email(session: AsyncSession, email: str) -> UserORM | None:
    """Retrieve a user by their email address.
    
    Returns the UserORM instance if found, otherwise None.
    """
    stmt = select(UserORM).where(UserORM.email == email)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_all_users(session: AsyncSession) -> list[UserORM]:
    """Retrieve all users in the database, ordered by creation date."""
    stmt = select(UserORM).order_by(UserORM.created_at)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_user(session: AsyncSession, data: UserCreate, hashed_password: str) -> UserORM:
    """Create a new user record and persist it.
    
    The password must be hashed before calling this function.
    """
    user = UserORM(
        email=data.email,
        hashed_password=hashed_password,
        full_name=data.full_name,
        role=data.role,
    )
    session.add(user)
    await session.flush()
    return user


async def deactivate_user(session: AsyncSession, user_id: UUID) -> bool:
    """Mark a user as inactive (is_active = False).
    
    Returns True if a record was updated, False otherwise.
    """
    stmt = update(UserORM).where(UserORM.id == user_id).values(is_active=False)
    result = await session.execute(stmt)
    return result.rowcount > 0


async def delete_user(session: AsyncSession, user_id: UUID) -> bool:
    """Permanently delete a user from the database.
    
    Returns True if a record was deleted, False otherwise.
    """
    stmt = delete(UserORM).where(UserORM.id == user_id)
    result = await session.execute(stmt)
    return result.rowcount > 0
