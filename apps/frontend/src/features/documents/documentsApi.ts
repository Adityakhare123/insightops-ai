import {
  apiClient,
  apiRequest,
} from "../../api/client";

import type {
  DocumentDeleteResponse,
  DocumentListParameters,
  DocumentListResponse,
  DocumentPageListParameters,
  DocumentPageListResponse,
  DocumentProcessingRunListResponse,
  DocumentProcessingStartResponse,
  DocumentRead,
  DocumentUploadResponse,
  DownloadedDocument,
  ProcessingRunListParameters,
} from "../../types/document";


function createDocumentQueryString(
  parameters: DocumentListParameters = {},
): string {
  const searchParameters =
    new URLSearchParams();

  if (parameters.limit !== undefined) {
    searchParameters.set(
      "limit",
      String(parameters.limit),
    );
  }

  if (parameters.offset !== undefined) {
    searchParameters.set(
      "offset",
      String(parameters.offset),
    );
  }

  if (parameters.status) {
    searchParameters.set(
      "status",
      parameters.status,
    );
  }

  if (parameters.documentType) {
    searchParameters.set(
      "document_type",
      parameters.documentType,
    );
  }

  const queryString =
    searchParameters.toString();

  return queryString
    ? `?${queryString}`
    : "";
}


function createProcessingRunQueryString(
  parameters: ProcessingRunListParameters = {},
): string {
  const searchParameters =
    new URLSearchParams();

  if (parameters.limit !== undefined) {
    searchParameters.set(
      "limit",
      String(parameters.limit),
    );
  }

  if (parameters.offset !== undefined) {
    searchParameters.set(
      "offset",
      String(parameters.offset),
    );
  }

  const queryString =
    searchParameters.toString();

  return queryString
    ? `?${queryString}`
    : "";
}


function createDocumentPageQueryString(
  parameters: DocumentPageListParameters = {},
): string {
  const searchParameters =
    new URLSearchParams();

  if (parameters.processingRunId) {
    searchParameters.set(
      "processing_run_id",
      parameters.processingRunId,
    );
  }

  if (parameters.limit !== undefined) {
    searchParameters.set(
      "limit",
      String(parameters.limit),
    );
  }

  if (parameters.offset !== undefined) {
    searchParameters.set(
      "offset",
      String(parameters.offset),
    );
  }

  const queryString =
    searchParameters.toString();

  return queryString
    ? `?${queryString}`
    : "";
}


export function listDocuments(
  parameters: DocumentListParameters = {},
): Promise<DocumentListResponse> {
  const queryString =
    createDocumentQueryString(parameters);

  return apiClient.get<DocumentListResponse>(
    `/documents${queryString}`,
  );
}


export function getDocument(
  documentId: string,
): Promise<DocumentRead> {
  return apiClient.get<DocumentRead>(
    `/documents/${documentId}`,
  );
}


export function uploadDocument(
  file: File,
): Promise<DocumentUploadResponse> {
  const formData = new FormData();

  formData.append(
    "file",
    file,
    file.name,
  );

  return apiRequest<DocumentUploadResponse>(
    "/documents/upload",
    {
      method: "POST",
      body: formData,
    },
  );
}


export function processDocument(
  documentId: string,
  ocrLanguage = "eng",
): Promise<DocumentProcessingStartResponse> {
  const searchParameters =
    new URLSearchParams({
      ocr_language: ocrLanguage,
    });

  return apiRequest<DocumentProcessingStartResponse>(
    (
      `/documents/${documentId}/process`
      + `?${searchParameters.toString()}`
    ),
    {
      method: "POST",
    },
  );
}


export function listDocumentProcessingRuns(
  documentId: string,
  parameters: ProcessingRunListParameters = {},
): Promise<DocumentProcessingRunListResponse> {
  const queryString =
    createProcessingRunQueryString(
      parameters,
    );

  return apiClient.get<DocumentProcessingRunListResponse>(
    (
      `/documents/${documentId}`
      + `/processing-runs${queryString}`
    ),
  );
}


export function listDocumentPages(
  documentId: string,
  parameters: DocumentPageListParameters = {},
): Promise<DocumentPageListResponse> {
  const queryString =
    createDocumentPageQueryString(
      parameters,
    );

  return apiClient.get<DocumentPageListResponse>(
    (
      `/documents/${documentId}`
      + `/pages${queryString}`
    ),
  );
}


export function deleteDocument(
  documentId: string,
): Promise<DocumentDeleteResponse> {
  return apiClient.delete<DocumentDeleteResponse>(
    `/documents/${documentId}`,
  );
}


export async function downloadDocument(
  document: DocumentRead,
): Promise<DownloadedDocument> {
  const downloadedFile =
    await apiClient.download(
      `/documents/${document.id}/download`,
    );

  return {
    blob: downloadedFile.blob,
    filename:
      downloadedFile.filename
      ?? document.original_filename,
    contentType:
      downloadedFile.contentType,
  };
}


export function saveDownloadedDocument(
  downloadedDocument: DownloadedDocument,
): void {
  const objectUrl = URL.createObjectURL(
    downloadedDocument.blob,
  );

  const downloadLink =
    window.document.createElement("a");

  downloadLink.href = objectUrl;
  downloadLink.download =
    downloadedDocument.filename;

  window.document.body.appendChild(
    downloadLink,
  );

  downloadLink.click();
  downloadLink.remove();

  URL.revokeObjectURL(objectUrl);
}