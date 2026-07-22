export interface RAGSearchRequest {
  query: string;
  top_k?: number;
  minimum_similarity?: number;
  document_ids?: string[];
}


export interface RAGSearchHit {
  chunk_id: string;
  workspace_id: string;
  document_id: string;
  document_name: string;
  processing_run_id: string;
  document_page_id: string;

  chunk_index: number;
  page_number: number;

  start_character: number;
  end_character: number;

  text_content: string;

  similarity_score: number;
  cosine_distance: number;

  embedding_provider: string | null;
  embedding_model: string | null;
  embedding_dimensions: number | null;

  extra_metadata: Record<string, unknown>;
}


export interface RAGSearchResponse {
  query: string;
  top_k: number;
  minimum_similarity: number;
  result_count: number;

  embedding_provider: string;
  embedding_model: string;
  embedding_dimensions: number;

  items: RAGSearchHit[];
}


export interface RAGAnswerRequest {
  question: string;
  top_k?: number;
  maximum_citations?: number;
  minimum_similarity?: number;
  document_ids?: string[];
}


export interface RAGCitation {
  citation_number: number;

  chunk_id: string;
  workspace_id: string;
  document_id: string;
  document_name: string;
  processing_run_id: string;
  document_page_id: string;

  chunk_index: number;
  page_number: number;

  start_character: number;
  end_character: number;

  excerpt: string;
  similarity_score: number;
  cosine_distance: number;

  extra_metadata: Record<string, unknown>;
}


export interface RAGAnswerResponse {
  question: string;
  answer: string;

  is_grounded: boolean;
  confidence_score: number;

  retrieved_chunk_count: number;
  citation_count: number;

  embedding_provider: string;
  embedding_model: string;
  embedding_dimensions: number;

  citations: RAGCitation[];
}