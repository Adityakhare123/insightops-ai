from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from apps.api.app.db.models.user import User
from apps.api.app.db.models.workspace import (
    Workspace,
)
from apps.api.app.db.session import SessionLocal
from apps.api.app.main import app


WORKSPACE_SLUG = (
    "insightops-insurance-demo"
)

TEST_PASSWORD = (
    "StrongPassword123!"
)


def get_demo_workspace_id():
    """Return the seeded demo workspace ID."""

    with SessionLocal() as database_session:
        workspace_id = database_session.scalar(
            select(Workspace.id).where(
                Workspace.slug
                == WORKSPACE_SLUG
            )
        )

    assert workspace_id is not None, (
        "The demo workspace is missing. Run the "
        "demo seed script before this test."
    )

    return workspace_id


def cleanup_test_user(
    email: str,
) -> None:
    """Remove the temporary integration-test user."""

    with SessionLocal() as database_session:
        database_session.execute(
            delete(User).where(
                User.email == email
            )
        )

        database_session.commit()


def test_authenticated_sql_agent_api_flow() -> None:
    workspace_id = (
        get_demo_workspace_id()
    )

    unique_identifier = (
        uuid4().hex[:12]
    )

    test_email = (
        "sql-agent-test-"
        f"{unique_identifier}"
        "@example.com"
    )

    cleanup_test_user(
        test_email
    )

    try:
        with TestClient(app) as client:
            unauthorized_response = (
                client.get(
                    "/api/v1/sql-agent/schema"
                )
            )

            assert (
                unauthorized_response.status_code
                == 401
            )

            registration_response = (
                client.post(
                    "/api/v1/auth/register",
                    json={
                        "workspace_slug": (
                            WORKSPACE_SLUG
                        ),
                        "email": test_email,
                        "full_name": (
                            "SQL Agent Test User"
                        ),
                        "password": (
                            TEST_PASSWORD
                        ),
                    },
                )
            )

            assert (
                registration_response.status_code
                == 201
            ), registration_response.text

            login_response = client.post(
                "/api/v1/auth/login",
                json={
                    "workspace_slug": (
                        WORKSPACE_SLUG
                    ),
                    "email": test_email,
                    "password": (
                        TEST_PASSWORD
                    ),
                },
            )

            assert (
                login_response.status_code
                == 200
            ), login_response.text

            access_token = (
                login_response.json()[
                    "access_token"
                ]
            )

            headers = {
                "Authorization": (
                    f"Bearer {access_token}"
                )
            }

            schema_response = client.get(
                "/api/v1/sql-agent/schema",
                headers=headers,
            )

            assert (
                schema_response.status_code
                == 200
            ), schema_response.text

            schema_data = (
                schema_response.json()
            )

            assert (
                schema_data["schema_name"]
                == "public"
            )

            assert (
                schema_data["table_count"]
                == 7
            )

            schema_table_names = {
                table["table_name"]
                for table
                in schema_data["tables"]
            }

            assert (
                "insurance_policies"
                in schema_table_names
            )

            assert (
                "insurance_payments"
                in schema_table_names
            )

            plan_response = client.post(
                "/api/v1/sql-agent/plan",
                headers=headers,
                json={
                    "question": (
                        "Find active policies "
                        "without payments"
                    ),
                    "max_rows": 100,
                },
            )

            assert (
                plan_response.status_code
                == 200
            ), plan_response.text

            plan_data = (
                plan_response.json()
            )

            assert plan_data["intent"] == (
                "active_policies_without_payments"
            )

            assert str(
                workspace_id
            ) in plan_data["generated_sql"]

            assert (
                plan_data["referenced_tables"]
                == [
                    "public.insurance_payments",
                    "public.insurance_policies",
                ]
            )

            assert (
                "LEFT JOIN"
                in plan_data["generated_sql"]
            )

            query_response = client.post(
                "/api/v1/sql-agent/query",
                headers=headers,
                json={
                    "question": (
                        "Find active policies "
                        "without payments"
                    ),
                    "max_rows": 100,
                    "statement_timeout_ms": (
                        5_000
                    ),
                },
            )

            assert (
                query_response.status_code
                == 200
            ), query_response.text

            query_data = (
                query_response.json()
            )

            assert (
                query_data["plan"]["intent"]
                == (
                    "active_policies_without_payments"
                )
            )

            execution = (
                query_data["execution"]
            )

            assert execution["row_count"] == 8

            assert (
                execution["max_rows"]
                == 100
            )

            assert (
                execution["limit_reached"]
                is False
            )

            assert (
                execution[
                    "statement_timeout_ms"
                ]
                == 5_000
            )

            assert (
                execution["execution_time_ms"]
                >= 0
            )

            assert execution["columns"] == [
                "policy_id",
                "policy_number",
                "status",
            ]

            assert len(
                execution["rows"]
            ) == 8

            assert all(
                row["status"].casefold()
                == "active"
                for row
                in execution["rows"]
            )

            unsupported_response = (
                client.post(
                    "/api/v1/sql-agent/plan",
                    headers=headers,
                    json={
                        "question": (
                            "Predict the future "
                            "insurance market"
                        )
                    },
                )
            )

            assert (
                unsupported_response.status_code
                == 422
            )

    finally:
        cleanup_test_user(
            test_email
        )