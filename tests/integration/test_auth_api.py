from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from apps.api.app.db.models.user import User
from apps.api.app.db.models.workspace import Workspace
from apps.api.app.db.session import SessionLocal
from apps.api.app.main import app


WORKSPACE_SLUG = "insightops-insurance-demo"
TEST_PASSWORD = "StrongPassword123!"


def _delete_test_user(email: str) -> None:
    """Remove a test user without deleting the demo workspace."""

    with SessionLocal() as database_session:
        workspace_id = database_session.scalar(
            select(Workspace.id).where(
                Workspace.slug == WORKSPACE_SLUG
            )
        )

        if workspace_id is None:
            return

        database_session.execute(
            delete(User).where(
                User.workspace_id == workspace_id,
                User.email == email,
            )
        )
        database_session.commit()


def _assert_demo_workspace_exists() -> None:
    """Ensure Day 2 demo data has been seeded."""

    with SessionLocal() as database_session:
        workspace_id = database_session.scalar(
            select(Workspace.id).where(
                Workspace.slug == WORKSPACE_SLUG
            )
        )

    assert workspace_id is not None, (
        "Demo workspace is missing. Run "
        "'python -m scripts.seed_demo_data' first."
    )


def test_complete_authentication_flow() -> None:
    _assert_demo_workspace_exists()

    test_email = (
        f"auth-test-{uuid4().hex[:12]}@example.com"
    )

    registration_payload = {
        "workspace_slug": WORKSPACE_SLUG,
        "email": test_email.upper(),
        "full_name": "Authentication Test User",
        "password": TEST_PASSWORD,
    }

    _delete_test_user(test_email)

    try:
        with TestClient(app) as client:
            # Register
            register_response = client.post(
                "/api/v1/auth/register",
                json=registration_payload,
            )

            assert register_response.status_code == 201

            registered_user = register_response.json()

            assert registered_user["email"] == test_email
            assert (
                registered_user["full_name"]
                == "Authentication Test User"
            )
            assert registered_user["role"] == "business_user"
            assert registered_user["is_active"] is True
            assert "password" not in registered_user
            assert "password_hash" not in registered_user

            # Duplicate registration
            duplicate_response = client.post(
                "/api/v1/auth/register",
                json=registration_payload,
            )

            assert duplicate_response.status_code == 409
            assert (
                "already exists"
                in duplicate_response.json()["detail"]
            )

            # Incorrect password
            invalid_login_response = client.post(
                "/api/v1/auth/login",
                json={
                    "workspace_slug": WORKSPACE_SLUG,
                    "email": test_email,
                    "password": "WrongPassword123!",
                },
            )

            assert invalid_login_response.status_code == 401

            # Successful login
            login_response = client.post(
                "/api/v1/auth/login",
                json={
                    "workspace_slug": WORKSPACE_SLUG,
                    "email": test_email,
                    "password": TEST_PASSWORD,
                },
            )

            assert login_response.status_code == 200

            login_data = login_response.json()

            assert login_data["token_type"] == "bearer"
            assert login_data["access_token"]
            assert login_data["refresh_token"]
            assert login_data["expires_in"] > 0
            assert login_data["user"]["email"] == test_email

            access_token = login_data["access_token"]
            refresh_token = login_data["refresh_token"]

            # Protected endpoint without token
            unauthorized_me_response = client.get(
                "/api/v1/auth/me"
            )

            assert unauthorized_me_response.status_code == 401

            # Protected endpoint with access token
            me_response = client.get(
                "/api/v1/auth/me",
                headers={
                    "Authorization": (
                        f"Bearer {access_token}"
                    )
                },
            )

            assert me_response.status_code == 200

            current_user_data = me_response.json()

            assert (
                current_user_data["user"]["email"]
                == test_email
            )
            assert (
                current_user_data["workspace_slug"]
                == WORKSPACE_SLUG
            )
            assert (
                current_user_data["workspace_name"]
                == "InsightOps Insurance Demo"
            )

            # Refresh token
            refresh_response = client.post(
                "/api/v1/auth/refresh",
                json={
                    "refresh_token": refresh_token,
                },
            )

            assert refresh_response.status_code == 200

            refreshed_tokens = refresh_response.json()

            assert refreshed_tokens["token_type"] == "bearer"
            assert refreshed_tokens["access_token"]
            assert refreshed_tokens["refresh_token"]
            assert refreshed_tokens["expires_in"] > 0

            # Access token cannot be used as a refresh token
            invalid_refresh_response = client.post(
                "/api/v1/auth/refresh",
                json={
                    "refresh_token": access_token,
                },
            )

            assert invalid_refresh_response.status_code == 401

    finally:
        _delete_test_user(test_email)