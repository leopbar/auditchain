"""Pydantic schemas for authentication requests and responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class LoginRequest(BaseModel):
    """Schema for login requests."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Schema for authentication tokens."""
    access_token: str
    token_type: str
    role: str


class UserOut(BaseModel):
    """Schema for user data sent to clients."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str | None = None
    role: str
    is_active: bool
    created_at: datetime


class UserCreate(BaseModel):
    """Schema for creating a new user."""
    email: EmailStr
    password: str
    full_name: str | None = None
    role: str = "viewer"
