import {
  useQuery,
} from "@tanstack/react-query";

import { ApiError } from "../../api/client";

import type {
  DocumentProcessingRunRead,
  DocumentRead,
} from "../../types/document";

import {
  listDocumentPages,
  listDocumentProcessingRuns,
} from "./documentsApi";


interface ExtractionReviewProps {
  document: DocumentRead;
  onClose: () => void;
  onProcess: (
    document: DocumentRead,
  ) => void;
  isProcessing: boolean;
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


function formatDate(
  dateValue: string | null,
): string {
  if (!dateValue) {
    return "—";
  }

  return new Intl.DateTimeFormat(
    "en",
    {
      dateStyle: "medium",
      timeStyle: "short",
    },
  ).format(new Date(dateValue));
}


function formatConfidence(
  value: number | null,
): string {
  if (value === null) {
    return "—";
  }

  return `${Math.round(value * 100)}%`;
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
    return "Reprocess document";
  }

  if (document.status === "failed") {
    return "Retry processing";
  }

  return "Process document";
}


function getRunDuration(
  run: DocumentProcessingRunRead,
): string {
  if (!run.started_at) {
    return "—";
  }

  const startTime =
    new Date(run.started_at).getTime();

  const endTime = run.completed_at
    ? new Date(run.completed_at).getTime()
    : Date.now();

  const durationSeconds = Math.max(
    0,
    (endTime - startTime) / 1000,
  );

  if (durationSeconds < 1) {
    return "< 1 second";
  }

  if (durationSeconds < 60) {
    return `${durationSeconds.toFixed(1)} seconds`;
  }

  return `${(durationSeconds / 60).toFixed(1)} minutes`;
}


export default function ExtractionReview({
  document,
  onClose,
  onProcess,
  isProcessing,
}: ExtractionReviewProps) {
  const processingRunsQuery = useQuery({
    queryKey: [
      "document-processing-runs",
      document.id,
    ],
    queryFn: () =>
      listDocumentProcessingRuns(
        document.id,
        {
          limit: 100,
          offset: 0,
        },
      ),
    refetchInterval: 2_000,
  });

  const pagesQuery = useQuery({
    queryKey: [
      "document-pages",
      document.id,
    ],
    queryFn: () =>
      listDocumentPages(
        document.id,
        {
          limit: 500,
          offset: 0,
        },
      ),
    refetchInterval: 2_000,
  });

  const processingRuns =
    processingRunsQuery.data?.items ?? [];

  const pages =
    pagesQuery.data?.items ?? [];

  const latestRun =
    processingRuns[0] ?? null;

  const processingIsActive =
    latestRun?.status === "queued"
    || latestRun?.status === "running"
    || document.status === "queued"
    || document.status === "processing";

  const queryError =
    processingRunsQuery.isError
      ? getErrorMessage(
          processingRunsQuery.error,
        )
      : pagesQuery.isError
        ? getErrorMessage(
            pagesQuery.error,
          )
        : null;


  return (
    <section
      className="documents-panel"
      aria-label="Document extraction review"
    >
      <div className="documents-panel-header">
        <div>
          <p className="dashboard-panel-label">
            Document intelligence
          </p>

          <h2>
            {document.original_filename}
          </h2>

          <p>
            Review processing attempts and
            extracted page content.
          </p>
        </div>

        <div className="document-actions">
          <button
            type="button"
            onClick={() => {
              onProcess(document);
            }}
            disabled={
              isProcessing
              || processingIsActive
            }
          >
            {
              isProcessing
                ? "Queueing…"
                : getProcessButtonLabel(
                    document,
                  )
            }
          </button>

          <button
            type="button"
            onClick={onClose}
          >
            Close
          </button>
        </div>
      </div>

      {queryError && (
        <div
          className="documents-message error"
          role="alert"
        >
          {queryError}
        </div>
      )}

      {latestRun && (
        <section
          style={{
            display: "grid",
            gridTemplateColumns:
              "repeat(auto-fit, minmax(160px, 1fr))",
            gap: "1rem",
            marginBottom: "1.5rem",
          }}
        >
          <div>
            <span>Latest attempt</span>
            <strong
              style={{
                display: "block",
                marginTop: "0.35rem",
              }}
            >
              #{latestRun.attempt_number}
            </strong>
          </div>

          <div>
            <span>Status</span>
            <strong
              style={{
                display: "block",
                marginTop: "0.35rem",
              }}
            >
              <span
                className={
                  `document-status ${
                    latestRun.status
                  }`
                }
              >
                {latestRun.status}
              </span>
            </strong>
          </div>

          <div>
            <span>Extracted pages</span>
            <strong
              style={{
                display: "block",
                marginTop: "0.35rem",
              }}
            >
              {latestRun.extracted_pages}
              {" / "}
              {latestRun.total_pages ?? "—"}
            </strong>
          </div>

          <div>
            <span>Duration</span>
            <strong
              style={{
                display: "block",
                marginTop: "0.35rem",
              }}
            >
              {getRunDuration(latestRun)}
            </strong>
          </div>
        </section>
      )}

      {latestRun?.error_message && (
        <div
          className="documents-message error"
          role="alert"
        >
          {latestRun.error_message}
        </div>
      )}

      <section
        style={{
          marginBottom: "2rem",
        }}
      >
        <div className="documents-panel-header">
          <div>
            <p className="dashboard-panel-label">
              Processing history
            </p>

            <h2>Extraction attempts</h2>
          </div>

          <button
            type="button"
            onClick={() => {
              void processingRunsQuery.refetch();
            }}
            disabled={
              processingRunsQuery.isFetching
            }
          >
            {
              processingRunsQuery.isFetching
                ? "Refreshing…"
                : "Refresh"
            }
          </button>
        </div>

        {processingRunsQuery.isPending && (
          <div className="documents-state">
            <strong>
              Loading processing history…
            </strong>
          </div>
        )}

        {!processingRunsQuery.isPending
          && processingRuns.length === 0 && (
            <div className="documents-state">
              <strong>
                This document has not been processed
              </strong>

              <p>
                Start document processing to extract
                searchable page content.
              </p>
            </div>
          )}

        {processingRuns.length > 0 && (
          <div className="documents-table-wrapper">
            <table className="documents-table">
              <thead>
                <tr>
                  <th>Attempt</th>
                  <th>Status</th>
                  <th>Processor</th>
                  <th>Pages</th>
                  <th>Started</th>
                  <th>Completed</th>
                </tr>
              </thead>

              <tbody>
                {processingRuns.map(
                  (run) => (
                    <tr key={run.id}>
                      <td>
                        #{run.attempt_number}
                      </td>

                      <td>
                        <span
                          className={
                            `document-status ${
                              run.status
                            }`
                          }
                        >
                          {run.status}
                        </span>
                      </td>

                      <td>
                        {run.processor_name}
                      </td>

                      <td>
                        {run.extracted_pages}
                        {" / "}
                        {run.total_pages ?? "—"}
                      </td>

                      <td>
                        {formatDate(
                          run.started_at,
                        )}
                      </td>

                      <td>
                        {formatDate(
                          run.completed_at,
                        )}
                      </td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section>
        <div className="documents-panel-header">
          <div>
            <p className="dashboard-panel-label">
              Extracted content
            </p>

            <h2>Document pages</h2>
          </div>

          <button
            type="button"
            onClick={() => {
              void pagesQuery.refetch();
            }}
            disabled={
              pagesQuery.isFetching
            }
          >
            {
              pagesQuery.isFetching
                ? "Refreshing…"
                : "Refresh"
            }
          </button>
        </div>

        {pagesQuery.isPending && (
          <div className="documents-state">
            <strong>
              Loading extracted pages…
            </strong>
          </div>
        )}

        {!pagesQuery.isPending
          && pages.length === 0 && (
            <div className="documents-state">
              <strong>
                No extracted pages available
              </strong>

              <p>
                Extracted text will appear here
                after processing completes.
              </p>
            </div>
          )}

        {pages.map(
          (page) => (
            <article
              key={page.id}
              style={{
                border:
                  "1px solid rgba(255, 255, 255, 0.1)",
                borderRadius: "14px",
                padding: "1rem",
                marginBottom: "1rem",
              }}
            >
              <header
                style={{
                  display: "flex",
                  justifyContent:
                    "space-between",
                  gap: "1rem",
                  marginBottom: "1rem",
                  flexWrap: "wrap",
                }}
              >
                <div>
                  <strong>
                    Page {page.page_number}
                  </strong>

                  <p
                    style={{
                      margin:
                        "0.35rem 0 0",
                    }}
                  >
                    {
                      page.extraction_method
                        ?.replaceAll("_", " ")
                      ?? "Unknown method"
                    }
                  </p>
                </div>

                <div>
                  <span>
                    Confidence:{" "}
                    {formatConfidence(
                      page.confidence_score,
                    )}
                  </span>

                  <span
                    style={{
                      marginLeft: "1rem",
                    }}
                  >
                    {page.word_count} words
                  </span>
                </div>
              </header>

              {page.error_message ? (
                <div
                  className="documents-message error"
                >
                  {page.error_message}
                </div>
              ) : (
                <pre
                  style={{
                    margin: 0,
                    maxHeight: "30rem",
                    overflow: "auto",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                    fontFamily:
                      "var(--font-mono, monospace)",
                    fontSize: "0.85rem",
                    lineHeight: 1.65,
                    padding: "1rem",
                    borderRadius: "10px",
                    background:
                      "rgba(0, 0, 0, 0.25)",
                  }}
                >
                  {
                    page.text_content
                    || "No text was extracted."
                  }
                </pre>
              )}
            </article>
          ),
        )}
      </section>
    </section>
  );
}