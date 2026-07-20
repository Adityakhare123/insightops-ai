from __future__ import annotations

from uuid import uuid4

from apps.api.app.core.config import settings
from apps.api.app.core.security import decode_token
from apps.api.app.services.auth import (
    create_user_token_pair,
    normalize_email,
    normalize_workspace_slug,
)


class FakeUser:
    """Minimal user object used for token tests."""

    def __init__(self) -> None:
        self.id = uuid4()
        self.workspace_id = uuid4()
        self.role = "administrator"


def test_normalize_email() -> None:
    assert normalize_email(
        "  ADMIN@EXAMPLE.COM  "
    ) == "admin@example.com"


def test_normalize_workspace_slug() -> None:
    assert normalize_workspace_slug(
        "  InsightOps-Insurance-Demo  "
    ) == "insightops-insurance-demo"


def test_create_user_token_pair() -> None:
    user = FakeUser()

    token_pair = create_user_token_pair(
        user  # type: ignore[arg-type]
    )

    assert token_pair["token_type"] == "bearer"
    assert token_pair["expires_in"] == (
        settings.access_token_expire_minutes * 60
    )
    assert token_pair["access_token"]
    assert token_pair["refresh_token"]


def test_access_token_contains_user_context() -> None:
    user = FakeUser()

    token_pair = create_user_token_pair(
        user  # type: ignore[arg-type]
    )

    payload = decode_token(
        str(token_pair["access_token"]),
        expected_type="access",
    )

    assert payload["sub"] == str(user.id)
    assert payload["workspace_id"] == str(
        user.workspace_id
    )
    assert payload["role"] == "administrator"


def test_refresh_token_contains_user_context() -> None:
    user = FakeUser()

    token_pair = create_user_token_pair(
        user  # type: ignore[arg-type]
    )

    payload = decode_token(
        str(token_pair["refresh_token"]),
        expected_type="refresh",
    )

    assert payload["sub"] == str(user.id)
    assert payload["workspace_id"] == str(
        user.workspace_id
    )
    assert payload["role"] == "administrator"