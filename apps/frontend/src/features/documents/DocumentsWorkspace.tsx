import {
  useState,
} from "react";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { ApiError } from "../../api/client";

import type {
  DocumentRead,
} from "../../types/document";

import ExtractionReview from "./ExtractionReview";

import {
  deleteDocument,
  downloadDocument,
  listDocuments,
  processDocument,
  saveDownloadedDocument,
} from "./documentsApi";


interface DocumentsWorkspaceProps {
  onUploadClick: () => void;
}


function formatFileSize(
  sizeInBytes: number,
): string {
  if (sizeInBytes < 1024) {
    return `${sizeInBytes} B`;
  }

  const kilobytes =
    sizeInBytes / 1024;

  if (kilobytes < 1024) {
    return `${kilobytes.toFixed(1)} KB`;
  }

  const megabytes =
    kilobytes / 1024;

  return `${megabytes.toFixed(2)} MB`;
}


function formatDocumentDate(
  dateValue: string,
): string {
  return new Intl.DateTimeFormat(
    "en",
    {
      dateStyle: "medium",
      timeStyle: "short",
    },
  ).format(new Date(dateValue));
}


function getDocumentTypeLabel(
  document: DocumentRead,
): string {
  if (document.document_type) {
    return document.document_type.replaceAll(
      "_",
      " ",
    );
  }

  return (
    document.file_extension
      ?.replace(".", "")
      .toUpperCase()
    ?? "Document"
  );
}


function getErrorMessage(
  error: unknown,
): string {
  if (error instanceof ApiError) {
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "An unexpected error occurred.";
}


function getProcessButtonLabel(
  document: DocumentRead,
): string {
  if (
    document.status === "queued"
    || document.status === "processing"
  ) {
    return "Processing…";
  }

  if (document.status === "processed") {
    return "Reprocess";
  }

  if (document.status === "failed") {
    return "Retry";
  }

  return "Process";
}


export default function DocumentsWorkspace({
  onUploadClick,
}: DocumentsWorkspaceProps) {
  const queryClient = useQueryClient();

  const [
    selectedDocumentId,
    setSelectedDocumentId,
  ] = useState<string | null>(null);

  const documentsQuery = useQuery({
    queryKey: ["documents"],
    queryFn: () =>
      listDocuments({
        limit: 100,
        offset: 0,
      }),
    refetchInterval: 3_000,
  });

  const downloadMutation = useMutation({
    mutationFn: downloadDocument,

    onSuccess: (
      downloadedDocument,
    ) => {
      saveDownloadedDocument(
        downloadedDocument,
      );
    },
  });

  const processMutation = useMutation({
    mutationFn: (
      documentId: string,
    ) => processDocument(
      documentId,
      "eng",
    ),

    onSuccess: async (
      _response,
      documentId,
    ) => {
      setSelectedDocumentId(
        documentId,
      );

      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["documents"],
        }),
        queryClient.invalidateQueries({
          queryKey: [
            "document-processing-runs",
            documentId,
          ],
        }),
        queryClient.invalidateQueries({
          queryKey: [
            "document-pages",
            documentId,
          ],
        }),
      ]);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteDocument,

    onSuccess: async (
      _response,
      documentId,
    ) => {
      if (
        selectedDocumentId
        === documentId
      ) {
        setSelectedDocumentId(null);
      }

      await queryClient.invalidateQueries({
        queryKey: ["documents"],
      });
    },
  });


  async function handleDelete(
    document: DocumentRead,
  ): Promise<void> {
    const shouldDelete = window.confirm(
      `Delete "${document.original_filename}"?`,
    );

    if (!shouldDelete) {
      return;
    }

    deleteMutation.mutate(
      document.id,
    );
  }


  function handleProcess(
    document: DocumentRead,
  ): void {
    if (
      document.status === "queued"
      || document.status === "processing"
    ) {
      setSelectedDocumentId(
        document.id,
      );

      return;
    }

    processMutation.mutate(
      document.id,
    );
  }


  const documents =
    documentsQuery.data?.items ?? [];

  const selectedDocument =
    documents.find(
      (document) =>
        document.id
        === selectedDocumentId,
    ) ?? null;

  const actionError =
    processMutation.isError
      ? getErrorMessage(
          processMutation.error,
        )
      : downloadMutation.isError
        ? getErrorMessage(
            downloadMutation.error,
          )
        : deleteMutation.isError
          ? getErrorMessage(
              deleteMutation.error,
            )
          : null;


  return (
    <section className="documents-workspace">
      <header className="documents-header">
        <div>
          <p className="dashboard-date">
            Document intelligence
          </p>

          <h1>Workspace documents</h1>

          <p>
            Upload, process, review, download,
            and manage source documents.
          </p>
        </div>

        <button
          className="dashboard-primary-action"
          type="button"
          onClick={onUploadClick}
        >
          Upload document
        </button>
      </header>

      <section className="documents-summary">
        <div>
          <span>Total documents</span>

          <strong>
            {documentsQuery.data?.total ?? 0}
          </strong>
        </div>

        <div>
          <span>Ready for processing</span>

          <strong>
            {
              documents.filter(
                (document) =>
                  document.status === "uploaded",
              ).length
            }
          </strong>
        </div>

        <div>
          <span>Processed</span>

          <strong>
            {
              documents.filter(
                (document) =>
                  document.status === "processed",
              ).length
            }
          </strong>
        </div>

        <div>
          <span>Failed</span>

          <strong>
            {
              documents.filter(
                (document) =>
                  document.status === "failed",
              ).length
            }
          </strong>
        </div>
      </section>

      {actionError && (
        <div
          className="documents-message error"
          role="alert"
        >
          {actionError}
        </div>
      )}

      <section className="documents-panel">
        <div className="documents-panel-header">
          <div>
            <p className="dashboard-panel-label">
              Source files
            </p>

            <h2>Uploaded documents</h2>
          </div>

          <button
            type="button"
            onClick={() => {
              void documentsQuery.refetch();
            }}
            disabled={
              documentsQuery.isFetching
            }
          >
            {
              documentsQuery.isFetching
                ? "Refreshing…"
                : "Refresh"
            }
          </button>
        </div>

        {documentsQuery.isPending && (
          <div className="documents-state">
            <strong>
              Loading documents…
            </strong>

            <p>
              Retrieving workspace files.
            </p>
          </div>
        )}

        {documentsQuery.isError && (
          <div className="documents-state error">
            <strong>
              Documents could not be loaded
            </strong>

            <p>
              {getErrorMessage(
                documentsQuery.error,
              )}
            </p>

            <button
              type="button"
              onClick={() => {
                void documentsQuery.refetch();
              }}
            >
              Try again
            </button>
          </div>
        )}

        {!documentsQuery.isPending
          && !documentsQuery.isError
          && documents.length === 0 && (
            <div className="documents-state">
              <strong>
                No documents uploaded
              </strong>

              <p>
                Upload the first source document
                for this workspace.
              </p>

              <button
                type="button"
                onClick={onUploadClick}
              >
                Upload document
              </button>
            </div>
          )}

        {!documentsQuery.isPending
          && !documentsQuery.isError
          && documents.length > 0 && (
            <div className="documents-table-wrapper">
              <table className="documents-table">
                <thead>
                  <tr>
                    <th>Document</th>
                    <th>Type</th>
                    <th>Size</th>
                    <th>Status</th>
                    <th>Pages</th>
                    <th>Uploaded</th>
                    <th aria-label="Actions" />
                  </tr>
                </thead>

                <tbody>
                  {documents.map(
                    (document) => {
                      const processingIsActive =
                        document.status
                          === "queued"
                        || document.status
                          === "processing";

                      return (
                        <tr key={document.id}>
                          <td>
                            <div className="document-name-cell">
                              <div className="document-file-icon">
                                {
                                  document.file_extension
                                    ?.replace(".", "")
                                    .slice(0, 4)
                                    .toUpperCase()
                                  ?? "FILE"
                                }
                              </div>

                              <div>
                                <strong>
                                  {
                                    document.original_filename
                                  }
                                </strong>

                                <span>
                                  {document.id}
                                </span>
                              </div>
                            </div>
                          </td>

                          <td>
                            <span className="document-type">
                              {
                                getDocumentTypeLabel(
                                  document,
                                )
                              }
                            </span>
                          </td>

                          <td>
                            {formatFileSize(
                              document.file_size_bytes,
                            )}
                          </td>

                          <td>
                            <span
                              className={
                                `document-status ${
                                  document.status
                                }`
                              }
                            >
                              {document.status}
                            </span>
                          </td>

                          <td>
                            {
                              document.page_count
                              ?? "—"
                            }
                          </td>

                          <td>
                            {formatDocumentDate(
                              document.created_at,
                            )}
                          </td>

                          <td>
                            <div className="document-actions">
                              <button
                                type="button"
                                onClick={() => {
                                  handleProcess(
                                    document,
                                  );
                                }}
                                disabled={
                                  processMutation.isPending
                                  && processMutation.variables
                                    === document.id
                                }
                              >
                                {
                                  processMutation.isPending
                                  && processMutation.variables
                                    === document.id
                                    ? "Queueing…"
                                    : getProcessButtonLabel(
                                        document,
                                      )
                                }
                              </button>

                              <button
                                type="button"
                                onClick={() => {
                                  setSelectedDocumentId(
                                    document.id,
                                  );
                                }}
                              >
                                Review
                              </button>

                              <button
                                type="button"
                                onClick={() => {
                                  downloadMutation.mutate(
                                    document,
                                  );
                                }}
                                disabled={
                                  downloadMutation.isPending
                                }
                              >
                                Download
                              </button>

                              <button
                                className="danger"
                                type="button"
                                onClick={() => {
                                  void handleDelete(
                                    document,
                                  );
                                }}
                                disabled={
                                  deleteMutation.isPending
                                  || processingIsActive
                                }
                              >
                                Delete
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    },
                  )}
                </tbody>
              </table>
            </div>
          )}
      </section>

      {selectedDocument && (
        <ExtractionReview
          document={selectedDocument}
          onClose={() => {
            setSelectedDocumentId(null);
          }}
          onProcess={handleProcess}
          isProcessing={
            processMutation.isPending
            && processMutation.variables
              === selectedDocument.id
          }
        />
      )}
    </section>
  );
}