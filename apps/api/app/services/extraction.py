from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
import pymupdf
import pytesseract
from PIL import Image, UnidentifiedImageError
from pytesseract import Output


MIN_NATIVE_PDF_TEXT_CHARACTERS = 12
PDF_RENDER_DPI = 200
DEFAULT_OCR_LANGUAGE = "eng"


SUPPORTED_EXTRACTION_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".csv",
    ".xls",
    ".xlsx",
}


class DocumentExtractionError(RuntimeError):
    """Base exception for extraction failures."""


class UnsupportedExtractionTypeError(
    DocumentExtractionError,
):
    """Raised when the extraction engine does not support a file."""


class CorruptDocumentError(
    DocumentExtractionError,
):
    """Raised when a document cannot be opened or parsed."""


class ExtractionDependencyError(
    DocumentExtractionError,
):
    """Raised when an external extraction dependency is unavailable."""


@dataclass(frozen=True)
class OCRTextResult:
    text_content: str
    confidence_score: float | None


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text_content: str
    extraction_method: str
    language_code: str | None = None
    confidence_score: float | None = None
    extra_metadata: dict[str, Any] = field(
        default_factory=dict,
    )

    @property
    def character_count(self) -> int:
        return len(self.text_content)

    @property
    def word_count(self) -> int:
        return len(self.text_content.split())


@dataclass(frozen=True)
class DocumentExtractionResult:
    document_type: str
    pages: list[ExtractedPage]
    extra_metadata: dict[str, Any] = field(
        default_factory=dict,
    )

    @property
    def total_pages(self) -> int:
        return len(self.pages)

    @property
    def total_characters(self) -> int:
        return sum(
            page.character_count
            for page in self.pages
        )

    @property
    def total_words(self) -> int:
        return sum(
            page.word_count
            for page in self.pages
        )


def normalize_extracted_text(
    text: str | None,
) -> str:
    """
    Normalize extracted text while preserving meaningful lines.

    Repeated spaces are collapsed, blank lines are removed,
    and surrounding whitespace is stripped.
    """

    if not text:
        return ""

    normalized_lines: list[str] = []

    for line in text.replace(
        "\r\n",
        "\n",
    ).replace(
        "\r",
        "\n",
    ).split("\n"):
        normalized_line = " ".join(
            line.split()
        ).strip()

        if normalized_line:
            normalized_lines.append(
                normalized_line
            )

    return "\n".join(normalized_lines)


def _normalize_extension(
    filename: str,
) -> str:
    extension = Path(
        filename
    ).suffix.lower()

    if extension not in SUPPORTED_EXTRACTION_EXTENSIONS:
        supported_extensions = ", ".join(
            sorted(
                SUPPORTED_EXTRACTION_EXTENSIONS
            )
        )

        raise UnsupportedExtractionTypeError(
            "Unsupported extraction file type. "
            f"Supported extensions: {supported_extensions}."
        )

    return extension


def _validate_document_bytes(
    data: bytes,
) -> None:
    if not data:
        raise CorruptDocumentError(
            "The document is empty."
        )


def _build_ocr_text(
    ocr_data: dict[str, list[Any]],
) -> str:
    grouped_lines: dict[
        tuple[int, int, int],
        list[str],
    ] = defaultdict(list)

    text_values = ocr_data.get(
        "text",
        [],
    )

    for index, raw_text in enumerate(
        text_values
    ):
        word = str(
            raw_text
        ).strip()

        if not word:
            continue

        block_number = int(
            ocr_data.get(
                "block_num",
                [0] * len(text_values),
            )[index]
        )

        paragraph_number = int(
            ocr_data.get(
                "par_num",
                [0] * len(text_values),
            )[index]
        )

        line_number = int(
            ocr_data.get(
                "line_num",
                [0] * len(text_values),
            )[index]
        )

        line_key = (
            block_number,
            paragraph_number,
            line_number,
        )

        grouped_lines[line_key].append(
            word
        )

    lines = [
        " ".join(words)
        for _, words in sorted(
            grouped_lines.items()
        )
    ]

    return normalize_extracted_text(
        "\n".join(lines)
    )


def _calculate_ocr_confidence(
    ocr_data: dict[str, list[Any]],
) -> float | None:
    confidence_values: list[float] = []

    for raw_confidence in ocr_data.get(
        "conf",
        [],
    ):
        try:
            confidence = float(
                raw_confidence
            )
        except (
            TypeError,
            ValueError,
        ):
            continue

        if confidence < 0:
            continue

        confidence_values.append(
            confidence
        )

    if not confidence_values:
        return None

    average_percentage = (
        sum(confidence_values)
        / len(confidence_values)
    )

    normalized_confidence = (
        average_percentage / 100
    )

    return round(
        max(
            0.0,
            min(
                normalized_confidence,
                1.0,
            ),
        ),
        4,
    )


def _ocr_image(
    image: Image.Image,
    *,
    language_code: str,
) -> OCRTextResult:
    try:
        prepared_image = image.convert(
            "RGB"
        )

        ocr_data = pytesseract.image_to_data(
            prepared_image,
            lang=language_code,
            config="--psm 6",
            output_type=Output.DICT,
        )
    except (
        pytesseract.TesseractNotFoundError,
        pytesseract.TesseractError,
    ) as error:
        raise ExtractionDependencyError(
            "Tesseract OCR could not process the image."
        ) from error

    return OCRTextResult(
        text_content=_build_ocr_text(
            ocr_data
        ),
        confidence_score=(
            _calculate_ocr_confidence(
                ocr_data
            )
        ),
    )


def _render_pdf_page(
    page: pymupdf.Page,
) -> Image.Image:
    zoom = PDF_RENDER_DPI / 72

    transformation_matrix = pymupdf.Matrix(
        zoom,
        zoom,
    )

    pixmap = page.get_pixmap(
        matrix=transformation_matrix,
        alpha=False,
    )

    image_bytes = pixmap.tobytes(
        "png"
    )

    with Image.open(
        BytesIO(image_bytes)
    ) as rendered_image:
        return rendered_image.convert(
            "RGB"
        )


def extract_pdf(
    data: bytes,
    *,
    language_code: str = DEFAULT_OCR_LANGUAGE,
) -> DocumentExtractionResult:
    _validate_document_bytes(
        data
    )

    try:
        pdf_document = pymupdf.open(
            stream=data,
            filetype="pdf",
        )
    except Exception as error:
        raise CorruptDocumentError(
            "The PDF document could not be opened."
        ) from error

    extracted_pages: list[
        ExtractedPage
    ] = []

    native_text_pages = 0
    ocr_pages = 0

    try:
        if pdf_document.page_count <= 0:
            raise CorruptDocumentError(
                "The PDF document does not contain any pages."
            )

        for page_index in range(
            pdf_document.page_count
        ):
            page = pdf_document.load_page(
                page_index
            )

            native_text = normalize_extracted_text(
                page.get_text(
                    "text",
                    sort=True,
                )
            )

            if (
                len(native_text)
                >= MIN_NATIVE_PDF_TEXT_CHARACTERS
            ):
                native_text_pages += 1

                extracted_pages.append(
                    ExtractedPage(
                        page_number=page_index + 1,
                        text_content=native_text,
                        extraction_method=(
                            "pdf_native_text"
                        ),
                        language_code=None,
                        confidence_score=1.0,
                        extra_metadata={
                            "ocr_used": False,
                        },
                    )
                )

                continue

            rendered_image = _render_pdf_page(
                page
            )

            ocr_result = _ocr_image(
                rendered_image,
                language_code=language_code,
            )

            ocr_pages += 1

            extracted_pages.append(
                ExtractedPage(
                    page_number=page_index + 1,
                    text_content=(
                        ocr_result.text_content
                    ),
                    extraction_method=(
                        "pdf_ocr"
                    ),
                    language_code=language_code,
                    confidence_score=(
                        ocr_result.confidence_score
                    ),
                    extra_metadata={
                        "ocr_used": True,
                        "render_dpi": (
                            PDF_RENDER_DPI
                        ),
                    },
                )
            )
    finally:
        pdf_document.close()

    return DocumentExtractionResult(
        document_type="pdf",
        pages=extracted_pages,
        extra_metadata={
            "native_text_pages": (
                native_text_pages
            ),
            "ocr_pages": ocr_pages,
            "ocr_language": language_code,
        },
    )


def extract_image(
    data: bytes,
    *,
    language_code: str = DEFAULT_OCR_LANGUAGE,
) -> DocumentExtractionResult:
    _validate_document_bytes(
        data
    )

    try:
        with Image.open(
            BytesIO(data)
        ) as source_image:
            prepared_image = source_image.convert(
                "RGB"
            )

            image_format = (
                source_image.format
                or "unknown"
            )

            width = source_image.width
            height = source_image.height
    except (
        UnidentifiedImageError,
        OSError,
    ) as error:
        raise CorruptDocumentError(
            "The image document could not be opened."
        ) from error

    ocr_result = _ocr_image(
        prepared_image,
        language_code=language_code,
    )

    return DocumentExtractionResult(
        document_type="image",
        pages=[
            ExtractedPage(
                page_number=1,
                text_content=(
                    ocr_result.text_content
                ),
                extraction_method="image_ocr",
                language_code=language_code,
                confidence_score=(
                    ocr_result.confidence_score
                ),
                extra_metadata={
                    "width": width,
                    "height": height,
                    "image_format": image_format,
                },
            )
        ],
        extra_metadata={
            "ocr_language": language_code,
        },
    )


def _read_csv_dataframe(
    data: bytes,
) -> pd.DataFrame:
    read_attempts = (
        {
            "encoding": "utf-8-sig",
        },
        {
            "encoding": "utf-8",
        },
        {
            "encoding": "latin-1",
        },
    )

    last_error: Exception | None = None

    for read_options in read_attempts:
        try:
            return pd.read_csv(
                BytesIO(data),
                dtype=str,
                keep_default_na=False,
                **read_options,
            )
        except (
            UnicodeDecodeError,
            pd.errors.ParserError,
        ) as error:
            last_error = error

    raise CorruptDocumentError(
        "The CSV document could not be parsed."
    ) from last_error


def _dataframe_to_text(
    dataframe: pd.DataFrame,
) -> str:
    if (
        dataframe.empty
        and len(dataframe.columns) == 0
    ):
        return ""

    normalized_dataframe = (
        dataframe.fillna("")
    )

    return normalize_extracted_text(
        normalized_dataframe.to_csv(
            index=False,
        )
    )


def extract_csv(
    data: bytes,
) -> DocumentExtractionResult:
    _validate_document_bytes(
        data
    )

    dataframe = _read_csv_dataframe(
        data
    )

    extracted_text = _dataframe_to_text(
        dataframe
    )

    return DocumentExtractionResult(
        document_type="data",
        pages=[
            ExtractedPage(
                page_number=1,
                text_content=extracted_text,
                extraction_method=(
                    "structured_csv"
                ),
                language_code=None,
                confidence_score=1.0,
                extra_metadata={
                    "row_count": len(
                        dataframe.index
                    ),
                    "column_count": len(
                        dataframe.columns
                    ),
                    "columns": [
                        str(column)
                        for column
                        in dataframe.columns
                    ],
                },
            )
        ],
        extra_metadata={
            "format": "csv",
        },
    )


def extract_excel(
    data: bytes,
    *,
    extension: str,
) -> DocumentExtractionResult:
    _validate_document_bytes(
        data
    )

    engine = (
        "openpyxl"
        if extension == ".xlsx"
        else "xlrd"
    )

    try:
        excel_file = pd.ExcelFile(
            BytesIO(data),
            engine=engine,
        )
    except Exception as error:
        raise CorruptDocumentError(
            "The spreadsheet document could not be opened."
        ) from error

    extracted_pages: list[
        ExtractedPage
    ] = []

    for page_number, sheet_name in enumerate(
        excel_file.sheet_names,
        start=1,
    ):
        try:
            dataframe = pd.read_excel(
                excel_file,
                sheet_name=sheet_name,
                dtype=str,
                keep_default_na=False,
            )
        except Exception as error:
            raise CorruptDocumentError(
                f"Spreadsheet sheet '{sheet_name}' "
                "could not be parsed."
            ) from error

        table_text = _dataframe_to_text(
            dataframe
        )

        page_text = normalize_extracted_text(
            f"Sheet: {sheet_name}\n{table_text}"
        )

        extracted_pages.append(
            ExtractedPage(
                page_number=page_number,
                text_content=page_text,
                extraction_method=(
                    "structured_excel"
                ),
                language_code=None,
                confidence_score=1.0,
                extra_metadata={
                    "sheet_name": sheet_name,
                    "row_count": len(
                        dataframe.index
                    ),
                    "column_count": len(
                        dataframe.columns
                    ),
                    "columns": [
                        str(column)
                        for column
                        in dataframe.columns
                    ],
                },
            )
        )

    return DocumentExtractionResult(
        document_type="spreadsheet",
        pages=extracted_pages,
        extra_metadata={
            "format": extension.lstrip(
                "."
            ),
            "sheet_count": len(
                extracted_pages
            ),
            "sheet_names": list(
                excel_file.sheet_names
            ),
        },
    )


def extract_document(
    *,
    data: bytes,
    filename: str,
    language_code: str = DEFAULT_OCR_LANGUAGE,
) -> DocumentExtractionResult:
    """
    Extract page-level text from a supported document.

    The filename extension determines the extraction strategy.
    """

    extension = _normalize_extension(
        filename
    )

    if extension == ".pdf":
        return extract_pdf(
            data,
            language_code=language_code,
        )

    if extension in {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
    }:
        return extract_image(
            data,
            language_code=language_code,
        )

    if extension == ".csv":
        return extract_csv(
            data
        )

    if extension in {
        ".xls",
        ".xlsx",
    }:
        return extract_excel(
            data,
            extension=extension,
        )

    raise UnsupportedExtractionTypeError(
        f"No extractor is configured for {extension}."
    )