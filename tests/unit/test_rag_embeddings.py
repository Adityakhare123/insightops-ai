from __future__ import annotations

from typing import Any, Iterable

import pytest

from apps.api.app.db.models.document_chunk import (
    DOCUMENT_CHUNK_EMBEDDING_DIMENSIONS,
)
from apps.api.app.services.rag_embeddings import (
    EMBEDDING_PROVIDER_NAME,
    EmbeddingDimensionError,
    EmbeddingGenerationError,
    InvalidEmbeddingInputError,
    embed_passages,
    embed_query,
    normalize_embedding_vector,
)


DIMENSIONS = (
    DOCUMENT_CHUNK_EMBEDDING_DIMENSIONS
)


class FakeEmbeddingModel:
    def __init__(
        self,
        *,
        passage_dimensions: int = DIMENSIONS,
        query_dimensions: int = DIMENSIONS,
        passage_count_override: int | None = None,
    ) -> None:
        self.passage_dimensions = (
            passage_dimensions
        )

        self.query_dimensions = (
            query_dimensions
        )

        self.passage_count_override = (
            passage_count_override
        )

        self.received_passages: list[str] = []
        self.received_batch_size: int | None = None
        self.received_query: str | None = None

    def passage_embed(
        self,
        documents: str | Iterable[str],
        batch_size: int = 256,
        **kwargs: Any,
    ) -> Iterable[list[float]]:
        del kwargs

        if isinstance(documents, str):
            document_list = [documents]
        else:
            document_list = list(documents)

        self.received_passages = (
            document_list
        )

        self.received_batch_size = (
            batch_size
        )

        vector_count = (
            self.passage_count_override
            if self.passage_count_override
            is not None
            else len(document_list)
        )

        for index in range(vector_count):
            yield [
                float(index + 1)
                / self.passage_dimensions
                for _ in range(
                    self.passage_dimensions
                )
            ]

    def query_embed(
        self,
        query: str | Iterable[str],
        **kwargs: Any,
    ) -> Iterable[list[float]]:
        del kwargs

        if isinstance(query, str):
            self.received_query = query
        else:
            query_items = list(query)
            self.received_query = (
                query_items[0]
                if query_items
                else None
            )

        yield [
            0.25
            for _ in range(
                self.query_dimensions
            )
        ]


def test_passage_embeddings_are_generated() -> None:
    fake_model = FakeEmbeddingModel()

    result = embed_passages(
        [
            "Policy POL-1001 is active.",
            "Customer Jane Doe has paid.",
        ],
        batch_size=8,
        embedding_model=fake_model,
    )

    assert result.provider == (
        EMBEDDING_PROVIDER_NAME
    )

    assert result.dimensions == DIMENSIONS
    assert result.count == 2
    assert len(result.vectors[0]) == DIMENSIONS

    assert fake_model.received_passages == [
        "Policy POL-1001 is active.",
        "Customer Jane Doe has paid.",
    ]

    assert (
        fake_model.received_batch_size
        == 8
    )


def test_query_embedding_is_generated() -> None:
    fake_model = FakeEmbeddingModel()

    result = embed_query(
        "Which policies are active?",
        embedding_model=fake_model,
    )

    assert result.count == 1
    assert result.dimensions == DIMENSIONS

    assert len(
        result.vectors[0]
    ) == DIMENSIONS

    assert fake_model.received_query == (
        "Which policies are active?"
    )


def test_passage_whitespace_is_normalized() -> None:
    fake_model = FakeEmbeddingModel()

    embed_passages(
        [
            "  Policy   POL-1001\n"
            "is active.  ",
        ],
        embedding_model=fake_model,
    )

    assert fake_model.received_passages == [
        "Policy POL-1001 is active."
    ]


def test_empty_passage_collection_is_allowed() -> None:
    result = embed_passages(
        [],
        embedding_model=(
            FakeEmbeddingModel()
        ),
    )

    assert result.count == 0
    assert result.vectors == []


def test_blank_passage_is_rejected() -> None:
    with pytest.raises(
        InvalidEmbeddingInputError,
        match="cannot be empty",
    ):
        embed_passages(
            ["   \n  "],
            embedding_model=(
                FakeEmbeddingModel()
            ),
        )


def test_single_string_passage_input_is_rejected() -> None:
    with pytest.raises(
        InvalidEmbeddingInputError,
        match="iterable of strings",
    ):
        embed_passages(
            "This should be a list.",
            embedding_model=(
                FakeEmbeddingModel()
            ),
        )


def test_blank_query_is_rejected() -> None:
    with pytest.raises(
        InvalidEmbeddingInputError,
        match="query cannot be empty",
    ):
        embed_query(
            "   ",
            embedding_model=(
                FakeEmbeddingModel()
            ),
        )


def test_dimension_mismatch_is_rejected() -> None:
    fake_model = FakeEmbeddingModel(
        passage_dimensions=10,
    )

    with pytest.raises(
        EmbeddingDimensionError,
        match="expected 384",
    ):
        embed_passages(
            ["Policy text"],
            embedding_model=fake_model,
        )


def test_unexpected_vector_count_is_rejected() -> None:
    fake_model = FakeEmbeddingModel(
        passage_count_override=1,
    )

    with pytest.raises(
        EmbeddingGenerationError,
        match="unexpected number",
    ):
        embed_passages(
            [
                "First policy",
                "Second policy",
            ],
            embedding_model=fake_model,
        )


def test_non_finite_vector_is_rejected() -> None:
    raw_vector = [
        0.1
        for _ in range(DIMENSIONS)
    ]

    raw_vector[10] = float("nan")

    with pytest.raises(
        EmbeddingGenerationError,
        match="non-finite",
    ):
        normalize_embedding_vector(
            raw_vector,
            expected_dimensions=DIMENSIONS,
        )