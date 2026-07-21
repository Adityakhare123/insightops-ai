from __future__ import annotations

import hashlib

import pytest

from apps.api.app.services.documents import (
    MAX_DOCUMENT_SIZE_BYTES,
    DocumentTooLargeError,
    DocumentValidationError,
    InvalidDocumentSignatureError,
    UnsupportedDocumentTypeError,
    calculate_sha256,
    get_file_extension,
    normalize_content_type,
    normalize_original_filename,
    validate_document_upload,
    validate_file_size,
)


def test_filename_is_normalized() -> None:
    assert normalize_original_filename(
        "../../reports/policy-report.pdf"
    ) == "policy-report.pdf"


def test_missing_filename_is_rejected() -> None:
    with pytest.raises(
        DocumentValidationError,
        match="filename is required",
    ):
        normalize_original_filename(None)


def test_supported_extension_is_normalized() -> None:
    assert get_file_extension(
        "REPORT.PDF"
    ) == ".pdf"


def test_unsupported_extension_is_rejected() -> None:
    with pytest.raises(
        UnsupportedDocumentTypeError,
        match="Unsupported file extension",
    ):
        get_file_extension(
            "malicious.exe"
        )


def test_content_type_parameters_are_removed() -> None:
    assert normalize_content_type(
        "text/csv; charset=utf-8"
    ) == "text/csv"


def test_empty_file_is_rejected() -> None:
    with pytest.raises(
        DocumentValidationError,
        match="empty",
    ):
        validate_file_size(0)


def test_large_file_is_rejected() -> None:
    with pytest.raises(
        DocumentTooLargeError,
        match="25 MB",
    ):
        validate_file_size(
            MAX_DOCUMENT_SIZE_BYTES + 1
        )


def test_sha256_checksum_is_generated() -> None:
    data = b"InsightOps document"

    expected_checksum = hashlib.sha256(
        data
    ).hexdigest()

    assert calculate_sha256(
        data
    ) == expected_checksum


def test_valid_pdf_is_accepted() -> None:
    data = (
        b"%PDF-1.7\n"
        b"InsightOps sample PDF content"
    )

    validated = validate_document_upload(
        filename="policy-report.pdf",
        content_type="application/pdf",
        data=data,
    )

    assert validated.original_filename == (
        "policy-report.pdf"
    )
    assert validated.file_extension == ".pdf"
    assert validated.document_type == "pdf"
    assert validated.file_size_bytes == len(data)
    assert len(validated.checksum_sha256) == 64


def test_pdf_with_invalid_signature_is_rejected() -> None:
    with pytest.raises(
        InvalidDocumentSignatureError,
        match="do not match",
    ):
        validate_document_upload(
            filename="fake.pdf",
            content_type="application/pdf",
            data=b"This is not a PDF",
        )


def test_mismatched_content_type_is_rejected() -> None:
    with pytest.raises(
        UnsupportedDocumentTypeError,
        match="does not match",
    ):
        validate_document_upload(
            filename="report.pdf",
            content_type="image/png",
            data=b"%PDF-1.7\nDocument",
        )


def test_valid_csv_is_accepted() -> None:
    data = (
        b"policy_number,status\n"
        b"POL-2026-0001,active\n"
    )

    validated = validate_document_upload(
        filename="policies.csv",
        content_type="text/csv",
        data=data,
    )

    assert validated.document_type == "data"
    assert validated.file_extension == ".csv"


def test_valid_xlsx_signature_is_accepted() -> None:
    data = (
        b"PK\x03\x04"
        b"mock-xlsx-zip-content"
    )

    validated = validate_document_upload(
        filename="payments.xlsx",
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        data=data,
    )

    assert validated.document_type == "spreadsheet"
    assert validated.file_extension == ".xlsx"