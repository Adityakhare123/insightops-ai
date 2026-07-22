from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from math import isfinite
from pathlib import Path
from typing import Any, Iterable, Protocol

from fastembed import TextEmbedding

from apps.api.app.core.config import settings
from apps.api.app.db.models.document_chunk import (
    DOCUMENT_CHUNK_EMBEDDING_DIMENSIONS,
)


EMBEDDING_PROVIDER_NAME = "fastembed"


class EmbeddingServiceError(RuntimeError):
    """Base exception for embedding-generation failures."""


class InvalidEmbeddingInputError(
    EmbeddingServiceError,
):
    """Raised when embedding input is empty or invalid."""


class EmbeddingDimensionError(
    EmbeddingServiceError,
):
    """Raised when a vector has an unexpected dimension."""


class EmbeddingGenerationError(
    EmbeddingServiceError,
):
    """Raised when the embedding model cannot generate vectors."""


class DenseEmbeddingModel(Protocol):
    """Minimum embedding-model interface used by this service."""

    def passage_embed(
        self,
        documents: str | Iterable[str],
        batch_size: int = 256,
        **kwargs: Any,
    ) -> Iterable[Any]:
        """Generate passage embeddings."""

    def query_embed(
        self,
        query: str | Iterable[str],
        **kwargs: Any,
    ) -> Iterable[Any]:
        """Generate query embeddings."""


@dataclass(frozen=True)
class EmbeddingBatch:
    """Generated embeddings with model provenance."""

    provider: str
    model_name: str
    dimensions: int
    vectors: list[list[float]]

    @property
    def count(self) -> int:
        return len(self.vectors)


def normalize_embedding_text(
    text: str,
    *,
    input_name: str,
) -> str:
    """Normalize and validate one embedding input."""

    normalized_text = " ".join(
        text.split()
    ).strip()

    if not normalized_text:
        raise InvalidEmbeddingInputError(
            f"{input_name} cannot be empty."
        )

    return normalized_text


def normalize_passage_inputs(
    passages: Iterable[str],
) -> list[str]:
    """Normalize and validate a passage collection."""

    if isinstance(passages, str):
        raise InvalidEmbeddingInputError(
            "passages must be an iterable of strings, "
            "not one string."
        )

    normalized_passages: list[str] = []

    for index, passage in enumerate(passages):
        if not isinstance(passage, str):
            raise InvalidEmbeddingInputError(
                f"passages[{index}] must be a string."
            )

        normalized_passages.append(
            normalize_embedding_text(
                passage,
                input_name=f"passages[{index}]",
            )
        )

    return normalized_passages


def normalize_embedding_vector(
    raw_vector: Iterable[Any],
    *,
    expected_dimensions: int,
) -> list[float]:
    """Convert and validate one generated vector."""

    try:
        vector = [
            float(value)
            for value in raw_vector
        ]
    except (
        TypeError,
        ValueError,
    ) as error:
        raise EmbeddingGenerationError(
            "The embedding model returned "
            "a non-numeric vector."
        ) from error

    if len(vector) != expected_dimensions:
        raise EmbeddingDimensionError(
            "Embedding dimension mismatch: "
            f"expected {expected_dimensions}, "
            f"received {len(vector)}."
        )

    if not all(
        isfinite(value)
        for value in vector
    ):
        raise EmbeddingGenerationError(
            "The embedding vector contains "
            "a non-finite numeric value."
        )

    return vector


def validate_embedding_configuration(
    *,
    model_name: str,
    dimensions: int,
    batch_size: int,
) -> None:
    """Validate model and embedding configuration."""

    if not model_name.strip():
        raise InvalidEmbeddingInputError(
            "model_name cannot be empty."
        )

    if dimensions <= 0:
        raise EmbeddingDimensionError(
            "dimensions must be greater than zero."
        )

    if batch_size <= 0:
        raise InvalidEmbeddingInputError(
            "batch_size must be greater than zero."
        )

    if (
        dimensions
        != DOCUMENT_CHUNK_EMBEDDING_DIMENSIONS
    ):
        raise EmbeddingDimensionError(
            "Configured embedding dimensions do not "
            "match the document_chunks vector column: "
            f"{dimensions} != "
            f"{DOCUMENT_CHUNK_EMBEDDING_DIMENSIONS}."
        )


@lru_cache(maxsize=4)
def get_embedding_model(
    *,
    model_name: str,
    cache_directory: str,
) -> TextEmbedding:
    """Load and cache a local FastEmbed model."""

    normalized_model_name = model_name.strip()

    if not normalized_model_name:
        raise InvalidEmbeddingInputError(
            "model_name cannot be empty."
        )

    model_cache_path = Path(
        cache_directory
    )

    model_cache_path.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        return TextEmbedding(
            model_name=normalized_model_name,
            cache_dir=str(model_cache_path),
        )
    except Exception as error:
        raise EmbeddingGenerationError(
            "The embedding model could not be "
            "loaded or initialized."
        ) from error


def embed_passages(
    passages: Iterable[str],
    *,
    model_name: str | None = None,
    dimensions: int | None = None,
    batch_size: int | None = None,
    cache_directory: str | None = None,
    embedding_model: DenseEmbeddingModel | None = None,
) -> EmbeddingBatch:
    """Generate embeddings for document chunks."""

    resolved_model_name = (
        model_name
        or settings.embedding_model_name
    )

    resolved_dimensions = (
        dimensions
        or settings.embedding_dimensions
    )

    resolved_batch_size = (
        batch_size
        or settings.embedding_batch_size
    )

    resolved_cache_directory = (
        cache_directory
        or settings.embedding_cache_directory
    )

    validate_embedding_configuration(
        model_name=resolved_model_name,
        dimensions=resolved_dimensions,
        batch_size=resolved_batch_size,
    )

    normalized_passages = (
        normalize_passage_inputs(passages)
    )

    if not normalized_passages:
        return EmbeddingBatch(
            provider=EMBEDDING_PROVIDER_NAME,
            model_name=resolved_model_name,
            dimensions=resolved_dimensions,
            vectors=[],
        )

    model = (
        embedding_model
        or get_embedding_model(
            model_name=resolved_model_name,
            cache_directory=(
                resolved_cache_directory
            ),
        )
    )

    try:
        raw_vectors = list(
            model.passage_embed(
                normalized_passages,
                batch_size=resolved_batch_size,
            )
        )
    except EmbeddingServiceError:
        raise
    except Exception as error:
        raise EmbeddingGenerationError(
            "Passage embeddings could not "
            "be generated."
        ) from error

    if (
        len(raw_vectors)
        != len(normalized_passages)
    ):
        raise EmbeddingGenerationError(
            "The embedding model returned an "
            "unexpected number of passage vectors: "
            f"expected {len(normalized_passages)}, "
            f"received {len(raw_vectors)}."
        )

    vectors = [
        normalize_embedding_vector(
            raw_vector,
            expected_dimensions=(
                resolved_dimensions
            ),
        )
        for raw_vector in raw_vectors
    ]

    return EmbeddingBatch(
        provider=EMBEDDING_PROVIDER_NAME,
        model_name=resolved_model_name,
        dimensions=resolved_dimensions,
        vectors=vectors,
    )


def embed_query(
    query: str,
    *,
    model_name: str | None = None,
    dimensions: int | None = None,
    cache_directory: str | None = None,
    embedding_model: DenseEmbeddingModel | None = None,
) -> EmbeddingBatch:
    """Generate one retrieval-query embedding."""

    resolved_model_name = (
        model_name
        or settings.embedding_model_name
    )

    resolved_dimensions = (
        dimensions
        or settings.embedding_dimensions
    )

    resolved_cache_directory = (
        cache_directory
        or settings.embedding_cache_directory
    )

    validate_embedding_configuration(
        model_name=resolved_model_name,
        dimensions=resolved_dimensions,
        batch_size=1,
    )

    normalized_query = normalize_embedding_text(
        query,
        input_name="query",
    )

    model = (
        embedding_model
        or get_embedding_model(
            model_name=resolved_model_name,
            cache_directory=(
                resolved_cache_directory
            ),
        )
    )

    try:
        raw_vectors = list(
            model.query_embed(
                normalized_query
            )
        )
    except EmbeddingServiceError:
        raise
    except Exception as error:
        raise EmbeddingGenerationError(
            "The query embedding could not "
            "be generated."
        ) from error

    if len(raw_vectors) != 1:
        raise EmbeddingGenerationError(
            "The embedding model returned an "
            "unexpected number of query vectors: "
            f"expected 1, received "
            f"{len(raw_vectors)}."
        )

    vector = normalize_embedding_vector(
        raw_vectors[0],
        expected_dimensions=(
            resolved_dimensions
        ),
    )

    return EmbeddingBatch(
        provider=EMBEDDING_PROVIDER_NAME,
        model_name=resolved_model_name,
        dimensions=resolved_dimensions,
        vectors=[vector],
    )