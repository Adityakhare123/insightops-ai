from __future__ import annotations

import pytest

from apps.api.app.services.sql_agent_guardrails import (
    EmptySQLQueryError,
    InvalidSQLAgentLimitError,
    MissingSQLDataSourceError,
    MultipleSQLStatementsError,
    NonReadOnlySQLQueryError,
    SQLQueryTooLongError,
    UnauthorizedSQLTableError,
    UnsafeSQLFunctionError,
    validate_sql_agent_query,
)


def test_valid_select_is_accepted() -> None:
    result = validate_sql_agent_query(
        """
        SELECT
            policy_number,
            status,
            effective_date
        FROM insurance_policies
        WHERE status = 'active'
        ORDER BY effective_date DESC
        """,
        max_rows=100,
    )

    assert result.max_rows == 100

    assert result.referenced_tables == (
        "public.insurance_policies",
    )

    assert (
        "SELECT *"
        in result.executable_sql
    )

    assert (
        "LIMIT 100"
        in result.executable_sql
    )


def test_valid_join_is_accepted() -> None:
    result = validate_sql_agent_query(
        """
        SELECT
            p.policy_number,
            c.first_name,
            c.last_name,
            ca.name AS carrier_name
        FROM insurance_policies AS p
        JOIN insurance_customers AS c
            ON c.id = p.customer_id
        JOIN insurance_carriers AS ca
            ON ca.id = p.carrier_id
        """,
        max_rows=50,
    )

    assert result.referenced_tables == (
        "public.insurance_carriers",
        "public.insurance_customers",
        "public.insurance_policies",
    )


def test_valid_cte_is_accepted() -> None:
    result = validate_sql_agent_query(
        """
        WITH active_policies AS (
            SELECT
                id,
                policy_number
            FROM insurance_policies
            WHERE status = 'active'
        )
        SELECT
            policy_number
        FROM active_policies
        """,
        max_rows=25,
    )

    assert result.referenced_tables == (
        "public.insurance_policies",
    )

    assert (
        "active_policies"
        in result.normalized_sql
    )


def test_empty_query_is_rejected() -> None:
    with pytest.raises(
        EmptySQLQueryError,
        match="cannot be empty",
    ):
        validate_sql_agent_query(
            "   "
        )


def test_query_length_is_enforced() -> None:
    with pytest.raises(
        SQLQueryTooLongError,
        match="maximum length",
    ):
        validate_sql_agent_query(
            (
                "SELECT * "
                "FROM insurance_policies"
            ),
            max_sql_length=10,
        )


def test_multiple_statements_are_rejected() -> None:
    with pytest.raises(
        MultipleSQLStatementsError,
        match="Exactly one",
    ):
        validate_sql_agent_query(
            """
            SELECT *
            FROM insurance_policies;

            SELECT *
            FROM insurance_customers;
            """
        )


@pytest.mark.parametrize(
    "sql_query",
    [
        (
            "UPDATE insurance_policies "
            "SET status = 'cancelled'"
        ),
        (
            "DELETE FROM insurance_policies"
        ),
        (
            "INSERT INTO insurance_policies "
            "(policy_number) VALUES ('X')"
        ),
        (
            "DROP TABLE insurance_policies"
        ),
        (
            "ALTER TABLE insurance_policies "
            "ADD COLUMN unsafe_column TEXT"
        ),
    ],
)
def test_write_operations_are_rejected(
    sql_query: str,
) -> None:
    with pytest.raises(
        NonReadOnlySQLQueryError,
    ):
        validate_sql_agent_query(
            sql_query
        )


def test_data_modifying_cte_is_rejected() -> None:
    with pytest.raises(
        NonReadOnlySQLQueryError,
    ):
        validate_sql_agent_query(
            """
            WITH changed AS (
                UPDATE insurance_policies
                SET status = 'cancelled'
                RETURNING id
            )
            SELECT id
            FROM changed
            """
        )


def test_unknown_table_is_rejected() -> None:
    with pytest.raises(
        UnauthorizedSQLTableError,
        match="unauthorized table",
    ):
        validate_sql_agent_query(
            "SELECT * FROM users"
        )


def test_non_public_schema_is_rejected() -> None:
    with pytest.raises(
        UnauthorizedSQLTableError,
        match="unauthorized schema",
    ):
        validate_sql_agent_query(
            """
            SELECT *
            FROM private.insurance_policies
            """
        )


def test_system_catalog_is_rejected() -> None:
    with pytest.raises(
        UnauthorizedSQLTableError,
    ):
        validate_sql_agent_query(
            """
            SELECT *
            FROM pg_catalog.pg_tables
            """
        )


def test_query_without_business_table_is_rejected() -> None:
    with pytest.raises(
        MissingSQLDataSourceError,
        match="approved insurance table",
    ):
        validate_sql_agent_query(
            "SELECT 1"
        )


def test_unsafe_function_is_rejected() -> None:
    with pytest.raises(
        UnsafeSQLFunctionError,
        match="pg_sleep",
    ):
        validate_sql_agent_query(
            """
            SELECT
                pg_sleep(1),
                policy_number
            FROM insurance_policies
            """
        )


def test_select_into_is_rejected() -> None:
    with pytest.raises(
        NonReadOnlySQLQueryError,
    ):
        validate_sql_agent_query(
            """
            SELECT *
            INTO temporary_policy_copy
            FROM insurance_policies
            """
        )


def test_invalid_max_rows_is_rejected() -> None:
    with pytest.raises(
        InvalidSQLAgentLimitError,
        match="greater than",
    ):
        validate_sql_agent_query(
            "SELECT * FROM insurance_policies",
            max_rows=0,
        )