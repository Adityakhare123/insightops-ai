from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence
from uuid import UUID

from sqlalchemy import (
    and_,
    func,
    select,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from apps.api.app.core.config import settings
from apps.api.app.db.models.document import Document
from apps.api.app.db.models.document_chunk import (
    DocumentChunk,
)
from apps.api.app.db.models.document_processing_run import (
    DocumentProcessingRun,
)
from apps.api.app.services.rag_embeddings import (
    DenseEmbeddingModel,
    EmbeddingBatch,
    embed_query,
)


class RAGRetrievalError(RuntimeError):
    """Base exception for semantic retrieval failures."""


class InvalidRAGSearchError(
    RAGRetrievalError,
    ValueError,
):
    """Raised when semantic-search input is invalid."""


class RAGSearchDatabaseError(
    RAGRetrievalError,
):
    """Raised when vector retrieval fails in PostgreSQL."""


@dataclass(frozen=True)
class RAGSearchHit:
    """One retrieved document chunk with provenance."""

    chunk_id: UUID
    workspace_id: UUID
    document_id: UUID
    document_name: str
    processing_run_id: UUID
    document_page_id: UUID

    chunk_index: int
    page_number: int

    start_character: int
    end_character: int

    text_content: str

    similarity_score: float
    cosine_distance: float

    embedding_provider: str | None
    embedding_model: str | None
    embedding_dimensions: int | None

    extra_metadata: dict[str, Any] = field(
        default_factory=dict,
    )


@dataclass(frozen=True)
class RAGSearchResult:
    """Semantic-search response with query provenance."""

    query: str
    top_k: int
    minimum_similarity: float

    embedding_provider: str
    embedding_model: str
    embedding_dimensions: int

    items: list[RAGSearchHit]

    @property
    def result_count(self) -> int:
        return len(self.items)


def normalize_rag_query(
    query: str,
) -> str:
    """Normalize and validate a semantic-search query."""

    normalized_query = " ".join(
        query.split()
    ).strip()

    if not normalized_query:
        raise InvalidRAGSearchError(
            "The search query cannot be empty."
        )

    if len(normalized_query) < 2:
        raise InvalidRAGSearchError(
            "The search query must contain at least "
            "two characters."
        )

    if len(normalized_query) > 4_000:
        raise InvalidRAGSearchError(
            "The search query cannot exceed "
            "4,000 characters."
        )

    return normalized_query


def resolve_rag_top_k(
    top_k: int | None,
) -> int:
    """Resolve and validate the retrieval result limit."""

    resolved_top_k = (
        top_k
        if top_k is not None
        else settings.rag_default_top_k
    )

    if resolved_top_k < 1:
        raise InvalidRAGSearchError(
            "top_k must be greater than or equal to one."
        )

    if resolved_top_k > settings.rag_max_top_k:
        raise InvalidRAGSearchError(
            "top_k cannot exceed the configured maximum "
            f"of {settings.rag_max_top_k}."
        )

    return resolved_top_k


def validate_minimum_similarity(
    minimum_similarity: float,
) -> float:
    """Validate a cosine-similarity threshold."""

    if not -1.0 <= minimum_similarity <= 1.0:
        raise InvalidRAGSearchError(
            "minimum_similarity must be between "
            "-1.0 and 1.0."
        )

    return minimum_similarity


def normalize_document_ids(
    document_ids: Sequence[UUID] | None,
) -> list[UUID]:
    """Return unique document IDs while preserving order."""

    if not document_ids:
        return []

    normalized_ids: list[UUID] = []
    seen_ids: set[UUID] = set()

    for document_id in document_ids:
        if document_id in seen_ids:
            continue

        seen_ids.add(document_id)
        normalized_ids.append(document_id)

    if len(normalized_ids) > 100:
        raise InvalidRAGSearchError(
            "A maximum of 100 document IDs may be "
            "searched at once."
        )

    return normalized_ids


def cosine_distance_to_similarity(
    cosine_distance: float,
) -> float:
    """
    Convert cosine distance into cosine similarity.

    pgvector cosine distance is converted using:
    similarity = 1 - distance.
    """

    similarity = 1.0 - float(
        cosine_distance
    )

    return round(
        max(
            -1.0,
            min(
                1.0,
                similarity,
            ),
        ),
        6,
    )


def build_rag_search_hit(
    *,
    chunk: DocumentChunk,
    document_name: str,
    cosine_distance: float,
) -> RAGSearchHit:
    """Build one retrieval result from a database row."""

    return RAGSearchHit(
        chunk_id=chunk.id,
        workspace_id=chunk.workspace_id,
        document_id=chunk.document_id,
        document_name=document_name,
        processing_run_id=(
            chunk.processing_run_id
        ),
        document_page_id=(
            chunk.document_page_id
        ),
        chunk_index=chunk.chunk_index,
        page_number=chunk.page_number,
        start_character=(
            chunk.start_character
        ),
        end_character=chunk.end_character,
        text_content=chunk.text_content,
        similarity_score=(
            cosine_distance_to_similarity(
                cosine_distance
            )
        ),
        cosine_distance=round(
            float(cosine_distance),
            6,
        ),
        embedding_provider=(
            chunk.embedding_provider
        ),
        embedding_model=(
            chunk.embedding_model
        ),
        embedding_dimensions=(
            chunk.embedding_dimensions
        ),
        extra_metadata=dict(
            chunk.extra_metadata or {}
        ),
    )


def search_document_chunks(
    database_session: Session,
    *,
    workspace_id: UUID,
    query: str,
    top_k: int | None = None,
    minimum_similarity: float = 0.0,
    document_ids: Sequence[UUID] | None = None,
    embedding_model: (
        DenseEmbeddingModel | None
    ) = None,
) -> RAGSearchResult:
    """
    Search ready document chunks using cosine similarity.

    Results are isolated to the supplied workspace and only use
    chunks from each document's latest completed processing run.
    """

    normalized_query = normalize_rag_query(
        query
    )

    resolved_top_k = resolve_rag_top_k(
        top_k
    )

    resolved_minimum_similarity = (
        validate_minimum_similarity(
            minimum_similarity
        )
    )

    resolved_document_ids = (
        normalize_document_ids(
            document_ids
        )
    )

    query_embedding: EmbeddingBatch = (
        embed_query(
            normalized_query,
            embedding_model=embedding_model,
        )
    )

    if query_embedding.count != 1:
        raise RAGRetrievalError(
            "Query embedding generation did not "
            "return exactly one vector."
        )

    query_vector = (
        query_embedding.vectors[0]
    )

    latest_completed_runs = (
        select(
            DocumentProcessingRun.document_id.label(
                "document_id"
            ),
            func.max(
                DocumentProcessingRun.attempt_number
            ).label(
                "attempt_number"
            ),
        )
        .where(
            DocumentProcessingRun.workspace_id
            == workspace_id,
            DocumentProcessingRun.status
            == "completed",
        )
        .group_by(
            DocumentProcessingRun.document_id
        )
        .subquery(
            "latest_completed_runs"
        )
    )

    cosine_distance_expression = (
        DocumentChunk.embedding.cosine_distance(
            query_vector
        )
    )

    maximum_cosine_distance = (
        1.0
        - resolved_minimum_similarity
    )

    statement = (
        select(
            DocumentChunk,
            Document.original_filename.label(
                "document_name"
            ),
            cosine_distance_expression.label(
                "cosine_distance"
            ),
        )
        .join(
            Document,
            Document.id
            == DocumentChunk.document_id,
        )
        .join(
            DocumentProcessingRun,
            DocumentProcessingRun.id
            == DocumentChunk.processing_run_id,
        )
        .join(
            latest_completed_runs,
            and_(
                latest_completed_runs.c.document_id
                == DocumentProcessingRun.document_id,
                latest_completed_runs.c.attempt_number
                == DocumentProcessingRun.attempt_number,
            ),
        )
        .where(
            DocumentChunk.workspace_id
            == workspace_id,
            Document.workspace_id
            == workspace_id,
            DocumentProcessingRun.workspace_id
            == workspace_id,
            DocumentChunk.status
            == "ready",
            DocumentChunk.embedding.is_not(
                None
            ),
            cosine_distance_expression
            <= maximum_cosine_distance,
        )
        .order_by(
            cosine_distance_expression.asc(),
            DocumentChunk.document_id.asc(),
            DocumentChunk.chunk_index.asc(),
        )
        .limit(
            resolved_top_k
        )
    )

    if resolved_document_ids:
        statement = statement.where(
            DocumentChunk.document_id.in_(
                resolved_document_ids
            )
        )

    try:
        rows = database_session.execute(
            statement
        ).all()
    except SQLAlchemyError as error:
        raise RAGSearchDatabaseError(
            "Semantic document search failed."
        ) from error

    search_hits = [
        build_rag_search_hit(
            chunk=row[0],
            document_name=str(row[1]),
            cosine_distance=float(row[2]),
        )
        for row in rows
    ]

    return RAGSearchResult(
        query=normalized_query,
        top_k=resolved_top_k,
        minimum_similarity=(
            resolved_minimum_similarity
        ),
        embedding_provider=(
            query_embedding.provider
        ),
        embedding_model=(
            query_embedding.model_name
        ),
        embedding_dimensions=(
            query_embedding.dimensions
        ),
        items=search_hits,
    )