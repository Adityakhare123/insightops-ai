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


class DocumentPage(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    """
    Stores text extracted from one page of a document.

    Each processing attempt can generate its own set of page
    records without overwriting earlier extraction results.
    """

    __tablename__ = "document_pages"

    __table_args__ = (
        UniqueConstraint(
            "processing_run_id",
            "page_number",
            name="processing_run_page_unique",
        ),
        CheckConstraint(
            "page_number >= 1",
            name="page_number_positive",
        ),
        CheckConstraint(
            (
                "status IN "
                "('pending', 'processing', "
                "'completed', 'failed')"
            ),
            name="status_valid",
        ),
        CheckConstraint(
            (
                "confidence_score IS NULL "
                "OR confidence_score BETWEEN 0 AND 1"
            ),
            name="confidence_score_valid",
        ),
        CheckConstraint(
            "character_count >= 0",
            name="character_count_non_negative",
        ),
        CheckConstraint(
            "word_count >= 0",
            name="word_count_non_negative",
        ),
        Index(
            "ix_document_pages_workspace_status",
            "workspace_id",
            "status",
        ),
        Index(
            "ix_document_pages_document_page",
            "document_id",
            "page_number",
        ),
        Index(
            "ix_document_pages_processing_run_page",
            "processing_run_id",
            "page_number",
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

    processing_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "document_processing_runs.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    page_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
    )

    extraction_method: Mapped[
        str | None
    ] = mapped_column(
        String(50),
        nullable=True,
    )

    language_code: Mapped[
        str | None
    ] = mapped_column(
        String(20),
        nullable=True,
    )

    text_content: Mapped[
        str | None
    ] = mapped_column(
        Text,
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

    character_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    word_count: Mapped[int] = mapped_column(
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