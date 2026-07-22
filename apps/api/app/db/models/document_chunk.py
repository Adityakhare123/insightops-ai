from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import VECTOR
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


DOCUMENT_CHUNK_EMBEDDING_DIMENSIONS = 384


class DocumentChunk(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    """
    Stores one searchable RAG chunk from an extracted document page.

    Chunks preserve the source document, processing attempt, page,
    and source-character range so retrieved answers can cite their
    original location.
    """

    __tablename__ = "document_chunks"

    __table_args__ = (
        UniqueConstraint(
            "processing_run_id",
            "chunk_index",
            name="processing_run_chunk_index_unique",
        ),
        CheckConstraint(
            "chunk_index >= 0",
            name="chunk_index_non_negative",
        ),
        CheckConstraint(
            "page_number >= 1",
            name="page_number_positive",
        ),
        CheckConstraint(
            "start_character >= 0",
            name="start_character_non_negative",
        ),
        CheckConstraint(
            "end_character >= start_character",
            name="character_range_valid",
        ),
        CheckConstraint(
            "character_count >= 0",
            name="character_count_non_negative",
        ),
        CheckConstraint(
            "word_count >= 0",
            name="word_count_non_negative",
        ),
        CheckConstraint(
            (
                "status IN "
                "('pending', 'embedding', 'ready', 'failed')"
            ),
            name="status_valid",
        ),
        CheckConstraint(
            (
                "embedding_dimensions IS NULL "
                "OR embedding_dimensions > 0"
            ),
            name="embedding_dimensions_positive",
        ),
        Index(
            "ix_document_chunks_workspace_status",
            "workspace_id",
            "status",
        ),
        Index(
            "ix_document_chunks_document_run",
            "document_id",
            "processing_run_id",
        ),
        Index(
            "ix_document_chunks_page_order",
            "document_page_id",
            "chunk_index",
        ),
        Index(
            "ix_document_chunks_workspace_document",
            "workspace_id",
            "document_id",
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

    document_page_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "document_pages.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    page_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    start_character: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    end_character: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    text_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    character_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    word_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    content_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
    )

    embedding: Mapped[
        list[float] | None
    ] = mapped_column(
        VECTOR(
            DOCUMENT_CHUNK_EMBEDDING_DIMENSIONS
        ),
        nullable=True,
    )

    embedding_provider: Mapped[
        str | None
    ] = mapped_column(
        String(100),
        nullable=True,
    )

    embedding_model: Mapped[
        str | None
    ] = mapped_column(
        String(255),
        nullable=True,
    )

    embedding_dimensions: Mapped[
        int | None
    ] = mapped_column(
        Integer,
        nullable=True,
    )

    embedded_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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


Index(
    "ix_document_chunks_embedding_hnsw",
    DocumentChunk.embedding,
    postgresql_using="hnsw",
    postgresql_with={
        "m": 16,
        "ef_construction": 64,
    },
    postgresql_ops={
        "embedding": "vector_cosine_ops",
    },
)