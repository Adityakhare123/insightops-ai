from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from apps.api.app.services.document_processing import (
    MAX_PROCESSING_ERROR_LENGTH,
    PROCESSOR_NAME,
    PROCESSOR_VERSION,
    build_document_page,
    build_extraction_metadata,
    normalize_processing_error,
    utc_now,
)
from apps.api.app.services.extraction import (
    DocumentExtractionResult,
    ExtractedPage,
)


def test_processor_identity() -> None:
    assert PROCESSOR_NAME == (
        "insightops-document-extractor"
    )

    assert PROCESSOR_VERSION == "0.1.0"


def test_utc_now_is_timezone_aware() -> None:
    timestamp = utc_now()

    assert timestamp.tzinfo is not None
    assert timestamp.utcoffset() is not None


def test_processing_error_is_normalized() -> None:
    error = RuntimeError(
        "  extraction failed  "
    )

    assert normalize_processing_error(
        error
    ) == "extraction failed"


def test_processing_error_is_bounded() -> None:
    error = RuntimeError(
        "x" * (
            MAX_PROCESSING_ERROR_LENGTH + 100
        )
    )

    normalized_error = (
        normalize_processing_error(error)
    )

    assert len(normalized_error) == (
        MAX_PROCESSING_ERROR_LENGTH
    )


def test_extraction_metadata_is_built() -> None:
    result = DocumentExtractionResult(
        document_type="pdf",
        pages=[
            ExtractedPage(
                page_number=1,
                text_content=(
                    "Policy number POL-1001"
                ),
                extraction_method=(
                    "pdf_native_text"
                ),
                confidence_score=1.0,
            )
        ],
        extra_metadata={
            "native_text_pages": 1,
            "ocr_pages": 0,
        },
    )

    metadata = build_extraction_metadata(
        result
    )

    assert metadata["document_type"] == "pdf"
    assert metadata["total_pages"] == 1
    assert metadata["total_characters"] > 0
    assert metadata["total_words"] == 3

    assert metadata[
        "extractor_metadata"
    ] == {
        "native_text_pages": 1,
        "ocr_pages": 0,
    }


def test_extracted_page_becomes_database_page() -> None:
    processing_run = SimpleNamespace(
        id=uuid4(),
        workspace_id=uuid4(),
        document_id=uuid4(),
    )

    extracted_page = ExtractedPage(
        page_number=2,
        text_content=(
            "Customer Name: Jane Doe"
        ),
        extraction_method="pdf_ocr",
        language_code="eng",
        confidence_score=0.9321,
        extra_metadata={
            "ocr_used": True,
        },
    )

    document_page = build_document_page(
        processing_run=processing_run,
        extracted_page=extracted_page,
    )

    assert document_page.page_number == 2
    assert document_page.status == "completed"
    assert (
        document_page.extraction_method
        == "pdf_ocr"
    )
    assert document_page.language_code == "eng"
    assert (
        document_page.confidence_score
        == 0.9321
    )
    assert document_page.character_count == (
        len("Customer Name: Jane Doe")
    )
    assert document_page.word_count == 4
    assert document_page.extra_metadata == {
        "ocr_used": True,
    }