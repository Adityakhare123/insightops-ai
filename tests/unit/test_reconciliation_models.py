from __future__ import annotations

from apps.api.app.db.base import Base
from apps.api.app.db.models.reconciliation_finding import (
    ReconciliationFinding,
)
from apps.api.app.db.models.reconciliation_run import (
    ReconciliationRun,
)
from apps.api.app.db.models.review_task import (
    ReviewTask,
)


def test_reconciliation_models_use_expected_tables() -> None:
    assert (
        ReconciliationRun.__tablename__
        == "reconciliation_runs"
    )

    assert (
        ReconciliationFinding.__tablename__
        == "reconciliation_findings"
    )

    assert (
        ReviewTask.__tablename__
        == "review_tasks"
    )


def test_reconciliation_tables_are_registered() -> None:
    assert "reconciliation_runs" in (
        Base.metadata.tables
    )

    assert "reconciliation_findings" in (
        Base.metadata.tables
    )

    assert "review_tasks" in (
        Base.metadata.tables
    )


def test_reconciliation_run_has_workspace_scope() -> None:
    table = Base.metadata.tables[
        "reconciliation_runs"
    ]

    assert "workspace_id" in table.c
    assert "document_id" in table.c
    assert "requested_by_user_id" in table.c

    workspace_foreign_key = next(
        iter(
            table.c.workspace_id.foreign_keys
        )
    )

    assert (
        workspace_foreign_key.target_fullname
        == "workspaces.id"
    )

    assert (
        workspace_foreign_key.ondelete
        == "CASCADE"
    )


def test_reconciliation_finding_preserves_evidence() -> None:
    table = Base.metadata.tables[
        "reconciliation_findings"
    ]

    expected_columns = {
        "rule_code",
        "finding_type",
        "field_name",
        "status",
        "severity",
        "expected_value",
        "actual_value",
        "message",
        "source_text",
        "source_page_number",
        "confidence_score",
        "evidence_data",
    }

    assert expected_columns.issubset(
        table.c.keys()
    )


def test_reconciliation_finding_can_reference_policy() -> None:
    table = Base.metadata.tables[
        "reconciliation_findings"
    ]

    policy_foreign_key = next(
        iter(
            table.c.business_policy_id
            .foreign_keys
        )
    )

    assert (
        policy_foreign_key.target_fullname
        == "insurance_policies.id"
    )

    assert (
        policy_foreign_key.ondelete
        == "SET NULL"
    )


def test_review_task_has_resolution_fields() -> None:
    table = Base.metadata.tables[
        "review_tasks"
    ]

    expected_columns = {
        "assigned_to_user_id",
        "resolved_by_user_id",
        "status",
        "priority",
        "resolution_notes",
        "corrected_value",
        "resolved_at",
    }

    assert expected_columns.issubset(
        table.c.keys()
    )


def test_review_task_is_unique_per_finding() -> None:
    table = Base.metadata.tables[
        "review_tasks"
    ]

    unique_column_sets = {
        tuple(
            constraint.columns.keys()
        )
        for constraint in table.constraints
        if constraint.__class__.__name__
        == "UniqueConstraint"
    }

    assert (
        "reconciliation_finding_id",
    ) in unique_column_sets