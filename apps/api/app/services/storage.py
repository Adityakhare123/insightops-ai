from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import BinaryIO
from uuid import UUID, uuid4

from minio import Minio
from minio.error import S3Error

from apps.api.app.core.config import settings


class StorageError(RuntimeError):
    """Raised when object storage operations fail."""


class StorageObjectNotFoundError(StorageError):
    """Raised when a requested object does not exist."""


@dataclass(frozen=True)
class StoredObject:
    """Metadata returned after storing a file."""

    bucket_name: str
    object_name: str
    etag: str | None
    version_id: str | None


@dataclass(frozen=True)
class DownloadedObject:
    """Downloaded object content and metadata."""

    data: bytes
    content_type: str
    size: int


def create_storage_client() -> Minio:
    """Create the configured MinIO client."""

    return Minio(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


storage_client = create_storage_client()


def ensure_storage_bucket(
    bucket_name: str | None = None,
) -> str:
    """Create the configured bucket when it does not exist."""

    resolved_bucket = (
        bucket_name or settings.minio_bucket
    ).strip()

    if not resolved_bucket:
        raise StorageError(
            "A MinIO bucket name is required."
        )

    try:
        if not storage_client.bucket_exists(
            resolved_bucket
        ):
            storage_client.make_bucket(
                resolved_bucket
            )
    except S3Error as error:
        raise StorageError(
            "Unable to initialize the MinIO bucket."
        ) from error

    return resolved_bucket


def sanitize_filename(
    filename: str,
) -> str:
    """Return a safe filename for object storage."""

    original_name = Path(filename).name.strip()

    if not original_name:
        return "uploaded-file"

    safe_characters: list[str] = []

    for character in original_name:
        if (
            character.isalnum()
            or character in {".", "-", "_"}
        ):
            safe_characters.append(character)
        else:
            safe_characters.append("-")

    sanitized_name = "".join(
        safe_characters
    ).strip(".-_")

    while "--" in sanitized_name:
        sanitized_name = sanitized_name.replace(
            "--",
            "-",
        )

    return sanitized_name or "uploaded-file"


def build_storage_object_name(
    workspace_id: UUID,
    document_id: UUID,
    filename: str,
) -> str:
    """Build a workspace-scoped object name."""

    safe_filename = sanitize_filename(filename)

    return (
        f"workspaces/{workspace_id}/"
        f"documents/{document_id}/"
        f"{uuid4().hex}-{safe_filename}"
    )


def upload_bytes(
    *,
    data: bytes,
    object_name: str,
    content_type: str,
    bucket_name: str | None = None,
) -> StoredObject:
    """Upload bytes to MinIO."""

    if not data:
        raise StorageError(
            "Cannot upload an empty object."
        )

    resolved_bucket = ensure_storage_bucket(
        bucket_name
    )

    data_stream = BytesIO(data)

    try:
        result = storage_client.put_object(
            bucket_name=resolved_bucket,
            object_name=object_name,
            data=data_stream,
            length=len(data),
            content_type=content_type,
        )
    except S3Error as error:
        raise StorageError(
            "Unable to upload the file to MinIO."
        ) from error

    return StoredObject(
        bucket_name=resolved_bucket,
        object_name=object_name,
        etag=result.etag,
        version_id=result.version_id,
    )


def upload_stream(
    *,
    stream: BinaryIO,
    length: int,
    object_name: str,
    content_type: str,
    bucket_name: str | None = None,
) -> StoredObject:
    """Upload a binary stream to MinIO."""

    if length <= 0:
        raise StorageError(
            "Cannot upload an empty object."
        )

    resolved_bucket = ensure_storage_bucket(
        bucket_name
    )

    try:
        result = storage_client.put_object(
            bucket_name=resolved_bucket,
            object_name=object_name,
            data=stream,
            length=length,
            content_type=content_type,
        )
    except S3Error as error:
        raise StorageError(
            "Unable to upload the file to MinIO."
        ) from error

    return StoredObject(
        bucket_name=resolved_bucket,
        object_name=object_name,
        etag=result.etag,
        version_id=result.version_id,
    )


def download_object(
    *,
    object_name: str,
    bucket_name: str | None = None,
) -> DownloadedObject:
    """Download an object from MinIO."""

    resolved_bucket = (
        bucket_name or settings.minio_bucket
    ).strip()

    response = None

    try:
        response = storage_client.get_object(
            bucket_name=resolved_bucket,
            object_name=object_name,
        )

        data = response.read()

        content_type = (
            response.headers.get(
                "Content-Type",
                "application/octet-stream",
            )
        )

        return DownloadedObject(
            data=data,
            content_type=content_type,
            size=len(data),
        )

    except S3Error as error:
        if error.code in {
            "NoSuchKey",
            "NoSuchObject",
            "NoSuchBucket",
        }:
            raise StorageObjectNotFoundError(
                "The requested storage object was not found."
            ) from error

        raise StorageError(
            "Unable to download the file from MinIO."
        ) from error

    finally:
        if response is not None:
            response.close()
            response.release_conn()


def delete_object(
    *,
    object_name: str,
    bucket_name: str | None = None,
) -> None:
    """Delete an object from MinIO."""

    resolved_bucket = (
        bucket_name or settings.minio_bucket
    ).strip()

    try:
        storage_client.remove_object(
            bucket_name=resolved_bucket,
            object_name=object_name,
        )
    except S3Error as error:
        raise StorageError(
            "Unable to delete the file from MinIO."
        ) from error


def object_exists(
    *,
    object_name: str,
    bucket_name: str | None = None,
) -> bool:
    """Return whether an object exists in MinIO."""

    resolved_bucket = (
        bucket_name or settings.minio_bucket
    ).strip()

    try:
        storage_client.stat_object(
            bucket_name=resolved_bucket,
            object_name=object_name,
        )
    except S3Error as error:
        if error.code in {
            "NoSuchKey",
            "NoSuchObject",
            "NoSuchBucket",
        }:
            return False

        raise StorageError(
            "Unable to inspect the MinIO object."
        ) from error

    return True