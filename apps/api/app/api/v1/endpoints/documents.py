from __future__ import annotations

from typing import Annotated
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from apps.api.app.api.deps import (
    CurrentUser,
    DatabaseSession,
)
from apps.api.app.db.models.document import Document
from apps.api.app.db.models.document_page import (
    DocumentPage,
)
from apps.api.app.db.models.document_processing_run import (
    DocumentProcessingRun,
)
from apps.api.app.schemas.document import (
    DocumentDeleteResponse,
    DocumentListResponse,
    DocumentRead,
    DocumentUploadResponse,
)
from apps.api.app.schemas.document_processing import (
    DocumentPageListResponse,
    DocumentPageRead,
    DocumentProcessingRunListResponse,
    DocumentProcessingRunRead,
    DocumentProcessingStartResponse,
)
from apps.api.app.services.document_processing import (
    ProcessingDocumentNotFoundError,
    create_document_processing_run,
    mark_processing_run_failed,
)
from apps.api.app.services.documents import (
    DocumentTooLargeError,
    DocumentValidationError,
    InvalidDocumentSignatureError,
    UnsupportedDocumentTypeError,
    validate_document_upload,
)
from apps.api.app.services.extraction import (
    SUPPORTED_EXTRACTION_EXTENSIONS,
)
from apps.api.app.services.storage import (
    StorageError,
    StorageObjectNotFoundError,
    build_storage_object_name,
    delete_object,
    download_object,
    upload_bytes,
)
from workers.document_tasks import (
    process_document as process_document_task,
)


router = APIRouter()


def get_workspace_document(
    *,
    database_session: DatabaseSession,
    workspace_id: UUID,
    document_id: UUID,
) -> Document:
    """Return a workspace document or raise a 404 response."""

    document = database_session.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.workspace_id == workspace_id,
        )
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document was not found.",
        )

    return document


def get_active_processing_run(
    *,
    database_session: DatabaseSession,
    workspace_id: UUID,
    document_id: UUID,
) -> DocumentProcessingRun | None:
    """Return the current queued or running attempt."""

    return database_session.scalar(
        select(DocumentProcessingRun)
        .where(
            DocumentProcessingRun.workspace_id
            == workspace_id,
            DocumentProcessingRun.document_id
            == document_id,
            DocumentProcessingRun.status.in_(
                (
                    "queued",
                    "running",
                )
            ),
        )
        .order_by(
            DocumentProcessingRun.created_at.desc(),
        )
        .limit(1)
    )


def get_latest_completed_processing_run(
    *,
    database_session: DatabaseSession,
    workspace_id: UUID,
    document_id: UUID,
) -> DocumentProcessingRun | None:
    """Return the newest completed attempt."""

    return database_session.scalar(
        select(DocumentProcessingRun)
        .where(
            DocumentProcessingRun.workspace_id
            == workspace_id,
            DocumentProcessingRun.document_id
            == document_id,
            DocumentProcessingRun.status
            == "completed",
        )
        .order_by(
            DocumentProcessingRun.attempt_number.desc(),
            DocumentProcessingRun.created_at.desc(),
        )
        .limit(1)
    )


def build_storage_metadata(
    *,
    etag: str | None,
    version_id: str | None,
) -> dict[str, str]:
    """Build serializable storage metadata."""

    metadata: dict[str, str] = {}

    if etag:
        metadata["storage_etag"] = etag

    if version_id:
        metadata["storage_version_id"] = version_id

    return metadata


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: Annotated[
        UploadFile,
        File(
            description=(
                "PDF, image, CSV, XLS, or XLSX document."
            )
        ),
    ],
    current_user: CurrentUser,
    database_session: DatabaseSession,
) -> DocumentUploadResponse:
    """Validate and upload a document to MinIO."""

    try:
        file_data = await file.read()

        validated_document = validate_document_upload(
            filename=file.filename,
            content_type=file.content_type,
            data=file_data,
        )
    except DocumentTooLargeError as error:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(error),
        ) from error
    except UnsupportedDocumentTypeError as error:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(error),
        ) from error
    except InvalidDocumentSignatureError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except DocumentValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    finally:
        await file.close()

    document_id = uuid4()

    storage_object_name = build_storage_object_name(
        workspace_id=current_user.workspace_id,
        document_id=document_id,
        filename=validated_document.original_filename,
    )

    try:
        stored_object = upload_bytes(
            data=file_data,
            object_name=storage_object_name,
            content_type=validated_document.content_type,
        )
    except StorageError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "The document could not be stored. "
                "Please try again."
            ),
        ) from error

    document = Document(
        id=document_id,
        workspace_id=current_user.workspace_id,
        uploaded_by_user_id=current_user.id,
        original_filename=(
            validated_document.original_filename
        ),
        storage_bucket=stored_object.bucket_name,
        storage_object_name=stored_object.object_name,
        content_type=validated_document.content_type,
        file_extension=validated_document.file_extension,
        file_size_bytes=(
            validated_document.file_size_bytes
        ),
        checksum_sha256=(
            validated_document.checksum_sha256
        ),
        source="manual_upload",
        document_type=validated_document.document_type,
        status="uploaded",
        processing_error=None,
        page_count=None,
        extra_metadata=build_storage_metadata(
            etag=stored_object.etag,
            version_id=stored_object.version_id,
        ),
    )

    database_session.add(document)

    try:
        database_session.commit()
        database_session.refresh(document)
    except SQLAlchemyError as error:
        database_session.rollback()

        try:
            delete_object(
                bucket_name=stored_object.bucket_name,
                object_name=stored_object.object_name,
            )
        except StorageError:
            pass

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "The document metadata could not be saved."
            ),
        ) from error

    return DocumentUploadResponse(
        document=DocumentRead.model_validate(document),
    )


@router.get(
    "",
    response_model=DocumentListResponse,
)
def list_documents(
    current_user: CurrentUser,
    database_session: DatabaseSession,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
        ),
    ] = 20,
    offset: Annotated[
        int,
        Query(
            ge=0,
        ),
    ] = 0,
    document_status: Annotated[
        str | None,
        Query(
            alias="status",
            max_length=50,
        ),
    ] = None,
    document_type: Annotated[
        str | None,
        Query(
            max_length=100,
        ),
    ] = None,
) -> DocumentListResponse:
    """List documents belonging to the current workspace."""

    filters = [
        Document.workspace_id
        == current_user.workspace_id,
    ]

    if document_status:
        filters.append(
            Document.status == document_status
        )

    if document_type:
        filters.append(
            Document.document_type == document_type
        )

    total = database_session.scalar(
        select(func.count())
        .select_from(Document)
        .where(*filters)
    )

    documents = list(
        database_session.scalars(
            select(Document)
            .where(*filters)
            .order_by(
                Document.created_at.desc(),
                Document.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()
    )

    return DocumentListResponse(
        items=[
            DocumentRead.model_validate(document)
            for document in documents
        ],
        total=int(total or 0),
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{document_id}/process",
    response_model=DocumentProcessingStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def queue_document_processing(
    document_id: UUID,
    current_user: CurrentUser,
    database_session: DatabaseSession,
    ocr_language: Annotated[
        str,
        Query(
            min_length=3,
            max_length=50,
            pattern=r"^[A-Za-z0-9_+\-]+$",
        ),
    ] = "eng",
) -> DocumentProcessingStartResponse:
    """Create a processing run and queue the Celery task."""

    document = get_workspace_document(
        database_session=database_session,
        workspace_id=current_user.workspace_id,
        document_id=document_id,
    )

    if (
        document.file_extension
        not in SUPPORTED_EXTRACTION_EXTENSIONS
    ):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                "This document type cannot be processed."
            ),
        )

    active_run = get_active_processing_run(
        database_session=database_session,
        workspace_id=current_user.workspace_id,
        document_id=document.id,
    )

    if active_run is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This document is already queued "
                "or being processed."
            ),
        )

    try:
        processing_run = create_document_processing_run(
            database_session=database_session,
            workspace_id=current_user.workspace_id,
            document_id=document.id,
            requested_by_user_id=current_user.id,
        )
    except ProcessingDocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    try:
        task_result = process_document_task.delay(
            str(processing_run.id),
            ocr_language,
        )
    except Exception as error:
        mark_processing_run_failed(
            database_session=database_session,
            processing_run_id=processing_run.id,
            error=error,
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The processing task could not be "
                "sent to the worker."
            ),
        ) from error

    database_session.refresh(processing_run)

    return DocumentProcessingStartResponse(
        task_id=str(task_result.id),
        processing_run=(
            DocumentProcessingRunRead.model_validate(
                processing_run
            )
        ),
    )


@router.get(
    "/{document_id}/processing-runs",
    response_model=DocumentProcessingRunListResponse,
)
def list_document_processing_runs(
    document_id: UUID,
    current_user: CurrentUser,
    database_session: DatabaseSession,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
        ),
    ] = 20,
    offset: Annotated[
        int,
        Query(
            ge=0,
        ),
    ] = 0,
) -> DocumentProcessingRunListResponse:
    """List processing attempts for a workspace document."""

    document = get_workspace_document(
        database_session=database_session,
        workspace_id=current_user.workspace_id,
        document_id=document_id,
    )

    filters = [
        DocumentProcessingRun.workspace_id
        == current_user.workspace_id,
        DocumentProcessingRun.document_id
        == document.id,
    ]

    total = database_session.scalar(
        select(func.count())
        .select_from(DocumentProcessingRun)
        .where(*filters)
    )

    processing_runs = list(
        database_session.scalars(
            select(DocumentProcessingRun)
            .where(*filters)
            .order_by(
                DocumentProcessingRun.attempt_number.desc(),
                DocumentProcessingRun.created_at.desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()
    )

    return DocumentProcessingRunListResponse(
        items=[
            DocumentProcessingRunRead.model_validate(
                processing_run
            )
            for processing_run in processing_runs
        ],
        total=int(total or 0),
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{document_id}/pages",
    response_model=DocumentPageListResponse,
)
def list_document_pages(
    document_id: UUID,
    current_user: CurrentUser,
    database_session: DatabaseSession,
    processing_run_id: Annotated[
        UUID | None,
        Query(),
    ] = None,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=500,
        ),
    ] = 100,
    offset: Annotated[
        int,
        Query(
            ge=0,
        ),
    ] = 0,
) -> DocumentPageListResponse:
    """List extracted pages from a processing attempt."""

    document = get_workspace_document(
        database_session=database_session,
        workspace_id=current_user.workspace_id,
        document_id=document_id,
    )

    if processing_run_id is not None:
        processing_run = database_session.scalar(
            select(DocumentProcessingRun).where(
                DocumentProcessingRun.id
                == processing_run_id,
                DocumentProcessingRun.workspace_id
                == current_user.workspace_id,
                DocumentProcessingRun.document_id
                == document.id,
            )
        )

        if processing_run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "The document processing run "
                    "was not found."
                ),
            )
    else:
        processing_run = (
            get_latest_completed_processing_run(
                database_session=database_session,
                workspace_id=current_user.workspace_id,
                document_id=document.id,
            )
        )

    if processing_run is None:
        return DocumentPageListResponse(
            processing_run_id=None,
            items=[],
            total=0,
            limit=limit,
            offset=offset,
        )

    filters = [
        DocumentPage.workspace_id
        == current_user.workspace_id,
        DocumentPage.document_id
        == document.id,
        DocumentPage.processing_run_id
        == processing_run.id,
    ]

    total = database_session.scalar(
        select(func.count())
        .select_from(DocumentPage)
        .where(*filters)
    )

    pages = list(
        database_session.scalars(
            select(DocumentPage)
            .where(*filters)
            .order_by(
                DocumentPage.page_number.asc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()
    )

    return DocumentPageListResponse(
        processing_run_id=processing_run.id,
        items=[
            DocumentPageRead.model_validate(page)
            for page in pages
        ],
        total=int(total or 0),
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{document_id}/download",
)
def download_document(
    document_id: UUID,
    current_user: CurrentUser,
    database_session: DatabaseSession,
) -> Response:
    """Download the original document from MinIO."""

    document = get_workspace_document(
        database_session=database_session,
        workspace_id=current_user.workspace_id,
        document_id=document_id,
    )

    try:
        downloaded_object = download_object(
            bucket_name=document.storage_bucket,
            object_name=document.storage_object_name,
        )
    except StorageObjectNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "The document file was not found in storage."
            ),
        ) from error
    except StorageError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "The document could not be downloaded."
            ),
        ) from error

    encoded_filename = quote(
        document.original_filename
    )

    return Response(
        content=downloaded_object.data,
        media_type=document.content_type,
        headers={
            "Content-Disposition": (
                "attachment; "
                f"filename*=UTF-8''{encoded_filename}"
            ),
            "Content-Length": str(
                downloaded_object.size
            ),
            "X-Document-Checksum-SHA256": (
                document.checksum_sha256
            ),
        },
    )


@router.get(
    "/{document_id}",
    response_model=DocumentRead,
)
def get_document(
    document_id: UUID,
    current_user: CurrentUser,
    database_session: DatabaseSession,
) -> DocumentRead:
    """Return metadata for a workspace document."""

    document = get_workspace_document(
        database_session=database_session,
        workspace_id=current_user.workspace_id,
        document_id=document_id,
    )

    return DocumentRead.model_validate(document)


@router.delete(
    "/{document_id}",
    response_model=DocumentDeleteResponse,
)
def remove_document(
    document_id: UUID,
    current_user: CurrentUser,
    database_session: DatabaseSession,
) -> DocumentDeleteResponse:
    """Delete a document from storage and PostgreSQL."""

    document = get_workspace_document(
        database_session=database_session,
        workspace_id=current_user.workspace_id,
        document_id=document_id,
    )

    active_run = get_active_processing_run(
        database_session=database_session,
        workspace_id=current_user.workspace_id,
        document_id=document.id,
    )

    if active_run is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A document cannot be deleted while "
                "it is queued or processing."
            ),
        )

    try:
        delete_object(
            bucket_name=document.storage_bucket,
            object_name=document.storage_object_name,
        )
    except StorageError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "The document could not be deleted "
                "from storage."
            ),
        ) from error

    database_session.delete(document)

    try:
        database_session.commit()
    except SQLAlchemyError as error:
        database_session.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "The document record could not be deleted."
            ),
        ) from error

    return DocumentDeleteResponse(
        message="Document deleted successfully.",
        document_id=document_id,
    )