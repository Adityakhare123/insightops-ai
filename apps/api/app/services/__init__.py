from apps.api.app.services.auth import (
    AuthenticationError,
    DuplicateUserError,
    InactiveUserError,
    WorkspaceNotFoundError,
    authenticate_user,
    create_user,
    create_user_token_pair,
    get_user_by_email,
    get_user_by_id,
    get_workspace_by_slug,
    normalize_email,
    normalize_workspace_slug,
)

__all__ = [
    "AuthenticationError",
    "InactiveUserError",
    "DuplicateUserError",
    "WorkspaceNotFoundError",
    "normalize_email",
    "normalize_workspace_slug",
    "get_workspace_by_slug",
    "get_user_by_id",
    "get_user_by_email",
    "create_user",
    "authenticate_user",
    "create_user_token_pair",
]