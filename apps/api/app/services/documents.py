from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


MAX_DOCUMENT_SIZE_BYTES = 25 * 1024 * 1024


ALLOWED_CONTENT_TYPES: dict[str, set[str]] = {
    ".pdf": {
        "application/pdf",
    },
    ".png": {
        "image/png",
    },
    ".jpg": {
        "image/jpeg",
    },
    ".jpeg": {
        "image/jpeg",
    },
    ".webp": {
        "image/webp",
    },
    ".csv": {
        "text/csv",
        "application/csv",
        "text/plain",
        "application/vnd.ms-excel",
    },
    ".xls": {
        "application/vnd.ms-excel",
        "application/octet-stream",
    },
    ".xlsx": {
        (
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        "application/octet-stream",
    },
}


DOCUMENT_TYPE_BY_EXTENSION: dict[str, str] = {
    ".pdf": "pdf",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".csv": "data",
    ".xls": "spreadsheet",
    ".xlsx": "spreadsheet",
}


class DocumentValidationError(ValueError):
    """Raised when an uploaded document is invalid."""


class UnsupportedDocumentTypeError(
    DocumentValidationError
):
    """Raised when a file type is not supported."""


class DocumentTooLargeError(
    DocumentValidationError
):
    """Raised when a file exceeds the upload limit."""


class InvalidDocumentSignatureError(
    DocumentValidationError
):
    """Raised when file contents do not match the extension."""


@dataclass(frozen=True)
class ValidatedDocument:
    """Normalized metadata for a validated upload."""

    original_filename: str
    file_extension: str
    content_type: str
    file_size_bytes: int
    document_type: str
    checksum_sha256: str


def normalize_original_filename(
    filename: str | None,
) -> str:
    """Remove directory components and validate a filename."""

    if filename is None:
        raise DocumentValidationError(
            "A filename is required."
        )

    normalized_filename = Path(
        filename
    ).name.strip()

    if not normalized_filename:
        raise DocumentValidationError(
            "A filename is required."
        )

    if len(normalized_filename) > 500:
        raise DocumentValidationError(
            "The filename cannot exceed 500 characters."
        )

    return normalized_filename


def get_file_extension(
    filename: str,
) -> str:
    """Return a normalized lowercase file extension."""

    extension = Path(filename).suffix.lower()

    if not extension:
        raise UnsupportedDocumentTypeError(
            "The uploaded file must have an extension."
        )

    if extension not in ALLOWED_CONTENT_TYPES:
        supported_extensions = ", ".join(
            sorted(ALLOWED_CONTENT_TYPES)
        )

        raise UnsupportedDocumentTypeError(
            "Unsupported file extension. "
            f"Supported extensions: {supported_extensions}."
        )

    return extension


def normalize_content_type(
    content_type: str | None,
) -> str:
    """Return a normalized MIME type."""

    if not content_type:
        return "application/octet-stream"

    return content_type.split(
        ";",
        maxsplit=1,
    )[0].strip().lower()


def validate_content_type(
    *,
    file_extension: str,
    content_type: str,
) -> None:
    """Confirm MIME type compatibility with the extension."""

    allowed_content_types = ALLOWED_CONTENT_TYPES[
        file_extension
    ]

    if content_type not in allowed_content_types:
        raise UnsupportedDocumentTypeError(
            "The uploaded file content type does not "
            f"match its extension: {content_type}."
        )


def validate_file_size(
    file_size_bytes: int,
) -> None:
    """Validate that the upload is nonempty and within limits."""

    if file_size_bytes <= 0:
        raise DocumentValidationError(
            "The uploaded file is empty."
        )

    if file_size_bytes > MAX_DOCUMENT_SIZE_BYTES:
        maximum_size_mb = (
            MAX_DOCUMENT_SIZE_BYTES
            // (1024 * 1024)
        )

        raise DocumentTooLargeError(
            "The uploaded file exceeds the "
            f"{maximum_size_mb} MB limit."
        )


def calculate_sha256(
    data: bytes,
) -> str:
    """Calculate a hexadecimal SHA-256 checksum."""

    return hashlib.sha256(data).hexdigest()


def _has_pdf_signature(
    data: bytes,
) -> bool:
    return data.startswith(b"%PDF-")


def _has_png_signature(
    data: bytes,
) -> bool:
    return data.startswith(
        b"\x89PNG\r\n\x1a\n"
    )


def _has_jpeg_signature(
    data: bytes,
) -> bool:
    return data.startswith(
        b"\xff\xd8\xff"
    )


def _has_webp_signature(
    data: bytes,
) -> bool:
    return (
        len(data) >= 12
        and data.startswith(b"RIFF")
        and data[8:12] == b"WEBP"
    )


def _has_xlsx_signature(
    data: bytes,
) -> bool:
    return data.startswith(
        b"PK\x03\x04"
    )


def _has_xls_signature(
    data: bytes,
) -> bool:
    return data.startswith(
        b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    )


def validate_file_signature(
    *,
    data: bytes,
    file_extension: str,
) -> None:
    """
    Validate basic file signatures for binary formats.

    CSV files do not have a standard binary signature and are
    validated through extension, content type, and size checks.
    """

    signature_validators = {
        ".pdf": _has_pdf_signature,
        ".png": _has_png_signature,
        ".jpg": _has_jpeg_signature,
        ".jpeg": _has_jpeg_signature,
        ".webp": _has_webp_signature,
        ".xlsx": _has_xlsx_signature,
        ".xls": _has_xls_signature,
    }

    validator = signature_validators.get(
        file_extension
    )

    if validator is None:
        return

    if not validator(data):
        raise InvalidDocumentSignatureError(
            "The file contents do not match the "
            f"{file_extension} extension."
        )


def validate_document_upload(
    *,
    filename: str | None,
    content_type: str | None,
    data: bytes,
) -> ValidatedDocument:
    """Validate an uploaded document and return its metadata."""

    original_filename = normalize_original_filename(
        filename
    )

    file_extension = get_file_extension(
        original_filename
    )

    normalized_content_type = normalize_content_type(
        content_type
    )

    validate_file_size(
        len(data)
    )

    validate_content_type(
        file_extension=file_extension,
        content_type=normalized_content_type,
    )

    validate_file_signature(
        data=data,
        file_extension=file_extension,
    )

    document_type = DOCUMENT_TYPE_BY_EXTENSION[
        file_extension
    ]

    checksum_sha256 = calculate_sha256(
        data
    )

    return ValidatedDocument(
        original_filename=original_filename,
        file_extension=file_extension,
        content_type=normalized_content_type,
        file_size_bytes=len(data),
        document_type=document_type,
        checksum_sha256=checksum_sha256,
    )