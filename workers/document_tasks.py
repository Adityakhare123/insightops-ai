from __future__ import annotations

from uuid import UUID

from apps.api.app.db.session import SessionLocal
from apps.api.app.services.document_processing import (
    process_document_run,
)
from workers.celery_app import celery_app


@celery_app.task(
    bind=True,
    name="workers.document_tasks.process_document",
    acks_late=True,
)
def process_document(
    self,
    processing_run_id: str,
    ocr_language: str = "eng",
) -> dict[str, object]:
    """
    Process one uploaded document asynchronously.

    The API creates a document_processing_runs record and sends
    its ID to this Celery task. The task downloads the original
    file from MinIO, extracts its contents, saves page records,
    and updates the document and processing-run statuses.
    """

    try:
        processing_run_uuid = UUID(
            processing_run_id
        )
    except ValueError as error:
        raise ValueError(
            "processing_run_id must be a valid UUID."
        ) from error

    with SessionLocal() as database_session:
        processing_run = process_document_run(
            database_session=database_session,
            processing_run_id=processing_run_uuid,
            ocr_language=ocr_language,
        )

        return {
            "task_id": str(self.request.id),
            "processing_run_id": str(
                processing_run.id
            ),
            "document_id": str(
                processing_run.document_id
            ),
            "workspace_id": str(
                processing_run.workspace_id
            ),
            "attempt_number": (
                processing_run.attempt_number
            ),
            "status": processing_run.status,
            "total_pages": (
                processing_run.total_pages
            ),
            "extracted_pages": (
                processing_run.extracted_pages
            ),
            "completed_at": (
                processing_run.completed_at.isoformat()
                if processing_run.completed_at
                else None
            ),
        }