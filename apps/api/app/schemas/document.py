from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


DocumentStatus = Literal[
    "uploaded",
    "queued",
    "processing",
    "processed",
    "failed",
]

DocumentType = Literal[
    "pdf",
    "image",
    "spreadsheet",
    "data",
]


class DocumentRead(BaseModel):
    """Document metadata returned by the API."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    workspace_id: UUID
    uploaded_by_user_id: UUID

    original_filename: str
    content_type: str
    file_extension: str | None
    file_size_bytes: int
    checksum_sha256: str

    source: str
    document_type: str | None
    status: str

    processing_error: str | None
    page_count: int | None
    extra_metadata: dict[str, Any]

    created_at: datetime
    updated_at: datetime


class DocumentUploadResponse(BaseModel):
    """Response returned after a successful upload."""

    message: str = "Document uploaded successfully."
    document: DocumentRead


class DocumentListResponse(BaseModel):
    """Paginated collection of workspace documents."""

    items: list[DocumentRead]

    total: int = Field(
        ge=0,
    )

    limit: int = Field(
        ge=1,
    )

    offset: int = Field(
        ge=0,
    )


class DocumentDeleteResponse(BaseModel):
    """Response returned after deleting a document."""

    message: str
    document_id: UUID