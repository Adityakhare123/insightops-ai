import {
  apiClient,
  apiRequest,
} from "../../api/client";

import type {
  DownloadedReconciliationReport,
  ReconciliationFindingListParameters,
  ReconciliationFindingListResponse,
  ReconciliationReportFormat,
  ReconciliationRunListParameters,
  ReconciliationRunListResponse,
  ReconciliationRunRead,
  ReconciliationStartRequest,
  ReconciliationStartResponse,
  ReviewTaskListParameters,
  ReviewTaskListResponse,
  ReviewTaskRead,
  ReviewTaskUpdateRequest,
  ReviewTaskUpdateResponse,
} from "../../types/reconciliation";


function buildQueryString(
  values: Record<
    string,
    string | number | undefined
  >,
): string {
  const searchParameters =
    new URLSearchParams();

  Object.entries(values).forEach(
    ([
      parameterName,
      parameterValue,
    ]) => {
      if (
        parameterValue === undefined
        || parameterValue === ""
      ) {
        return;
      }

      searchParameters.set(
        parameterName,
        String(parameterValue),
      );
    },
  );

  const queryString =
    searchParameters.toString();

  return queryString
    ? `?${queryString}`
    : "";
}


export function listReconciliationRuns(
  parameters:
    ReconciliationRunListParameters = {},
): Promise<ReconciliationRunListResponse> {
  const queryString = buildQueryString({
    limit: parameters.limit,
    offset: parameters.offset,
    status: parameters.status,
    document_id:
      parameters.documentId,
  });

  return apiClient.get<
    ReconciliationRunListResponse
  >(
    `/reconciliation/runs${queryString}`,
  );
}


export function getReconciliationRun(
  runId: string,
): Promise<ReconciliationRunRead> {
  return apiClient.get<
    ReconciliationRunRead
  >(
    `/reconciliation/runs/${runId}`,
  );
}


export function startDocumentReconciliation(
  documentId: string,
  request:
    ReconciliationStartRequest = {},
): Promise<ReconciliationStartResponse> {
  const requestPayload = {
    minimum_confidence:
      request.minimum_confidence
      ?? 0.75,

    premium_tolerance:
      request.premium_tolerance
      ?? "0.01",

    exclude_cancelled:
      request.exclude_cancelled
      ?? true,
  };

  return apiRequest<
    ReconciliationStartResponse
  >(
    (
      "/reconciliation/documents/"
      + `${documentId}/run`
    ),
    {
      method: "POST",

      headers: {
        "Content-Type":
          "application/json",
      },

      body: JSON.stringify(
        requestPayload,
      ),
    },
  );
}


export function listReconciliationFindings(
  runId: string,
  parameters:
    ReconciliationFindingListParameters = {},
): Promise<
  ReconciliationFindingListResponse
> {
  const queryString = buildQueryString({
    limit: parameters.limit,
    offset: parameters.offset,
    status: parameters.status,
    severity: parameters.severity,
  });

  return apiClient.get<
    ReconciliationFindingListResponse
  >(
    (
      `/reconciliation/runs/${runId}`
      + `/findings${queryString}`
    ),
  );
}


export function listReviewTasks(
  parameters:
    ReviewTaskListParameters = {},
): Promise<ReviewTaskListResponse> {
  const queryString = buildQueryString({
    limit: parameters.limit,
    offset: parameters.offset,
    status: parameters.status,
    priority: parameters.priority,
    assigned_to_user_id:
      parameters.assignedToUserId,
    run_id: parameters.runId,
    document_id:
      parameters.documentId,
  });

  return apiClient.get<
    ReviewTaskListResponse
  >(
    (
      "/reconciliation/review-tasks"
      + queryString
    ),
  );
}


export function getReviewTask(
  taskId: string,
): Promise<ReviewTaskRead> {
  return apiClient.get<
    ReviewTaskRead
  >(
    (
      "/reconciliation/review-tasks/"
      + taskId
    ),
  );
}


export function updateReviewTask(
  taskId: string,
  request: ReviewTaskUpdateRequest,
): Promise<ReviewTaskUpdateResponse> {
  return apiRequest<
    ReviewTaskUpdateResponse
  >(
    (
      "/reconciliation/review-tasks/"
      + taskId
    ),
    {
      method: "PATCH",

      headers: {
        "Content-Type":
          "application/json",
      },

      body: JSON.stringify(
        request,
      ),
    },
  );
}


export async function downloadReconciliationReport(
  runId: string,
  format: ReconciliationReportFormat,
): Promise<
  DownloadedReconciliationReport
> {
  const downloadedFile =
    await apiClient.download(
      (
        `/reconciliation/runs/${runId}`
        + `/reports/${format}`
      ),
    );

  return {
    blob: downloadedFile.blob,

    filename:
      downloadedFile.filename
      ?? (
        `reconciliation-${runId}`
        + `.${format}`
      ),

    contentType:
      downloadedFile.contentType,

    format,
  };
}


export function saveReconciliationReport(
  report: DownloadedReconciliationReport,
): void {
  const objectUrl =
    URL.createObjectURL(
      report.blob,
    );

  const downloadLink =
    window.document.createElement(
      "a",
    );

  downloadLink.href = objectUrl;

  downloadLink.download =
    report.filename;

  window.document.body.appendChild(
    downloadLink,
  );

  downloadLink.click();

  downloadLink.remove();

  URL.revokeObjectURL(
    objectUrl,
  );
}