from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.db.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class ReconciliationFinding(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    """
    Stores one validation result produced during reconciliation.

    Findings preserve expected and actual values, source evidence,
    severity, rule identity, confidence, and the associated business
    policy when one could be matched.
    """

    __tablename__ = "reconciliation_findings"

    __table_args__ = (
        CheckConstraint(
            (
                "status IN "
                "('passed', 'failed', "
                "'needs_review', 'skipped')"
            ),
            name="status_valid",
        ),
        CheckConstraint(
            (
                "severity IN "
                "('high', 'medium', 'low', 'info')"
            ),
            name="severity_valid",
        ),
        CheckConstraint(
            (
                "confidence_score IS NULL "
                "OR confidence_score BETWEEN 0 AND 1"
            ),
            name="confidence_score_valid",
        ),
        CheckConstraint(
            (
                "source_page_number IS NULL "
                "OR source_page_number >= 1"
            ),
            name="source_page_number_positive",
        ),
        Index(
            "ix_reconciliation_findings_workspace_status",
            "workspace_id",
            "status",
        ),
        Index(
            "ix_reconciliation_findings_run_severity",
            "reconciliation_run_id",
            "severity",
        ),
        Index(
            "ix_reconciliation_findings_document_type",
            "document_id",
            "finding_type",
        ),
        Index(
            "ix_reconciliation_findings_policy",
            "business_policy_id",
            "finding_type",
        ),
        Index(
            "ix_reconciliation_findings_rule",
            "rule_code",
            "status",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "workspaces.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    reconciliation_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "reconciliation_runs.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    document_page_id: Mapped[
        UUID | None
    ] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "document_pages.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    business_policy_id: Mapped[
        UUID | None
    ] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "insurance_policies.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    rule_code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    finding_type: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    field_name: Mapped[
        str | None
    ] = mapped_column(
        String(100),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    expected_value: Mapped[
        Any | None
    ] = mapped_column(
        JSONB,
        nullable=True,
    )

    actual_value: Mapped[
        Any | None
    ] = mapped_column(
        JSONB,
        nullable=True,
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    source_text: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    source_page_number: Mapped[
        int | None
    ] = mapped_column(
        Integer,
        nullable=True,
    )

    confidence_score: Mapped[
        float | None
    ] = mapped_column(
        Numeric(
            precision=5,
            scale=4,
            asdecimal=False,
        ),
        nullable=True,
    )

    evidence_data: Mapped[
        dict[str, Any]
    ] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text(
            "'{}'::jsonb"
        ),
    )