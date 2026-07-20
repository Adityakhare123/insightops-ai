from __future__ import annotations

import pytest
from pydantic import ValidationError

from apps.api.app.schemas.auth import (
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenPair,
)
from apps.api.app.schemas.user import UserCreate


def test_user_create_normalizes_email_and_name() -> None:
    payload = UserCreate(
        email="ADMIN@EXAMPLE.COM",
        full_name="  Aditya   Khare  ",
        password="StrongPassword123!",
        role="administrator",
    )

    assert payload.email == "admin@example.com"
    assert payload.full_name == "Aditya Khare"
    assert payload.role == "administrator"


def test_user_create_uses_default_business_role() -> None:
    payload = UserCreate(
        email="user@example.com",
        full_name="Business User",
        password="StrongPassword123!",
    )

    assert payload.role == "business_user"


@pytest.mark.parametrize(
    "password",
    [
        "short1!",
        "NOLOWERCASE123!",
        "nouppercase123!",
        "NoNumberPassword!",
        "NoSpecialPassword123",
    ],
)
def test_weak_passwords_are_rejected(
    password: str,
) -> None:
    with pytest.raises(ValidationError):
        UserCreate(
            email="user@example.com",
            full_name="Business User",
            password=password,
        )


def test_unsupported_user_role_is_rejected() -> None:
    with pytest.raises(ValidationError):
        UserCreate(
            email="user@example.com",
            full_name="Business User",
            password="StrongPassword123!",
            role="super_admin",  # type: ignore[arg-type]
        )


def test_register_request_normalizes_fields() -> None:
    payload = RegisterRequest(
        workspace_slug="InsightOps-Insurance-Demo",
        email="USER@EXAMPLE.COM",
        full_name="  Demo   User  ",
        password="StrongPassword123!",
    )

    assert (
        payload.workspace_slug
        == "insightops-insurance-demo"
    )
    assert payload.email == "user@example.com"
    assert payload.full_name == "Demo User"
    assert payload.role == "business_user"


def test_register_request_rejects_privileged_role() -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(
            workspace_slug="insightops-insurance-demo",
            email="user@example.com",
            full_name="Business User",
            password="StrongPassword123!",
            role="administrator",  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "workspace_slug",
    [
        "invalid workspace",
        "invalid_workspace",
        "-invalid-workspace",
        "invalid-workspace-",
        "@invalid",
    ],
)
def test_invalid_workspace_slugs_are_rejected(
    workspace_slug: str,
) -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(
            workspace_slug=workspace_slug,
            email="user@example.com",
            full_name="Business User",
            password="StrongPassword123!",
        )


def test_login_request_normalizes_workspace_and_email() -> None:
    payload = LoginRequest(
        workspace_slug="InsightOps-Insurance-Demo",
        email="USER@EXAMPLE.COM",
        password="StrongPassword123!",
    )

    assert (
        payload.workspace_slug
        == "insightops-insurance-demo"
    )
    assert payload.email == "user@example.com"


def test_empty_login_password_is_rejected() -> None:
    with pytest.raises(ValidationError):
        LoginRequest(
            workspace_slug="insightops-insurance-demo",
            email="user@example.com",
            password="",
        )


def test_login_requires_workspace_slug() -> None:
    with pytest.raises(ValidationError):
        LoginRequest(
            email="user@example.com",
            password="StrongPassword123!",
        )


def test_empty_refresh_token_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RefreshTokenRequest(
            refresh_token="",
        )


def test_token_pair_defaults_to_bearer() -> None:
    payload = TokenPair(
        access_token="access-token",
        refresh_token="refresh-token",
        expires_in=3600,
    )

    assert payload.token_type == "bearer"
    assert payload.expires_in == 3600


def test_token_pair_rejects_invalid_expiration() -> None:
    with pytest.raises(ValidationError):
        TokenPair(
            access_token="access-token",
            refresh_token="refresh-token",
            expires_in=0,
        )