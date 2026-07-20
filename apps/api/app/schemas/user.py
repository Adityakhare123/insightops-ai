from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


UserRole = Literal[
    "business_user",
    "reviewer",
    "administrator",
    "organization_owner",
]


class UserBase(BaseModel):
    """Fields shared by user request and response models."""

    email: EmailStr
    full_name: str = Field(
        min_length=2,
        max_length=150,
    )

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        """Store email addresses in a normalized lowercase form."""

        return str(value).strip().lower()

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        """Trim and normalize whitespace in a user's name."""

        normalized_value = " ".join(value.split())

        if len(normalized_value) < 2:
            raise ValueError(
                "Full name must contain at least 2 characters."
            )

        return normalized_value


class UserCreate(UserBase):
    """Payload used when creating a user account."""

    password: str = Field(
        min_length=8,
        max_length=128,
    )

    role: UserRole = "business_user"

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        """Enforce the MVP password-strength requirements."""

        if not any(character.islower() for character in value):
            raise ValueError(
                "Password must contain at least one lowercase letter."
            )

        if not any(character.isupper() for character in value):
            raise ValueError(
                "Password must contain at least one uppercase letter."
            )

        if not any(character.isdigit() for character in value):
            raise ValueError(
                "Password must contain at least one number."
            )

        if not any(
            not character.isalnum()
            for character in value
        ):
            raise ValueError(
                "Password must contain at least one special character."
            )

        return value


class UserRead(UserBase):
    """Safe user information returned by the API."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    workspace_id: UUID
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CurrentUserResponse(BaseModel):
    """Current authenticated user and workspace context."""

    user: UserRead
    workspace_name: str
    workspace_slug: str