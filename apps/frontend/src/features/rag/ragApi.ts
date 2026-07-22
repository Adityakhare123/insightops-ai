import {
  apiRequest,
} from "../../api/client";

import type {
  RAGAnswerRequest,
  RAGAnswerResponse,
  RAGSearchRequest,
  RAGSearchResponse,
} from "../../types/rag";


export function searchDocumentChunks(
  request: RAGSearchRequest,
): Promise<RAGSearchResponse> {
  return apiRequest<RAGSearchResponse>(
    "/rag/search",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    },
  );
}


export function answerDocumentQuestion(
  request: RAGAnswerRequest,
): Promise<RAGAnswerResponse> {
  return apiRequest<RAGAnswerResponse>(
    "/rag/answer",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    },
  );
}