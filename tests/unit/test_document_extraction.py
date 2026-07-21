from __future__ import annotations

from io import BytesIO

import pandas as pd
import pymupdf
import pytest
from PIL import Image

from apps.api.app.services import extraction
from apps.api.app.services.extraction import (
    CorruptDocumentError,
    OCRTextResult,
    UnsupportedExtractionTypeError,
    extract_document,
    normalize_extracted_text,
)


def create_selectable_pdf() -> bytes:
    document = pymupdf.open()

    page = document.new_page()

    page.insert_text(
        (72, 72),
        "InsightOps selectable policy document",
        fontsize=12,
    )

    pdf_data = document.tobytes()
    document.close()

    return pdf_data


def create_blank_pdf() -> bytes:
    document = pymupdf.open()
    document.new_page()

    pdf_data = document.tobytes()
    document.close()

    return pdf_data


def create_png_image() -> bytes:
    image = Image.new(
        "RGB",
        (400, 120),
        "white",
    )

    output = BytesIO()

    image.save(
        output,
        format="PNG",
    )

    return output.getvalue()


def create_xlsx_workbook() -> bytes:
    output = BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl",
    ) as writer:
        pd.DataFrame(
            {
                "policy_number": [
                    "POL-1001",
                    "POL-1002",
                ],
                "status": [
                    "active",
                    "pending",
                ],
            }
        ).to_excel(
            writer,
            sheet_name="Policies",
            index=False,
        )

        pd.DataFrame(
            {
                "payment_id": [
                    "PAY-1",
                ],
                "amount": [
                    "125.50",
                ],
            }
        ).to_excel(
            writer,
            sheet_name="Payments",
            index=False,
        )

    return output.getvalue()


def test_text_normalization() -> None:
    text = (
        "  Policy    Number  \n\n"
        " POL-1001     Active "
    )

    assert normalize_extracted_text(
        text
    ) == (
        "Policy Number\n"
        "POL-1001 Active"
    )


def test_selectable_pdf_uses_native_text() -> None:
    result = extract_document(
        data=create_selectable_pdf(),
        filename="policy.pdf",
    )

    assert result.document_type == "pdf"
    assert result.total_pages == 1

    page = result.pages[0]

    assert page.extraction_method == (
        "pdf_native_text"
    )

    assert (
        "InsightOps selectable policy document"
        in page.text_content
    )

    assert page.confidence_score == 1.0
    assert page.extra_metadata["ocr_used"] is False


def test_blank_pdf_uses_ocr_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_ocr_image(
        image: Image.Image,
        *,
        language_code: str,
    ) -> OCRTextResult:
        assert image.width > 0
        assert image.height > 0
        assert language_code == "eng"

        return OCRTextResult(
            text_content="Scanned policy OCR result",
            confidence_score=0.91,
        )

    monkeypatch.setattr(
        extraction,
        "_ocr_image",
        fake_ocr_image,
    )

    result = extract_document(
        data=create_blank_pdf(),
        filename="scanned-policy.pdf",
    )

    page = result.pages[0]

    assert page.extraction_method == "pdf_ocr"
    assert page.text_content == (
        "Scanned policy OCR result"
    )

    assert page.confidence_score == 0.91
    assert page.extra_metadata["ocr_used"] is True
    assert result.extra_metadata["ocr_pages"] == 1


def test_image_uses_ocr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_ocr_image(
        image: Image.Image,
        *,
        language_code: str,
    ) -> OCRTextResult:
        assert image.mode == "RGB"
        assert language_code == "eng"

        return OCRTextResult(
            text_content="Enrollment confirmation",
            confidence_score=0.88,
        )

    monkeypatch.setattr(
        extraction,
        "_ocr_image",
        fake_ocr_image,
    )

    result = extract_document(
        data=create_png_image(),
        filename="enrollment.png",
    )

    assert result.document_type == "image"
    assert result.total_pages == 1

    page = result.pages[0]

    assert page.extraction_method == "image_ocr"
    assert page.text_content == (
        "Enrollment confirmation"
    )

    assert page.confidence_score == 0.88


def test_csv_is_extracted_as_structured_text() -> None:
    csv_data = (
        b"policy_number,status\n"
        b"POL-1001,active\n"
        b"POL-1002,pending\n"
    )

    result = extract_document(
        data=csv_data,
        filename="policies.csv",
    )

    assert result.document_type == "data"
    assert result.total_pages == 1

    page = result.pages[0]

    assert page.extraction_method == (
        "structured_csv"
    )

    assert "policy_number,status" in (
        page.text_content
    )

    assert "POL-1001,active" in (
        page.text_content
    )

    assert page.extra_metadata["row_count"] == 2
    assert page.extra_metadata["column_count"] == 2


def test_xlsx_sheets_become_pages() -> None:
    result = extract_document(
        data=create_xlsx_workbook(),
        filename="insurance-data.xlsx",
    )

    assert result.document_type == "spreadsheet"
    assert result.total_pages == 2

    first_page = result.pages[0]
    second_page = result.pages[1]

    assert first_page.page_number == 1
    assert first_page.extra_metadata[
        "sheet_name"
    ] == "Policies"

    assert "POL-1001" in first_page.text_content

    assert second_page.page_number == 2
    assert second_page.extra_metadata[
        "sheet_name"
    ] == "Payments"

    assert "PAY-1" in second_page.text_content

    assert result.extra_metadata[
        "sheet_count"
    ] == 2


def test_unsupported_extension_is_rejected() -> None:
    with pytest.raises(
        UnsupportedExtractionTypeError,
        match="Unsupported extraction",
    ):
        extract_document(
            data=b"unsupported",
            filename="payload.exe",
        )


def test_empty_document_is_rejected() -> None:
    with pytest.raises(
        CorruptDocumentError,
        match="empty",
    ):
        extract_document(
            data=b"",
            filename="empty.pdf",
        )


def test_corrupt_pdf_is_rejected() -> None:
    with pytest.raises(
        CorruptDocumentError,
        match="could not be opened",
    ):
        extract_document(
            data=b"This is not a PDF",
            filename="invalid.pdf",
        )


def test_page_counts_are_calculated() -> None:
    result = extract_document(
        data=(
            b"policy_number,status\n"
            b"POL-1001,active\n"
        ),
        filename="policies.csv",
    )

    page = result.pages[0]

    assert page.character_count > 0
    assert page.word_count > 0
    assert result.total_characters == (
        page.character_count
    )

    assert result.total_words == (
        page.word_count
    )