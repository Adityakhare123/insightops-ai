from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import (
    date,
    datetime,
    time,
)
from decimal import Decimal
from enum import Enum
from math import isfinite
from pathlib import Path
from time import perf_counter
from typing import (
    Any,
    Iterator,
    Mapping,
)
from uuid import UUID

from sqlalchemy.engine import (
    Connection,
    Engine,
)
from sqlalchemy.exc import (
    DBAPIError,
    SQLAlchemyError,
)
from sqlalchemy.orm import Session

from apps.api.app.core.config import settings
from apps.api.app.services.sql_agent_guardrails import (
    SafeSQLValidationResult,
    validate_sql_agent_query,
)


POSTGRES_QUERY_CANCELLED_SQLSTATE = "57014"


class SQLAgentExecutionError(RuntimeError):
    """Base exception for SQL Agent execution failures."""


class SQLAgentDatabaseError(
    SQLAgentExecutionError,
):
    """Raised when PostgreSQL cannot execute a validated query."""


class SQLAgentTimeoutError(
    SQLAgentExecutionError,
):
    """Raised when PostgreSQL cancels a query after its timeout."""


class InvalidSQLAgentTimeoutError(
    SQLAgentExecutionError,
    ValueError,
):
    """Raised when the configured statement timeout is invalid."""


class SQLAgentConnectionError(
    SQLAgentExecutionError,
):
    """Raised when a separate SQL Agent connection cannot be opened."""


@dataclass(frozen=True)
class SQLAgentExecutionResult:
    """Read-only SQL execution result and audit metadata."""

    original_sql: str
    normalized_sql: str
    executable_sql: str

    referenced_tables: tuple[str, ...]

    columns: tuple[str, ...]
    rows: list[dict[str, Any]]

    row_count: int
    max_rows: int
    limit_reached: bool

    statement_timeout_ms: int
    execution_time_ms: float

    @property
    def table_count(self) -> int:
        """Return the number of approved tables queried."""

        return len(
            self.referenced_tables
        )

    def to_metadata(self) -> dict[str, Any]:
        """Return JSON-safe query execution metadata."""

        return {
            "referenced_tables": list(
                self.referenced_tables
            ),
            "table_count": self.table_count,
            "columns": list(self.columns),
            "row_count": self.row_count,
            "max_rows": self.max_rows,
            "limit_reached": (
                self.limit_reached
            ),
            "statement_timeout_ms": (
                self.statement_timeout_ms
            ),
            "execution_time_ms": (
                self.execution_time_ms
            ),
        }


def resolve_statement_timeout_ms(
    statement_timeout_ms: int | None,
) -> int:
    """Resolve and validate PostgreSQL statement timeout."""

    resolved_timeout_ms = (
        statement_timeout_ms
        if statement_timeout_ms is not None
        else settings.sql_agent_statement_timeout_ms
    )

    if resolved_timeout_ms < 100:
        raise InvalidSQLAgentTimeoutError(
            "The SQL Agent statement timeout must "
            "be at least 100 milliseconds."
        )

    if resolved_timeout_ms > 60_000:
        raise InvalidSQLAgentTimeoutError(
            "The SQL Agent statement timeout cannot "
            "exceed 60,000 milliseconds."
        )

    return resolved_timeout_ms


def serialize_sql_value(
    value: Any,
) -> Any:
    """Convert a PostgreSQL value into JSON-safe data."""

    if value is None:
        return None

    if isinstance(
        value,
        (
            bool,
            int,
            str,
        ),
    ):
        return value

    if isinstance(
        value,
        float,
    ):
        if isfinite(value):
            return value

        return str(value)

    if isinstance(
        value,
        Decimal,
    ):
        return str(value)

    if isinstance(
        value,
        datetime,
    ):
        return value.isoformat()

    if isinstance(
        value,
        date,
    ):
        return value.isoformat()

    if isinstance(
        value,
        time,
    ):
        return value.isoformat()

    if isinstance(
        value,
        UUID,
    ):
        return str(value)

    if isinstance(
        value,
        Enum,
    ):
        return serialize_sql_value(
            value.value
        )

    if isinstance(
        value,
        Path,
    ):
        return str(value)

    if isinstance(
        value,
        memoryview,
    ):
        return value.tobytes().hex()

    if isinstance(
        value,
        (
            bytes,
            bytearray,
        ),
    ):
        return bytes(value).hex()

    if isinstance(
        value,
        Mapping,
    ):
        return {
            str(key): serialize_sql_value(
                nested_value
            )
            for key, nested_value
            in value.items()
        }

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
            frozenset,
        ),
    ):
        return [
            serialize_sql_value(
                nested_value
            )
            for nested_value in value
        ]

    to_list_method = getattr(
        value,
        "tolist",
        None,
    )

    if callable(to_list_method):
        try:
            return serialize_sql_value(
                to_list_method()
            )
        except Exception:
            pass

    return str(value)


def serialize_sql_row(
    row: Mapping[str, Any],
) -> dict[str, Any]:
    """Convert one SQLAlchemy row mapping into JSON-safe data."""

    return {
        str(column_name): serialize_sql_value(
            column_value
        )
        for column_name, column_value
        in row.items()
    }


def extract_database_sqlstate(
    error: DBAPIError,
) -> str | None:
    """Extract a PostgreSQL SQLSTATE from a SQLAlchemy error."""

    original_error = error.orig

    sqlstate = getattr(
        original_error,
        "sqlstate",
        None,
    )

    if sqlstate:
        return str(sqlstate)

    legacy_pgcode = getattr(
        original_error,
        "pgcode",
        None,
    )

    if legacy_pgcode:
        return str(legacy_pgcode)

    return None


def is_statement_timeout_error(
    error: DBAPIError,
) -> bool:
    """Return whether PostgreSQL cancelled a timed-out query."""

    if (
        extract_database_sqlstate(error)
        == POSTGRES_QUERY_CANCELLED_SQLSTATE
    ):
        return True

    normalized_error_message = (
        str(error).casefold()
    )

    return (
        "statement timeout"
        in normalized_error_message
        or "query canceled"
        in normalized_error_message
        or "query cancelled"
        in normalized_error_message
    )


@contextmanager
def open_sql_agent_connection(
    database_session: Session,
) -> Iterator[Connection]:
    """
    Open an isolated database transaction for SQL Agent work.

    The SQL Agent does not execute through the caller's current
    ORM transaction because it must establish READ ONLY mode
    before any business query is executed.
    """

    bind = database_session.get_bind()

    if isinstance(
        bind,
        Engine,
    ):
        with bind.connect() as connection:
            with connection.begin():
                yield connection

        return

    if isinstance(
        bind,
        Connection,
    ):
        if bind.in_transaction():
            raise SQLAgentConnectionError(
                "The SQL Agent cannot reuse a database "
                "connection that already has an active "
                "transaction."
            )

        with bind.begin():
            yield bind

        return

    connect_method = getattr(
        bind,
        "connect",
        None,
    )

    if callable(connect_method):
        try:
            with connect_method() as connection:
                with connection.begin():
                    yield connection

            return
        except SQLAgentExecutionError:
            raise
        except Exception as error:
            raise SQLAgentConnectionError(
                "The SQL Agent could not open an "
                "isolated database connection."
            ) from error

    raise SQLAgentConnectionError(
        "The database session is not bound to a "
        "supported SQLAlchemy engine or connection."
    )


def execute_validated_sql(
    database_session: Session,
    *,
    validation_result: SafeSQLValidationResult,
    statement_timeout_ms: int | None = None,
) -> SQLAgentExecutionResult:
    """
    Execute already validated SQL in a read-only transaction.

    PostgreSQL READ ONLY mode protects against database writes
    even if an unsafe statement somehow bypasses the parser.
    """

    resolved_timeout_ms = (
        resolve_statement_timeout_ms(
            statement_timeout_ms
        )
    )

    started_at = perf_counter()

    try:
        with open_sql_agent_connection(
            database_session
        ) as connection:
            connection.exec_driver_sql(
                "SET TRANSACTION READ ONLY"
            )

            connection.exec_driver_sql(
                "SET LOCAL statement_timeout = "
                f"{resolved_timeout_ms}"
            )

            query_result = (
                connection.exec_driver_sql(
                    validation_result.executable_sql
                )
            )

            columns = tuple(
                str(column_name)
                for column_name
                in query_result.keys()
            )

            raw_rows = (
                query_result.mappings().all()
            )

            rows = [
                serialize_sql_row(
                    row
                )
                for row in raw_rows
            ]

    except DBAPIError as error:
        if is_statement_timeout_error(
            error
        ):
            raise SQLAgentTimeoutError(
                "The SQL query exceeded the configured "
                f"timeout of {resolved_timeout_ms:,} "
                "milliseconds."
            ) from error

        raise SQLAgentDatabaseError(
            "PostgreSQL could not execute the "
            "validated SQL query."
        ) from error

    except SQLAgentExecutionError:
        raise

    except SQLAlchemyError as error:
        raise SQLAgentDatabaseError(
            "SQLAlchemy could not execute the "
            "validated SQL query."
        ) from error

    execution_time_ms = round(
        (
            perf_counter()
            - started_at
        )
        * 1_000,
        3,
    )

    row_count = len(rows)

    return SQLAgentExecutionResult(
        original_sql=(
            validation_result.original_sql
        ),
        normalized_sql=(
            validation_result.normalized_sql
        ),
        executable_sql=(
            validation_result.executable_sql
        ),
        referenced_tables=(
            validation_result.referenced_tables
        ),
        columns=columns,
        rows=rows,
        row_count=row_count,
        max_rows=validation_result.max_rows,
        limit_reached=(
            row_count
            >= validation_result.max_rows
        ),
        statement_timeout_ms=(
            resolved_timeout_ms
        ),
        execution_time_ms=(
            execution_time_ms
        ),
    )


def validate_and_execute_sql(
    database_session: Session,
    *,
    sql_query: str,
    max_rows: int | None = None,
    max_sql_length: int | None = None,
    statement_timeout_ms: int | None = None,
) -> SQLAgentExecutionResult:
    """Validate generated SQL and execute it read-only."""

    validation_result = (
        validate_sql_agent_query(
            sql_query,
            max_rows=max_rows,
            max_sql_length=max_sql_length,
        )
    )

    return execute_validated_sql(
        database_session,
        validation_result=validation_result,
        statement_timeout_ms=(
            statement_timeout_ms
        ),
    )