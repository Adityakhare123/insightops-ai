from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import (
    JSONB,
    UUID as PostgreSQLUUID,
)
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.db.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class Document(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    """File uploaded to an InsightOps workspace."""

    __tablename__ = "documents"

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "storage_object_name",
            name="uq_documents_workspace_storage_object",
        ),
        CheckConstraint(
    "file_size_bytes >= 0",
    name="file_size_non_negative",
        ),
        Index(
            "ix_documents_workspace_created_at",
            "workspace_id",
            "created_at",
        ),
        Index(
            "ix_documents_workspace_status",
            "workspace_id",
            "status",
        ),
        Index(
            "ix_documents_workspace_document_type",
            "workspace_id",
            "document_type",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "workspaces.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    uploaded_by_user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    original_filename: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    storage_bucket: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    storage_object_name: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    content_type: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    file_extension: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    checksum_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'manual_upload'"),
    )

    document_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'uploaded'"),
    )

    processing_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    page_count: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )