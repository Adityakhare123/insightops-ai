from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)


class RAGSearchRequest(BaseModel):
    """Workspace-isolated semantic-search request."""

    query: str = Field(
        min_length=2,
        max_length=4_000,
    )

    top_k: int | None = Field(
        default=None,
        ge=1,
        le=100,
    )

    minimum_similarity: float = Field(
        default=0.0,
        ge=-1.0,
        le=1.0,
    )

    document_ids: list[UUID] = Field(
        default_factory=list,
        max_length=100,
    )

    @field_validator(
        "query",
    )
    @classmethod
    def normalize_query(
        cls,
        value: str,
    ) -> str:
        normalized_value = " ".join(
            value.split()
        ).strip()

        if len(normalized_value) < 2:
            raise ValueError(
                "Query must contain at least "
                "two characters."
            )

        return normalized_value


class RAGSearchHitRead(BaseModel):
    """One semantically retrieved document chunk."""

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

    extra_metadata: dict[str, Any]


class RAGSearchResponse(BaseModel):
    """Semantic-search response with model provenance."""

    query: str
    top_k: int
    minimum_similarity: float
    result_count: int

    embedding_provider: str
    embedding_model: str
    embedding_dimensions: int

    items: list[RAGSearchHitRead]


class RAGAnswerRequest(BaseModel):
    """Request for a grounded answer from indexed documents."""

    question: str = Field(
        min_length=2,
        max_length=4_000,
    )

    top_k: int | None = Field(
        default=None,
        ge=1,
        le=100,
    )

    maximum_citations: int = Field(
        default=4,
        ge=1,
        le=10,
    )

    minimum_similarity: float = Field(
        default=0.0,
        ge=-1.0,
        le=1.0,
    )

    document_ids: list[UUID] = Field(
        default_factory=list,
        max_length=100,
    )

    @field_validator(
        "question",
    )
    @classmethod
    def normalize_question(
        cls,
        value: str,
    ) -> str:
        normalized_value = " ".join(
            value.split()
        ).strip()

        if len(normalized_value) < 2:
            raise ValueError(
                "Question must contain at least "
                "two characters."
            )

        return normalized_value


class RAGCitationRead(BaseModel):
    """Numbered citation supporting a grounded answer."""

    citation_number: int = Field(
        ge=1,
    )

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

    excerpt: str
    similarity_score: float
    cosine_distance: float

    extra_metadata: dict[str, Any]


class RAGAnswerResponse(BaseModel):
    """Grounded answer with explicit source citations."""

    question: str
    answer: str

    is_grounded: bool

    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
    )

    retrieved_chunk_count: int = Field(
        ge=0,
    )

    citation_count: int = Field(
        ge=0,
    )

    embedding_provider: str
    embedding_model: str
    embedding_dimensions: int

    citations: list[RAGCitationRead]