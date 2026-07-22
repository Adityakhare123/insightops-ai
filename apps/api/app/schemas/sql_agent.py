from __future__ import annotations

from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class SQLAgentPlanRequest(BaseModel):
    """Natural-language SQL planning request."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    question: str = Field(
        min_length=1,
        max_length=1_000,
        description=(
            "Natural-language question about the "
            "approved insurance database."
        ),
    )

    max_rows: int | None = Field(
        default=None,
        ge=1,
        le=10_000,
        description=(
            "Maximum number of rows that the query "
            "may return."
        ),
    )


class SQLAgentQueryRequest(
    SQLAgentPlanRequest,
):
    """Natural-language SQL planning and execution request."""

    statement_timeout_ms: int | None = Field(
        default=None,
        ge=100,
        le=60_000,
        description=(
            "PostgreSQL statement timeout in milliseconds."
        ),
    )


class SQLAgentColumnRead(BaseModel):
    """Approved database column metadata."""

    name: str
    data_type: str
    nullable: bool
    primary_key: bool
    description: str | None = None


class SQLAgentRelationshipRead(BaseModel):
    """Approved database foreign-key relationship."""

    source_table: str
    source_columns: list[str]

    target_table: str
    target_columns: list[str]


class SQLAgentTableRead(BaseModel):
    """Approved database table metadata."""

    schema_name: str
    table_name: str
    qualified_name: str
    description: str

    columns: list[
        SQLAgentColumnRead
    ]

    relationships: list[
        SQLAgentRelationshipRead
    ]


class SQLAgentSchemaResponse(BaseModel):
    """SQL Agent semantic schema catalog."""

    schema_name: str
    table_count: int

    tables: list[
        SQLAgentTableRead
    ]


class SQLAgentPlanResponse(BaseModel):
    """Generated and validated SQL plan."""

    question: str
    normalized_question: str

    intent: str
    explanation: str

    generated_sql: str
    normalized_sql: str
    executable_sql: str

    referenced_tables: list[str]
    max_rows: int


class SQLAgentExecutionResponse(BaseModel):
    """Read-only SQL execution result."""

    original_sql: str
    normalized_sql: str
    executable_sql: str

    referenced_tables: list[str]

    columns: list[str]
    rows: list[
        dict[str, Any]
    ]

    row_count: int
    max_rows: int
    limit_reached: bool

    statement_timeout_ms: int
    execution_time_ms: float


class SQLAgentQueryResponse(BaseModel):
    """Combined SQL plan and execution response."""

    plan: SQLAgentPlanResponse
    execution: SQLAgentExecutionResponse