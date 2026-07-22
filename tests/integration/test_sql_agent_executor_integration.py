from __future__ import annotations

from apps.api.app.db.session import SessionLocal
from apps.api.app.services.sql_agent_executor import (
    validate_and_execute_sql,
)


def test_sql_agent_executes_read_only_policy_summary() -> None:
    with SessionLocal() as database_session:
        result = validate_and_execute_sql(
            database_session,
            sql_query="""
                SELECT
                    status,
                    COUNT(*) AS policy_count
                FROM insurance_policies
                GROUP BY status
                ORDER BY status
            """,
            max_rows=50,
            statement_timeout_ms=5_000,
        )

    assert result.row_count > 0

    assert result.columns == (
        "status",
        "policy_count",
    )

    assert result.referenced_tables == (
        "public.insurance_policies",
    )

    assert result.execution_time_ms >= 0
    assert result.statement_timeout_ms == 5_000

    assert all(
        isinstance(
            row["policy_count"],
            int,
        )
        for row in result.rows
    )


def test_sql_agent_enforces_result_limit() -> None:
    with SessionLocal() as database_session:
        result = validate_and_execute_sql(
            database_session,
            sql_query="""
                SELECT
                    policy_number,
                    status
                FROM insurance_policies
                ORDER BY policy_number
            """,
            max_rows=3,
            statement_timeout_ms=5_000,
        )

    assert result.row_count == 3
    assert result.max_rows == 3
    assert result.limit_reached is True

    assert result.columns == (
        "policy_number",
        "status",
    )


def test_sql_agent_serializes_business_values() -> None:
    with SessionLocal() as database_session:
        result = validate_and_execute_sql(
            database_session,
            sql_query="""
                SELECT
                    id,
                    policy_number,
                    effective_date,
                    premium
                FROM insurance_policies
                ORDER BY policy_number
            """,
            max_rows=1,
            statement_timeout_ms=5_000,
        )

    assert result.row_count == 1

    assert result.columns == (
        "id",
        "policy_number",
        "effective_date",
        "premium",
    )

    row = result.rows[0]

    assert isinstance(
        row["id"],
        str,
    )

    assert isinstance(
        row["policy_number"],
        str,
    )

    assert isinstance(
        row["effective_date"],
        str,
    )

    assert isinstance(
        row["premium"],
        str,
    )
