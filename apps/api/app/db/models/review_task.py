from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
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


class ReviewTask(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    """
    Stores a human-review task created from a reconciliation finding.

    Review history remains available after approval, correction, or
    rejection so that automated decisions remain auditable.
    """

    __tablename__ = "review_tasks"

    __table_args__ = (
        UniqueConstraint(
            "reconciliation_finding_id",
            name="finding_review_task_unique",
        ),
        CheckConstraint(
            (
                "status IN "
                "('open', 'in_progress', "
                "'approved', 'corrected', 'rejected')"
            ),
            name="status_valid",
        ),
        CheckConstraint(
            (
                "priority IN "
                "('high', 'medium', 'low')"
            ),
            name="priority_valid",
        ),
        Index(
            "ix_review_tasks_workspace_status",
            "workspace_id",
            "status",
        ),
        Index(
            "ix_review_tasks_assignee_status",
            "assigned_to_user_id",
            "status",
        ),
        Index(
            "ix_review_tasks_run_status",
            "reconciliation_run_id",
            "status",
        ),
        Index(
            "ix_review_tasks_document_status",
            "document_id",
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

    reconciliation_finding_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "reconciliation_findings.id",
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

    created_by_user_id: Mapped[
        UUID | None
    ] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    assigned_to_user_id: Mapped[
        UUID | None
    ] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    resolved_by_user_id: Mapped[
        UUID | None
    ] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="open",
        server_default=text(
            "'open'"
        ),
    )

    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="medium",
        server_default=text(
            "'medium'"
        ),
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    resolution_notes: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    corrected_value: Mapped[
        Any | None
    ] = mapped_column(
        JSONB,
        nullable=True,
    )

    due_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    resolved_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    extra_metadata: Mapped[
        dict[str, Any]
    ] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text(
            "'{}'::jsonb"
        ),
    )