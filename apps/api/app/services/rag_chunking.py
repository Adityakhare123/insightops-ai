from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Sequence
from uuid import UUID

from apps.api.app.services.extraction import (
    normalize_extracted_text,
)


DEFAULT_CHUNK_SIZE_CHARACTERS = 1_200
DEFAULT_CHUNK_OVERLAP_CHARACTERS = 200
MINIMUM_BREAK_RATIO = 0.6

BREAK_SEPARATORS = (
    "\n\n",
    "\n",
    ". ",
    "? ",
    "! ",
    "; ",
    ", ",
    " ",
)


class DocumentChunkingError(ValueError):
    """Raised when document text cannot be chunked safely."""


@dataclass(frozen=True)
class SourceDocumentPage:
    """Page-level text supplied to the chunking engine."""

    document_page_id: UUID
    page_number: int
    text_content: str | None
    extra_metadata: dict[str, Any] = field(
        default_factory=dict,
    )


@dataclass(frozen=True)
class TextChunk:
    """One deterministic chunk with source provenance."""

    chunk_index: int
    document_page_id: UUID
    page_number: int

    start_character: int
    end_character: int

    text_content: str
    character_count: int
    word_count: int
    content_sha256: str

    extra_metadata: dict[str, Any] = field(
        default_factory=dict,
    )


def calculate_chunk_sha256(
    text_content: str,
) -> str:
    """Return a deterministic SHA-256 checksum for chunk text."""

    return sha256(
        text_content.encode("utf-8")
    ).hexdigest()


def validate_chunking_parameters(
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> None:
    """Validate chunk size and overlap configuration."""

    if chunk_size <= 0:
        raise DocumentChunkingError(
            "chunk_size must be greater than zero."
        )

    if chunk_overlap < 0:
        raise DocumentChunkingError(
            "chunk_overlap cannot be negative."
        )

    if chunk_overlap >= chunk_size:
        raise DocumentChunkingError(
            "chunk_overlap must be smaller than chunk_size."
        )


def _find_chunk_end(
    *,
    text_content: str,
    start_character: int,
    chunk_size: int,
) -> int:
    """
    Find a readable chunk boundary no later than the hard limit.

    The function prefers paragraph, line, sentence, punctuation,
    and word boundaries while avoiding extremely small chunks.
    """

    hard_end = min(
        len(text_content),
        start_character + chunk_size,
    )

    if hard_end >= len(text_content):
        return len(text_content)

    minimum_end = min(
        hard_end,
        start_character
        + max(
            1,
            int(
                chunk_size
                * MINIMUM_BREAK_RATIO
            ),
        ),
    )

    boundary_candidates: list[int] = []

    for separator in BREAK_SEPARATORS:
        separator_position = text_content.rfind(
            separator,
            minimum_end,
            hard_end,
        )

        if separator_position < 0:
            continue

        boundary_candidates.append(
            separator_position
            + len(separator)
        )

    if boundary_candidates:
        return max(boundary_candidates)

    return hard_end


def _trim_chunk_range(
    *,
    text_content: str,
    start_character: int,
    end_character: int,
) -> tuple[int, int, str]:
    """Trim surrounding whitespace and update source offsets."""

    raw_chunk = text_content[
        start_character:end_character
    ]

    left_trimmed = raw_chunk.lstrip()
    left_trim_count = (
        len(raw_chunk)
        - len(left_trimmed)
    )

    fully_trimmed = left_trimmed.rstrip()
    right_trim_count = (
        len(left_trimmed)
        - len(fully_trimmed)
    )

    adjusted_start = (
        start_character
        + left_trim_count
    )

    adjusted_end = (
        end_character
        - right_trim_count
    )

    return (
        adjusted_start,
        adjusted_end,
        fully_trimmed,
    )


def _find_next_start(
    *,
    text_content: str,
    current_start: int,
    current_end: int,
    chunk_overlap: int,
) -> int:
    """Return the start position for the following chunk."""

    if current_end >= len(text_content):
        return len(text_content)

    next_start = max(
        current_start + 1,
        current_end - chunk_overlap,
    )

    if (
        0 < next_start < len(text_content)
        and text_content[next_start - 1].isalnum()
        and text_content[next_start].isalnum()
    ):
        previous_space = text_content.rfind(
            " ",
            current_start + 1,
            next_start + 1,
        )

        if previous_space > current_start:
            next_start = previous_space + 1

    while (
        next_start < len(text_content)
        and text_content[next_start].isspace()
    ):
        next_start += 1

    return next_start


def chunk_page_text(
    *,
    source_page: SourceDocumentPage,
    starting_chunk_index: int = 0,
    chunk_size: int = (
        DEFAULT_CHUNK_SIZE_CHARACTERS
    ),
    chunk_overlap: int = (
        DEFAULT_CHUNK_OVERLAP_CHARACTERS
    ),
) -> list[TextChunk]:
    """Split one extracted page into overlapping text chunks."""

    validate_chunking_parameters(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    if source_page.page_number < 1:
        raise DocumentChunkingError(
            "page_number must be greater than or equal to one."
        )

    if starting_chunk_index < 0:
        raise DocumentChunkingError(
            "starting_chunk_index cannot be negative."
        )

    normalized_text = normalize_extracted_text(
        source_page.text_content
    )

    if not normalized_text:
        return []

    chunks: list[TextChunk] = []
    start_character = 0

    while start_character < len(
        normalized_text
    ):
        proposed_end = _find_chunk_end(
            text_content=normalized_text,
            start_character=start_character,
            chunk_size=chunk_size,
        )

        (
            adjusted_start,
            adjusted_end,
            chunk_text,
        ) = _trim_chunk_range(
            text_content=normalized_text,
            start_character=start_character,
            end_character=proposed_end,
        )

        if chunk_text:
            chunk_index = (
                starting_chunk_index
                + len(chunks)
            )

            chunks.append(
                TextChunk(
                    chunk_index=chunk_index,
                    document_page_id=(
                        source_page.document_page_id
                    ),
                    page_number=(
                        source_page.page_number
                    ),
                    start_character=(
                        adjusted_start
                    ),
                    end_character=(
                        adjusted_end
                    ),
                    text_content=chunk_text,
                    character_count=len(
                        chunk_text
                    ),
                    word_count=len(
                        chunk_text.split()
                    ),
                    content_sha256=(
                        calculate_chunk_sha256(
                            chunk_text
                        )
                    ),
                    extra_metadata={
                        **source_page.extra_metadata,
                        "source_page_number": (
                            source_page.page_number
                        ),
                        "source_start_character": (
                            adjusted_start
                        ),
                        "source_end_character": (
                            adjusted_end
                        ),
                    },
                )
            )

        next_start = _find_next_start(
            text_content=normalized_text,
            current_start=start_character,
            current_end=proposed_end,
            chunk_overlap=chunk_overlap,
        )

        if next_start <= start_character:
            raise DocumentChunkingError(
                "Chunking failed to advance through the text."
            )

        start_character = next_start

    return chunks


def chunk_document_pages(
    *,
    source_pages: Sequence[
        SourceDocumentPage
    ],
    chunk_size: int = (
        DEFAULT_CHUNK_SIZE_CHARACTERS
    ),
    chunk_overlap: int = (
        DEFAULT_CHUNK_OVERLAP_CHARACTERS
    ),
) -> list[TextChunk]:
    """
    Chunk multiple pages while maintaining a global chunk index.

    Pages are processed in page-number order so chunk identifiers
    remain deterministic across repeated processing runs.
    """

    validate_chunking_parameters(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    chunks: list[TextChunk] = []

    ordered_pages = sorted(
        source_pages,
        key=lambda page: (
            page.page_number,
            str(page.document_page_id),
        ),
    )

    for source_page in ordered_pages:
        page_chunks = chunk_page_text(
            source_page=source_page,
            starting_chunk_index=len(chunks),
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        chunks.extend(page_chunks)

    return chunks