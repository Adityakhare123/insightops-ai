from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
    status,
)

from apps.api.app.api.deps import (
    CurrentUser,
    DatabaseSession,
)
from apps.api.app.schemas.rag import (
    RAGAnswerRequest,
    RAGAnswerResponse,
    RAGCitationRead,
    RAGSearchHitRead,
    RAGSearchRequest,
    RAGSearchResponse,
)
from apps.api.app.services.rag_answering import (
    InvalidRAGAnswerRequestError,
    RAGAnsweringError,
    answer_document_question,
)
from apps.api.app.services.rag_embeddings import (
    EmbeddingServiceError,
)
from apps.api.app.services.rag_retrieval import (
    InvalidRAGSearchError,
    RAGRetrievalError,
    RAGSearchDatabaseError,
    search_document_chunks,
)


router = APIRouter()


@router.post(
    "/search",
    response_model=RAGSearchResponse,
)
def semantic_document_search(
    request: RAGSearchRequest,
    current_user: CurrentUser,
    database_session: DatabaseSession,
) -> RAGSearchResponse:
    """Search indexed chunks in the current workspace."""

    try:
        search_result = search_document_chunks(
            database_session,
            workspace_id=(
                current_user.workspace_id
            ),
            query=request.query,
            top_k=request.top_k,
            minimum_similarity=(
                request.minimum_similarity
            ),
            document_ids=(
                request.document_ids
            ),
        )
    except InvalidRAGSearchError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except EmbeddingServiceError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The query embedding could not "
                "be generated."
            ),
        ) from error
    except RAGSearchDatabaseError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Semantic document search failed."
            ),
        ) from error
    except RAGRetrievalError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=str(error),
        ) from error

    return RAGSearchResponse(
        query=search_result.query,
        top_k=search_result.top_k,
        minimum_similarity=(
            search_result.minimum_similarity
        ),
        result_count=(
            search_result.result_count
        ),
        embedding_provider=(
            search_result.embedding_provider
        ),
        embedding_model=(
            search_result.embedding_model
        ),
        embedding_dimensions=(
            search_result.embedding_dimensions
        ),
        items=[
            RAGSearchHitRead(
                chunk_id=item.chunk_id,
                workspace_id=(
                    item.workspace_id
                ),
                document_id=(
                    item.document_id
                ),
                document_name=(
                    item.document_name
                ),
                processing_run_id=(
                    item.processing_run_id
                ),
                document_page_id=(
                    item.document_page_id
                ),
                chunk_index=(
                    item.chunk_index
                ),
                page_number=(
                    item.page_number
                ),
                start_character=(
                    item.start_character
                ),
                end_character=(
                    item.end_character
                ),
                text_content=(
                    item.text_content
                ),
                similarity_score=(
                    item.similarity_score
                ),
                cosine_distance=(
                    item.cosine_distance
                ),
                embedding_provider=(
                    item.embedding_provider
                ),
                embedding_model=(
                    item.embedding_model
                ),
                embedding_dimensions=(
                    item.embedding_dimensions
                ),
                extra_metadata=(
                    item.extra_metadata
                ),
            )
            for item in search_result.items
        ],
    )


@router.post(
    "/answer",
    response_model=RAGAnswerResponse,
)
def answer_document_question_endpoint(
    request: RAGAnswerRequest,
    current_user: CurrentUser,
    database_session: DatabaseSession,
) -> RAGAnswerResponse:
    """Answer a question using indexed workspace documents."""

    try:
        grounded_answer = (
            answer_document_question(
                database_session,
                workspace_id=(
                    current_user.workspace_id
                ),
                question=request.question,
                top_k=request.top_k,
                maximum_citations=(
                    request.maximum_citations
                ),
                minimum_similarity=(
                    request.minimum_similarity
                ),
                document_ids=(
                    request.document_ids
                ),
            )
        )
    except InvalidRAGAnswerRequestError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except InvalidRAGSearchError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except EmbeddingServiceError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The question embedding could not "
                "be generated."
            ),
        ) from error
    except RAGSearchDatabaseError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Grounded document retrieval failed."
            ),
        ) from error
    except (
        RAGAnsweringError,
        RAGRetrievalError,
    ) as error:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=str(error),
        ) from error

    return RAGAnswerResponse(
        question=grounded_answer.question,
        answer=grounded_answer.answer,
        is_grounded=(
            grounded_answer.is_grounded
        ),
        confidence_score=(
            grounded_answer.confidence_score
        ),
        retrieved_chunk_count=(
            grounded_answer.retrieved_chunk_count
        ),
        citation_count=(
            grounded_answer.citation_count
        ),
        embedding_provider=(
            grounded_answer.embedding_provider
        ),
        embedding_model=(
            grounded_answer.embedding_model
        ),
        embedding_dimensions=(
            grounded_answer.embedding_dimensions
        ),
        citations=[
            RAGCitationRead(
                citation_number=(
                    citation.citation_number
                ),
                chunk_id=(
                    citation.chunk_id
                ),
                workspace_id=(
                    citation.workspace_id
                ),
                document_id=(
                    citation.document_id
                ),
                document_name=(
                    citation.document_name
                ),
                processing_run_id=(
                    citation.processing_run_id
                ),
                document_page_id=(
                    citation.document_page_id
                ),
                chunk_index=(
                    citation.chunk_index
                ),
                page_number=(
                    citation.page_number
                ),
                start_character=(
                    citation.start_character
                ),
                end_character=(
                    citation.end_character
                ),
                excerpt=(
                    citation.excerpt
                ),
                similarity_score=(
                    citation.similarity_score
                ),
                cosine_distance=(
                    citation.cosine_distance
                ),
                extra_metadata=(
                    citation.extra_metadata
                ),
            )
            for citation
            in grounded_answer.citations
        ],
    )