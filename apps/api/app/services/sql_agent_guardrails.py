from __future__ import annotations

from collections.abc import (
    Collection,
    Iterator,
)
from dataclasses import dataclass
from typing import Any

from sqlglot import exp, parse
from sqlglot.errors import ParseError

from apps.api.app.core.config import settings


SQL_AGENT_ALLOWED_SCHEMAS = frozenset(
    {
        "public",
    }
)

SQL_AGENT_ALLOWED_TABLES = frozenset(
    {
        "insurance_carriers",
        "insurance_plans",
        "insurance_agents",
        "insurance_customers",
        "insurance_policies",
        "insurance_payments",
        "insurance_commissions",
    }
)

ALLOWED_QUERY_ROOT_NAMES = frozenset(
    {
        "select",
        "union",
        "intersect",
        "except",
    }
)

FORBIDDEN_SQL_NODE_NAMES = frozenset(
    {
        "insert",
        "update",
        "delete",
        "merge",
        "create",
        "drop",
        "alter",
        "truncate",
        "truncatetable",
        "command",
        "copy",
        "grant",
        "revoke",
        "transaction",
        "commit",
        "rollback",
        "set",
        "use",
        "call",
        "execute",
        "prepare",
        "deallocate",
        "lock",
        "into",
        "load",
        "attach",
        "detach",
        "vacuum",
        "analyze",
        "refresh",
        "replace",
    }
)

FORBIDDEN_FUNCTION_NAMES = frozenset(
    {
        "pg_sleep",
        "pg_read_file",
        "pg_read_binary_file",
        "pg_ls_dir",
        "pg_stat_file",
        "pg_advisory_lock",
        "pg_advisory_xact_lock",
        "pg_try_advisory_lock",
        "pg_try_advisory_xact_lock",
        "pg_terminate_backend",
        "pg_cancel_backend",
        "lo_import",
        "lo_export",
        "dblink",
        "dblink_connect",
        "dblink_exec",
        "set_config",
        "query_to_xml",
        "database_to_xml",
        "table_to_xml",
    }
)


class SQLAgentGuardrailError(ValueError):
    """Base exception for rejected SQL Agent queries."""


class EmptySQLQueryError(
    SQLAgentGuardrailError,
):
    """Raised when the SQL query is empty."""


class SQLQueryTooLongError(
    SQLAgentGuardrailError,
):
    """Raised when generated SQL exceeds the configured limit."""


class SQLParsingError(
    SQLAgentGuardrailError,
):
    """Raised when SQLGlot cannot parse generated SQL."""


class MultipleSQLStatementsError(
    SQLAgentGuardrailError,
):
    """Raised when more than one SQL statement is supplied."""


class NonReadOnlySQLQueryError(
    SQLAgentGuardrailError,
):
    """Raised when the SQL query is not strictly read-only."""


class UnauthorizedSQLTableError(
    SQLAgentGuardrailError,
):
    """Raised when SQL references a table outside the allowlist."""


class UnsafeSQLFunctionError(
    SQLAgentGuardrailError,
):
    """Raised when SQL references a blocked PostgreSQL function."""


class MissingSQLDataSourceError(
    SQLAgentGuardrailError,
):
    """Raised when SQL does not query an approved business table."""


class InvalidSQLAgentLimitError(
    SQLAgentGuardrailError,
):
    """Raised when the configured result limit is invalid."""


@dataclass(frozen=True)
class SafeSQLValidationResult:
    """Validated and row-limited SQL Agent query."""

    original_sql: str
    normalized_sql: str
    executable_sql: str

    referenced_tables: tuple[str, ...]

    max_rows: int

    @property
    def table_count(self) -> int:
        return len(
            self.referenced_tables
        )


def normalize_sql_identifier(
    identifier: Any,
) -> str:
    """Normalize a SQL identifier for allowlist comparison."""

    if identifier is None:
        return ""

    if isinstance(identifier, str):
        identifier_value = identifier
    else:
        identifier_name = getattr(
            identifier,
            "name",
            None,
        )

        identifier_value = (
            str(identifier_name)
            if identifier_name is not None
            else str(identifier)
        )

    return (
        identifier_value
        .strip()
        .strip('"')
        .casefold()
    )


def normalize_allowed_tables(
    allowed_tables: Collection[str],
) -> frozenset[str]:
    """Normalize table allowlist values."""

    normalized_tables: set[str] = set()

    for table_name in allowed_tables:
        normalized_name = (
            normalize_sql_identifier(
                table_name
            )
        )

        if "." in normalized_name:
            normalized_name = (
                normalized_name.rsplit(
                    ".",
                    maxsplit=1,
                )[-1]
            )

        if normalized_name:
            normalized_tables.add(
                normalized_name
            )

    return frozenset(
        normalized_tables
    )


def normalize_allowed_schemas(
    allowed_schemas: Collection[str],
) -> frozenset[str]:
    """Normalize schema allowlist values."""

    return frozenset(
        normalized_schema
        for schema_name in allowed_schemas
        if (
            normalized_schema
            := normalize_sql_identifier(
                schema_name
            )
        )
    )


def iter_expression_nodes(
    expression: exp.Expression,
) -> Iterator[exp.Expression]:
    """
    Iterate through SQLGlot nodes.

    The tuple handling keeps this compatible with SQLGlot
    traversal return formats across versions.
    """

    for walk_item in expression.walk():
        if isinstance(
            walk_item,
            tuple,
        ):
            node = walk_item[0]
        else:
            node = walk_item

        if isinstance(
            node,
            exp.Expression,
        ):
            yield node


def get_expression_node_name(
    expression: exp.Expression,
) -> str:
    """Return the lowercase SQLGlot AST node class name."""

    return (
        type(expression)
        .__name__
        .casefold()
    )


def get_cte_names(
    expression: exp.Expression,
) -> frozenset[str]:
    """Return all common-table-expression aliases."""

    cte_names: set[str] = set()

    for cte_expression in expression.find_all(
        exp.CTE
    ):
        cte_name = normalize_sql_identifier(
            cte_expression.alias_or_name
        )

        if cte_name:
            cte_names.add(
                cte_name
            )

    return frozenset(
        cte_names
    )


def find_forbidden_nodes(
    expression: exp.Expression,
) -> tuple[str, ...]:
    """Find write, DDL, locking, and command AST nodes."""

    forbidden_nodes = {
        node_name
        for node in iter_expression_nodes(
            expression
        )
        if (
            node_name
            := get_expression_node_name(
                node
            )
        )
        in FORBIDDEN_SQL_NODE_NAMES
    }

    return tuple(
        sorted(
            forbidden_nodes
        )
    )


def get_function_name(
    function_expression: exp.Func,
) -> str:
    """Return a normalized SQL function name."""

    explicit_name = getattr(
        function_expression,
        "name",
        None,
    )

    if explicit_name:
        return normalize_sql_identifier(
            explicit_name
        )

    sql_name_method = getattr(
        function_expression,
        "sql_name",
        None,
    )

    if callable(sql_name_method):
        try:
            return normalize_sql_identifier(
                sql_name_method()
            )
        except Exception:
            return ""

    return ""


def find_forbidden_functions(
    expression: exp.Expression,
) -> tuple[str, ...]:
    """Find blocked PostgreSQL functions in a query."""

    forbidden_functions: set[str] = set()

    for function_expression in (
        expression.find_all(
            exp.Func
        )
    ):
        function_name = get_function_name(
            function_expression
        )

        if (
            function_name
            in FORBIDDEN_FUNCTION_NAMES
        ):
            forbidden_functions.add(
                function_name
            )

    return tuple(
        sorted(
            forbidden_functions
        )
    )


def validate_sql_tables(
    expression: exp.Expression,
    *,
    allowed_tables: Collection[str],
    allowed_schemas: Collection[str],
) -> tuple[str, ...]:
    """Validate every physical table referenced by the query."""

    resolved_allowed_tables = (
        normalize_allowed_tables(
            allowed_tables
        )
    )

    resolved_allowed_schemas = (
        normalize_allowed_schemas(
            allowed_schemas
        )
    )

    cte_names = get_cte_names(
        expression
    )

    referenced_tables: set[str] = set()

    for table_expression in (
        expression.find_all(
            exp.Table
        )
    ):
        table_name = normalize_sql_identifier(
            table_expression.name
        )

        schema_name = normalize_sql_identifier(
            table_expression.db
        )

        catalog_name = normalize_sql_identifier(
            table_expression.catalog
        )

        if (
            table_name in cte_names
            and not schema_name
            and not catalog_name
        ):
            continue

        if catalog_name:
            raise UnauthorizedSQLTableError(
                "Cross-database table references are "
                "not allowed: "
                f"{catalog_name}."
                f"{schema_name or 'public'}."
                f"{table_name}."
            )

        resolved_schema_name = (
            schema_name or "public"
        )

        if (
            resolved_schema_name
            not in resolved_allowed_schemas
        ):
            raise UnauthorizedSQLTableError(
                "The SQL query references an "
                "unauthorized schema: "
                f"{resolved_schema_name}."
            )

        if (
            table_name
            not in resolved_allowed_tables
        ):
            raise UnauthorizedSQLTableError(
                "The SQL query references an "
                "unauthorized table: "
                f"{resolved_schema_name}."
                f"{table_name}."
            )

        referenced_tables.add(
            (
                f"{resolved_schema_name}."
                f"{table_name}"
            )
        )

    if not referenced_tables:
        raise MissingSQLDataSourceError(
            "The SQL query must reference at least one "
            "approved insurance table."
        )

    return tuple(
        sorted(
            referenced_tables
        )
    )


def build_row_limited_sql(
    normalized_sql: str,
    *,
    max_rows: int,
) -> str:
    """Wrap validated SQL with a hard outer result limit."""

    if max_rows < 1:
        raise InvalidSQLAgentLimitError(
            "SQL Agent max_rows must be greater "
            "than or equal to one."
        )

    return (
        "SELECT *\n"
        "FROM (\n"
        f"{normalized_sql}\n"
        ") AS insightops_safe_query\n"
        f"LIMIT {max_rows}"
    )


def validate_sql_agent_query(
    sql_query: str,
    *,
    allowed_tables: Collection[str] = (
        SQL_AGENT_ALLOWED_TABLES
    ),
    allowed_schemas: Collection[str] = (
        SQL_AGENT_ALLOWED_SCHEMAS
    ),
    max_rows: int | None = None,
    max_sql_length: int | None = None,
) -> SafeSQLValidationResult:
    """
    Validate generated SQL before it reaches PostgreSQL.

    This is the application-level guardrail. Database execution
    will also use a read-only transaction and statement timeout.
    """

    if not isinstance(
        sql_query,
        str,
    ):
        raise EmptySQLQueryError(
            "The SQL query must be a string."
        )

    normalized_input = (
        sql_query.strip()
    )

    if not normalized_input:
        raise EmptySQLQueryError(
            "The SQL query cannot be empty."
        )

    resolved_max_rows = (
        max_rows
        if max_rows is not None
        else settings.sql_agent_max_rows
    )

    resolved_max_sql_length = (
        max_sql_length
        if max_sql_length is not None
        else settings.sql_agent_max_sql_length
    )

    if resolved_max_rows < 1:
        raise InvalidSQLAgentLimitError(
            "SQL Agent max_rows must be greater "
            "than or equal to one."
        )

    if resolved_max_sql_length < 1:
        raise SQLQueryTooLongError(
            "SQL Agent max SQL length must be "
            "greater than or equal to one."
        )

    if (
        len(normalized_input)
        > resolved_max_sql_length
    ):
        raise SQLQueryTooLongError(
            "The SQL query exceeds the configured "
            f"maximum length of "
            f"{resolved_max_sql_length:,} characters."
        )

    try:
        parsed_statements = [
            statement
            for statement in parse(
                normalized_input,
                read="postgres",
            )
            if statement is not None
        ]
    except ParseError as error:
        raise SQLParsingError(
            "The generated SQL could not be parsed "
            "as PostgreSQL."
        ) from error

    if len(parsed_statements) != 1:
        raise MultipleSQLStatementsError(
            "Exactly one SQL statement is allowed."
        )

    expression = parsed_statements[0]

    root_node_name = (
        get_expression_node_name(
            expression
        )
    )

    if (
        root_node_name
        not in ALLOWED_QUERY_ROOT_NAMES
    ):
        raise NonReadOnlySQLQueryError(
            "Only read-only SELECT queries are allowed. "
            f"Received SQL node: {root_node_name}."
        )

    forbidden_nodes = (
        find_forbidden_nodes(
            expression
        )
    )

    if forbidden_nodes:
        raise NonReadOnlySQLQueryError(
            "The SQL query contains forbidden "
            "operations: "
            + ", ".join(
                forbidden_nodes
            )
            + "."
        )

    forbidden_functions = (
        find_forbidden_functions(
            expression
        )
    )

    if forbidden_functions:
        raise UnsafeSQLFunctionError(
            "The SQL query contains unsafe "
            "functions: "
            + ", ".join(
                forbidden_functions
            )
            + "."
        )

    referenced_tables = (
        validate_sql_tables(
            expression,
            allowed_tables=allowed_tables,
            allowed_schemas=allowed_schemas,
        )
    )

    try:
        normalized_sql = expression.sql(
            dialect="postgres",
            pretty=False,
        )
    except Exception as error:
        raise SQLParsingError(
            "The SQL query could not be normalized."
        ) from error

    executable_sql = build_row_limited_sql(
        normalized_sql,
        max_rows=resolved_max_rows,
    )

    return SafeSQLValidationResult(
        original_sql=normalized_input,
        normalized_sql=normalized_sql,
        executable_sql=executable_sql,
        referenced_tables=referenced_tables,
        max_rows=resolved_max_rows,
    )