import {
  useState,
} from "react";

import type {
  FormEvent,
} from "react";

import {
  useMutation,
  useQuery,
} from "@tanstack/react-query";

import {
  ApiError,
} from "../../api/client";

import type {
  DocumentRead,
} from "../../types/document";

import {
  downloadDocument,
  listDocuments,
  saveDownloadedDocument,
} from "../documents/documentsApi";

import {
  answerDocumentQuestion,
} from "./ragApi";

import type {
  RAGAnswerRequest,
  RAGCitation,
} from "../../types/rag";

import "./RAGWorkspace.css";


const EXAMPLE_QUESTIONS = [
  "What is the policy number for customer Jane Doe?",
  "Which customer is associated with this policy?",
  "What information does the document provide about the policy?",
  "Summarize the important policy details in the selected documents.",
];


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


function formatPercentage(
  value: number,
): string {
  return `${Math.round(value * 100)}%`;
}


function formatDocumentType(
  document: DocumentRead,
): string {
  if (document.document_type) {
    return document.document_type
      .replaceAll("_", " ");
  }

  return (
    document.file_extension
      ?.replace(".", "")
      .toUpperCase()
    ?? "Document"
  );
}


function buildCitationLabel(
  citation: RAGCitation,
): string {
  return (
    `[${citation.citation_number}] `
    + `${citation.document_name}, `
    + `page ${citation.page_number}`
  );
}


export default function RAGWorkspace() {
  const [
    question,
    setQuestion,
  ] = useState("");

  const [
    selectedDocumentIds,
    setSelectedDocumentIds,
  ] = useState<string[]>([]);

  const [
    validationError,
    setValidationError,
  ] = useState<string | null>(null);


  const documentsQuery = useQuery({
    queryKey: [
      "documents",
      "rag-source-documents",
    ],

    queryFn: () =>
      listDocuments({
        limit: 100,
        offset: 0,
      }),
  });


  const answerMutation = useMutation({
    mutationFn: (
      request: RAGAnswerRequest,
    ) => answerDocumentQuestion(request),
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


  const allDocuments =
    documentsQuery.data?.items ?? [];

  const processedDocuments =
    allDocuments.filter(
      (document) =>
        document.status === "processed",
    );

  const selectedDocumentCount =
    selectedDocumentIds.length;

  const allProcessedDocumentsSelected =
    processedDocuments.length > 0
    && processedDocuments.every(
      (document) =>
        selectedDocumentIds.includes(
          document.id,
        ),
    );


  function toggleDocument(
    documentId: string,
  ): void {
    setSelectedDocumentIds(
      (currentDocumentIds) => {
        if (
          currentDocumentIds.includes(
            documentId,
          )
        ) {
          return currentDocumentIds.filter(
            (currentDocumentId) =>
              currentDocumentId
              !== documentId,
          );
        }

        return [
          ...currentDocumentIds,
          documentId,
        ];
      },
    );
  }


  function toggleAllDocuments(): void {
    if (allProcessedDocumentsSelected) {
      setSelectedDocumentIds([]);
      return;
    }

    setSelectedDocumentIds(
      processedDocuments.map(
        (document) => document.id,
      ),
    );
  }


  function selectExampleQuestion(
    exampleQuestion: string,
  ): void {
    setQuestion(exampleQuestion);
    setValidationError(null);
  }


  function submitQuestion(
    event: FormEvent<HTMLFormElement>,
  ): void {
    event.preventDefault();

    const normalizedQuestion =
      question.trim();

    if (normalizedQuestion.length < 2) {
      setValidationError(
        "Enter a question containing at least two characters.",
      );

      return;
    }

    if (processedDocuments.length === 0) {
      setValidationError(
        "Process at least one document before asking a question.",
      );

      return;
    }

    setValidationError(null);

    answerMutation.mutate({
      question: normalizedQuestion,
      top_k: 8,
      maximum_citations: 4,
      minimum_similarity: 0,
      document_ids:
        selectedDocumentIds,
    });
  }


  function clearAnswer(): void {
    setQuestion("");
    setValidationError(null);
    answerMutation.reset();
  }


  function downloadCitationSource(
    citation: RAGCitation,
  ): void {
    const sourceDocument =
      allDocuments.find(
        (document) =>
          document.id
          === citation.document_id,
      );

    if (!sourceDocument) {
      setValidationError(
        "The citation source document is no longer available.",
      );

      return;
    }

    setValidationError(null);

    downloadMutation.mutate(
      sourceDocument,
    );
  }


  const answer =
    answerMutation.data;

  const requestError =
    answerMutation.isError
      ? getErrorMessage(
          answerMutation.error,
        )
      : downloadMutation.isError
        ? getErrorMessage(
            downloadMutation.error,
          )
        : null;


  return (
    <section className="rag-workspace">
      <header className="rag-header">
        <div>
          <p className="dashboard-date">
            Retrieval augmented generation
          </p>

          <h1>Ask your documents</h1>

          <p>
            Ask questions across processed
            workspace documents and receive
            evidence-backed answers with page
            citations.
          </p>
        </div>

        <div className="rag-header-status">
          <span>
            Indexed sources
          </span>

          <strong>
            {processedDocuments.length}
          </strong>
        </div>
      </header>

      <div className="rag-layout">
        <aside className="rag-source-panel">
          <div className="rag-panel-heading">
            <div>
              <p className="dashboard-panel-label">
                Retrieval scope
              </p>

              <h2>Source documents</h2>
            </div>

            {processedDocuments.length > 0 && (
              <button
                className="rag-text-button"
                type="button"
                onClick={toggleAllDocuments}
              >
                {allProcessedDocumentsSelected
                  ? "Clear all"
                  : "Select all"}
              </button>
            )}
          </div>

          <p className="rag-source-description">
            Select specific documents or leave
            every document unchecked to search
            all processed sources.
          </p>

          {documentsQuery.isPending && (
            <div className="rag-source-state">
              Loading document sources...
            </div>
          )}

          {documentsQuery.isError && (
            <div
              className="rag-source-state error"
              role="alert"
            >
              <strong>
                Documents could not be loaded
              </strong>

              <span>
                {getErrorMessage(
                  documentsQuery.error,
                )}
              </span>

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
            && processedDocuments.length
              === 0 && (
              <div className="rag-source-state">
                <strong>
                  No indexed documents
                </strong>

                <span>
                  Upload and process a document
                  before using document Q&amp;A.
                </span>
              </div>
            )}

          {processedDocuments.length > 0 && (
            <div className="rag-document-list">
              {processedDocuments.map(
                (document) => {
                  const isSelected =
                    selectedDocumentIds.includes(
                      document.id,
                    );

                  return (
                    <label
                      className={
                        `rag-document-option ${
                          isSelected
                            ? "selected"
                            : ""
                        }`
                      }
                      key={document.id}
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => {
                          toggleDocument(
                            document.id,
                          );
                        }}
                      />

                      <span className="rag-document-icon">
                        {
                          document.file_extension
                            ?.replace(".", "")
                            .slice(0, 4)
                            .toUpperCase()
                          ?? "FILE"
                        }
                      </span>

                      <span className="rag-document-details">
                        <strong>
                          {
                            document.original_filename
                          }
                        </strong>

                        <small>
                          {formatDocumentType(
                            document,
                          )}

                          {document.page_count
                            ? (
                              ` · ${
                                document.page_count
                              } page${
                                document.page_count
                                === 1
                                  ? ""
                                  : "s"
                              }`
                            )
                            : ""}
                        </small>
                      </span>
                    </label>
                  );
                },
              )}
            </div>
          )}

          <div className="rag-scope-summary">
            <span>
              Search scope
            </span>

            <strong>
              {selectedDocumentCount > 0
                ? (
                  `${selectedDocumentCount} selected`
                )
                : "All processed documents"}
            </strong>
          </div>
        </aside>

        <main className="rag-main-panel">
          <form
            className="rag-question-form"
            onSubmit={submitQuestion}
          >
            <div className="rag-panel-heading">
              <div>
                <p className="dashboard-panel-label">
                  Grounded document Q&amp;A
                </p>

                <h2>Ask a question</h2>
              </div>

              {answer && (
                <button
                  className="rag-text-button"
                  type="button"
                  onClick={clearAnswer}
                >
                  New question
                </button>
              )}
            </div>

            <label
              className="rag-question-label"
              htmlFor="rag-question"
            >
              Question
            </label>

            <textarea
              id="rag-question"
              value={question}
              onChange={(event) => {
                setQuestion(
                  event.target.value,
                );

                if (validationError) {
                  setValidationError(null);
                }
              }}
              placeholder={
                "Ask about a policy, customer, "
                + "date, payment, or any detail "
                + "inside the processed documents."
              }
              maxLength={4_000}
              rows={5}
              disabled={
                answerMutation.isPending
              }
            />

            <div className="rag-question-footer">
              <span>
                {question.length.toLocaleString()}
                /4,000
              </span>

              <button
                className="dashboard-primary-action"
                type="submit"
                disabled={
                  answerMutation.isPending
                  || processedDocuments.length
                    === 0
                }
              >
                {answerMutation.isPending
                  ? "Searching documents..."
                  : "Generate grounded answer"}
              </button>
            </div>

            <div className="rag-examples">
              <span>
                Example questions
              </span>

              <div>
                {EXAMPLE_QUESTIONS.map(
                  (exampleQuestion) => (
                    <button
                      type="button"
                      key={exampleQuestion}
                      onClick={() => {
                        selectExampleQuestion(
                          exampleQuestion,
                        );
                      }}
                      disabled={
                        answerMutation.isPending
                      }
                    >
                      {exampleQuestion}
                    </button>
                  ),
                )}
              </div>
            </div>
          </form>

          {(validationError || requestError) && (
            <div
              className="rag-message error"
              role="alert"
            >
              {validationError ?? requestError}
            </div>
          )}

          {answerMutation.isPending && (
            <section className="rag-answer-state">
              <div className="rag-loading-indicator">
                <span />
                <span />
                <span />
              </div>

              <strong>
                Retrieving supporting evidence
              </strong>

              <p>
                Searching indexed document chunks
                and preparing source citations.
              </p>
            </section>
          )}

          {!answerMutation.isPending
            && !answer && (
              <section className="rag-answer-state">
                <div className="rag-empty-mark">
                  AI
                </div>

                <strong>
                  Your grounded answer will appear here
                </strong>

                <p>
                  Answers include the source document,
                  page number, matching excerpt, and
                  retrieval confidence.
                </p>
              </section>
            )}

          {!answerMutation.isPending
            && answer && (
              <section className="rag-answer-panel">
                <header className="rag-answer-header">
                  <div>
                    <span
                      className={
                        `rag-grounding-status ${
                          answer.is_grounded
                            ? "grounded"
                            : "insufficient"
                        }`
                      }
                    >
                      {answer.is_grounded
                        ? "Grounded answer"
                        : "Insufficient evidence"}
                    </span>

                    <h2>
                      Response
                    </h2>
                  </div>

                  <div className="rag-confidence">
                    <span>
                      Confidence
                    </span>

                    <strong>
                      {formatPercentage(
                        answer.confidence_score,
                      )}
                    </strong>
                  </div>
                </header>

                <div
                  className="rag-confidence-track"
                  aria-label={
                    `Confidence ${
                      formatPercentage(
                        answer.confidence_score,
                      )
                    }`
                  }
                >
                  <span
                    style={{
                      width: formatPercentage(
                        answer.confidence_score,
                      ),
                    }}
                  />
                </div>

                <div className="rag-answer-copy">
                  {answer.answer}
                </div>

                <dl className="rag-answer-metrics">
                  <div>
                    <dt>
                      Retrieved chunks
                    </dt>

                    <dd>
                      {
                        answer.retrieved_chunk_count
                      }
                    </dd>
                  </div>

                  <div>
                    <dt>
                      Citations
                    </dt>

                    <dd>
                      {answer.citation_count}
                    </dd>
                  </div>

                  <div>
                    <dt>
                      Embedding model
                    </dt>

                    <dd>
                      {answer.embedding_model}
                    </dd>
                  </div>

                  <div>
                    <dt>
                      Vector dimensions
                    </dt>

                    <dd>
                      {
                        answer.embedding_dimensions
                      }
                    </dd>
                  </div>
                </dl>

                {answer.citations.length > 0 && (
                  <div className="rag-citations">
                    <div className="rag-citations-heading">
                      <div>
                        <p className="dashboard-panel-label">
                          Supporting evidence
                        </p>

                        <h3>
                          Citations
                        </h3>
                      </div>

                      <span>
                        {
                          answer.citations.length
                        } source
                        {
                          answer.citations.length
                          === 1
                            ? ""
                            : "s"
                        }
                      </span>
                    </div>

                    {answer.citations.map(
                      (citation) => (
                        <article
                          className="rag-citation"
                          key={citation.chunk_id}
                        >
                          <header>
                            <div>
                              <strong>
                                {
                                  buildCitationLabel(
                                    citation,
                                  )
                                }
                              </strong>

                              <span>
                                Chunk {
                                  citation.chunk_index
                                  + 1
                                }
                                {" · "}
                                Similarity {
                                  formatPercentage(
                                    citation.similarity_score,
                                  )
                                }
                              </span>
                            </div>

                            <button
                              type="button"
                              onClick={() => {
                                downloadCitationSource(
                                  citation,
                                );
                              }}
                              disabled={
                                downloadMutation.isPending
                              }
                            >
                              {downloadMutation.isPending
                                ? "Preparing..."
                                : "Download source"}
                            </button>
                          </header>

                          <blockquote>
                            {citation.excerpt}
                          </blockquote>

                          <footer>
                            <span>
                              Page {
                                citation.page_number
                              }
                            </span>

                            <span>
                              Characters {
                                citation.start_character
                              }–{
                                citation.end_character
                              }
                            </span>

                            <span>
                              Distance {
                                citation.cosine_distance
                                  .toFixed(4)
                              }
                            </span>
                          </footer>
                        </article>
                      ),
                    )}
                  </div>
                )}
              </section>
            )}
        </main>
      </div>
    </section>
  );
}