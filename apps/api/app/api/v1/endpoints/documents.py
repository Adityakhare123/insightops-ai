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
from apps.api.app.schemas.document import (
    DocumentDeleteResponse,
    DocumentListResponse,
    DocumentRead,
    DocumentUploadResponse,
)
from apps.api.app.services.documents import (
    DocumentTooLargeError,
    DocumentValidationError,
    InvalidDocumentSignatureError,
    UnsupportedDocumentTypeError,
    validate_document_upload,
)
from apps.api.app.services.storage import (
    StorageError,
    StorageObjectNotFoundError,
    build_storage_object_name,
    delete_object,
    download_object,
    upload_bytes,
)


router = APIRouter()


def get_workspace_document(
    *,
    database_session: DatabaseSession,
    workspace_id: UUID,
    document_id: UUID,
) -> Document:
    """Return a workspace document or raise a 404 response."""

    statement = select(Document).where(
        Document.id == document_id,
        Document.workspace_id == workspace_id,
    )

    document = database_session.scalar(statement)

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document was not found.",
        )

    return document


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
            description="Maximum number of records.",
        ),
    ] = 20,
    offset: Annotated[
        int,
        Query(
            ge=0,
            description="Number of records to skip.",
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

    total_statement = (
        select(func.count())
        .select_from(Document)
        .where(*filters)
    )

    total = database_session.scalar(
        total_statement
    )

    documents_statement = (
        select(Document)
        .where(*filters)
        .order_by(
            Document.created_at.desc(),
            Document.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    documents = list(
        database_session.scalars(
            documents_statement
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