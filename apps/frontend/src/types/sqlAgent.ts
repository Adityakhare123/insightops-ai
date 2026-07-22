export interface SQLAgentPlanRequest {
  question: string;
  max_rows?: number | null;
}


export interface SQLAgentQueryRequest
  extends SQLAgentPlanRequest {
  statement_timeout_ms?: number | null;
}


export interface SQLAgentColumn {
  name: string;
  data_type: string;
  nullable: boolean;
  primary_key: boolean;
  description: string | null;
}


export interface SQLAgentRelationship {
  source_table: string;
  source_columns: string[];
  target_table: string;
  target_columns: string[];
}


export interface SQLAgentTable {
  schema_name: string;
  table_name: string;
  qualified_name: string;
  description: string;
  columns: SQLAgentColumn[];
  relationships: SQLAgentRelationship[];
}


export interface SQLAgentSchemaResponse {
  schema_name: string;
  table_count: number;
  tables: SQLAgentTable[];
}


export interface SQLAgentPlanResponse {
  question: string;
  normalized_question: string;

  intent: string;
  explanation: string;

  generated_sql: string;
  normalized_sql: string;
  executable_sql: string;

  referenced_tables: string[];
  max_rows: number;
}


export type SQLAgentRowValue =
  | string
  | number
  | boolean
  | null
  | SQLAgentRowValue[]
  | {
      [key: string]: SQLAgentRowValue;
    };


export interface SQLAgentExecutionResponse {
  original_sql: string;
  normalized_sql: string;
  executable_sql: string;

  referenced_tables: string[];

  columns: string[];

  rows: Array<
    Record<string, SQLAgentRowValue>
  >;

  row_count: number;
  max_rows: number;
  limit_reached: boolean;

  statement_timeout_ms: number;
  execution_time_ms: number;
}


export interface SQLAgentQueryResponse {
  plan: SQLAgentPlanResponse;
  execution: SQLAgentExecutionResponse;
}