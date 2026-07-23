"""add reconciliation and review tables

Revision ID: 2c7555a2f07f
Revises: a1e98c5322a5
Create Date: 2026-07-23 07:36:45.573917
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "2c7555a2f07f"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "a1e98c5322a5"

branch_labels: Union[
    str,
    Sequence[str],
    None,
] = None

depends_on: Union[
    str,
    Sequence[str],
    None,
] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "reconciliation_runs",
        sa.Column(
            "workspace_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "processing_run_id",
            sa.UUID(),
            nullable=True,
        ),
        sa.Column(
            "requested_by_user_id",
            sa.UUID(),
            nullable=True,
        ),
        sa.Column(
            "reconciliation_type",
            sa.String(length=40),
            server_default=sa.text(
                "'policy_document'"
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default=sa.text(
                "'queued'"
            ),
            nullable=False,
        ),
        sa.Column(
            "exclude_cancelled",
            sa.Boolean(),
            server_default=sa.text(
                "true"
            ),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "total_checks",
            sa.Integer(),
            server_default=sa.text(
                "0"
            ),
            nullable=False,
        ),
        sa.Column(
            "passed_checks",
            sa.Integer(),
            server_default=sa.text(
                "0"
            ),
            nullable=False,
        ),
        sa.Column(
            "failed_checks",
            sa.Integer(),
            server_default=sa.text(
                "0"
            ),
            nullable=False,
        ),
        sa.Column(
            "review_checks",
            sa.Integer(),
            server_default=sa.text(
                "0"
            ),
            nullable=False,
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "run_parameters",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            server_default=sa.text(
                "'{}'::jsonb"
            ),
            nullable=False,
        ),
        sa.Column(
            "summary_data",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            server_default=sa.text(
                "'{}'::jsonb"
            ),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text(
                "now()"
            ),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text(
                "now()"
            ),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "reconciliation_type IN "
                "('policy_document', "
                "'payment_statement', "
                "'commission_statement')"
            ),
            name=op.f(
                "ck_reconciliation_runs_type_valid"
            ),
        ),
        sa.CheckConstraint(
            (
                "status IN "
                "('queued', 'running', "
                "'completed', 'needs_review', "
                "'failed', 'cancelled')"
            ),
            name=op.f(
                "ck_reconciliation_runs_status_valid"
            ),
        ),
        sa.CheckConstraint(
            "failed_checks >= 0",
            name=op.f(
                "ck_reconciliation_runs_"
                "failed_checks_non_negative"
            ),
        ),
        sa.CheckConstraint(
            "passed_checks >= 0",
            name=op.f(
                "ck_reconciliation_runs_"
                "passed_checks_non_negative"
            ),
        ),
        sa.CheckConstraint(
            "review_checks >= 0",
            name=op.f(
                "ck_reconciliation_runs_"
                "review_checks_non_negative"
            ),
        ),
        sa.CheckConstraint(
            "total_checks >= 0",
            name=op.f(
                "ck_reconciliation_runs_"
                "total_checks_non_negative"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f(
                "fk_reconciliation_runs_"
                "document_id_documents"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["processing_run_id"],
            [
                "document_processing_runs.id"
            ],
            name=op.f(
                "fk_reconciliation_runs_"
                "processing_run_id_"
                "document_processing_runs"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["users.id"],
            name=op.f(
                "fk_reconciliation_runs_"
                "requested_by_user_id_users"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f(
                "fk_reconciliation_runs_"
                "workspace_id_workspaces"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f(
                "pk_reconciliation_runs"
            ),
        ),
    )

    op.create_index(
        "ix_reconciliation_runs_document_created",
        "reconciliation_runs",
        [
            "document_id",
            "created_at",
        ],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_reconciliation_runs_"
            "processing_run_id"
        ),
        "reconciliation_runs",
        [
            "processing_run_id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_reconciliation_runs_requested_by",
        "reconciliation_runs",
        [
            "requested_by_user_id",
            "created_at",
        ],
        unique=False,
    )

    op.create_index(
        "ix_reconciliation_runs_workspace_status",
        "reconciliation_runs",
        [
            "workspace_id",
            "status",
        ],
        unique=False,
    )

    op.create_table(
        "reconciliation_findings",
        sa.Column(
            "workspace_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "reconciliation_run_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "document_page_id",
            sa.UUID(),
            nullable=True,
        ),
        sa.Column(
            "business_policy_id",
            sa.UUID(),
            nullable=True,
        ),
        sa.Column(
            "rule_code",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "finding_type",
            sa.String(length=80),
            nullable=False,
        ),
        sa.Column(
            "field_name",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "severity",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "expected_value",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            nullable=True,
        ),
        sa.Column(
            "actual_value",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            nullable=True,
        ),
        sa.Column(
            "message",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "source_text",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "source_page_number",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "confidence_score",
            sa.Numeric(
                precision=5,
                scale=4,
                asdecimal=False,
            ),
            nullable=True,
        ),
        sa.Column(
            "evidence_data",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            server_default=sa.text(
                "'{}'::jsonb"
            ),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text(
                "now()"
            ),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text(
                "now()"
            ),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "severity IN "
                "('high', 'medium', "
                "'low', 'info')"
            ),
            name=op.f(
                "ck_reconciliation_findings_"
                "severity_valid"
            ),
        ),
        sa.CheckConstraint(
            (
                "status IN "
                "('passed', 'failed', "
                "'needs_review', 'skipped')"
            ),
            name=op.f(
                "ck_reconciliation_findings_"
                "status_valid"
            ),
        ),
        sa.CheckConstraint(
            (
                "confidence_score IS NULL "
                "OR confidence_score "
                "BETWEEN 0 AND 1"
            ),
            name=op.f(
                "ck_reconciliation_findings_"
                "confidence_score_valid"
            ),
        ),
        sa.CheckConstraint(
            (
                "source_page_number IS NULL "
                "OR source_page_number >= 1"
            ),
            name=op.f(
                "ck_reconciliation_findings_"
                "source_page_number_positive"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["business_policy_id"],
            ["insurance_policies.id"],
            name=op.f(
                "fk_reconciliation_findings_"
                "business_policy_id_"
                "insurance_policies"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f(
                "fk_reconciliation_findings_"
                "document_id_documents"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_page_id"],
            ["document_pages.id"],
            name=op.f(
                "fk_reconciliation_findings_"
                "document_page_id_"
                "document_pages"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reconciliation_run_id"],
            ["reconciliation_runs.id"],
            name=op.f(
                "fk_reconciliation_findings_"
                "reconciliation_run_id_"
                "reconciliation_runs"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f(
                "fk_reconciliation_findings_"
                "workspace_id_workspaces"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f(
                "pk_reconciliation_findings"
            ),
        ),
    )

    op.create_index(
        op.f(
            "ix_reconciliation_findings_"
            "document_page_id"
        ),
        "reconciliation_findings",
        [
            "document_page_id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_reconciliation_findings_document_type",
        "reconciliation_findings",
        [
            "document_id",
            "finding_type",
        ],
        unique=False,
    )

    op.create_index(
        "ix_reconciliation_findings_policy",
        "reconciliation_findings",
        [
            "business_policy_id",
            "finding_type",
        ],
        unique=False,
    )

    op.create_index(
        "ix_reconciliation_findings_rule",
        "reconciliation_findings",
        [
            "rule_code",
            "status",
        ],
        unique=False,
    )

    op.create_index(
        "ix_reconciliation_findings_run_severity",
        "reconciliation_findings",
        [
            "reconciliation_run_id",
            "severity",
        ],
        unique=False,
    )

    op.create_index(
        "ix_reconciliation_findings_workspace_status",
        "reconciliation_findings",
        [
            "workspace_id",
            "status",
        ],
        unique=False,
    )

    op.create_table(
        "review_tasks",
        sa.Column(
            "workspace_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "reconciliation_run_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "reconciliation_finding_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            sa.UUID(),
            nullable=True,
        ),
        sa.Column(
            "assigned_to_user_id",
            sa.UUID(),
            nullable=True,
        ),
        sa.Column(
            "resolved_by_user_id",
            sa.UUID(),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default=sa.text(
                "'open'"
            ),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.String(length=20),
            server_default=sa.text(
                "'medium'"
            ),
            nullable=False,
        ),
        sa.Column(
            "title",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "resolution_notes",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "corrected_value",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            nullable=True,
        ),
        sa.Column(
            "due_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "extra_metadata",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            server_default=sa.text(
                "'{}'::jsonb"
            ),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text(
                "now()"
            ),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text(
                "now()"
            ),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "priority IN "
                "('high', 'medium', 'low')"
            ),
            name=op.f(
                "ck_review_tasks_priority_valid"
            ),
        ),
        sa.CheckConstraint(
            (
                "status IN "
                "('open', 'in_progress', "
                "'approved', 'corrected', "
                "'rejected')"
            ),
            name=op.f(
                "ck_review_tasks_status_valid"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to_user_id"],
            ["users.id"],
            name=op.f(
                "fk_review_tasks_"
                "assigned_to_user_id_users"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f(
                "fk_review_tasks_"
                "created_by_user_id_users"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f(
                "fk_review_tasks_"
                "document_id_documents"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reconciliation_finding_id"],
            ["reconciliation_findings.id"],
            name=op.f(
                "fk_review_tasks_"
                "reconciliation_finding_id_"
                "reconciliation_findings"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reconciliation_run_id"],
            ["reconciliation_runs.id"],
            name=op.f(
                "fk_review_tasks_"
                "reconciliation_run_id_"
                "reconciliation_runs"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_user_id"],
            ["users.id"],
            name=op.f(
                "fk_review_tasks_"
                "resolved_by_user_id_users"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f(
                "fk_review_tasks_"
                "workspace_id_workspaces"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f(
                "pk_review_tasks"
            ),
        ),
        sa.UniqueConstraint(
            "reconciliation_finding_id",
            name="finding_review_task_unique",
        ),
    )

    op.create_index(
        "ix_review_tasks_assignee_status",
        "review_tasks",
        [
            "assigned_to_user_id",
            "status",
        ],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_review_tasks_created_by_user_id"
        ),
        "review_tasks",
        [
            "created_by_user_id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_review_tasks_document_status",
        "review_tasks",
        [
            "document_id",
            "status",
        ],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_review_tasks_resolved_by_user_id"
        ),
        "review_tasks",
        [
            "resolved_by_user_id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_review_tasks_run_status",
        "review_tasks",
        [
            "reconciliation_run_id",
            "status",
        ],
        unique=False,
    )

    op.create_index(
        "ix_review_tasks_workspace_status",
        "review_tasks",
        [
            "workspace_id",
            "status",
        ],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(
        "ix_review_tasks_workspace_status",
        table_name="review_tasks",
    )

    op.drop_index(
        "ix_review_tasks_run_status",
        table_name="review_tasks",
    )

    op.drop_index(
        op.f(
            "ix_review_tasks_resolved_by_user_id"
        ),
        table_name="review_tasks",
    )

    op.drop_index(
        "ix_review_tasks_document_status",
        table_name="review_tasks",
    )

    op.drop_index(
        op.f(
            "ix_review_tasks_created_by_user_id"
        ),
        table_name="review_tasks",
    )

    op.drop_index(
        "ix_review_tasks_assignee_status",
        table_name="review_tasks",
    )

    op.drop_table(
        "review_tasks"
    )

    op.drop_index(
        "ix_reconciliation_findings_workspace_status",
        table_name="reconciliation_findings",
    )

    op.drop_index(
        "ix_reconciliation_findings_run_severity",
        table_name="reconciliation_findings",
    )

    op.drop_index(
        "ix_reconciliation_findings_rule",
        table_name="reconciliation_findings",
    )

    op.drop_index(
        "ix_reconciliation_findings_policy",
        table_name="reconciliation_findings",
    )

    op.drop_index(
        "ix_reconciliation_findings_document_type",
        table_name="reconciliation_findings",
    )

    op.drop_index(
        op.f(
            "ix_reconciliation_findings_"
            "document_page_id"
        ),
        table_name="reconciliation_findings",
    )

    op.drop_table(
        "reconciliation_findings"
    )

    op.drop_index(
        "ix_reconciliation_runs_workspace_status",
        table_name="reconciliation_runs",
    )

    op.drop_index(
        "ix_reconciliation_runs_requested_by",
        table_name="reconciliation_runs",
    )

    op.drop_index(
        op.f(
            "ix_reconciliation_runs_"
            "processing_run_id"
        ),
        table_name="reconciliation_runs",
    )

    op.drop_index(
        "ix_reconciliation_runs_document_created",
        table_name="reconciliation_runs",
    )

    op.drop_table(
        "reconciliation_runs"
    )