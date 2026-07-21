export type DocumentStatus =
  | "uploaded"
  | "queued"
  | "processing"
  | "processed"
  | "failed";

export type DocumentType =
  | "pdf"
  | "image"
  | "spreadsheet"
  | "data";

export type DocumentProcessingRunStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed";

export type DocumentPageStatus =
  | "pending"
  | "processing"
  | "completed"
  | "failed";


export interface DocumentRead {
  id: string;
  workspace_id: string;
  uploaded_by_user_id: string;

  original_filename: string;
  content_type: string;
  file_extension: string | null;
  file_size_bytes: number;
  checksum_sha256: string;

  source: string;
  document_type: string | null;
  status: DocumentStatus;

  processing_error: string | null;
  page_count: number | null;
  extra_metadata: Record<string, unknown>;

  created_at: string;
  updated_at: string;
}


export interface DocumentUploadResponse {
  message: string;
  document: DocumentRead;
}


export interface DocumentListResponse {
  items: DocumentRead[];
  total: number;
  limit: number;
  offset: number;
}


export interface DocumentDeleteResponse {
  message: string;
  document_id: string;
}


export interface DocumentListParameters {
  limit?: number;
  offset?: number;
  status?: DocumentStatus;
  documentType?: DocumentType;
}


export interface DownloadedDocument {
  blob: Blob;
  filename: string;
  contentType: string;
}


export interface DocumentProcessingRunRead {
  id: string;
  workspace_id: string;
  document_id: string;
  requested_by_user_id: string | null;

  attempt_number: number;
  status: DocumentProcessingRunStatus;

  processor_name: string;
  processor_version: string | null;

  started_at: string | null;
  completed_at: string | null;

  total_pages: number | null;
  extracted_pages: number;

  error_message: string | null;
  extra_metadata: Record<string, unknown>;

  created_at: string;
  updated_at: string;
}


export interface DocumentProcessingStartResponse {
  message: string;
  task_id: string;
  processing_run: DocumentProcessingRunRead;
}


export interface DocumentProcessingRunListResponse {
  items: DocumentProcessingRunRead[];
  total: number;
  limit: number;
  offset: number;
}


export interface DocumentPageRead {
  id: string;
  workspace_id: string;
  document_id: string;
  processing_run_id: string;

  page_number: number;
  status: DocumentPageStatus;

  extraction_method: string | null;
  language_code: string | null;

  text_content: string | null;
  confidence_score: number | null;

  character_count: number;
  word_count: number;

  error_message: string | null;
  extra_metadata: Record<string, unknown>;

  created_at: string;
  updated_at: string;
}


export interface DocumentPageListResponse {
  processing_run_id: string | null;
  items: DocumentPageRead[];
  total: number;
  limit: number;
  offset: number;
}


export interface ProcessingRunListParameters {
  limit?: number;
  offset?: number;
}


export interface DocumentPageListParameters {
  processingRunId?: string;
  limit?: number;
  offset?: number;
}