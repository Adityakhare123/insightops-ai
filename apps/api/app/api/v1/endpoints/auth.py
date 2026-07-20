from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from apps.api.app.api.deps import (
    CurrentUser,
    DatabaseSession,
)
from apps.api.app.core.security import (
    TokenDecodeError,
    decode_token,
)
from apps.api.app.db.models.workspace import Workspace
from apps.api.app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    RegisterRequest,
)
from apps.api.app.schemas.user import (
    CurrentUserResponse,
    UserCreate,
    UserRead,
)
from apps.api.app.services.auth import (
    AuthenticationError,
    DuplicateUserError,
    InactiveUserError,
    authenticate_user,
    create_user,
    create_user_token_pair,
    get_user_by_id,
    get_workspace_by_slug,
)


router = APIRouter()


def _unauthorized_exception(
    detail: str = "Could not validate credentials.",
) -> HTTPException:
    """Create a standard unauthorized API response."""

    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    request: RegisterRequest,
    database_session: DatabaseSession,
) -> UserRead:
    """Register a business user in an existing workspace."""

    workspace = get_workspace_by_slug(
        database_session=database_session,
        workspace_slug=request.workspace_slug,
    )

    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace was not found.",
        )

    user_data = UserCreate(
        email=request.email,
        full_name=request.full_name,
        password=request.password,
        role="business_user",
    )

    try:
        user = create_user(
            database_session=database_session,
            workspace=workspace,
            user_data=user_data,
        )
    except DuplicateUserError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return UserRead.model_validate(user)


@router.post(
    "/login",
    response_model=LoginResponse,
)
def login_user(
    request: LoginRequest,
    database_session: DatabaseSession,
) -> LoginResponse:
    """Authenticate a user and return a token pair."""

    try:
        user = authenticate_user(
            database_session=database_session,
            workspace_slug=request.workspace_slug,
            email=str(request.email),
            password=request.password,
        )
    except InactiveUserError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error
    except AuthenticationError as error:
        raise _unauthorized_exception(
            str(error)
        ) from error

    token_pair = create_user_token_pair(user)

    return LoginResponse(
        user=UserRead.model_validate(user),
        **token_pair,
    )


@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
)
def refresh_tokens(
    request: RefreshTokenRequest,
    database_session: DatabaseSession,
) -> RefreshTokenResponse:
    """Exchange a valid refresh token for a new token pair."""

    try:
        token_payload = decode_token(
            token=request.refresh_token,
            expected_type="refresh",
        )

        user_id = UUID(token_payload["sub"])
    except (
        TokenDecodeError,
        TypeError,
        ValueError,
    ) as error:
        raise _unauthorized_exception(
            "Refresh token is invalid or expired."
        ) from error

    user = get_user_by_id(
        database_session=database_session,
        user_id=user_id,
    )

    if user is None:
        raise _unauthorized_exception(
            "The authenticated user no longer exists."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This user account is inactive.",
        )

    if token_payload.get("workspace_id") != str(
        user.workspace_id
    ):
        raise _unauthorized_exception(
            "Refresh token workspace context is invalid."
        )

    token_pair = create_user_token_pair(user)

    return RefreshTokenResponse(
        **token_pair,
    )


@router.get(
    "/me",
    response_model=CurrentUserResponse,
)
def read_current_user(
    current_user: CurrentUser,
    database_session: DatabaseSession,
) -> CurrentUserResponse:
    """Return the authenticated user and workspace context."""

    workspace = database_session.get(
        Workspace,
        current_user.workspace_id,
    )

    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The user's workspace was not found.",
        )

    return CurrentUserResponse(
        user=UserRead.model_validate(current_user),
        workspace_name=workspace.name,
        workspace_slug=workspace.slug,
    )