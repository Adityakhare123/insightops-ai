import {
  apiRequest,
} from "../../api/client";

import type {
  SQLAgentPlanRequest,
  SQLAgentPlanResponse,
  SQLAgentQueryRequest,
  SQLAgentQueryResponse,
  SQLAgentSchemaResponse,
} from "../../types/sqlAgent";


export function getSQLAgentSchema():
Promise<SQLAgentSchemaResponse> {
  return apiRequest<SQLAgentSchemaResponse>(
    "/sql-agent/schema",
    {
      method: "GET",
    },
  );
}


export function planSQLAgentQuery(
  request: SQLAgentPlanRequest,
): Promise<SQLAgentPlanResponse> {
  return apiRequest<SQLAgentPlanResponse>(
    "/sql-agent/plan",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    },
  );
}


export function executeSQLAgentQuery(
  request: SQLAgentQueryRequest,
): Promise<SQLAgentQueryResponse> {
  return apiRequest<SQLAgentQueryResponse>(
    "/sql-agent/query",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    },
  );
}