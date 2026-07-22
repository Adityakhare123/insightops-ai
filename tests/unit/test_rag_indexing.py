from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, Iterable
from uuid import uuid4

import pytest

from apps.api.app.db.models.document_page import (
    DocumentPage,
)
from apps.api.app.services.rag_chunking import (
    SourceDocumentPage,
    chunk_document_pages,
)
from apps.api.app.services.rag_embeddings import (
    EmbeddingBatch,
)
from apps.api.app.services.rag_indexing import (
    RAGIndexingError,
    RAGIndexingResult,
    build_document_chunk_models,
    build_source_document_pages,
)


EMBEDDING_DIMENSIONS = 384


class FakeEmbeddingModel:
    def passage_embed(
        self,
        documents: str | Iterable[str],
        batch_size: int = 256,
        **kwargs: Any,
    ) -> Iterable[list[float]]:
        del batch_size
        del kwargs

        if isinstance(documents, str):
            documents = [documents]

        for _document in documents:
            yield [
                0.01
                for _ in range(
                    EMBEDDING_DIMENSIONS
                )
            ]

    def query_embed(
        self,
        query: str | Iterable[str],
        **kwargs: Any,
    ) -> Iterable[list[float]]:
        del query
        del kwargs

        yield [
            0.01
            for _ in range(
                EMBEDDING_DIMENSIONS
            )
        ]


def create_document_page(
    *,
    page_number: int,
    text_content: str | None,
    status: str = "completed",
) -> DocumentPage:
    text = text_content or ""

    return DocumentPage(
        id=uuid4(),
        workspace_id=uuid4(),
        document_id=uuid4(),
        processing_run_id=uuid4(),
        page_number=page_number,
        status=status,
        extraction_method=(
            "pdf_native_text"
        ),
        language_code="eng",
        text_content=text_content,
        confidence_score=1.0,
        character_count=len(text),
        word_count=len(text.split()),
        error_message=None,
        extra_metadata={},
    )


def test_completed_pages_become_source_pages() -> None:
    second_page = create_document_page(
        page_number=2,
        text_content="Second page.",
    )

    first_page = create_document_page(
        page_number=1,
        text_content="First page.",
    )

    failed_page = create_document_page(
        page_number=3,
        text_content="Failed page.",
        status="failed",
    )

    blank_page = create_document_page(
        page_number=4,
        text_content="   ",
    )

    source_pages = build_source_document_pages(
        [
            second_page,
            failed_page,
            blank_page,
            first_page,
        ]
    )

    assert len(source_pages) == 2

    assert [
        page.page_number
        for page in source_pages
    ] == [1, 2]

    assert source_pages[0].text_content == (
        "First page."
    )

    assert source_pages[0].extra_metadata[
        "extraction_method"
    ] == "pdf_native_text"


def test_chunk_models_preserve_provenance() -> None:
    workspace_id = uuid4()
    document_id = uuid4()
    processing_run_id = uuid4()

    processing_run = SimpleNamespace(
        id=processing_run_id,
        workspace_id=workspace_id,
        document_id=document_id,
        attempt_number=2,
    )

    page_id = uuid4()

    text_chunks = chunk_document_pages(
        source_pages=[
            SourceDocumentPage(
                document_page_id=page_id,
                page_number=4,
                text_content=(
                    "Policy POL-1001 belongs to "
                    "customer Jane Doe."
                ),
            )
        ],
        chunk_size=100,
        chunk_overlap=20,
    )

    embedding_batch = EmbeddingBatch(
        provider="fastembed",
        model_name=(
            "BAAI/bge-small-en-v1.5"
        ),
        dimensions=EMBEDDING_DIMENSIONS,
        vectors=[
            [
                0.01
                for _ in range(
                    EMBEDDING_DIMENSIONS
                )
            ]
            for _ in text_chunks
        ],
    )

    chunks = build_document_chunk_models(
        processing_run=processing_run,
        text_chunks=text_chunks,
        embedding_batch=embedding_batch,
        embedded_at=datetime.now(UTC),
        chunk_size=100,
        chunk_overlap=20,
    )

    assert len(chunks) == 1

    chunk = chunks[0]

    assert chunk.workspace_id == workspace_id
    assert chunk.document_id == document_id

    assert (
        chunk.processing_run_id
        == processing_run_id
    )

    assert chunk.document_page_id == page_id
    assert chunk.page_number == 4
    assert chunk.chunk_index == 0
    assert chunk.status == "ready"

    assert chunk.embedding_provider == (
        "fastembed"
    )

    assert chunk.embedding_dimensions == (
        EMBEDDING_DIMENSIONS
    )

    assert len(chunk.embedding) == (
        EMBEDDING_DIMENSIONS
    )

    assert chunk.extra_metadata[
        "processing_attempt"
    ] == 2


def test_embedding_count_mismatch_is_rejected() -> None:
    processing_run = SimpleNamespace(
        id=uuid4(),
        workspace_id=uuid4(),
        document_id=uuid4(),
        attempt_number=1,
    )

    text_chunks = chunk_document_pages(
        source_pages=[
            SourceDocumentPage(
                document_page_id=uuid4(),
                page_number=1,
                text_content="Policy content.",
            )
        ],
        chunk_size=100,
        chunk_overlap=20,
    )

    embedding_batch = EmbeddingBatch(
        provider="fastembed",
        model_name="test-model",
        dimensions=EMBEDDING_DIMENSIONS,
        vectors=[],
    )

    with pytest.raises(
        RAGIndexingError,
        match="counts do not match",
    ):
        build_document_chunk_models(
            processing_run=processing_run,
            text_chunks=text_chunks,
            embedding_batch=embedding_batch,
            embedded_at=datetime.now(UTC),
            chunk_size=100,
            chunk_overlap=20,
        )


def test_indexing_result_metadata_is_json_safe() -> None:
    result = RAGIndexingResult(
        processing_run_id=str(
            uuid4()
        ),
        source_page_count=3,
        chunk_count=8,
        embedded_chunk_count=8,
        embedding_provider="fastembed",
        embedding_model=(
            "BAAI/bge-small-en-v1.5"
        ),
        embedding_dimensions=384,
        chunk_size=1200,
        chunk_overlap=200,
    )

    metadata = result.to_metadata()

    assert metadata["source_page_count"] == 3
    assert metadata["chunk_count"] == 8

    assert (
        metadata["embedded_chunk_count"]
        == 8
    )

    assert (
        metadata["embedding_dimensions"]
        == 384
    )