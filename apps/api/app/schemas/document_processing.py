from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


ProcessingRunStatus = Literal[
    "queued",
    "running",
    "completed",
    "failed",
]

DocumentPageStatus = Literal[
    "pending",
    "processing",
    "completed",
    "failed",
]


class DocumentProcessingRunRead(BaseModel):
    """Document processing-run information."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    workspace_id: UUID
    document_id: UUID
    requested_by_user_id: UUID | None

    attempt_number: int
    status: str

    processor_name: str
    processor_version: str | None

    started_at: datetime | None
    completed_at: datetime | None

    total_pages: int | None
    extracted_pages: int

    error_message: str | None
    extra_metadata: dict[str, Any]

    created_at: datetime
    updated_at: datetime


class DocumentProcessingStartResponse(BaseModel):
    """Response returned after queueing document processing."""

    message: str = "Document processing queued successfully."
    task_id: str
    processing_run: DocumentProcessingRunRead


class DocumentProcessingRunListResponse(BaseModel):
    """Paginated processing-run collection."""

    items: list[DocumentProcessingRunRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class DocumentPageRead(BaseModel):
    """Extracted page information."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    workspace_id: UUID
    document_id: UUID
    processing_run_id: UUID

    page_number: int
    status: str

    extraction_method: str | None
    language_code: str | None

    text_content: str | None
    confidence_score: float | None

    character_count: int
    word_count: int

    error_message: str | None
    extra_metadata: dict[str, Any]

    created_at: datetime
    updated_at: datetime


class DocumentPageListResponse(BaseModel):
    """Extracted pages belonging to one processing run."""

    processing_run_id: UUID | None
    items: list[DocumentPageRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)