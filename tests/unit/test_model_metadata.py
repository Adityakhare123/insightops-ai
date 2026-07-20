from sqlalchemy import UniqueConstraint

from apps.api.app.db import models  # noqa: F401
from apps.api.app.db.base import Base


EXPECTED_TABLES = {
    "workspaces",
    "insurance_carriers",
    "insurance_plans",
    "insurance_agents",
    "insurance_customers",
    "insurance_policies",
    "insurance_payments",
    "insurance_commissions",
}


def test_expected_tables_are_registered() -> None:
    registered_tables = set(Base.metadata.tables.keys())

    assert EXPECTED_TABLES == registered_tables


def test_policy_number_is_not_unique() -> None:
    policy_table = Base.metadata.tables["insurance_policies"]
    policy_number = policy_table.columns["policy_number"]

    assert policy_number.unique is not True


def test_policy_source_record_constraint_exists() -> None:
    policy_table = Base.metadata.tables["insurance_policies"]

    unique_constraints = [
        constraint
        for constraint in policy_table.constraints
        if isinstance(constraint, UniqueConstraint)
    ]

    constraint_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in unique_constraints
    }

    assert (
        "workspace_id",
        "source_system",
        "source_record_id",
    ) in constraint_columns


def test_all_business_tables_have_workspace_id() -> None:
    workspace_scoped_tables = EXPECTED_TABLES - {"workspaces"}

    for table_name in workspace_scoped_tables:
        table = Base.metadata.tables[table_name]

        assert "workspace_id" in table.columns


def test_all_tables_have_audit_columns() -> None:
    for table_name in EXPECTED_TABLES:
        table = Base.metadata.tables[table_name]

        assert "id" in table.columns
        assert "created_at" in table.columns
        assert "updated_at" in table.columns