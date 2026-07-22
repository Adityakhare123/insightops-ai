from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Sequence

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from apps.api.app.services.sql_agent_guardrails import (
    SQL_AGENT_ALLOWED_SCHEMAS,
    SQL_AGENT_ALLOWED_TABLES,
)


SQL_IDENTIFIER_PATTERN = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*$"
)


TABLE_DESCRIPTIONS: dict[str, str] = {
    "insurance_carriers": (
        "Insurance carrier or insurance company."
    ),
    "insurance_plans": (
        "Insurance plans offered by carriers."
    ),
    "insurance_agents": (
        "Agents responsible for insurance sales."
    ),
    "insurance_customers": (
        "Customers who own insurance policies."
    ),
    "insurance_policies": (
        "Insurance policies sold to customers."
    ),
    "insurance_payments": (
        "Payments received for insurance policies."
    ),
    "insurance_commissions": (
        "Agent commissions associated with policies."
    ),
}


COLUMN_DESCRIPTIONS: dict[
    tuple[str, str],
    str,
] = {
    (
        "insurance_policies",
        "policy_number",
    ): "Unique policy identifier.",
    (
        "insurance_policies",
        "status",
    ): "Current policy status.",
    (
        "insurance_policies",
        "effective_date",
    ): "Date on which policy coverage begins.",
    (
        "insurance_policies",
        "termination_date",
    ): "Date on which policy coverage ends.",
    (
        "insurance_policies",
        "premium",
    ): "Policy premium amount.",
    (
        "insurance_payments",
        "amount",
    ): "Payment amount.",
    (
        "insurance_commissions",
        "amount",
    ): "Commission amount.",
    (
        "insurance_carriers",
        "name",
    ): "Carrier name.",
    (
        "insurance_agents",
        "first_name",
    ): "Agent first name.",
    (
        "insurance_agents",
        "last_name",
    ): "Agent last name.",
    (
        "insurance_customers",
        "first_name",
    ): "Customer first name.",
    (
        "insurance_customers",
        "last_name",
    ): "Customer last name.",
}


class SQLAgentSchemaError(RuntimeError):
    """Base exception for SQL Agent schema catalog errors."""


class MissingSQLAgentTableError(
    SQLAgentSchemaError,
):
    """Raised when an expected insurance table does not exist."""


class MissingSQLAgentColumnError(
    SQLAgentSchemaError,
):
    """Raised when a required business column does not exist."""


class InvalidSQLAgentIdentifierError(
    SQLAgentSchemaError,
):
    """Raised when a schema identifier is unsafe."""


@dataclass(frozen=True)
class SQLAgentColumnCatalog:
    """Metadata describing one database column."""

    name: str
    data_type: str
    nullable: bool
    primary_key: bool
    description: str | None = None


@dataclass(frozen=True)
class SQLAgentRelationship:
    """Foreign-key relationship between insurance tables."""

    source_table: str
    source_columns: tuple[str, ...]

    target_table: str
    target_columns: tuple[str, ...]


@dataclass(frozen=True)
class SQLAgentTableCatalog:
    """Metadata describing one approved business table."""

    schema_name: str
    table_name: str
    description: str

    columns: dict[
        str,
        SQLAgentColumnCatalog,
    ]

    relationships: tuple[
        SQLAgentRelationship,
        ...,
    ] = ()

    @property
    def qualified_name(self) -> str:
        """Return schema-qualified table name."""

        return (
            f"{self.schema_name}."
            f"{self.table_name}"
        )

    @property
    def column_names(self) -> frozenset[str]:
        """Return all available column names."""

        return frozenset(
            self.columns
        )

    def has_column(
        self,
        column_name: str,
    ) -> bool:
        """Return whether this table has the requested column."""

        return (
            column_name.casefold()
            in self.columns
        )

    def require_column(
        self,
        column_name: str,
    ) -> str:
        """Return a required column or raise an error."""

        normalized_column = (
            column_name.casefold()
        )

        if normalized_column not in self.columns:
            raise MissingSQLAgentColumnError(
                f"Table {self.qualified_name} does not "
                f"contain required column "
                f"{column_name!r}."
            )

        return normalized_column

    def resolve_column(
        self,
        candidates: Sequence[str],
    ) -> str | None:
        """Return the first available candidate column."""

        for candidate in candidates:
            normalized_candidate = (
                candidate.casefold()
            )

            if normalized_candidate in self.columns:
                return normalized_candidate

        return None

    def require_one_of(
        self,
        candidates: Sequence[str],
        *,
        semantic_name: str,
    ) -> str:
        """Resolve one of several possible physical columns."""

        resolved_column = self.resolve_column(
            candidates
        )

        if resolved_column is None:
            raise MissingSQLAgentColumnError(
                f"Table {self.qualified_name} does not "
                f"contain a column for {semantic_name}. "
                "Expected one of: "
                + ", ".join(candidates)
                + "."
            )

        return resolved_column


@dataclass(frozen=True)
class InsuranceSchemaCatalog:
    """Catalog of approved insurance analytics tables."""

    tables: dict[
        str,
        SQLAgentTableCatalog,
    ]

    def has_table(
        self,
        table_name: str,
    ) -> bool:
        """Return whether the table exists in the catalog."""

        return (
            table_name.casefold()
            in self.tables
        )

    def require_table(
        self,
        table_name: str,
    ) -> SQLAgentTableCatalog:
        """Return a required table or raise an error."""

        normalized_table_name = (
            table_name.casefold()
        )

        table = self.tables.get(
            normalized_table_name
        )

        if table is None:
            raise MissingSQLAgentTableError(
                "The SQL Agent schema catalog does not "
                f"contain table {table_name!r}."
            )

        return table

    @property
    def table_names(self) -> tuple[str, ...]:
        """Return sorted catalog table names."""

        return tuple(
            sorted(
                self.tables
            )
        )

    def to_prompt_text(self) -> str:
        """Render a compact schema description for later LLM use."""

        output_lines: list[str] = []

        for table_name in self.table_names:
            table = self.tables[
                table_name
            ]

            output_lines.append(
                (
                    f"TABLE {table.qualified_name}: "
                    f"{table.description}"
                )
            )

            for column_name in sorted(
                table.columns
            ):
                column = table.columns[
                    column_name
                ]

                attributes = [
                    column.data_type,
                    (
                        "nullable"
                        if column.nullable
                        else "required"
                    ),
                ]

                if column.primary_key:
                    attributes.append(
                        "primary key"
                    )

                description_suffix = (
                    f" — {column.description}"
                    if column.description
                    else ""
                )

                output_lines.append(
                    (
                        f"  - {column.name}: "
                        f"{', '.join(attributes)}"
                        f"{description_suffix}"
                    )
                )

            for relationship in (
                table.relationships
            ):
                output_lines.append(
                    (
                        "  -> "
                        f"{relationship.target_table}"
                        f"({', '.join(relationship.target_columns)}) "
                        "using "
                        f"{', '.join(relationship.source_columns)}"
                    )
                )

        return "\n".join(
            output_lines
        )


def validate_schema_identifier(
    identifier: str,
) -> str:
    """Validate and normalize a SQL schema identifier."""

    normalized_identifier = (
        identifier.strip().casefold()
    )

    if not SQL_IDENTIFIER_PATTERN.fullmatch(
        normalized_identifier
    ):
        raise InvalidSQLAgentIdentifierError(
            "Invalid SQL identifier: "
            f"{identifier!r}."
        )

    return normalized_identifier


def build_schema_catalog_from_mapping(
    table_columns: Mapping[
        str,
        Sequence[str],
    ],
    *,
    schema_name: str = "public",
) -> InsuranceSchemaCatalog:
    """Build a catalog from simple mappings for unit tests."""

    normalized_schema_name = (
        validate_schema_identifier(
            schema_name
        )
    )

    tables: dict[
        str,
        SQLAgentTableCatalog,
    ] = {}

    for table_name, column_names in (
        table_columns.items()
    ):
        normalized_table_name = (
            validate_schema_identifier(
                table_name
            )
        )

        columns: dict[
            str,
            SQLAgentColumnCatalog,
        ] = {}

        for column_name in column_names:
            normalized_column_name = (
                validate_schema_identifier(
                    column_name
                )
            )

            columns[
                normalized_column_name
            ] = SQLAgentColumnCatalog(
                name=normalized_column_name,
                data_type="unknown",
                nullable=True,
                primary_key=(
                    normalized_column_name
                    == "id"
                ),
                description=(
                    COLUMN_DESCRIPTIONS.get(
                        (
                            normalized_table_name,
                            normalized_column_name,
                        )
                    )
                ),
            )

        tables[
            normalized_table_name
        ] = SQLAgentTableCatalog(
            schema_name=(
                normalized_schema_name
            ),
            table_name=(
                normalized_table_name
            ),
            description=(
                TABLE_DESCRIPTIONS.get(
                    normalized_table_name,
                    "Approved insurance business table.",
                )
            ),
            columns=columns,
        )

    return InsuranceSchemaCatalog(
        tables=tables
    )


def load_insurance_schema_catalog(
    database_session: Session,
    *,
    schema_name: str = "public",
) -> InsuranceSchemaCatalog:
    """Inspect PostgreSQL and load approved insurance tables."""

    normalized_schema_name = (
        validate_schema_identifier(
            schema_name
        )
    )

    if (
        normalized_schema_name
        not in SQL_AGENT_ALLOWED_SCHEMAS
    ):
        raise SQLAgentSchemaError(
            "Schema is not approved for SQL Agent use: "
            f"{normalized_schema_name}."
        )

    database_inspector = inspect(
        database_session.get_bind()
    )

    tables: dict[
        str,
        SQLAgentTableCatalog,
    ] = {}

    for table_name in sorted(
        SQL_AGENT_ALLOWED_TABLES
    ):
        if not database_inspector.has_table(
            table_name,
            schema=normalized_schema_name,
        ):
            raise MissingSQLAgentTableError(
                "Expected SQL Agent table does not exist: "
                f"{normalized_schema_name}.{table_name}."
            )

        primary_key_data = (
            database_inspector.get_pk_constraint(
                table_name,
                schema=normalized_schema_name,
            )
        )

        primary_key_columns = {
            str(column_name).casefold()
            for column_name
            in (
                primary_key_data.get(
                    "constrained_columns"
                )
                or []
            )
        }

        columns: dict[
            str,
            SQLAgentColumnCatalog,
        ] = {}

        for column_data in (
            database_inspector.get_columns(
                table_name,
                schema=normalized_schema_name,
            )
        ):
            column_name = (
                validate_schema_identifier(
                    str(
                        column_data[
                            "name"
                        ]
                    )
                )
            )

            columns[
                column_name
            ] = SQLAgentColumnCatalog(
                name=column_name,
                data_type=str(
                    column_data.get(
                        "type",
                        "unknown",
                    )
                ),
                nullable=bool(
                    column_data.get(
                        "nullable",
                        True,
                    )
                ),
                primary_key=(
                    column_name
                    in primary_key_columns
                ),
                description=(
                    COLUMN_DESCRIPTIONS.get(
                        (
                            table_name,
                            column_name,
                        )
                    )
                ),
            )

        relationships: list[
            SQLAgentRelationship
        ] = []

        for foreign_key in (
            database_inspector.get_foreign_keys(
                table_name,
                schema=normalized_schema_name,
            )
        ):
            target_table = str(
                foreign_key.get(
                    "referred_table",
                    "",
                )
            ).casefold()

            if (
                target_table
                not in SQL_AGENT_ALLOWED_TABLES
            ):
                continue

            source_columns = tuple(
                str(column_name).casefold()
                for column_name
                in (
                    foreign_key.get(
                        "constrained_columns"
                    )
                    or []
                )
            )

            target_columns = tuple(
                str(column_name).casefold()
                for column_name
                in (
                    foreign_key.get(
                        "referred_columns"
                    )
                    or []
                )
            )

            relationships.append(
                SQLAgentRelationship(
                    source_table=table_name,
                    source_columns=(
                        source_columns
                    ),
                    target_table=(
                        target_table
                    ),
                    target_columns=(
                        target_columns
                    ),
                )
            )

        tables[
            table_name
        ] = SQLAgentTableCatalog(
            schema_name=(
                normalized_schema_name
            ),
            table_name=table_name,
            description=(
                TABLE_DESCRIPTIONS.get(
                    table_name,
                    "Approved insurance business table.",
                )
            ),
            columns=columns,
            relationships=tuple(
                relationships
            ),
        )

    return InsuranceSchemaCatalog(
        tables=tables
    )