from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
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


class ReconciliationRun(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    """
    Stores one document-to-database reconciliation attempt.

    A run belongs to one workspace and records the source document,
    processing attempt, execution status, counters, parameters, and
    final reconciliation summary.
    """

    __tablename__ = "reconciliation_runs"

    __table_args__ = (
        CheckConstraint(
            (
                "status IN "
                "('queued', 'running', 'completed', "
                "'needs_review', 'failed', 'cancelled')"
            ),
            name="status_valid",
        ),
        CheckConstraint(
            (
                "reconciliation_type IN "
                "('policy_document', "
                "'payment_statement', "
                "'commission_statement')"
            ),
            name="type_valid",
        ),
        CheckConstraint(
            "total_checks >= 0",
            name="total_checks_non_negative",
        ),
        CheckConstraint(
            "passed_checks >= 0",
            name="passed_checks_non_negative",
        ),
        CheckConstraint(
            "failed_checks >= 0",
            name="failed_checks_non_negative",
        ),
        CheckConstraint(
            "review_checks >= 0",
            name="review_checks_non_negative",
        ),
        Index(
            "ix_reconciliation_runs_workspace_status",
            "workspace_id",
            "status",
        ),
        Index(
            "ix_reconciliation_runs_document_created",
            "document_id",
            "created_at",
        ),
        Index(
            "ix_reconciliation_runs_requested_by",
            "requested_by_user_id",
            "created_at",
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

    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    processing_run_id: Mapped[
        UUID | None
    ] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "document_processing_runs.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    requested_by_user_id: Mapped[
        UUID | None
    ] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    reconciliation_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="policy_document",
        server_default=text(
            "'policy_document'"
        ),
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="queued",
        server_default=text(
            "'queued'"
        ),
    )

    exclude_cancelled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text(
            "true"
        ),
    )

    started_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    total_checks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text(
            "0"
        ),
    )

    passed_checks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text(
            "0"
        ),
    )

    failed_checks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text(
            "0"
        ),
    )

    review_checks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text(
            "0"
        ),
    )

    error_message: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    run_parameters: Mapped[
        dict[str, Any]
    ] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text(
            "'{}'::jsonb"
        ),
    )

    summary_data: Mapped[
        dict[str, Any]
    ] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text(
            "'{}'::jsonb"
        ),
    )