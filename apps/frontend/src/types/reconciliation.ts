export type ReconciliationRunStatus =
  | "queued"
  | "running"
  | "completed"
  | "needs_review"
  | "failed"
  | "cancelled";

export type ReconciliationFindingStatus =
  | "passed"
  | "failed"
  | "needs_review"
  | "skipped";

export type ReconciliationFindingSeverity =
  | "high"
  | "medium"
  | "low"
  | "info";

export type ReviewTaskStatus =
  | "open"
  | "in_progress"
  | "approved"
  | "corrected"
  | "rejected";

export type ReviewTaskPriority =
  | "high"
  | "medium"
  | "low";

export type ReconciliationReportFormat =
  | "csv"
  | "xlsx";


export interface ReconciliationRunRead {
  id: string;
  workspace_id: string;
  document_id: string;

  processing_run_id: string | null;
  requested_by_user_id: string | null;

  reconciliation_type: string;
  status: ReconciliationRunStatus;

  exclude_cancelled: boolean;

  started_at: string | null;
  completed_at: string | null;

  total_checks: number;
  passed_checks: number;
  failed_checks: number;
  review_checks: number;

  error_message: string | null;

  run_parameters: Record<
    string,
    unknown
  >;

  summary_data: Record<
    string,
    unknown
  >;

  created_at: string;
  updated_at: string;
}


export interface ReconciliationFindingRead {
  id: string;
  workspace_id: string;

  reconciliation_run_id: string;
  document_id: string;
  document_page_id: string | null;

  business_policy_id: string | null;

  rule_code: string;
  finding_type: string;
  field_name: string | null;

  status: ReconciliationFindingStatus;
  severity: ReconciliationFindingSeverity;

  expected_value: unknown;
  actual_value: unknown;

  message: string;

  source_text: string | null;
  source_page_number: number | null;
  confidence_score: number | null;

  evidence_data: Record<
    string,
    unknown
  >;

  created_at: string;
  updated_at: string;
}


export interface ReviewTaskRead {
  id: string;
  workspace_id: string;

  reconciliation_run_id: string;
  reconciliation_finding_id: string;
  document_id: string;

  created_by_user_id: string | null;
  assigned_to_user_id: string | null;
  resolved_by_user_id: string | null;

  status: ReviewTaskStatus;
  priority: ReviewTaskPriority;

  title: string;
  description: string | null;

  resolution_notes: string | null;
  corrected_value: unknown;

  due_at: string | null;
  resolved_at: string | null;

  extra_metadata: Record<
    string,
    unknown
  >;

  created_at: string;
  updated_at: string;
}


export interface ExtractedPolicyFieldRead {
  name: string;
  value: unknown;
  raw_value: string | null;

  found: boolean;

  page_number: number | null;
  source_text: string | null;

  confidence_score: number | null;
  extraction_method: string | null;
}


export interface PolicyDocumentExtractionRead {
  fields: Record<
    string,
    ExtractedPolicyFieldRead
  >;

  warnings: string[];

  document_confidence: number;
  page_count: number;
}


export interface ReconciliationStartRequest {
  minimum_confidence?: number;
  premium_tolerance?: string;
  exclude_cancelled?: boolean;
}


export interface ReconciliationStartResponse {
  message: string;

  run: ReconciliationRunRead;

  findings: ReconciliationFindingRead[];

  review_tasks: ReviewTaskRead[];

  extraction: PolicyDocumentExtractionRead;
}


export interface ReconciliationRunListResponse {
  items: ReconciliationRunRead[];

  total: number;
  limit: number;
  offset: number;
}


export interface ReconciliationFindingListResponse {
  items: ReconciliationFindingRead[];

  total: number;
  limit: number;
  offset: number;
}


export interface ReviewTaskListResponse {
  items: ReviewTaskRead[];

  total: number;
  limit: number;
  offset: number;
}


export interface ReviewTaskUpdateRequest {
  status?: ReviewTaskStatus;

  assigned_to_user_id?:
    | string
    | null;

  resolution_notes?:
    | string
    | null;

  corrected_value?: unknown;
}


export interface ReviewTaskUpdateResponse {
  message: string;
  task: ReviewTaskRead;
}


export interface ReconciliationRunListParameters {
  limit?: number;
  offset?: number;

  status?: ReconciliationRunStatus;

  documentId?: string;
}


export interface ReconciliationFindingListParameters {
  limit?: number;
  offset?: number;

  status?:
    ReconciliationFindingStatus;

  severity?:
    ReconciliationFindingSeverity;
}


export interface ReviewTaskListParameters {
  limit?: number;
  offset?: number;

  status?: ReviewTaskStatus;

  priority?: ReviewTaskPriority;

  assignedToUserId?: string;

  runId?: string;

  documentId?: string;
}


export interface DownloadedReconciliationReport {
  blob: Blob;

  filename: string;

  contentType: string;

  format: ReconciliationReportFormat;
}