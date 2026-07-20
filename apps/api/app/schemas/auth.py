from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    field_validator,
)

from apps.api.app.schemas.user import (
    UserCreate,
    UserRead,
)


TokenType = Literal["bearer"]


class RegisterRequest(UserCreate):
    """Payload used to register a business user."""

    workspace_slug: str = Field(
        min_length=2,
        max_length=100,
        pattern=r"^[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)*$",
    )

    role: Literal["business_user"] = "business_user"

    @field_validator("workspace_slug")
    @classmethod
    def normalize_workspace_slug(
        cls,
        value: str,
    ) -> str:
        """Normalize a workspace slug before lookup."""

        return value.strip().lower()


class LoginRequest(BaseModel):
    """Workspace, email, and password login payload."""

    workspace_slug: str = Field(
        min_length=2,
        max_length=100,
        pattern=r"^[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)*$",
    )

    email: EmailStr

    password: str = Field(
        min_length=1,
        max_length=128,
    )

    @field_validator("workspace_slug")
    @classmethod
    def normalize_workspace_slug(
        cls,
        value: str,
    ) -> str:
        """Normalize a workspace slug before authentication."""

        return value.strip().lower()

    @field_validator("email")
    @classmethod
    def normalize_email(
        cls,
        value: EmailStr,
    ) -> str:
        """Normalize an email address before authentication."""

        return str(value).strip().lower()


class RefreshTokenRequest(BaseModel):
    """Payload used to exchange a refresh token."""

    refresh_token: str = Field(
        min_length=1,
    )


class TokenPair(BaseModel):
    """Access and refresh tokens returned after authentication."""

    access_token: str
    refresh_token: str
    token_type: TokenType = "bearer"

    expires_in: int = Field(
        ge=1,
        description="Access-token lifetime in seconds.",
    )


class LoginResponse(TokenPair):
    """Authentication tokens and authenticated user details."""

    user: UserRead


class RefreshTokenResponse(TokenPair):
    """Replacement token pair returned after refresh."""


class MessageResponse(BaseModel):
    """Generic API message response."""

    message: str