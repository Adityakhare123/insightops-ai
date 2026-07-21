from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from apps.api.app.db.models.document import Document
from apps.api.app.db.models.document_page import DocumentPage
from apps.api.app.db.models.document_processing_run import (
    DocumentProcessingRun,
)
from apps.api.app.services.extraction import (
    DocumentExtractionResult,
    ExtractedPage,
    extract_document,
)
from apps.api.app.services.storage import download_object


PROCESSOR_NAME = "insightops-document-extractor"
PROCESSOR_VERSION = "0.1.0"
MAX_PROCESSING_ERROR_LENGTH = 4_000


class DocumentProcessingError(RuntimeError):
    """Base exception for document-processing failures."""


class DocumentProcessingRunNotFoundError(
    DocumentProcessingError,
):
    """Raised when a processing run does not exist."""


class ProcessingDocumentNotFoundError(
    DocumentProcessingError,
):
    """Raised when the processing run's document is missing."""


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""

    return datetime.now(UTC)


def normalize_processing_error(
    error: Exception,
) -> str:
    """Return a bounded error message suitable for PostgreSQL."""

    error_message = str(error).strip()

    if not error_message:
        error_message = error.__class__.__name__

    return error_message[
        :MAX_PROCESSING_ERROR_LENGTH
    ]


def get_next_attempt_number(
    database_session: Session,
    *,
    document_id: UUID,
) -> int:
    """Return the next processing-attempt number."""

    maximum_attempt = database_session.scalar(
        select(
            func.max(
                DocumentProcessingRun.attempt_number
            )
        ).where(
            DocumentProcessingRun.document_id
            == document_id
        )
    )

    return int(maximum_attempt or 0) + 1


def create_document_processing_run(
    database_session: Session,
    *,
    workspace_id: UUID,
    document_id: UUID,
    requested_by_user_id: UUID | None,
) -> DocumentProcessingRun:
    """
    Create a queued processing run for a workspace document.

    The document row is locked while calculating the next attempt
    number so concurrent requests cannot select the same attempt.
    """

    document = database_session.scalar(
        select(Document)
        .where(
            Document.id == document_id,
            Document.workspace_id == workspace_id,
        )
        .with_for_update()
    )

    if document is None:
        raise ProcessingDocumentNotFoundError(
            "The document was not found."
        )

    attempt_number = get_next_attempt_number(
        database_session,
        document_id=document.id,
    )

    processing_run = DocumentProcessingRun(
        workspace_id=document.workspace_id,
        document_id=document.id,
        requested_by_user_id=requested_by_user_id,
        attempt_number=attempt_number,
        status="queued",
        processor_name=PROCESSOR_NAME,
        processor_version=PROCESSOR_VERSION,
        started_at=None,
        completed_at=None,
        total_pages=None,
        extracted_pages=0,
        error_message=None,
        extra_metadata={},
    )

    document.status = "queued"
    document.processing_error = None

    database_session.add(processing_run)
    database_session.commit()
    database_session.refresh(processing_run)

    return processing_run


def get_processing_run(
    database_session: Session,
    *,
    processing_run_id: UUID,
) -> DocumentProcessingRun:
    """Return a processing run or raise a domain error."""

    processing_run = database_session.scalar(
        select(DocumentProcessingRun).where(
            DocumentProcessingRun.id
            == processing_run_id
        )
    )

    if processing_run is None:
        raise DocumentProcessingRunNotFoundError(
            "The document processing run was not found."
        )

    return processing_run


def build_document_page(
    *,
    processing_run: DocumentProcessingRun,
    extracted_page: ExtractedPage,
) -> DocumentPage:
    """Convert an extracted page into a database model."""

    return DocumentPage(
        workspace_id=processing_run.workspace_id,
        document_id=processing_run.document_id,
        processing_run_id=processing_run.id,
        page_number=extracted_page.page_number,
        status="completed",
        extraction_method=(
            extracted_page.extraction_method
        ),
        language_code=extracted_page.language_code,
        text_content=extracted_page.text_content,
        confidence_score=(
            extracted_page.confidence_score
        ),
        character_count=(
            extracted_page.character_count
        ),
        word_count=extracted_page.word_count,
        error_message=None,
        extra_metadata=dict(
            extracted_page.extra_metadata
        ),
    )


def build_extraction_metadata(
    result: DocumentExtractionResult,
) -> dict[str, Any]:
    """Build JSON-safe extraction summary metadata."""

    return {
        "document_type": result.document_type,
        "total_pages": result.total_pages,
        "total_characters": (
            result.total_characters
        ),
        "total_words": result.total_words,
        "extractor_metadata": dict(
            result.extra_metadata
        ),
    }


def mark_processing_run_failed(
    database_session: Session,
    *,
    processing_run_id: UUID,
    error: Exception,
) -> None:
    """Persist a failed processing result."""

    database_session.rollback()

    processing_run = database_session.scalar(
        select(DocumentProcessingRun).where(
            DocumentProcessingRun.id
            == processing_run_id
        )
    )

    if processing_run is None:
        return

    document = database_session.scalar(
        select(Document).where(
            Document.id
            == processing_run.document_id
        )
    )

    error_message = normalize_processing_error(
        error
    )

    processing_run.status = "failed"
    processing_run.completed_at = utc_now()
    processing_run.error_message = error_message

    if document is not None:
        document.status = "failed"
        document.processing_error = error_message

    database_session.commit()


def process_document_run(
    database_session: Session,
    *,
    processing_run_id: UUID,
    ocr_language: str = "eng",
) -> DocumentProcessingRun:
    """
    Execute one complete document extraction attempt.

    This function is designed to be called by a Celery worker.
    It raises the original failure after persisting failed status.
    """

    processing_run = database_session.scalar(
        select(DocumentProcessingRun)
        .where(
            DocumentProcessingRun.id
            == processing_run_id
        )
        .with_for_update()
    )

    if processing_run is None:
        raise DocumentProcessingRunNotFoundError(
            "The document processing run was not found."
        )

    if processing_run.status == "completed":
        return processing_run

    document = database_session.scalar(
        select(Document).where(
            Document.id
            == processing_run.document_id,
            Document.workspace_id
            == processing_run.workspace_id,
        )
    )

    if document is None:
        raise ProcessingDocumentNotFoundError(
            "The document associated with the "
            "processing run was not found."
        )

    document_id = document.id
    storage_bucket = document.storage_bucket
    storage_object_name = (
        document.storage_object_name
    )
    original_filename = (
        document.original_filename
    )

    processing_run.status = "running"
    processing_run.started_at = (
        processing_run.started_at
        or utc_now()
    )
    processing_run.completed_at = None
    processing_run.error_message = None
    processing_run.total_pages = None
    processing_run.extracted_pages = 0

    document.status = "processing"
    document.processing_error = None

    database_session.commit()

    try:
        downloaded_object = download_object(
            bucket_name=storage_bucket,
            object_name=storage_object_name,
        )

        extraction_result = extract_document(
            data=downloaded_object.data,
            filename=original_filename,
            language_code=ocr_language,
        )

        processing_run = get_processing_run(
            database_session,
            processing_run_id=processing_run_id,
        )

        document = database_session.scalar(
            select(Document).where(
                Document.id == document_id
            )
        )

        if document is None:
            raise ProcessingDocumentNotFoundError(
                "The document was removed during processing."
            )

        database_session.execute(
            delete(DocumentPage).where(
                DocumentPage.processing_run_id
                == processing_run.id
            )
        )

        document_pages = [
            build_document_page(
                processing_run=processing_run,
                extracted_page=extracted_page,
            )
            for extracted_page
            in extraction_result.pages
        ]

        database_session.add_all(
            document_pages
        )

        extraction_metadata = (
            build_extraction_metadata(
                extraction_result
            )
        )

        completed_at = utc_now()

        processing_run.status = "completed"
        processing_run.completed_at = completed_at
        processing_run.total_pages = (
            extraction_result.total_pages
        )
        processing_run.extracted_pages = (
            extraction_result.total_pages
        )
        processing_run.error_message = None
        processing_run.extra_metadata = (
            extraction_metadata
        )

        document.status = "processed"
        document.processing_error = None
        document.page_count = (
            extraction_result.total_pages
        )

        document_metadata = dict(
            document.extra_metadata or {}
        )

        document_metadata[
            "latest_extraction"
        ] = {
            **extraction_metadata,
            "processing_run_id": str(
                processing_run.id
            ),
            "attempt_number": (
                processing_run.attempt_number
            ),
            "completed_at": (
                completed_at.isoformat()
            ),
        }

        document.extra_metadata = (
            document_metadata
        )

        database_session.commit()
        database_session.refresh(
            processing_run
        )

        return processing_run

    except Exception as error:
        mark_processing_run_failed(
            database_session,
            processing_run_id=processing_run_id,
            error=error,
        )

        raise