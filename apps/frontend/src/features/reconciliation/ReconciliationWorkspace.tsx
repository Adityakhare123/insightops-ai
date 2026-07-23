import {
  useEffect,
  useMemo,
  useState,
  type FormEvent,
} from "react";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  downloadReconciliationReport,
  listReconciliationFindings,
  listReconciliationRuns,
  listReviewTasks,
  saveReconciliationReport,
  startDocumentReconciliation,
  updateReviewTask,
} from "./reconciliationApi";

import type {
  ReconciliationFindingRead,
  ReconciliationFindingSeverity,
  ReconciliationFindingStatus,
  ReconciliationReportFormat,
  ReconciliationRunRead,
  ReconciliationRunStatus,
  ReviewTaskPriority,
  ReviewTaskRead,
  ReviewTaskStatus,
} from "../../types/reconciliation";

import "./ReconciliationWorkspace.css";


type WorkspaceTab =
  | "findings"
  | "reviews"
  | "extraction";

type ResolutionAction =
  | "approved"
  | "corrected"
  | "rejected";


const RUN_STATUS_OPTIONS: Array<{
  value: ReconciliationRunStatus | "";
  label: string;
}> = [
  { value: "", label: "All runs" },
  { value: "completed", label: "Completed" },
  { value: "needs_review", label: "Needs review" },
  { value: "running", label: "Running" },
  { value: "queued", label: "Queued" },
  { value: "failed", label: "Failed" },
  { value: "cancelled", label: "Cancelled" },
];

const FINDING_STATUS_OPTIONS: Array<{
  value: ReconciliationFindingStatus | "";
  label: string;
}> = [
  { value: "", label: "All statuses" },
  { value: "failed", label: "Failed" },
  { value: "needs_review", label: "Needs review" },
  { value: "passed", label: "Passed" },
  { value: "skipped", label: "Skipped" },
];

const FINDING_SEVERITY_OPTIONS: Array<{
  value: ReconciliationFindingSeverity | "";
  label: string;
}> = [
  { value: "", label: "All severities" },
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
  { value: "info", label: "Info" },
];

const REVIEW_STATUS_OPTIONS: Array<{
  value: ReviewTaskStatus | "";
  label: string;
}> = [
  { value: "", label: "All tasks" },
  { value: "open", label: "Open" },
  { value: "in_progress", label: "In progress" },
  { value: "approved", label: "Approved" },
  { value: "corrected", label: "Corrected" },
  { value: "rejected", label: "Rejected" },
];

const REVIEW_PRIORITY_OPTIONS: Array<{
  value: ReviewTaskPriority | "";
  label: string;
}> = [
  { value: "", label: "All priorities" },
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

const RESOLVED_REVIEW_STATUSES: ReviewTaskStatus[] = [
  "approved",
  "corrected",
  "rejected",
];


function formatLabel(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}


function formatDateTime(value: string | null): string {
  if (!value) {
    return "Not available";
  }

  const parsedDate = new Date(value);

  if (Number.isNaN(parsedDate.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsedDate);
}


function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "Not available";
  }

  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }

  if (typeof value === "object") {
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  }

  return String(value);
}


function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }

  return "An unexpected error occurred.";
}


function getRunStatusTone(status: ReconciliationRunStatus): string {
  switch (status) {
    case "completed":
      return "success";
    case "needs_review":
      return "warning";
    case "failed":
    case "cancelled":
      return "danger";
    case "running":
      return "active";
    default:
      return "neutral";
  }
}


function getFindingTone(finding: ReconciliationFindingRead): string {
  if (finding.status === "passed") {
    return "success";
  }

  if (finding.status === "failed") {
    return "danger";
  }

  if (finding.status === "needs_review") {
    return "warning";
  }

  return "neutral";
}


function getSeverityTone(
  severity: ReconciliationFindingSeverity | ReviewTaskPriority,
): string {
  if (severity === "high") {
    return "danger";
  }

  if (severity === "medium") {
    return "warning";
  }

  return "neutral";
}


function StatusBadge({
  value,
  tone,
}: {
  value: string;
  tone: string;
}) {
  return (
    <span
      className={[
        "reconciliation-badge",
        `reconciliation-badge--${tone}`,
      ].join(" ")}
    >
      {formatLabel(value)}
    </span>
  );
}


function MetricCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: number | string;
  detail?: string;
}) {
  return (
    <article className="reconciliation-metric">
      <span className="reconciliation-metric__label">{label}</span>
      <strong className="reconciliation-metric__value">{value}</strong>
      {detail ? (
        <span className="reconciliation-metric__detail">{detail}</span>
      ) : null}
    </article>
  );
}


function EmptyState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="reconciliation-empty">
      <div className="reconciliation-empty__mark">IO</div>
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
}


export function ReconciliationWorkspace() {
  const queryClient = useQueryClient();

  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("findings");

  const [runStatusFilter, setRunStatusFilter] = useState<
    ReconciliationRunStatus | ""
  >("");

  const [findingStatusFilter, setFindingStatusFilter] = useState<
    ReconciliationFindingStatus | ""
  >("");

  const [findingSeverityFilter, setFindingSeverityFilter] = useState<
    ReconciliationFindingSeverity | ""
  >("");

  const [reviewStatusFilter, setReviewStatusFilter] = useState<
    ReviewTaskStatus | ""
  >("");

  const [reviewPriorityFilter, setReviewPriorityFilter] = useState<
    ReviewTaskPriority | ""
  >("");

  const [selectedFinding, setSelectedFinding] = useState<
    ReconciliationFindingRead | null
  >(null);

  const [selectedTask, setSelectedTask] = useState<ReviewTaskRead | null>(null);
  const [resolutionAction, setResolutionAction] = useState<
    ResolutionAction | null
  >(null);

  const [resolutionNotes, setResolutionNotes] = useState("");
  const [correctedValue, setCorrectedValue] = useState("");

  const [documentId, setDocumentId] = useState("");
  const [minimumConfidence, setMinimumConfidence] = useState("0.75");
  const [premiumTolerance, setPremiumTolerance] = useState("0.01");
  const [excludeCancelled, setExcludeCancelled] = useState(true);
  const [workspaceNotice, setWorkspaceNotice] = useState<string | null>(null);

  const runsQuery = useQuery({
    queryKey: ["reconciliation-runs", runStatusFilter],
    queryFn: () =>
      listReconciliationRuns({
        limit: 100,
        status: runStatusFilter || undefined,
      }),
  });

  const selectedRun = useMemo(
    () =>
      runsQuery.data?.items.find((run) => run.id === selectedRunId) ?? null,
    [runsQuery.data?.items, selectedRunId],
  );

  useEffect(() => {
    const availableRuns = runsQuery.data?.items ?? [];

    if (availableRuns.length === 0) {
      setSelectedRunId(null);
      return;
    }

    const currentRunExists = availableRuns.some(
      (run) => run.id === selectedRunId,
    );

    if (!currentRunExists) {
      setSelectedRunId(availableRuns[0].id);
    }
  }, [runsQuery.data?.items, selectedRunId]);

  const findingsQuery = useQuery({
    queryKey: [
      "reconciliation-findings",
      selectedRunId,
      findingStatusFilter,
      findingSeverityFilter,
    ],
    enabled: Boolean(selectedRunId),
    queryFn: () =>
      listReconciliationFindings(selectedRunId as string, {
        limit: 500,
        status: findingStatusFilter || undefined,
        severity: findingSeverityFilter || undefined,
      }),
  });

  const reviewTasksQuery = useQuery({
    queryKey: [
      "reconciliation-review-tasks",
      selectedRunId,
      reviewStatusFilter,
      reviewPriorityFilter,
    ],
    enabled: Boolean(selectedRunId),
    queryFn: () =>
      listReviewTasks({
        limit: 200,
        runId: selectedRunId ?? undefined,
        status: reviewStatusFilter || undefined,
        priority: reviewPriorityFilter || undefined,
      }),
  });

  useEffect(() => {
    const findings = findingsQuery.data?.items ?? [];

    if (findings.length === 0) {
      setSelectedFinding(null);
      return;
    }

    const selectedStillExists = findings.some(
      (finding) => finding.id === selectedFinding?.id,
    );

    if (!selectedStillExists) {
      setSelectedFinding(findings[0]);
    }
  }, [findingsQuery.data?.items, selectedFinding?.id]);

  const startRunMutation = useMutation({
    mutationFn: () =>
      startDocumentReconciliation(documentId.trim(), {
        minimum_confidence: Number(minimumConfidence),
        premium_tolerance: premiumTolerance,
        exclude_cancelled: excludeCancelled,
      }),
    onSuccess: async (response) => {
      setWorkspaceNotice(response.message);
      setSelectedRunId(response.run.id);
      setActiveTab("findings");

      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["reconciliation-runs"],
        }),
        queryClient.invalidateQueries({
          queryKey: ["reconciliation-findings"],
        }),
        queryClient.invalidateQueries({
          queryKey: ["reconciliation-review-tasks"],
        }),
      ]);
    },
  });

  const updateTaskMutation = useMutation({
    mutationFn: ({
      task,
      status,
      notes,
      corrected,
    }: {
      task: ReviewTaskRead;
      status: ReviewTaskStatus;
      notes?: string;
      corrected?: unknown;
    }) =>
      updateReviewTask(task.id, {
        status,
        resolution_notes: notes,
        ...(status === "corrected"
          ? {
              corrected_value: corrected,
            }
          : {}),
      }),
    onSuccess: async (response) => {
      setWorkspaceNotice(response.message);
      setSelectedTask(response.task);
      setResolutionAction(null);
      setResolutionNotes("");
      setCorrectedValue("");

      await queryClient.invalidateQueries({
        queryKey: ["reconciliation-review-tasks"],
      });
    },
  });

  const downloadMutation = useMutation({
    mutationFn: async ({
      run,
      format,
    }: {
      run: ReconciliationRunRead;
      format: ReconciliationReportFormat;
    }) => {
      const report = await downloadReconciliationReport(run.id, format);
      saveReconciliationReport(report);
      return report;
    },
    onSuccess: (report) => {
      setWorkspaceNotice(`${report.filename} downloaded.`);
    },
  });

  const handleStartRun = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setWorkspaceNotice(null);

    if (!documentId.trim()) {
      setWorkspaceNotice(
        "Enter a document ID before starting reconciliation.",
      );
      return;
    }

    const parsedConfidence = Number(minimumConfidence);

    if (
      Number.isNaN(parsedConfidence)
      || parsedConfidence < 0
      || parsedConfidence > 1
    ) {
      setWorkspaceNotice("Minimum confidence must be between 0 and 1.");
      return;
    }

    const parsedTolerance = Number(premiumTolerance);

    if (Number.isNaN(parsedTolerance) || parsedTolerance < 0) {
      setWorkspaceNotice("Premium tolerance must be zero or greater.");
      return;
    }

    startRunMutation.mutate();
  };

  const handleBeginTask = (task: ReviewTaskRead) => {
    updateTaskMutation.mutate({
      task,
      status: "in_progress",
    });
  };

  const openResolution = (
    task: ReviewTaskRead,
    action: ResolutionAction,
  ) => {
    setSelectedTask(task);
    setResolutionAction(action);
    setResolutionNotes(task.resolution_notes ?? "");
    setCorrectedValue(
      task.corrected_value === null || task.corrected_value === undefined
        ? ""
        : formatValue(task.corrected_value),
    );
  };

  const submitResolution = () => {
    if (!selectedTask || !resolutionAction) {
      return;
    }

    if (!resolutionNotes.trim()) {
      setWorkspaceNotice("Resolution notes are required.");
      return;
    }

    if (resolutionAction === "corrected" && !correctedValue.trim()) {
      setWorkspaceNotice("Enter the corrected value.");
      return;
    }

    updateTaskMutation.mutate({
      task: selectedTask,
      status: resolutionAction,
      notes: resolutionNotes.trim(),
      corrected:
        resolutionAction === "corrected"
          ? correctedValue.trim()
          : undefined,
    });
  };

  const extractionSummary = selectedRun?.summary_data ?? {};
  const findings = findingsQuery.data?.items ?? [];
  const reviewTasks = reviewTasksQuery.data?.items ?? [];

  const openReviewCount = reviewTasks.filter(
    (task) => task.status === "open" || task.status === "in_progress",
  ).length;

  return (
    <section className="reconciliation-workspace">
      <header className="reconciliation-hero">
        <div className="reconciliation-hero__copy">
          <span className="reconciliation-eyebrow">Document intelligence</span>
          <h1>Reconciliation</h1>
          <p>
            Compare processed policy documents with operational records,
            review mismatches, and export audit-ready reports.
          </p>
        </div>

        <form className="reconciliation-launcher" onSubmit={handleStartRun}>
          <div className="reconciliation-launcher__heading">
            <div>
              <span>New reconciliation</span>
              <strong>Processed document</strong>
            </div>
            <span className="reconciliation-launcher__state">
              Deterministic
            </span>
          </div>

          <label className="reconciliation-field reconciliation-field--wide">
            <span>Document ID</span>
            <input
              type="text"
              value={documentId}
              onChange={(event) => setDocumentId(event.target.value)}
              placeholder="Paste the processed document UUID"
            />
          </label>

          <div className="reconciliation-launcher__grid">
            <label className="reconciliation-field">
              <span>Minimum confidence</span>
              <input
                type="number"
                min="0"
                max="1"
                step="0.01"
                value={minimumConfidence}
                onChange={(event) => setMinimumConfidence(event.target.value)}
              />
            </label>

            <label className="reconciliation-field">
              <span>Premium tolerance</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={premiumTolerance}
                onChange={(event) => setPremiumTolerance(event.target.value)}
              />
            </label>
          </div>

          <label className="reconciliation-switch">
            <input
              type="checkbox"
              checked={excludeCancelled}
              onChange={(event) => setExcludeCancelled(event.target.checked)}
            />
            <span className="reconciliation-switch__control" />
            <span>Exclude cancelled policies from payment checks</span>
          </label>

          <button
            type="submit"
            className="reconciliation-primary-button"
            disabled={startRunMutation.isPending}
          >
            {startRunMutation.isPending
              ? "Running reconciliation..."
              : "Start reconciliation"}
          </button>

          {startRunMutation.isError ? (
            <p className="reconciliation-form-error">
              {getErrorMessage(startRunMutation.error)}
            </p>
          ) : null}
        </form>
      </header>

      {workspaceNotice ? (
        <div className="reconciliation-notice">
          <span>{workspaceNotice}</span>
          <button
            type="button"
            onClick={() => setWorkspaceNotice(null)}
            aria-label="Dismiss message"
          >
            ×
          </button>
        </div>
      ) : null}

      <div className="reconciliation-layout">
        <aside className="reconciliation-runs-panel">
          <div className="reconciliation-panel-heading">
            <div>
              <span>Run history</span>
              <strong>{runsQuery.data?.total ?? 0} runs</strong>
            </div>

            <select
              value={runStatusFilter}
              onChange={(event) =>
                setRunStatusFilter(
                  event.target.value as ReconciliationRunStatus | "",
                )
              }
            >
              {RUN_STATUS_OPTIONS.map((option) => (
                <option key={option.value || "all"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="reconciliation-run-list">
            {runsQuery.isLoading ? (
              <div className="reconciliation-loading">Loading runs…</div>
            ) : null}

            {runsQuery.isError ? (
              <div className="reconciliation-inline-error">
                {getErrorMessage(runsQuery.error)}
              </div>
            ) : null}

            {!runsQuery.isLoading
            && !runsQuery.isError
            && (runsQuery.data?.items.length ?? 0) === 0 ? (
              <EmptyState
                title="No reconciliation runs"
                description="Start a reconciliation using a processed policy document."
              />
            ) : null}

            {runsQuery.data?.items.map((run) => (
              <button
                type="button"
                key={run.id}
                className={[
                  "reconciliation-run-card",
                  selectedRunId === run.id
                    ? "reconciliation-run-card--selected"
                    : "",
                ].join(" ")}
                onClick={() => {
                  setSelectedRunId(run.id);
                  setSelectedFinding(null);
                  setSelectedTask(null);
                }}
              >
                <div className="reconciliation-run-card__top">
                  <StatusBadge
                    value={run.status}
                    tone={getRunStatusTone(run.status)}
                  />
                  <span>{formatDateTime(run.created_at)}</span>
                </div>

                <strong>{formatLabel(run.reconciliation_type)}</strong>
                <code>{run.document_id}</code>

                <div className="reconciliation-run-card__metrics">
                  <span>{run.passed_checks} passed</span>
                  <span>{run.failed_checks} failed</span>
                  <span>{run.review_checks} review</span>
                </div>
              </button>
            ))}
          </div>
        </aside>

        <main className="reconciliation-main">
          {!selectedRun ? (
            <EmptyState
              title="Select a reconciliation run"
              description="Choose a run from the history panel to inspect its findings and review tasks."
            />
          ) : (
            <>
              <section className="reconciliation-run-header">
                <div>
                  <div className="reconciliation-run-header__status">
                    <StatusBadge
                      value={selectedRun.status}
                      tone={getRunStatusTone(selectedRun.status)}
                    />
                    <span>Run {selectedRun.id.slice(0, 8)}</span>
                  </div>

                  <h2>{formatLabel(selectedRun.reconciliation_type)}</h2>
                  <p>
                    Document <code>{selectedRun.document_id}</code>
                  </p>
                </div>

                <div className="reconciliation-report-actions">
                  <button
                    type="button"
                    onClick={() =>
                      downloadMutation.mutate({
                        run: selectedRun,
                        format: "csv",
                      })
                    }
                    disabled={downloadMutation.isPending}
                  >
                    Download CSV
                  </button>

                  <button
                    type="button"
                    className="reconciliation-report-actions__primary"
                    onClick={() =>
                      downloadMutation.mutate({
                        run: selectedRun,
                        format: "xlsx",
                      })
                    }
                    disabled={downloadMutation.isPending}
                  >
                    Download Excel
                  </button>
                </div>
              </section>

              <section className="reconciliation-metrics-grid">
                <MetricCard
                  label="Total checks"
                  value={selectedRun.total_checks}
                  detail="Rules evaluated"
                />
                <MetricCard
                  label="Passed"
                  value={selectedRun.passed_checks}
                  detail="No action required"
                />
                <MetricCard
                  label="Failed"
                  value={selectedRun.failed_checks}
                  detail="Confirmed mismatch"
                />
                <MetricCard
                  label="Review queue"
                  value={openReviewCount}
                  detail="Open or in progress"
                />
              </section>

              <nav className="reconciliation-tabs">
                <button
                  type="button"
                  className={
                    activeTab === "findings"
                      ? "reconciliation-tabs__active"
                      : ""
                  }
                  onClick={() => setActiveTab("findings")}
                >
                  Findings
                  <span>{findingsQuery.data?.total ?? 0}</span>
                </button>

                <button
                  type="button"
                  className={
                    activeTab === "reviews"
                      ? "reconciliation-tabs__active"
                      : ""
                  }
                  onClick={() => setActiveTab("reviews")}
                >
                  Review queue
                  <span>{reviewTasksQuery.data?.total ?? 0}</span>
                </button>

                <button
                  type="button"
                  className={
                    activeTab === "extraction"
                      ? "reconciliation-tabs__active"
                      : ""
                  }
                  onClick={() => setActiveTab("extraction")}
                >
                  Run details
                </button>
              </nav>

              {activeTab === "findings" ? (
                <section className="reconciliation-tab-panel">
                  <div className="reconciliation-toolbar">
                    <div>
                      <h3>Reconciliation findings</h3>
                      <p>
                        Review expected values, extracted values, and source
                        evidence.
                      </p>
                    </div>

                    <div className="reconciliation-toolbar__filters">
                      <select
                        value={findingStatusFilter}
                        onChange={(event) =>
                          setFindingStatusFilter(
                            event.target.value as
                              | ReconciliationFindingStatus
                              | "",
                          )
                        }
                      >
                        {FINDING_STATUS_OPTIONS.map((option) => (
                          <option
                            key={option.value || "all"}
                            value={option.value}
                          >
                            {option.label}
                          </option>
                        ))}
                      </select>

                      <select
                        value={findingSeverityFilter}
                        onChange={(event) =>
                          setFindingSeverityFilter(
                            event.target.value as
                              | ReconciliationFindingSeverity
                              | "",
                          )
                        }
                      >
                        {FINDING_SEVERITY_OPTIONS.map((option) => (
                          <option
                            key={option.value || "all"}
                            value={option.value}
                          >
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="reconciliation-findings-layout">
                    <div className="reconciliation-findings-table-wrapper">
                      {findingsQuery.isLoading ? (
                        <div className="reconciliation-loading">
                          Loading findings…
                        </div>
                      ) : null}

                      {findingsQuery.isError ? (
                        <div className="reconciliation-inline-error">
                          {getErrorMessage(findingsQuery.error)}
                        </div>
                      ) : null}

                      {!findingsQuery.isLoading && findings.length === 0 ? (
                        <EmptyState
                          title="No matching findings"
                          description="Change the filters or select another reconciliation run."
                        />
                      ) : null}

                      {findings.length > 0 ? (
                        <table className="reconciliation-table">
                          <thead>
                            <tr>
                              <th>Rule</th>
                              <th>Field</th>
                              <th>Result</th>
                              <th>Severity</th>
                              <th>Expected</th>
                              <th>Actual</th>
                            </tr>
                          </thead>

                          <tbody>
                            {findings.map((finding) => (
                              <tr
                                key={finding.id}
                                className={
                                  selectedFinding?.id === finding.id
                                    ? "reconciliation-table__selected"
                                    : ""
                                }
                                onClick={() => setSelectedFinding(finding)}
                              >
                                <td>
                                  <strong>{finding.rule_code}</strong>
                                  <span>{formatLabel(finding.finding_type)}</span>
                                </td>

                                <td>
                                  {finding.field_name
                                    ? formatLabel(finding.field_name)
                                    : "General"}
                                </td>

                                <td>
                                  <StatusBadge
                                    value={finding.status}
                                    tone={getFindingTone(finding)}
                                  />
                                </td>

                                <td>
                                  <StatusBadge
                                    value={finding.severity}
                                    tone={getSeverityTone(finding.severity)}
                                  />
                                </td>

                                <td>
                                  <span className="reconciliation-value-cell">
                                    {formatValue(finding.expected_value)}
                                  </span>
                                </td>

                                <td>
                                  <span className="reconciliation-value-cell">
                                    {formatValue(finding.actual_value)}
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      ) : null}
                    </div>

                    <aside className="reconciliation-evidence-panel">
                      {!selectedFinding ? (
                        <EmptyState
                          title="Select a finding"
                          description="Choose a row to inspect its source evidence and normalized values."
                        />
                      ) : (
                        <>
                          <div className="reconciliation-evidence-panel__heading">
                            <div>
                              <span>{selectedFinding.rule_code}</span>
                              <h3>{formatLabel(selectedFinding.finding_type)}</h3>
                            </div>

                            <StatusBadge
                              value={selectedFinding.status}
                              tone={getFindingTone(selectedFinding)}
                            />
                          </div>

                          <p className="reconciliation-evidence-panel__message">
                            {selectedFinding.message}
                          </p>

                          <div className="reconciliation-comparison">
                            <div>
                              <span>Database value</span>
                              <pre>
                                {formatValue(selectedFinding.expected_value)}
                              </pre>
                            </div>

                            <div>
                              <span>Document value</span>
                              <pre>{formatValue(selectedFinding.actual_value)}</pre>
                            </div>
                          </div>

                          <div className="reconciliation-evidence">
                            <div className="reconciliation-evidence__meta">
                              <span>Source evidence</span>
                              <span>
                                Page {selectedFinding.source_page_number ?? "—"}
                              </span>
                            </div>

                            <blockquote>
                              {selectedFinding.source_text
                                || "No page-level evidence was recorded."}
                            </blockquote>
                          </div>

                          <dl className="reconciliation-detail-list">
                            <div>
                              <dt>Confidence</dt>
                              <dd>
                                {selectedFinding.confidence_score !== null
                                  ? `${(
                                      selectedFinding.confidence_score * 100
                                    ).toFixed(1)}%`
                                  : "Not available"}
                              </dd>
                            </div>

                            <div>
                              <dt>Policy ID</dt>
                              <dd>
                                {selectedFinding.business_policy_id
                                  || "Not matched"}
                              </dd>
                            </div>

                            <div>
                              <dt>Created</dt>
                              <dd>{formatDateTime(selectedFinding.created_at)}</dd>
                            </div>
                          </dl>
                        </>
                      )}
                    </aside>
                  </div>
                </section>
              ) : null}

              {activeTab === "reviews" ? (
                <section className="reconciliation-tab-panel">
                  <div className="reconciliation-toolbar">
                    <div>
                      <h3>Human review queue</h3>
                      <p>
                        Resolve uncertain or failed reconciliation results with
                        an auditable decision.
                      </p>
                    </div>

                    <div className="reconciliation-toolbar__filters">
                      <select
                        value={reviewStatusFilter}
                        onChange={(event) =>
                          setReviewStatusFilter(
                            event.target.value as ReviewTaskStatus | "",
                          )
                        }
                      >
                        {REVIEW_STATUS_OPTIONS.map((option) => (
                          <option
                            key={option.value || "all"}
                            value={option.value}
                          >
                            {option.label}
                          </option>
                        ))}
                      </select>

                      <select
                        value={reviewPriorityFilter}
                        onChange={(event) =>
                          setReviewPriorityFilter(
                            event.target.value as ReviewTaskPriority | "",
                          )
                        }
                      >
                        {REVIEW_PRIORITY_OPTIONS.map((option) => (
                          <option
                            key={option.value || "all"}
                            value={option.value}
                          >
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  {reviewTasksQuery.isLoading ? (
                    <div className="reconciliation-loading">
                      Loading review tasks…
                    </div>
                  ) : null}

                  {reviewTasksQuery.isError ? (
                    <div className="reconciliation-inline-error">
                      {getErrorMessage(reviewTasksQuery.error)}
                    </div>
                  ) : null}

                  {!reviewTasksQuery.isLoading && reviewTasks.length === 0 ? (
                    <EmptyState
                      title="No review tasks"
                      description="This run has no tasks matching the selected filters."
                    />
                  ) : null}

                  <div className="reconciliation-review-grid">
                    {reviewTasks.map((task) => {
                      const resolved = RESOLVED_REVIEW_STATUSES.includes(
                        task.status,
                      );

                      return (
                        <article
                          key={task.id}
                          className="reconciliation-review-card"
                        >
                          <div className="reconciliation-review-card__top">
                            <StatusBadge
                              value={task.priority}
                              tone={getSeverityTone(task.priority)}
                            />

                            <StatusBadge
                              value={task.status}
                              tone={
                                resolved
                                  ? "success"
                                  : task.status === "in_progress"
                                    ? "active"
                                    : "warning"
                              }
                            />
                          </div>

                          <h4>{task.title}</h4>
                          <p>{task.description || "No description provided."}</p>

                          <dl>
                            <div>
                              <dt>Rule</dt>
                              <dd>
                                {formatValue(task.extra_metadata["rule_code"])}
                              </dd>
                            </div>

                            <div>
                              <dt>Field</dt>
                              <dd>
                                {formatValue(task.extra_metadata["field_name"])}
                              </dd>
                            </div>

                            <div>
                              <dt>Created</dt>
                              <dd>{formatDateTime(task.created_at)}</dd>
                            </div>
                          </dl>

                          {resolved ? (
                            <div className="reconciliation-resolution-summary">
                              <strong>Resolution</strong>
                              <p>{task.resolution_notes || "No notes provided."}</p>

                              {task.status === "corrected" ? (
                                <code>{formatValue(task.corrected_value)}</code>
                              ) : null}
                            </div>
                          ) : (
                            <div className="reconciliation-review-card__actions">
                              {task.status === "open" ? (
                                <button
                                  type="button"
                                  onClick={() => handleBeginTask(task)}
                                  disabled={updateTaskMutation.isPending}
                                >
                                  Start review
                                </button>
                              ) : null}

                              <button
                                type="button"
                                onClick={() => openResolution(task, "approved")}
                              >
                                Approve
                              </button>

                              <button
                                type="button"
                                onClick={() => openResolution(task, "corrected")}
                              >
                                Correct
                              </button>

                              <button
                                type="button"
                                className="reconciliation-danger-button"
                                onClick={() => openResolution(task, "rejected")}
                              >
                                Reject
                              </button>
                            </div>
                          )}
                        </article>
                      );
                    })}
                  </div>
                </section>
              ) : null}

              {activeTab === "extraction" ? (
                <section className="reconciliation-tab-panel">
                  <div className="reconciliation-toolbar">
                    <div>
                      <h3>Run details</h3>
                      <p>
                        Processing identifiers, configuration, extraction
                        confidence, and recorded summary data.
                      </p>
                    </div>
                  </div>

                  <div className="reconciliation-details-grid">
                    <article>
                      <span>Run information</span>
                      <dl>
                        <div>
                          <dt>Run ID</dt>
                          <dd>{selectedRun.id}</dd>
                        </div>
                        <div>
                          <dt>Processing run</dt>
                          <dd>
                            {selectedRun.processing_run_id || "Not available"}
                          </dd>
                        </div>
                        <div>
                          <dt>Requested by</dt>
                          <dd>
                            {selectedRun.requested_by_user_id || "System"}
                          </dd>
                        </div>
                        <div>
                          <dt>Started</dt>
                          <dd>{formatDateTime(selectedRun.started_at)}</dd>
                        </div>
                        <div>
                          <dt>Completed</dt>
                          <dd>{formatDateTime(selectedRun.completed_at)}</dd>
                        </div>
                      </dl>
                    </article>

                    <article>
                      <span>Run parameters</span>
                      <pre>
                        {JSON.stringify(selectedRun.run_parameters, null, 2)}
                      </pre>
                    </article>

                    <article>
                      <span>Summary data</span>
                      <pre>{JSON.stringify(extractionSummary, null, 2)}</pre>
                    </article>

                    {selectedRun.error_message ? (
                      <article className="reconciliation-details-grid__error">
                        <span>Error</span>
                        <pre>{selectedRun.error_message}</pre>
                      </article>
                    ) : null}
                  </div>
                </section>
              ) : null}
            </>
          )}
        </main>
      </div>

      {selectedTask && resolutionAction ? (
        <div
          className="reconciliation-modal-backdrop"
          role="presentation"
          onMouseDown={() => {
            if (!updateTaskMutation.isPending) {
              setResolutionAction(null);
            }
          }}
        >
          <section
            className="reconciliation-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="reconciliation-resolution-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="reconciliation-modal__heading">
              <div>
                <span>Review decision</span>
                <h3 id="reconciliation-resolution-title">
                  {formatLabel(resolutionAction)} task
                </h3>
              </div>

              <button
                type="button"
                onClick={() => setResolutionAction(null)}
                disabled={updateTaskMutation.isPending}
                aria-label="Close review dialog"
              >
                ×
              </button>
            </div>

            <div className="reconciliation-modal__task">
              <strong>{selectedTask.title}</strong>
              <p>{selectedTask.description || "No task description provided."}</p>
            </div>

            <label className="reconciliation-field reconciliation-field--wide">
              <span>Resolution notes</span>
              <textarea
                rows={5}
                value={resolutionNotes}
                onChange={(event) => setResolutionNotes(event.target.value)}
                placeholder="Describe what was reviewed and why this decision was made."
              />
            </label>

            {resolutionAction === "corrected" ? (
              <label className="reconciliation-field reconciliation-field--wide">
                <span>Corrected value</span>
                <textarea
                  rows={3}
                  value={correctedValue}
                  onChange={(event) => setCorrectedValue(event.target.value)}
                  placeholder="Enter the corrected value"
                />
              </label>
            ) : null}

            {updateTaskMutation.isError ? (
              <p className="reconciliation-form-error">
                {getErrorMessage(updateTaskMutation.error)}
              </p>
            ) : null}

            <div className="reconciliation-modal__actions">
              <button
                type="button"
                onClick={() => setResolutionAction(null)}
                disabled={updateTaskMutation.isPending}
              >
                Cancel
              </button>

              <button
                type="button"
                className={
                  resolutionAction === "rejected"
                    ? "reconciliation-danger-button"
                    : "reconciliation-primary-button"
                }
                onClick={submitResolution}
                disabled={updateTaskMutation.isPending}
              >
                {updateTaskMutation.isPending
                  ? "Saving decision..."
                  : `Confirm ${formatLabel(resolutionAction)}`}
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </section>
  );
}