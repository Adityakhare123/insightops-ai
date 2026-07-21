import {
  apiClient,
  apiRequest,
} from "../../api/client";

import type {
  DocumentDeleteResponse,
  DocumentListParameters,
  DocumentListResponse,
  DocumentRead,
  DocumentUploadResponse,
  DownloadedDocument,
} from "../../types/document";


function createDocumentQueryString(
  parameters: DocumentListParameters = {},
): string {
  const searchParameters = new URLSearchParams();

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