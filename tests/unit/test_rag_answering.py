from __future__ import annotations

from uuid import uuid4

import pytest

from apps.api.app.services.rag_answering import (
    InvalidRAGAnswerRequestError,
    build_grounded_answer,
    calculate_answer_confidence,
    extract_best_answer_excerpt,
    resolve_max_citations,
    tokenize_answer_text,
)
from apps.api.app.services.rag_retrieval import (
    RAGSearchHit,
    RAGSearchResult,
)


def create_search_hit(
    *,
    text_content: str,
    similarity_score: float = 0.85,
    page_number: int = 1,
) -> RAGSearchHit:
    return RAGSearchHit(
        chunk_id=uuid4(),
        workspace_id=uuid4(),
        document_id=uuid4(),
        document_name="policy-record.pdf",
        processing_run_id=uuid4(),
        document_page_id=uuid4(),
        chunk_index=0,
        page_number=page_number,
        start_character=0,
        end_character=len(
            text_content
        ),
        text_content=text_content,
        similarity_score=similarity_score,
        cosine_distance=(
            1.0 - similarity_score
        ),
        embedding_provider="fastembed",
        embedding_model=(
            "BAAI/bge-small-en-v1.5"
        ),
        embedding_dimensions=384,
        extra_metadata={},
    )


def create_search_result(
    hits: list[RAGSearchHit],
) -> RAGSearchResult:
    return RAGSearchResult(
        query=(
            "What is Jane Doe's policy number?"
        ),
        top_k=8,
        minimum_similarity=0.0,
        embedding_provider="fastembed",
        embedding_model=(
            "BAAI/bge-small-en-v1.5"
        ),
        embedding_dimensions=384,
        items=hits,
    )


def test_answer_tokens_remove_stop_words() -> None:
    tokens = tokenize_answer_text(
        "What is the policy number for Jane Doe?"
    )

    assert "policy" in tokens
    assert "number" in tokens
    assert "jane" in tokens
    assert "doe" in tokens

    assert "what" not in tokens
    assert "the" not in tokens


def test_best_excerpt_prefers_question_terms() -> None:
    hit = create_search_hit(
        text_content=(
            "The customer enrolled yesterday. "
            "Jane Doe has policy number "
            "POL-ASYNC-2026. "
            "The policy is active."
        ),
    )

    excerpt = extract_best_answer_excerpt(
        question=(
            "What is Jane Doe's policy number?"
        ),
        search_hit=hit,
    )

    assert "Jane Doe" in excerpt
    assert "POL-ASYNC-2026" in excerpt


def test_grounded_answer_contains_numbered_citation() -> None:
    hit = create_search_hit(
        text_content=(
            "Jane Doe has policy number "
            "POL-ASYNC-2026."
        ),
    )

    answer = build_grounded_answer(
        question=(
            "What is Jane Doe's policy number?"
        ),
        search_result=create_search_result(
            [hit]
        ),
        max_citations=4,
    )

    assert answer.is_grounded is True
    assert answer.citation_count == 1
    assert answer.retrieved_chunk_count == 1

    assert "POL-ASYNC-2026" in (
        answer.answer
    )

    assert "[1]" in answer.answer

    assert (
        answer.citations[0].document_name
        == "policy-record.pdf"
    )

    assert (
        answer.citations[0].page_number
        == 1
    )


def test_no_hits_returns_safe_fallback() -> None:
    answer = build_grounded_answer(
        question=(
            "What is Jane Doe's policy number?"
        ),
        search_result=create_search_result(
            []
        ),
        max_citations=4,
    )

    assert answer.is_grounded is False
    assert answer.citation_count == 0
    assert answer.confidence_score == 0.0

    assert (
        "could not find enough relevant information"
        in answer.answer
    )


def test_citation_limit_is_enforced() -> None:
    hits = [
        create_search_hit(
            text_content=(
                f"Policy record {index} "
                f"belongs to Jane Doe."
            ),
            page_number=index + 1,
        )
        for index in range(5)
    ]

    answer = build_grounded_answer(
        question=(
            "Which policies belong to Jane Doe?"
        ),
        search_result=create_search_result(
            hits
        ),
        max_citations=2,
    )

    assert answer.citation_count == 2
    assert len(answer.citations) == 2

    assert "[1]" in answer.answer
    assert "[2]" in answer.answer
    assert "[3]" not in answer.answer


def test_answer_confidence_is_bounded() -> None:
    hit = create_search_hit(
        text_content="Policy content.",
        similarity_score=0.75,
    )

    answer = build_grounded_answer(
        question="What is the policy?",
        search_result=create_search_result(
            [hit]
        ),
        max_citations=1,
    )

    assert (
        calculate_answer_confidence(
            answer.citations
        )
        == 0.75
    )


@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
        11,
    ],
)
def test_invalid_citation_limit_is_rejected(
    value: int,
) -> None:
    with pytest.raises(
        InvalidRAGAnswerRequestError,
    ):
        resolve_max_citations(
            value
        )