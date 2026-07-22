from __future__ import annotations

import pytest

from apps.api.app.services.sql_agent_schema import (
    InvalidSQLAgentIdentifierError,
    MissingSQLAgentColumnError,
    MissingSQLAgentTableError,
    build_schema_catalog_from_mapping,
    validate_schema_identifier,
)


def test_builds_schema_catalog() -> None:
    catalog = build_schema_catalog_from_mapping(
        {
            "insurance_policies": (
                "id",
                "workspace_id",
                "policy_number",
                "status",
            ),
        }
    )

    table = catalog.require_table(
        "insurance_policies"
    )

    assert table.qualified_name == (
        "public.insurance_policies"
    )

    assert table.require_column(
        "policy_number"
    ) == "policy_number"


def test_resolves_column_candidates() -> None:
    catalog = build_schema_catalog_from_mapping(
        {
            "insurance_payments": (
                "id",
                "payment_amount",
            ),
        }
    )

    table = catalog.require_table(
        "insurance_payments"
    )

    assert table.require_one_of(
        (
            "amount",
            "payment_amount",
        ),
        semantic_name="payment amount",
    ) == "payment_amount"


def test_missing_table_is_rejected() -> None:
    catalog = build_schema_catalog_from_mapping(
        {}
    )

    with pytest.raises(
        MissingSQLAgentTableError,
    ):
        catalog.require_table(
            "insurance_policies"
        )


def test_missing_column_is_rejected() -> None:
    catalog = build_schema_catalog_from_mapping(
        {
            "insurance_policies": (
                "id",
            ),
        }
    )

    with pytest.raises(
        MissingSQLAgentColumnError,
    ):
        catalog.require_table(
            "insurance_policies"
        ).require_column(
            "policy_number"
        )


@pytest.mark.parametrize(
    "identifier",
    (
        "insurance_policies; DROP TABLE users",
        "public.insurance_policies",
        "insurance-policies",
        "",
    ),
)
def test_invalid_identifier_is_rejected(
    identifier: str,
) -> None:
    with pytest.raises(
        InvalidSQLAgentIdentifierError,
    ):
        validate_schema_identifier(
            identifier
        )