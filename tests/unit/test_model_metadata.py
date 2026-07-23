from __future__ import annotations

from sqlalchemy import UniqueConstraint

from apps.api.app.db import models  # noqa: F401
from apps.api.app.db.base import Base
from apps.api.app.db.models.document_chunk import (
    DOCUMENT_CHUNK_EMBEDDING_DIMENSIONS,
)


EXPECTED_TABLES = {
    "workspaces",
    "users",
    "insurance_agents",
    "insurance_carriers",
    "insurance_commissions",
    "insurance_customers",
    "insurance_payments",
    "insurance_plans",
    "insurance_policies",
    "documents",
    "document_processing_runs",
    "document_pages",
    "document_chunks",
    "reconciliation_runs",
    "reconciliation_findings",
    "review_tasks",
}


def test_expected_tables_are_registered() -> None:
    registered_tables = set(
        Base.metadata.tables.keys()
    )

    assert EXPECTED_TABLES == registered_tables


def test_policy_number_is_not_unique() -> None:
    policy_table = Base.metadata.tables[
        "insurance_policies"
    ]

    policy_number = policy_table.columns[
        "policy_number"
    ]

    assert policy_number.unique is not True


def test_policy_source_record_constraint_exists() -> None:
    policy_table = Base.metadata.tables[
        "insurance_policies"
    ]

    unique_constraints = [
        constraint
        for constraint
        in policy_table.constraints
        if isinstance(
            constraint,
            UniqueConstraint,
        )
    ]

    constraint_columns = {
        tuple(
            column.name
            for column
            in constraint.columns
        )
        for constraint
        in unique_constraints
    }

    assert (
        "workspace_id",
        "source_system",
        "source_record_id",
    ) in constraint_columns


def test_all_business_tables_have_workspace_id() -> None:
    workspace_scoped_tables = (
        EXPECTED_TABLES
        - {"workspaces"}
    )

    for table_name in workspace_scoped_tables:
        table = Base.metadata.tables[
            table_name
        ]

        assert "workspace_id" in table.columns, (
            f"Table '{table_name}' "
            "is missing workspace_id."
        )


def test_all_tables_have_audit_columns() -> None:
    for table_name in EXPECTED_TABLES:
        table = Base.metadata.tables[
            table_name
        ]

        assert "id" in table.columns, (
            f"Table '{table_name}' is missing id."
        )

        assert "created_at" in table.columns, (
            f"Table '{table_name}' "
            "is missing created_at."
        )

        assert "updated_at" in table.columns, (
            f"Table '{table_name}' "
            "is missing updated_at."
        )


def test_document_chunk_vector_dimension() -> None:
    chunk_table = Base.metadata.tables[
        "document_chunks"
    ]

    embedding_column = chunk_table.columns[
        "embedding"
    ]

    assert getattr(
        embedding_column.type,
        "dim",
        None,
    ) == DOCUMENT_CHUNK_EMBEDDING_DIMENSIONS

    assert (
        DOCUMENT_CHUNK_EMBEDDING_DIMENSIONS
        == 384
    )


def test_document_chunk_hnsw_index_exists() -> None:
    chunk_table = Base.metadata.tables[
        "document_chunks"
    ]

    index_names = {
        index.name
        for index in chunk_table.indexes
    }

    assert (
        "ix_document_chunks_embedding_hnsw"
        in index_names
    )