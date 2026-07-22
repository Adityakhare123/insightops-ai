import {
  useEffect,
  useRef,
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
  SQLAgentExecutionResponse,
  SQLAgentPlanResponse,
  SQLAgentRowValue,
  SQLAgentTable,
} from "../../types/sqlAgent";

import {
  executeSQLAgentQuery,
  getSQLAgentSchema,
  planSQLAgentQuery,
} from "./sqlAgentApi";

import "./SQLAnalystWorkspace.css";


const EXAMPLE_QUESTIONS = [
  "Show me the policy status breakdown",
  "How many active policies are there?",
  "Show policies by carrier",
  "Find active policies without payments",
  "Show duplicate policy numbers",
  "Show total payments by carrier",
  "Show commissions by agent",
  "Show recent policies",
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

  return (
    "An unexpected SQL Analyst error occurred."
  );
}


function formatIntent(
  intent: string,
): string {
  return intent
    .replaceAll("_", " ")
    .replace(
      /\b\w/g,
      (character) =>
        character.toUpperCase(),
    );
}


function formatTableName(
  tableName: string,
): string {
  return tableName
    .replace("public.", "")
    .replaceAll("_", " ")
    .replace(
      /\b\w/g,
      (character) =>
        character.toUpperCase(),
    );
}


function formatColumnName(
  columnName: string,
): string {
  return columnName
    .replaceAll("_", " ")
    .replace(
      /\b\w/g,
      (character) =>
        character.toUpperCase(),
    );
}


function formatCellValue(
  value: SQLAgentRowValue | undefined,
): string {
  if (
    value === null
    || value === undefined
  ) {
    return "—";
  }

  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }

  if (
    typeof value === "string"
    || typeof value === "number"
  ) {
    return String(value);
  }

  try {
    return JSON.stringify(
      value,
      null,
      2,
    );
  } catch {
    return String(value);
  }
}


function formatMilliseconds(
  milliseconds: number,
): string {
  if (milliseconds < 1) {
    return "<1 ms";
  }

  if (milliseconds < 1_000) {
    return `${milliseconds.toFixed(1)} ms`;
  }

  return `${(
    milliseconds / 1_000
  ).toFixed(2)} s`;
}


function formatTimeout(
  timeoutMilliseconds: number,
): string {
  if (
    timeoutMilliseconds
    < 1_000
  ) {
    return `${timeoutMilliseconds} ms`;
  }

  return `${(
    timeoutMilliseconds / 1_000
  ).toFixed(1)} seconds`;
}


function getSchemaColumnCount(
  tables: SQLAgentTable[],
): number {
  return tables.reduce(
    (
      totalColumns,
      table,
    ) =>
      totalColumns
      + table.columns.length,
    0,
  );
}


export default function SQLAnalystWorkspace() {
  const sqlPreviewRef =
    useRef<HTMLPreElement | null>(null);

  const [
    question,
    setQuestion,
  ] = useState("");

  const [
    validationError,
    setValidationError,
  ] = useState<string | null>(null);

  const [
    displayedPlan,
    setDisplayedPlan,
  ] = useState<
    SQLAgentPlanResponse | null
  >(null);

  const [
    execution,
    setExecution,
  ] = useState<
    SQLAgentExecutionResponse | null
  >(null);


  useEffect(() => {
    const sqlPreview =
      sqlPreviewRef.current;

    if (!sqlPreview) {
      return;
    }

    sqlPreview.scrollTo({
      top: 0,
      left: 0,
      behavior: "instant",
    });
  }, [
    displayedPlan,
  ]);


  const schemaQuery = useQuery({
    queryKey: [
      "sql-agent",
      "schema",
    ],

    queryFn: getSQLAgentSchema,
  });


  const planMutation = useMutation({
    mutationFn: planSQLAgentQuery,

    onSuccess: (
      plan,
    ) => {
      setDisplayedPlan(plan);
      setExecution(null);
      setValidationError(null);
    },
  });


  const queryMutation = useMutation({
    mutationFn: executeSQLAgentQuery,

    onSuccess: (
      response,
    ) => {
      setDisplayedPlan(
        response.plan,
      );

      setExecution(
        response.execution,
      );

      setValidationError(null);
    },
  });


  const isBusy =
    planMutation.isPending
    || queryMutation.isPending;

  const schemaTables =
    schemaQuery.data?.tables ?? [];

  const schemaColumnCount =
    getSchemaColumnCount(
      schemaTables,
    );


  function validateQuestion():
  string | null {
    const normalizedQuestion =
      question.trim();

    if (
      normalizedQuestion.length
      < 3
    ) {
      setValidationError(
        "Enter a business question containing at least three characters.",
      );

      return null;
    }

    setValidationError(null);

    return normalizedQuestion;
  }


  function previewSQL(): void {
    const normalizedQuestion =
      validateQuestion();

    if (!normalizedQuestion) {
      return;
    }

    planMutation.reset();
    queryMutation.reset();

    planMutation.mutate({
      question: normalizedQuestion,
      max_rows: 500,
    });
  }


  function runQuery(
    event: FormEvent<HTMLFormElement>,
  ): void {
    event.preventDefault();

    const normalizedQuestion =
      validateQuestion();

    if (!normalizedQuestion) {
      return;
    }

    planMutation.reset();
    queryMutation.reset();

    queryMutation.mutate({
      question: normalizedQuestion,
      max_rows: 500,
      statement_timeout_ms: 5_000,
    });
  }


  function selectExampleQuestion(
    exampleQuestion: string,
  ): void {
    setQuestion(
      exampleQuestion,
    );

    setValidationError(null);
  }


  function clearWorkspace(): void {
    setQuestion("");
    setValidationError(null);
    setDisplayedPlan(null);
    setExecution(null);

    planMutation.reset();
    queryMutation.reset();
  }


  const requestError =
    planMutation.isError
      ? getErrorMessage(
          planMutation.error,
        )
      : queryMutation.isError
        ? getErrorMessage(
            queryMutation.error,
          )
        : null;


  return (
    <section className="sql-analyst-workspace">
      <header className="sql-analyst-header">
        <div>
          <p className="dashboard-date">
            Guarded database intelligence
          </p>

          <h1>SQL Analyst</h1>

          <p>
            Ask operational questions in plain
            English and receive workspace-scoped,
            read-only PostgreSQL results.
          </p>
        </div>

        <div className="sql-analyst-header-status">
          <span>
            Approved tables
          </span>

          <strong>
            {
              schemaQuery.data
                ?.table_count
              ?? "—"
            }
          </strong>

          <small>
            Read-only access
          </small>
        </div>
      </header>

      <div className="sql-analyst-layout">
        <aside className="sql-schema-panel">
          <div className="sql-panel-heading">
            <div>
              <p className="dashboard-panel-label">
                Semantic catalog
              </p>

              <h2>
                Insurance schema
              </h2>
            </div>

            <span className="sql-safe-badge">
              Safe
            </span>
          </div>

          <p className="sql-schema-description">
            The SQL Agent can query only these
            approved workspace-aware business
            tables.
          </p>

          {schemaQuery.isPending && (
            <div className="sql-schema-state">
              Loading approved schema...
            </div>
          )}

          {schemaQuery.isError && (
            <div
              className="sql-schema-state error"
              role="alert"
            >
              <strong>
                Schema unavailable
              </strong>

              <span>
                {getErrorMessage(
                  schemaQuery.error,
                )}
              </span>

              <button
                type="button"
                onClick={() => {
                  void schemaQuery.refetch();
                }}
              >
                Try again
              </button>
            </div>
          )}

          {!schemaQuery.isPending
            && !schemaQuery.isError
            && (
              <>
                <div className="sql-schema-summary">
                  <div>
                    <span>Tables</span>

                    <strong>
                      {schemaTables.length}
                    </strong>
                  </div>

                  <div>
                    <span>Columns</span>

                    <strong>
                      {schemaColumnCount}
                    </strong>
                  </div>
                </div>

                <div className="sql-schema-tables">
                  {schemaTables.map(
                    (table) => (
                      <details
                        className="sql-schema-table"
                        key={
                          table.qualified_name
                        }
                      >
                        <summary>
                          <span className="sql-table-icon">
                            DB
                          </span>

                          <span>
                            <strong>
                              {
                                formatTableName(
                                  table.table_name,
                                )
                              }
                            </strong>

                            <small>
                              {
                                table.columns.length
                              } columns
                            </small>
                          </span>

                          <span className="sql-table-toggle">
                            +
                          </span>
                        </summary>

                        <div className="sql-schema-table-content">
                          <p>
                            {table.description}
                          </p>

                          <div className="sql-schema-columns">
                            {table.columns.map(
                              (column) => (
                                <div
                                  className="sql-schema-column"
                                  key={
                                    `${
                                      table.table_name
                                    }-${
                                      column.name
                                    }`
                                  }
                                >
                                  <div>
                                    <strong>
                                      {
                                        column.name
                                      }
                                    </strong>

                                    <span>
                                      {
                                        column.data_type
                                      }
                                    </span>
                                  </div>

                                  <div className="sql-column-flags">
                                    {
                                      column.primary_key
                                      && (
                                        <span>
                                          PK
                                        </span>
                                      )
                                    }

                                    {
                                      !column.nullable
                                      && (
                                        <span>
                                          Required
                                        </span>
                                      )
                                    }
                                  </div>
                                </div>
                              ),
                            )}
                          </div>
                        </div>
                      </details>
                    ),
                  )}
                </div>
              </>
            )}

          <div className="sql-security-note">
            <span className="sql-security-icon">
              RO
            </span>

            <div>
              <strong>
                Read-only transaction
              </strong>

              <p>
                Writes, DDL, unsafe functions,
                unknown tables, and multi-statement
                SQL are rejected.
              </p>
            </div>
          </div>
        </aside>

        <main className="sql-analyst-main">
          <form
            className="sql-question-panel"
            onSubmit={runQuery}
          >
            <div className="sql-panel-heading">
              <div>
                <p className="dashboard-panel-label">
                  Natural language to SQL
                </p>

                <h2>
                  Ask a business question
                </h2>
              </div>

              {(
                displayedPlan
                || execution
                || question
              ) && (
                <button
                  className="sql-text-button"
                  type="button"
                  onClick={clearWorkspace}
                  disabled={isBusy}
                >
                  Clear workspace
                </button>
              )}
            </div>

            <label
              className="sql-question-label"
              htmlFor="sql-agent-question"
            >
              Business question
            </label>

            <textarea
              id="sql-agent-question"
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
                "Example: Find active policies "
                + "without payments"
              }
              maxLength={1_000}
              rows={4}
              disabled={isBusy}
            />

            <div className="sql-question-footer">
              <span>
                {question.length.toLocaleString()}
                /1,000
              </span>

              <div>
                <button
                  className="sql-secondary-action"
                  type="button"
                  onClick={previewSQL}
                  disabled={isBusy}
                >
                  {planMutation.isPending
                    ? "Planning..."
                    : "Preview SQL"}
                </button>

                <button
                  className="dashboard-primary-action"
                  type="submit"
                  disabled={isBusy}
                >
                  {queryMutation.isPending
                    ? "Running query..."
                    : "Run safe query"}
                </button>
              </div>
            </div>

            <div className="sql-question-examples">
              <span>
                Supported questions
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
                      disabled={isBusy}
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
              className="sql-message error"
              role="alert"
            >
              <strong>
                Query could not be completed
              </strong>

              <span>
                {
                  validationError
                  ?? requestError
                }
              </span>
            </div>
          )}

          {isBusy && (
            <section className="sql-loading-state">
              <div className="sql-loading-indicator">
                <span />
                <span />
                <span />
              </div>

              <strong>
                {queryMutation.isPending
                  ? (
                    "Executing guarded PostgreSQL query"
                  )
                  : "Building safe SQL plan"}
              </strong>

              <p>
                Validating the query against the
                approved schema and SQL safety
                policies.
              </p>
            </section>
          )}

          {!isBusy
            && !displayedPlan
            && !execution && (
              <section className="sql-empty-state">
                <div className="sql-empty-mark">
                  SQL
                </div>

                <strong>
                  Your SQL analysis will appear here
                </strong>

                <p>
                  Preview the generated SQL before
                  execution or run a guarded query
                  directly against the insurance
                  dataset.
                </p>

                <div className="sql-empty-guardrails">
                  <span>
                    Single SELECT
                  </span>

                  <span>
                    Workspace scoped
                  </span>

                  <span>
                    500-row maximum
                  </span>

                  <span>
                    Five-second timeout
                  </span>
                </div>
              </section>
            )}

          {!isBusy
            && displayedPlan && (
              <section className="sql-plan-panel">
                <header className="sql-plan-header">
                  <div>
                    <span className="sql-plan-status">
                      Validated SQL
                    </span>

                    <h2>
                      Query plan
                    </h2>
                  </div>

                  <div className="sql-plan-intent">
                    <span>
                      Detected intent
                    </span>

                    <strong>
                      {
                        formatIntent(
                          displayedPlan.intent,
                        )
                      }
                    </strong>
                  </div>
                </header>

                <p className="sql-plan-explanation">
                  {displayedPlan.explanation}
                </p>

                <div className="sql-safety-strip">
                  <div>
                    <span className="sql-safety-check">
                      ✓
                    </span>

                    <span>
                      Read-only SELECT
                    </span>
                  </div>

                  <div>
                    <span className="sql-safety-check">
                      ✓
                    </span>

                    <span>
                      Workspace isolated
                    </span>
                  </div>

                  <div>
                    <span className="sql-safety-check">
                      ✓
                    </span>

                    <span>
                      Maximum {
                        displayedPlan.max_rows
                      } rows
                    </span>
                  </div>
                </div>

                <div className="sql-code-heading">
                  <div>
                    <p className="dashboard-panel-label">
                      Generated statement
                    </p>

                    <h3>
                      PostgreSQL
                    </h3>
                  </div>

                  <span>
                    Guardrail approved
                  </span>
                </div>

                <pre
                  className="sql-code-preview"
                  ref={sqlPreviewRef}
                >
                  <code>
                    {
                      displayedPlan
                        .generated_sql
                    }
                  </code>
                </pre>

                <div className="sql-referenced-tables">
                  <span>
                    Referenced tables
                  </span>

                  <div>
                    {
                      displayedPlan
                        .referenced_tables
                        .map(
                          (tableName) => (
                            <span
                              key={
                                tableName
                              }
                            >
                              {
                                formatTableName(
                                  tableName,
                                )
                              }
                            </span>
                          ),
                        )
                    }
                  </div>
                </div>
              </section>
            )}

          {!isBusy
            && execution && (
              <section className="sql-results-panel">
                <header className="sql-results-header">
                  <div>
                    <span className="sql-results-status">
                      Query completed
                    </span>

                    <h2>
                      Analysis results
                    </h2>
                  </div>

                  <div className="sql-results-summary">
                    <strong>
                      {
                        execution.row_count
                      }
                    </strong>

                    <span>
                      row{
                        execution.row_count
                        === 1
                          ? ""
                          : "s"
                      }
                    </span>
                  </div>
                </header>

                <dl className="sql-result-metrics">
                  <div>
                    <dt>
                      Execution time
                    </dt>

                    <dd>
                      {
                        formatMilliseconds(
                          execution
                            .execution_time_ms,
                        )
                      }
                    </dd>
                  </div>

                  <div>
                    <dt>
                      Row count
                    </dt>

                    <dd>
                      {
                        execution.row_count
                      }
                    </dd>
                  </div>

                  <div>
                    <dt>
                      Maximum rows
                    </dt>

                    <dd>
                      {
                        execution.max_rows
                      }
                    </dd>
                  </div>

                  <div>
                    <dt>
                      Statement timeout
                    </dt>

                    <dd>
                      {
                        formatTimeout(
                          execution
                            .statement_timeout_ms,
                        )
                      }
                    </dd>
                  </div>
                </dl>

                {execution.limit_reached && (
                  <div className="sql-limit-warning">
                    <strong>
                      Result limit reached
                    </strong>

                    <span>
                      The query returned the maximum
                      permitted {
                        execution.max_rows
                      } rows. Refine the question to
                      narrow the result.
                    </span>
                  </div>
                )}

                {execution.row_count === 0 ? (
                  <div className="sql-no-results">
                    <strong>
                      No matching records
                    </strong>

                    <p>
                      The SQL query completed
                      successfully but returned no
                      rows.
                    </p>
                  </div>
                ) : (
                  <div className="sql-results-table-wrapper">
                    <table className="sql-results-table">
                      <thead>
                        <tr>
                          {
                            execution.columns.map(
                              (columnName) => (
                                <th
                                  key={
                                    columnName
                                  }
                                  scope="col"
                                >
                                  {
                                    formatColumnName(
                                      columnName,
                                    )
                                  }
                                </th>
                              ),
                            )
                          }
                        </tr>
                      </thead>

                      <tbody>
                        {
                          execution.rows.map(
                            (
                              row,
                              rowIndex,
                            ) => (
                              <tr
                                key={
                                  `sql-result-${
                                    rowIndex
                                  }`
                                }
                              >
                                {
                                  execution.columns.map(
                                    (
                                      columnName,
                                    ) => (
                                      <td
                                        key={
                                          `${
                                            rowIndex
                                          }-${
                                            columnName
                                          }`
                                        }
                                        title={
                                          formatCellValue(
                                            row[
                                              columnName
                                            ],
                                          )
                                        }
                                      >
                                        {
                                          formatCellValue(
                                            row[
                                              columnName
                                            ],
                                          )
                                        }
                                      </td>
                                    ),
                                  )
                                }
                              </tr>
                            ),
                          )
                        }
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            )}
        </main>
      </div>
    </section>
  );
}