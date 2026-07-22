from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Sequence

from sqlalchemy import delete
from sqlalchemy.orm import Session

from apps.api.app.core.config import settings
from apps.api.app.db.models.document_chunk import (
    DocumentChunk,
)
from apps.api.app.db.models.document_page import (
    DocumentPage,
)
from apps.api.app.db.models.document_processing_run import (
    DocumentProcessingRun,
)
from apps.api.app.services.rag_chunking import (
    SourceDocumentPage,
    TextChunk,
    chunk_document_pages,
)
from apps.api.app.services.rag_embeddings import (
    DenseEmbeddingModel,
    EmbeddingBatch,
    embed_passages,
)


class RAGIndexingError(RuntimeError):
    """Raised when document chunks cannot be indexed."""


@dataclass(frozen=True)
class RAGIndexingResult:
    """Summary of one document indexing operation."""

    processing_run_id: str
    source_page_count: int
    chunk_count: int
    embedded_chunk_count: int
    embedding_provider: str | None
    embedding_model: str | None
    embedding_dimensions: int | None
    chunk_size: int
    chunk_overlap: int

    def to_metadata(self) -> dict[str, Any]:
        """Return JSON-safe indexing metadata."""

        return {
            "processing_run_id": (
                self.processing_run_id
            ),
            "source_page_count": (
                self.source_page_count
            ),
            "chunk_count": self.chunk_count,
            "embedded_chunk_count": (
                self.embedded_chunk_count
            ),
            "embedding_provider": (
                self.embedding_provider
            ),
            "embedding_model": (
                self.embedding_model
            ),
            "embedding_dimensions": (
                self.embedding_dimensions
            ),
            "chunk_size": self.chunk_size,
            "chunk_overlap": (
                self.chunk_overlap
            ),
        }


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(UTC)


def build_source_document_pages(
    document_pages: Sequence[DocumentPage],
) -> list[SourceDocumentPage]:
    """
    Convert completed database pages into chunking inputs.

    Failed, incomplete, and blank pages are ignored.
    """

    source_pages: list[
        SourceDocumentPage
    ] = []

    ordered_pages = sorted(
        document_pages,
        key=lambda page: (
            page.page_number,
            str(page.id),
        ),
    )

    for page in ordered_pages:
        if page.status != "completed":
            continue

        text_content = (
            page.text_content or ""
        ).strip()

        if not text_content:
            continue

        source_pages.append(
            SourceDocumentPage(
                document_page_id=page.id,
                page_number=page.page_number,
                text_content=text_content,
                extra_metadata={
                    "extraction_method": (
                        page.extraction_method
                    ),
                    "language_code": (
                        page.language_code
                    ),
                    "confidence_score": (
                        page.confidence_score
                    ),
                    "source_character_count": (
                        page.character_count
                    ),
                    "source_word_count": (
                        page.word_count
                    ),
                },
            )
        )

    return source_pages


def build_document_chunk_models(
    *,
    processing_run: DocumentProcessingRun,
    text_chunks: Sequence[TextChunk],
    embedding_batch: EmbeddingBatch,
    embedded_at: datetime,
    chunk_size: int,
    chunk_overlap: int,
) -> list[DocumentChunk]:
    """Build database chunk models from text and vectors."""

    if (
        len(text_chunks)
        != embedding_batch.count
    ):
        raise RAGIndexingError(
            "Text chunk and embedding counts do not "
            "match: "
            f"{len(text_chunks)} != "
            f"{embedding_batch.count}."
        )

    document_chunks: list[
        DocumentChunk
    ] = []

    for text_chunk, embedding in zip(
        text_chunks,
        embedding_batch.vectors,
        strict=True,
    ):
        document_chunks.append(
            DocumentChunk(
                workspace_id=(
                    processing_run.workspace_id
                ),
                document_id=(
                    processing_run.document_id
                ),
                processing_run_id=(
                    processing_run.id
                ),
                document_page_id=(
                    text_chunk.document_page_id
                ),
                chunk_index=(
                    text_chunk.chunk_index
                ),
                page_number=(
                    text_chunk.page_number
                ),
                start_character=(
                    text_chunk.start_character
                ),
                end_character=(
                    text_chunk.end_character
                ),
                text_content=(
                    text_chunk.text_content
                ),
                character_count=(
                    text_chunk.character_count
                ),
                word_count=(
                    text_chunk.word_count
                ),
                content_sha256=(
                    text_chunk.content_sha256
                ),
                status="ready",
                embedding=embedding,
                embedding_provider=(
                    embedding_batch.provider
                ),
                embedding_model=(
                    embedding_batch.model_name
                ),
                embedding_dimensions=(
                    embedding_batch.dimensions
                ),
                embedded_at=embedded_at,
                error_message=None,
                extra_metadata={
                    **text_chunk.extra_metadata,
                    "chunk_size": chunk_size,
                    "chunk_overlap": (
                        chunk_overlap
                    ),
                    "processing_attempt": (
                        processing_run.attempt_number
                    ),
                },
            )
        )

    return document_chunks


def index_document_pages(
    database_session: Session,
    *,
    processing_run: DocumentProcessingRun,
    document_pages: Sequence[DocumentPage],
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    embedding_model: (
        DenseEmbeddingModel | None
    ) = None,
) -> RAGIndexingResult:
    """
    Chunk, embed, and persist pages from a processing run.

    Existing chunks from the same processing run are deleted,
    making this function safe to execute again after a retry.
    """

    resolved_chunk_size = (
        chunk_size
        if chunk_size is not None
        else settings.rag_chunk_size_characters
    )

    resolved_chunk_overlap = (
        chunk_overlap
        if chunk_overlap is not None
        else settings.rag_chunk_overlap_characters
    )

    database_session.execute(
        delete(DocumentChunk).where(
            DocumentChunk.processing_run_id
            == processing_run.id
        )
    )

    source_pages = (
        build_source_document_pages(
            document_pages
        )
    )

    text_chunks = chunk_document_pages(
        source_pages=source_pages,
        chunk_size=resolved_chunk_size,
        chunk_overlap=(
            resolved_chunk_overlap
        ),
    )

    if not text_chunks:
        return RAGIndexingResult(
            processing_run_id=str(
                processing_run.id
            ),
            source_page_count=len(
                source_pages
            ),
            chunk_count=0,
            embedded_chunk_count=0,
            embedding_provider=None,
            embedding_model=None,
            embedding_dimensions=None,
            chunk_size=resolved_chunk_size,
            chunk_overlap=(
                resolved_chunk_overlap
            ),
        )

    embedding_batch = embed_passages(
        [
            text_chunk.text_content
            for text_chunk in text_chunks
        ],
        embedding_model=embedding_model,
    )

    document_chunks = (
        build_document_chunk_models(
            processing_run=processing_run,
            text_chunks=text_chunks,
            embedding_batch=embedding_batch,
            embedded_at=utc_now(),
            chunk_size=resolved_chunk_size,
            chunk_overlap=(
                resolved_chunk_overlap
            ),
        )
    )

    database_session.add_all(
        document_chunks
    )

    database_session.flush()

    return RAGIndexingResult(
        processing_run_id=str(
            processing_run.id
        ),
        source_page_count=len(
            source_pages
        ),
        chunk_count=len(
            document_chunks
        ),
        embedded_chunk_count=len(
            document_chunks
        ),
        embedding_provider=(
            embedding_batch.provider
        ),
        embedding_model=(
            embedding_batch.model_name
        ),
        embedding_dimensions=(
            embedding_batch.dimensions
        ),
        chunk_size=resolved_chunk_size,
        chunk_overlap=(
            resolved_chunk_overlap
        ),
    )