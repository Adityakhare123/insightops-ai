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
  status: string;

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