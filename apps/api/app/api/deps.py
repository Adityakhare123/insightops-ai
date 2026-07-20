from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy.orm import Session

from apps.api.app.core.security import (
    TokenDecodeError,
    decode_token,
)
from apps.api.app.db.models.user import User
from apps.api.app.db.session import get_db
from apps.api.app.services.auth import get_user_by_id


bearer_scheme = HTTPBearer(
    auto_error=False,
)


def _credentials_exception(
    detail: str = "Could not validate credentials.",
) -> HTTPException:
    """Create a standard unauthorized response."""

    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    database_session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> User:
    """Return the user represented by an access token."""

    if credentials is None:
        raise _credentials_exception(
            "Authentication credentials were not provided."
        )

    if credentials.scheme.lower() != "bearer":
        raise _credentials_exception(
            "Unsupported authentication scheme."
        )

    try:
        token_payload = decode_token(
            token=credentials.credentials,
            expected_type="access",
        )

        user_id = UUID(token_payload["sub"])
    except (
        TokenDecodeError,
        TypeError,
        ValueError,
    ) as error:
        raise _credentials_exception() from error

    user = get_user_by_id(
        database_session=database_session,
        user_id=user_id,
    )

    if user is None:
        raise _credentials_exception(
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
        raise _credentials_exception(
            "Token workspace context is invalid."
        )

    if token_payload.get("role") != user.role:
        raise _credentials_exception(
            "Token role context is no longer valid."
        )

    return user


CurrentUser = Annotated[
    User,
    Depends(get_current_user),
]

DatabaseSession = Annotated[
    Session,
    Depends(get_db),
]