from __future__ import annotations

from uuid import uuid4

import pytest

from apps.api.app.services.rag_chunking import (
    DocumentChunkingError,
    SourceDocumentPage,
    calculate_chunk_sha256,
    chunk_document_pages,
    chunk_page_text,
)


def create_source_page(
    *,
    page_number: int = 1,
    text_content: str | None,
) -> SourceDocumentPage:
    return SourceDocumentPage(
        document_page_id=uuid4(),
        page_number=page_number,
        text_content=text_content,
        extra_metadata={
            "test_source": True,
        },
    )


def test_short_page_creates_one_chunk() -> None:
    source_page = create_source_page(
        text_content=(
            "Policy POL-1001 belongs to Jane Doe."
        ),
    )

    chunks = chunk_page_text(
        source_page=source_page,
        chunk_size=100,
        chunk_overlap=20,
    )

    assert len(chunks) == 1

    chunk = chunks[0]

    assert chunk.chunk_index == 0
    assert chunk.page_number == 1

    assert chunk.text_content == (
        "Policy POL-1001 belongs to Jane Doe."
    )

    assert chunk.start_character == 0

    assert chunk.end_character == len(
        chunk.text_content
    )

    assert chunk.character_count == len(
        chunk.text_content
    )

    assert chunk.word_count == 6


def test_long_page_creates_overlapping_chunks() -> None:
    text_content = " ".join(
        f"Policy record number {index} is active."
        for index in range(30)
    )

    source_page = create_source_page(
        text_content=text_content,
    )

    chunks = chunk_page_text(
        source_page=source_page,
        chunk_size=180,
        chunk_overlap=40,
    )

    assert len(chunks) > 1

    assert [
        chunk.chunk_index
        for chunk in chunks
    ] == list(range(len(chunks)))

    for chunk in chunks:
        assert chunk.text_content
        assert chunk.character_count <= 180
        assert chunk.start_character < (
            chunk.end_character
        )

    for previous, current in zip(
        chunks,
        chunks[1:],
        strict=False,
    ):
        assert (
            current.start_character
            < previous.end_character
        )


def test_empty_page_creates_no_chunks() -> None:
    source_page = create_source_page(
        text_content=" \n\n ",
    )

    assert chunk_page_text(
        source_page=source_page,
        chunk_size=100,
        chunk_overlap=20,
    ) == []


def test_multiple_pages_use_global_chunk_indexes() -> None:
    second_page = create_source_page(
        page_number=2,
        text_content="B " * 200,
    )

    first_page = create_source_page(
        page_number=1,
        text_content="A " * 200,
    )

    chunks = chunk_document_pages(
        source_pages=[
            second_page,
            first_page,
        ],
        chunk_size=100,
        chunk_overlap=20,
    )

    assert len(chunks) > 2

    assert [
        chunk.chunk_index
        for chunk in chunks
    ] == list(range(len(chunks)))

    page_numbers = [
        chunk.page_number
        for chunk in chunks
    ]

    assert page_numbers == sorted(
        page_numbers
    )

    assert page_numbers[0] == 1
    assert page_numbers[-1] == 2


def test_chunk_checksum_is_deterministic() -> None:
    text_content = (
        "Customer Jane Doe has policy POL-1001."
    )

    first_checksum = calculate_chunk_sha256(
        text_content
    )

    second_checksum = calculate_chunk_sha256(
        text_content
    )

    assert first_checksum == second_checksum
    assert len(first_checksum) == 64


def test_chunk_contains_page_provenance() -> None:
    source_page = create_source_page(
        page_number=4,
        text_content=(
            "Commission payment amount is 125 dollars."
        ),
    )

    chunk = chunk_page_text(
        source_page=source_page,
        chunk_size=100,
        chunk_overlap=20,
    )[0]

    assert chunk.page_number == 4

    assert chunk.document_page_id == (
        source_page.document_page_id
    )

    assert chunk.extra_metadata[
        "source_page_number"
    ] == 4

    assert chunk.extra_metadata[
        "test_source"
    ] is True


@pytest.mark.parametrize(
    (
        "chunk_size",
        "chunk_overlap",
        "expected_message",
    ),
    [
        (
            0,
            0,
            "greater than zero",
        ),
        (
            100,
            -1,
            "cannot be negative",
        ),
        (
            100,
            100,
            "smaller than chunk_size",
        ),
        (
            100,
            101,
            "smaller than chunk_size",
        ),
    ],
)
def test_invalid_chunk_configuration_is_rejected(
    chunk_size: int,
    chunk_overlap: int,
    expected_message: str,
) -> None:
    source_page = create_source_page(
        text_content="Policy content.",
    )

    with pytest.raises(
        DocumentChunkingError,
        match=expected_message,
    ):
        chunk_page_text(
            source_page=source_page,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )


def test_invalid_page_number_is_rejected() -> None:
    source_page = create_source_page(
        page_number=0,
        text_content="Policy content.",
    )

    with pytest.raises(
        DocumentChunkingError,
        match="page_number",
    ):
        chunk_page_text(
            source_page=source_page,
            chunk_size=100,
            chunk_overlap=20,
        )