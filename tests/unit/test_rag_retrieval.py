from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from apps.api.app.services.rag_retrieval import (
    InvalidRAGSearchError,
    build_rag_search_hit,
    cosine_distance_to_similarity,
    normalize_document_ids,
    normalize_rag_query,
    resolve_rag_top_k,
    validate_minimum_similarity,
)


def test_query_is_normalized() -> None:
    assert normalize_rag_query(
        "  active   insurance\npolicies "
    ) == "active insurance policies"


def test_blank_query_is_rejected() -> None:
    with pytest.raises(
        InvalidRAGSearchError,
        match="cannot be empty",
    ):
        normalize_rag_query("   ")


def test_short_query_is_rejected() -> None:
    with pytest.raises(
        InvalidRAGSearchError,
        match="at least two",
    ):
        normalize_rag_query("a")


def test_top_k_is_validated() -> None:
    assert resolve_rag_top_k(5) == 5

    with pytest.raises(
        InvalidRAGSearchError,
        match="greater than",
    ):
        resolve_rag_top_k(0)


def test_similarity_is_validated() -> None:
    assert (
        validate_minimum_similarity(0.4)
        == 0.4
    )

    with pytest.raises(
        InvalidRAGSearchError,
        match="between",
    ):
        validate_minimum_similarity(1.5)


def test_cosine_distance_becomes_similarity() -> None:
    assert (
        cosine_distance_to_similarity(0.0)
        == 1.0
    )

    assert (
        cosine_distance_to_similarity(0.25)
        == 0.75
    )

    assert (
        cosine_distance_to_similarity(1.0)
        == 0.0
    )


def test_document_ids_are_deduplicated() -> None:
    first_id = uuid4()
    second_id = uuid4()

    assert normalize_document_ids(
        [
            first_id,
            second_id,
            first_id,
        ]
    ) == [
        first_id,
        second_id,
    ]


def test_search_hit_preserves_provenance() -> None:
    chunk = SimpleNamespace(
        id=uuid4(),
        workspace_id=uuid4(),
        document_id=uuid4(),
        processing_run_id=uuid4(),
        document_page_id=uuid4(),
        chunk_index=3,
        page_number=2,
        start_character=100,
        end_character=250,
        text_content=(
            "Policy POL-1001 is active."
        ),
        embedding_provider="fastembed",
        embedding_model=(
            "BAAI/bge-small-en-v1.5"
        ),
        embedding_dimensions=384,
        extra_metadata={
            "source_page_number": 2,
        },
    )

    hit = build_rag_search_hit(
        chunk=chunk,
        document_name="policies.pdf",
        cosine_distance=0.15,
    )

    assert hit.chunk_id == chunk.id
    assert hit.document_id == (
        chunk.document_id
    )

    assert hit.document_name == (
        "policies.pdf"
    )

    assert hit.page_number == 2
    assert hit.chunk_index == 3

    assert hit.similarity_score == 0.85
    assert hit.cosine_distance == 0.15

    assert hit.embedding_dimensions == 384