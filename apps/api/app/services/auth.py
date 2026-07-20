from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.app.core.config import settings
from apps.api.app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from apps.api.app.db.models.user import User
from apps.api.app.db.models.workspace import Workspace
from apps.api.app.schemas.user import UserCreate


class AuthenticationError(ValueError):
    """Raised when authentication credentials are invalid."""


class InactiveUserError(AuthenticationError):
    """Raised when an inactive user attempts to authenticate."""


class DuplicateUserError(ValueError):
    """Raised when an email already exists in a workspace."""


class WorkspaceNotFoundError(ValueError):
    """Raised when the requested workspace does not exist."""


def normalize_email(email: str) -> str:
    """Normalize an email address for storage and lookup."""

    return email.strip().lower()


def normalize_workspace_slug(workspace_slug: str) -> str:
    """Normalize a workspace slug for lookup."""

    return workspace_slug.strip().lower()


def get_workspace_by_slug(
    database_session: Session,
    workspace_slug: str,
) -> Workspace | None:
    """Return a workspace matching the supplied slug."""

    normalized_slug = normalize_workspace_slug(
        workspace_slug
    )

    statement = select(Workspace).where(
        Workspace.slug == normalized_slug
    )

    return database_session.scalar(statement)


def get_user_by_id(
    database_session: Session,
    user_id: UUID,
) -> User | None:
    """Return a user by primary key."""

    statement = select(User).where(
        User.id == user_id
    )

    return database_session.scalar(statement)


def get_user_by_email(
    database_session: Session,
    workspace_id: UUID,
    email: str,
) -> User | None:
    """Return a user by workspace and email."""

    normalized_email = normalize_email(email)

    statement = select(User).where(
        User.workspace_id == workspace_id,
        User.email == normalized_email,
    )

    return database_session.scalar(statement)


def create_user(
    database_session: Session,
    workspace: Workspace,
    user_data: UserCreate,
) -> User:
    """Create a user inside a workspace."""

    existing_user = get_user_by_email(
        database_session=database_session,
        workspace_id=workspace.id,
        email=str(user_data.email),
    )

    if existing_user is not None:
        raise DuplicateUserError(
            "A user with this email already exists "
            "in the workspace."
        )

    user = User(
        workspace_id=workspace.id,
        email=normalize_email(
            str(user_data.email)
        ),
        full_name=user_data.full_name,
        password_hash=hash_password(
            user_data.password
        ),
        role=user_data.role,
        is_active=True,
    )

    database_session.add(user)

    try:
        database_session.commit()
    except IntegrityError as error:
        database_session.rollback()

        raise DuplicateUserError(
            "A user with this email already exists "
            "in the workspace."
        ) from error

    database_session.refresh(user)

    return user


def authenticate_user(
    database_session: Session,
    workspace_slug: str,
    email: str,
    password: str,
) -> User:
    """
    Authenticate a user using workspace, email, and password.

    A generic credentials error is returned so the API does not reveal
    whether a workspace or email address exists.
    """

    workspace = get_workspace_by_slug(
        database_session=database_session,
        workspace_slug=workspace_slug,
    )

    if workspace is None:
        raise AuthenticationError(
            "Invalid workspace, email, or password."
        )

    user = get_user_by_email(
        database_session=database_session,
        workspace_id=workspace.id,
        email=email,
    )

    if user is None:
        raise AuthenticationError(
            "Invalid workspace, email, or password."
        )

    if not verify_password(
        plain_password=password,
        password_hash=user.password_hash,
    ):
        raise AuthenticationError(
            "Invalid workspace, email, or password."
        )

    if not user.is_active:
        raise InactiveUserError(
            "This user account is inactive."
        )

    return user


def create_user_token_pair(
    user: User,
) -> dict[str, Any]:
    """Create access and refresh tokens for a user."""

    additional_claims = {
        "workspace_id": str(user.workspace_id),
        "role": user.role,
    }

    access_token = create_access_token(
        subject=user.id,
        additional_claims=additional_claims,
    )

    refresh_token = create_refresh_token(
        subject=user.id,
        additional_claims=additional_claims,
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": (
            settings.access_token_expire_minutes
            * 60
        ),
    }