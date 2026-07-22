from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
    status,
)

from apps.api.app.api.deps import (
    CurrentUser,
    DatabaseSession,
)
from apps.api.app.schemas.sql_agent import (
    SQLAgentColumnRead,
    SQLAgentExecutionResponse,
    SQLAgentPlanRequest,
    SQLAgentPlanResponse,
    SQLAgentQueryRequest,
    SQLAgentQueryResponse,
    SQLAgentRelationshipRead,
    SQLAgentSchemaResponse,
    SQLAgentTableRead,
)
from apps.api.app.services.sql_agent_executor import (
    SQLAgentConnectionError,
    SQLAgentDatabaseError,
    SQLAgentExecutionResult,
    SQLAgentTimeoutError,
    validate_and_execute_sql,
)
from apps.api.app.services.sql_agent_guardrails import (
    SQLAgentGuardrailError,
)
from apps.api.app.services.sql_agent_planner import (
    SQLAgentPlan,
    SQLAgentPlannerError,
    UnsupportedSQLAgentQuestionError,
    plan_sql_agent_question,
)
from apps.api.app.services.sql_agent_schema import (
    InsuranceSchemaCatalog,
    SQLAgentSchemaError,
    load_insurance_schema_catalog,
)


router = APIRouter()


def load_workspace_schema_catalog(
    database_session: DatabaseSession,
) -> InsuranceSchemaCatalog:
    """Load the approved SQL Agent schema catalog."""

    try:
        return load_insurance_schema_catalog(
            database_session
        )
    except SQLAgentSchemaError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "The approved insurance schema could "
                "not be loaded. "
                f"{error}"
            ),
        ) from error


def create_plan_response(
    plan: SQLAgentPlan,
) -> SQLAgentPlanResponse:
    """Convert a SQL Agent plan into its API schema."""

    return SQLAgentPlanResponse(
        question=plan.question,
        normalized_question=(
            plan.normalized_question
        ),
        intent=plan.intent.value,
        explanation=plan.explanation,
        generated_sql=plan.generated_sql,
        normalized_sql=plan.normalized_sql,
        executable_sql=plan.executable_sql,
        referenced_tables=list(
            plan.referenced_tables
        ),
        max_rows=plan.max_rows,
    )


def create_execution_response(
    execution_result: SQLAgentExecutionResult,
) -> SQLAgentExecutionResponse:
    """Convert an execution result into its API schema."""

    return SQLAgentExecutionResponse(
        original_sql=(
            execution_result.original_sql
        ),
        normalized_sql=(
            execution_result.normalized_sql
        ),
        executable_sql=(
            execution_result.executable_sql
        ),
        referenced_tables=list(
            execution_result.referenced_tables
        ),
        columns=list(
            execution_result.columns
        ),
        rows=execution_result.rows,
        row_count=execution_result.row_count,
        max_rows=execution_result.max_rows,
        limit_reached=(
            execution_result.limit_reached
        ),
        statement_timeout_ms=(
            execution_result.statement_timeout_ms
        ),
        execution_time_ms=(
            execution_result.execution_time_ms
        ),
    )


def build_sql_agent_plan(
    *,
    request: SQLAgentPlanRequest,
    current_user: CurrentUser,
    database_session: DatabaseSession,
) -> SQLAgentPlan:
    """Build a workspace-scoped SQL plan."""

    catalog = load_workspace_schema_catalog(
        database_session
    )

    try:
        return plan_sql_agent_question(
            question=request.question,
            workspace_id=current_user.workspace_id,
            catalog=catalog,
            max_rows=request.max_rows,
        )
    except UnsupportedSQLAgentQuestionError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(error),
        ) from error
    except SQLAgentPlannerError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except SQLAgentGuardrailError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The generated SQL did not pass the "
                f"safety checks. {error}"
            ),
        ) from error


@router.get(
    "/schema",
    response_model=SQLAgentSchemaResponse,
)
def get_sql_agent_schema(
    current_user: CurrentUser,
    database_session: DatabaseSession,
) -> SQLAgentSchemaResponse:
    """Return the approved SQL Agent semantic schema."""

    del current_user

    catalog = load_workspace_schema_catalog(
        database_session
    )

    table_responses: list[
        SQLAgentTableRead
    ] = []

    for table_name in catalog.table_names:
        table = catalog.tables[
            table_name
        ]

        column_responses = [
            SQLAgentColumnRead(
                name=column.name,
                data_type=column.data_type,
                nullable=column.nullable,
                primary_key=(
                    column.primary_key
                ),
                description=(
                    column.description
                ),
            )
            for column in sorted(
                table.columns.values(),
                key=lambda item: item.name,
            )
        ]

        relationship_responses = [
            SQLAgentRelationshipRead(
                source_table=(
                    relationship.source_table
                ),
                source_columns=list(
                    relationship.source_columns
                ),
                target_table=(
                    relationship.target_table
                ),
                target_columns=list(
                    relationship.target_columns
                ),
            )
            for relationship
            in table.relationships
        ]

        table_responses.append(
            SQLAgentTableRead(
                schema_name=table.schema_name,
                table_name=table.table_name,
                qualified_name=(
                    table.qualified_name
                ),
                description=table.description,
                columns=column_responses,
                relationships=(
                    relationship_responses
                ),
            )
        )

    return SQLAgentSchemaResponse(
        schema_name="public",
        table_count=len(
            table_responses
        ),
        tables=table_responses,
    )


@router.post(
    "/plan",
    response_model=SQLAgentPlanResponse,
)
def plan_sql_agent_query(
    request: SQLAgentPlanRequest,
    current_user: CurrentUser,
    database_session: DatabaseSession,
) -> SQLAgentPlanResponse:
    """Generate and validate SQL without executing it."""

    plan = build_sql_agent_plan(
        request=request,
        current_user=current_user,
        database_session=database_session,
    )

    return create_plan_response(
        plan
    )


@router.post(
    "/query",
    response_model=SQLAgentQueryResponse,
)
def execute_sql_agent_query(
    request: SQLAgentQueryRequest,
    current_user: CurrentUser,
    database_session: DatabaseSession,
) -> SQLAgentQueryResponse:
    """Plan and execute a workspace-scoped read-only query."""

    plan = build_sql_agent_plan(
        request=request,
        current_user=current_user,
        database_session=database_session,
    )

    try:
        execution_result = (
            validate_and_execute_sql(
                database_session,
                sql_query=plan.generated_sql,
                max_rows=plan.max_rows,
                statement_timeout_ms=(
                    request.statement_timeout_ms
                ),
            )
        )
    except SQLAgentTimeoutError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_408_REQUEST_TIMEOUT
            ),
            detail=str(error),
        ) from error
    except SQLAgentConnectionError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "The SQL Agent database connection "
                "is unavailable."
            ),
        ) from error
    except SQLAgentDatabaseError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "The validated SQL query could not "
                "be executed."
            ),
        ) from error
    except SQLAgentGuardrailError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The generated SQL did not pass the "
                f"safety checks. {error}"
            ),
        ) from error

    return SQLAgentQueryResponse(
        plan=create_plan_response(
            plan
        ),
        execution=create_execution_response(
            execution_result
        ),
    )