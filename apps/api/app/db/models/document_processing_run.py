from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
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


class DocumentProcessingRun(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    """
    Tracks every document extraction attempt.

    A document may be processed more than once. Each attempt
    receives its own processing run for auditability.
    """

    __tablename__ = "document_processing_runs"

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "attempt_number",
            name="document_attempt_unique",
        ),
        CheckConstraint(
            (
                "status IN "
                "('queued', 'running', 'completed', 'failed')"
            ),
            name="status_valid",
        ),
        CheckConstraint(
            "attempt_number >= 1",
            name="attempt_number_positive",
        ),
        CheckConstraint(
            "total_pages IS NULL OR total_pages >= 0",
            name="total_pages_non_negative",
        ),
        CheckConstraint(
            "extracted_pages >= 0",
            name="extracted_pages_non_negative",
        ),
        CheckConstraint(
            (
                "total_pages IS NULL "
                "OR extracted_pages <= total_pages"
            ),
            name="extracted_pages_within_total",
        ),
        Index(
            "ix_document_processing_runs_workspace_status",
            "workspace_id",
            "status",
        ),
        Index(
            "ix_document_processing_runs_document_created",
            "document_id",
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
        index=True,
    )

    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
        ),
        nullable=False,
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
        index=True,
    )

    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="queued",
        server_default=text("'queued'"),
    )

    processor_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="insightops-document-extractor",
        server_default=text(
            "'insightops-document-extractor'"
        ),
    )

    processor_version: Mapped[
        str | None
    ] = mapped_column(
        String(50),
        nullable=True,
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

    total_pages: Mapped[
        int | None
    ] = mapped_column(
        Integer,
        nullable=True,
    )

    extracted_pages: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    error_message: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    extra_metadata: Mapped[
        dict[str, Any]
    ] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )