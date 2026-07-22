from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from apps.api.app.services.sql_agent_guardrails import (
    SafeSQLValidationResult,
    validate_sql_agent_query,
)
from apps.api.app.services.sql_agent_schema import (
    InsuranceSchemaCatalog,
    SQLAgentTableCatalog,
)


QUESTION_NORMALIZATION_PATTERN = re.compile(
    r"[^a-z0-9]+"
)


class SQLAgentPlannerError(ValueError):
    """Base exception for SQL planning failures."""


class EmptySQLAgentQuestionError(
    SQLAgentPlannerError,
):
    """Raised when the natural-language question is empty."""


class SQLAgentQuestionTooLongError(
    SQLAgentPlannerError,
):
    """Raised when a business question is excessively long."""


class UnsupportedSQLAgentQuestionError(
    SQLAgentPlannerError,
):
    """Raised when no deterministic query template matches."""


class SQLAgentIntent(str, Enum):
    """Supported deterministic business question intents."""

    POLICY_STATUS_SUMMARY = (
        "policy_status_summary"
    )

    ACTIVE_POLICY_COUNT = (
        "active_policy_count"
    )

    POLICIES_BY_CARRIER = (
        "policies_by_carrier"
    )

    ACTIVE_POLICIES_WITHOUT_PAYMENTS = (
        "active_policies_without_payments"
    )

    DUPLICATE_POLICY_NUMBERS = (
        "duplicate_policy_numbers"
    )

    PAYMENTS_BY_CARRIER = (
        "payments_by_carrier"
    )

    COMMISSIONS_BY_AGENT = (
        "commissions_by_agent"
    )

    RECENT_POLICIES = (
        "recent_policies"
    )


@dataclass(frozen=True)
class SQLAgentPlan:
    """Generated, validated SQL plan for one business question."""

    question: str
    normalized_question: str

    intent: SQLAgentIntent
    explanation: str

    generated_sql: str
    normalized_sql: str
    executable_sql: str

    referenced_tables: tuple[str, ...]
    max_rows: int


def normalize_sql_agent_question(
    question: str,
) -> str:
    """Normalize and validate a business question."""

    if not isinstance(
        question,
        str,
    ):
        raise EmptySQLAgentQuestionError(
            "The SQL Agent question must be a string."
        )

    stripped_question = (
        question.strip()
    )

    if not stripped_question:
        raise EmptySQLAgentQuestionError(
            "The SQL Agent question cannot be empty."
        )

    if len(stripped_question) > 1_000:
        raise SQLAgentQuestionTooLongError(
            "The SQL Agent question cannot exceed "
            "1,000 characters."
        )

    return QUESTION_NORMALIZATION_PATTERN.sub(
        " ",
        stripped_question.casefold(),
    ).strip()


def contains_any_phrase(
    normalized_question: str,
    phrases: tuple[str, ...],
) -> bool:
    """Return whether the question contains any phrase."""

    padded_question = (
        f" {normalized_question} "
    )

    return any(
        f" {phrase} "
        in padded_question
        for phrase in phrases
    )


def detect_sql_agent_intent(
    normalized_question: str,
) -> SQLAgentIntent:
    """Map a normalized question to a supported intent."""

    has_policy = (
        "policy" in normalized_question
        or "policies" in normalized_question
    )

    has_payment = (
        "payment" in normalized_question
        or "payments" in normalized_question
    )

    has_commission = (
        "commission" in normalized_question
        or "commissions" in normalized_question
    )

    has_carrier = (
        "carrier" in normalized_question
        or "carriers" in normalized_question
    )

    has_agent = (
        "agent" in normalized_question
        or "agents" in normalized_question
    )

    if (
        has_policy
        and has_payment
        and contains_any_phrase(
            normalized_question,
            (
                "without payment",
                "without payments",
                "missing payment",
                "missing payments",
                "no payment",
                "no payments",
                "not paid",
                "unpaid active policies",
            ),
        )
    ):
        return (
            SQLAgentIntent
            .ACTIVE_POLICIES_WITHOUT_PAYMENTS
        )

    if (
        has_policy
        and contains_any_phrase(
            normalized_question,
            (
                "duplicate policy",
                "duplicate policies",
                "duplicate policy number",
                "duplicate policy numbers",
                "repeated policy number",
                "repeated policy numbers",
            ),
        )
    ):
        return (
            SQLAgentIntent
            .DUPLICATE_POLICY_NUMBERS
        )

    if (
        has_commission
        and has_agent
    ):
        return (
            SQLAgentIntent
            .COMMISSIONS_BY_AGENT
        )

    if (
        has_payment
        and has_carrier
    ):
        return (
            SQLAgentIntent
            .PAYMENTS_BY_CARRIER
        )

    if (
        has_policy
        and has_carrier
    ):
        return (
            SQLAgentIntent
            .POLICIES_BY_CARRIER
        )

    if (
        has_policy
        and contains_any_phrase(
            normalized_question,
            (
                "by status",
                "status breakdown",
                "status summary",
                "each status",
                "policy statuses",
            ),
        )
    ):
        return (
            SQLAgentIntent
            .POLICY_STATUS_SUMMARY
        )

    if (
        has_policy
        and "active" in normalized_question
        and contains_any_phrase(
            normalized_question,
            (
                "how many",
                "count active",
                "number of active",
                "total active",
            ),
        )
    ):
        return (
            SQLAgentIntent
            .ACTIVE_POLICY_COUNT
        )

    if (
        has_policy
        and contains_any_phrase(
            normalized_question,
            (
                "recent policies",
                "latest policies",
                "newest policies",
                "recent policy",
                "latest policy",
            ),
        )
    ):
        return (
            SQLAgentIntent
            .RECENT_POLICIES
        )

    raise UnsupportedSQLAgentQuestionError(
        "This question is not yet supported by the "
        "deterministic SQL planner. Try questions such as: "
        "'Show policies by status', "
        "'How many active policies are there?', "
        "'Show policies by carrier', "
        "'Find active policies without payments', "
        "'Find duplicate policy numbers', "
        "'Show payments by carrier', "
        "'Show commissions by agent', or "
        "'Show recent policies'."
    )


def qualified_column(
    alias: str,
    column_name: str,
) -> str:
    """Return an alias-qualified column reference."""

    return (
        f"{alias}.{column_name}"
    )


def build_workspace_condition(
    table: SQLAgentTableCatalog,
    *,
    alias: str,
    workspace_id: UUID,
) -> str:
    """Create a tenant-isolation condition."""

    workspace_column = (
        table.require_column(
            "workspace_id"
        )
    )

    return (
        f"{qualified_column(alias, workspace_column)} "
        f"= '{workspace_id}'::uuid"
    )


def build_agent_name_expression(
    agent_table: SQLAgentTableCatalog,
    *,
    alias: str,
) -> str:
    """Build the best available agent display expression."""

    first_name_column = (
        agent_table.resolve_column(
            (
                "first_name",
                "firstname",
            )
        )
    )

    last_name_column = (
        agent_table.resolve_column(
            (
                "last_name",
                "lastname",
            )
        )
    )

    if (
        first_name_column
        and last_name_column
    ):
        return (
            "TRIM(CONCAT_WS(' ', "
            f"{alias}.{first_name_column}, "
            f"{alias}.{last_name_column}"
            "))"
        )

    name_column = (
        agent_table.resolve_column(
            (
                "name",
                "full_name",
                "agent_name",
            )
        )
    )

    if name_column:
        return (
            f"{alias}.{name_column}"
        )

    email_column = (
        agent_table.require_one_of(
            (
                "email",
                "work_email",
            ),
            semantic_name="agent display name",
        )
    )

    return (
        f"{alias}.{email_column}"
    )


def build_policy_status_summary(
    *,
    catalog: InsuranceSchemaCatalog,
    workspace_id: UUID,
) -> tuple[str, str]:
    """Build policy counts grouped by status."""

    policy_table = catalog.require_table(
        "insurance_policies"
    )

    status_column = (
        policy_table.require_column(
            "status"
        )
    )

    workspace_condition = (
        build_workspace_condition(
            policy_table,
            alias="p",
            workspace_id=workspace_id,
        )
    )

    sql = f"""
        SELECT
            p.{status_column} AS status,
            COUNT(*)::bigint AS policy_count
        FROM public.insurance_policies AS p
        WHERE {workspace_condition}
        GROUP BY p.{status_column}
        ORDER BY
            policy_count DESC,
            p.{status_column}
    """.strip()

    return (
        sql,
        "Counts policies in the current workspace "
        "and groups them by policy status.",
    )


def build_active_policy_count(
    *,
    catalog: InsuranceSchemaCatalog,
    workspace_id: UUID,
) -> tuple[str, str]:
    """Build active policy count."""

    policy_table = catalog.require_table(
        "insurance_policies"
    )

    status_column = (
        policy_table.require_column(
            "status"
        )
    )

    workspace_condition = (
        build_workspace_condition(
            policy_table,
            alias="p",
            workspace_id=workspace_id,
        )
    )

    sql = f"""
        SELECT
            COUNT(*)::bigint AS active_policy_count
        FROM public.insurance_policies AS p
        WHERE
            {workspace_condition}
            AND LOWER(
                CAST(p.{status_column} AS TEXT)
            ) = 'active'
    """.strip()

    return (
        sql,
        "Counts active policies in the current workspace.",
    )


def build_policies_by_carrier(
    *,
    catalog: InsuranceSchemaCatalog,
    workspace_id: UUID,
) -> tuple[str, str]:
    """Build policy counts grouped by carrier."""

    policy_table = catalog.require_table(
        "insurance_policies"
    )

    carrier_table = catalog.require_table(
        "insurance_carriers"
    )

    policy_carrier_column = (
        policy_table.require_column(
            "carrier_id"
        )
    )

    carrier_id_column = (
        carrier_table.require_column(
            "id"
        )
    )

    carrier_name_column = (
        carrier_table.require_one_of(
            (
                "name",
                "carrier_name",
            ),
            semantic_name="carrier name",
        )
    )

    policy_workspace_condition = (
        build_workspace_condition(
            policy_table,
            alias="p",
            workspace_id=workspace_id,
        )
    )

    carrier_workspace_condition = (
        build_workspace_condition(
            carrier_table,
            alias="c",
            workspace_id=workspace_id,
        )
    )

    sql = f"""
        SELECT
            c.{carrier_name_column} AS carrier_name,
            COUNT(*)::bigint AS policy_count
        FROM public.insurance_policies AS p
        JOIN public.insurance_carriers AS c
            ON c.{carrier_id_column}
                = p.{policy_carrier_column}
            AND {carrier_workspace_condition}
        WHERE {policy_workspace_condition}
        GROUP BY c.{carrier_name_column}
        ORDER BY
            policy_count DESC,
            c.{carrier_name_column}
    """.strip()

    return (
        sql,
        "Counts workspace policies grouped by carrier.",
    )


def build_active_without_payments(
    *,
    catalog: InsuranceSchemaCatalog,
    workspace_id: UUID,
) -> tuple[str, str]:
    """Build active policies without a payment record."""

    policy_table = catalog.require_table(
        "insurance_policies"
    )

    payment_table = catalog.require_table(
        "insurance_payments"
    )

    policy_id_column = (
        policy_table.require_column(
            "id"
        )
    )

    policy_number_column = (
        policy_table.require_column(
            "policy_number"
        )
    )

    policy_status_column = (
        policy_table.require_column(
            "status"
        )
    )

    payment_id_column = (
        payment_table.require_column(
            "id"
        )
    )

    payment_policy_column = (
        payment_table.require_column(
            "policy_id"
        )
    )

    policy_workspace_condition = (
        build_workspace_condition(
            policy_table,
            alias="p",
            workspace_id=workspace_id,
        )
    )

    payment_workspace_condition = (
        build_workspace_condition(
            payment_table,
            alias="pay",
            workspace_id=workspace_id,
        )
    )

    sql = f"""
        SELECT
            p.{policy_id_column} AS policy_id,
            p.{policy_number_column} AS policy_number,
            p.{policy_status_column} AS status
        FROM public.insurance_policies AS p
        LEFT JOIN public.insurance_payments AS pay
            ON pay.{payment_policy_column}
                = p.{policy_id_column}
            AND {payment_workspace_condition}
        WHERE
            {policy_workspace_condition}
            AND LOWER(
                CAST(p.{policy_status_column} AS TEXT)
            ) = 'active'
            AND pay.{payment_id_column} IS NULL
        ORDER BY p.{policy_number_column}
    """.strip()

    return (
        sql,
        "Returns active workspace policies that have "
        "no matching payment record.",
    )


def build_duplicate_policy_numbers(
    *,
    catalog: InsuranceSchemaCatalog,
    workspace_id: UUID,
) -> tuple[str, str]:
    """Build duplicate policy-number report."""

    policy_table = catalog.require_table(
        "insurance_policies"
    )

    policy_number_column = (
        policy_table.require_column(
            "policy_number"
        )
    )

    workspace_condition = (
        build_workspace_condition(
            policy_table,
            alias="p",
            workspace_id=workspace_id,
        )
    )

    sql = f"""
        SELECT
            p.{policy_number_column} AS policy_number,
            COUNT(*)::bigint AS duplicate_count
        FROM public.insurance_policies AS p
        WHERE {workspace_condition}
        GROUP BY p.{policy_number_column}
        HAVING COUNT(*) > 1
        ORDER BY
            duplicate_count DESC,
            p.{policy_number_column}
    """.strip()

    return (
        sql,
        "Finds policy numbers appearing more than once "
        "inside the current workspace.",
    )


def build_payments_by_carrier(
    *,
    catalog: InsuranceSchemaCatalog,
    workspace_id: UUID,
) -> tuple[str, str]:
    """Build payment totals grouped by carrier."""

    payment_table = catalog.require_table(
        "insurance_payments"
    )

    policy_table = catalog.require_table(
        "insurance_policies"
    )

    carrier_table = catalog.require_table(
        "insurance_carriers"
    )

    payment_policy_column = (
        payment_table.require_column(
            "policy_id"
        )
    )

    payment_amount_column = (
        payment_table.require_one_of(
            (
                "amount",
                "payment_amount",
                "paid_amount",
            ),
            semantic_name="payment amount",
        )
    )

    policy_id_column = (
        policy_table.require_column(
            "id"
        )
    )

    policy_carrier_column = (
        policy_table.require_column(
            "carrier_id"
        )
    )

    carrier_id_column = (
        carrier_table.require_column(
            "id"
        )
    )

    carrier_name_column = (
        carrier_table.require_one_of(
            (
                "name",
                "carrier_name",
            ),
            semantic_name="carrier name",
        )
    )

    payment_workspace_condition = (
        build_workspace_condition(
            payment_table,
            alias="pay",
            workspace_id=workspace_id,
        )
    )

    policy_workspace_condition = (
        build_workspace_condition(
            policy_table,
            alias="p",
            workspace_id=workspace_id,
        )
    )

    carrier_workspace_condition = (
        build_workspace_condition(
            carrier_table,
            alias="c",
            workspace_id=workspace_id,
        )
    )

    sql = f"""
        SELECT
            c.{carrier_name_column} AS carrier_name,
            COUNT(pay.id)::bigint AS payment_count,
            COALESCE(
                SUM(pay.{payment_amount_column}),
                0
            ) AS total_payment_amount
        FROM public.insurance_payments AS pay
        JOIN public.insurance_policies AS p
            ON p.{policy_id_column}
                = pay.{payment_policy_column}
            AND {policy_workspace_condition}
        JOIN public.insurance_carriers AS c
            ON c.{carrier_id_column}
                = p.{policy_carrier_column}
            AND {carrier_workspace_condition}
        WHERE {payment_workspace_condition}
        GROUP BY c.{carrier_name_column}
        ORDER BY
            total_payment_amount DESC,
            c.{carrier_name_column}
    """.strip()

    return (
        sql,
        "Calculates payment counts and total payment "
        "amounts grouped by carrier.",
    )


def build_commissions_by_agent(
    *,
    catalog: InsuranceSchemaCatalog,
    workspace_id: UUID,
) -> tuple[str, str]:
    """Build commission totals grouped by agent."""

    commission_table = catalog.require_table(
        "insurance_commissions"
    )

    agent_table = catalog.require_table(
        "insurance_agents"
    )

    commission_amount_column = (
        commission_table.require_one_of(
            (
                "amount",
                "commission_amount",
            ),
            semantic_name="commission amount",
        )
    )

    commission_agent_column = (
        commission_table.resolve_column(
            (
                "agent_id",
            )
        )
    )

    agent_id_column = (
        agent_table.require_column(
            "id"
        )
    )

    agent_name_expression = (
        build_agent_name_expression(
            agent_table,
            alias="a",
        )
    )

    commission_workspace_condition = (
        build_workspace_condition(
            commission_table,
            alias="comm",
            workspace_id=workspace_id,
        )
    )

    agent_workspace_condition = (
        build_workspace_condition(
            agent_table,
            alias="a",
            workspace_id=workspace_id,
        )
    )

    if commission_agent_column:
        join_sql = f"""
            JOIN public.insurance_agents AS a
                ON a.{agent_id_column}
                    = comm.{commission_agent_column}
                AND {agent_workspace_condition}
        """.strip()

    else:
        policy_table = catalog.require_table(
            "insurance_policies"
        )

        commission_policy_column = (
            commission_table.require_column(
                "policy_id"
            )
        )

        policy_id_column = (
            policy_table.require_column(
                "id"
            )
        )

        policy_agent_column = (
            policy_table.require_column(
                "agent_id"
            )
        )

        policy_workspace_condition = (
            build_workspace_condition(
                policy_table,
                alias="p",
                workspace_id=workspace_id,
            )
        )

        join_sql = f"""
            JOIN public.insurance_policies AS p
                ON p.{policy_id_column}
                    = comm.{commission_policy_column}
                AND {policy_workspace_condition}
            JOIN public.insurance_agents AS a
                ON a.{agent_id_column}
                    = p.{policy_agent_column}
                AND {agent_workspace_condition}
        """.strip()

    sql = f"""
        SELECT
            {agent_name_expression} AS agent_name,
            COUNT(comm.id)::bigint AS commission_count,
            COALESCE(
                SUM(comm.{commission_amount_column}),
                0
            ) AS total_commission_amount
        FROM public.insurance_commissions AS comm
        {join_sql}
        WHERE {commission_workspace_condition}
        GROUP BY {agent_name_expression}
        ORDER BY
            total_commission_amount DESC,
            agent_name
    """.strip()

    return (
        sql,
        "Calculates commission counts and total commission "
        "amounts grouped by agent.",
    )


def build_recent_policies(
    *,
    catalog: InsuranceSchemaCatalog,
    workspace_id: UUID,
) -> tuple[str, str]:
    """Build a recent-policy listing."""

    policy_table = catalog.require_table(
        "insurance_policies"
    )

    policy_number_column = (
        policy_table.require_column(
            "policy_number"
        )
    )

    status_column = (
        policy_table.require_column(
            "status"
        )
    )

    effective_date_column = (
        policy_table.require_one_of(
            (
                "effective_date",
                "created_at",
            ),
            semantic_name="policy date",
        )
    )

    premium_column = (
        policy_table.resolve_column(
            (
                "premium",
                "premium_amount",
                "monthly_premium",
            )
        )
    )

    workspace_condition = (
        build_workspace_condition(
            policy_table,
            alias="p",
            workspace_id=workspace_id,
        )
    )

    premium_selection = (
        (
            f",\n            p.{premium_column} "
            "AS premium"
        )
        if premium_column
        else ""
    )

    sql = f"""
        SELECT
            p.id AS policy_id,
            p.{policy_number_column} AS policy_number,
            p.{status_column} AS status,
            p.{effective_date_column} AS effective_date
            {premium_selection}
        FROM public.insurance_policies AS p
        WHERE {workspace_condition}
        ORDER BY
            p.{effective_date_column} DESC,
            p.{policy_number_column}
    """.strip()

    return (
        sql,
        "Returns the newest policies in the current workspace.",
    )


def build_sql_for_intent(
    *,
    intent: SQLAgentIntent,
    catalog: InsuranceSchemaCatalog,
    workspace_id: UUID,
) -> tuple[str, str]:
    """Build SQL and explanation for a supported intent."""

    builders = {
        SQLAgentIntent.POLICY_STATUS_SUMMARY: (
            build_policy_status_summary
        ),
        SQLAgentIntent.ACTIVE_POLICY_COUNT: (
            build_active_policy_count
        ),
        SQLAgentIntent.POLICIES_BY_CARRIER: (
            build_policies_by_carrier
        ),
        SQLAgentIntent.ACTIVE_POLICIES_WITHOUT_PAYMENTS: (
            build_active_without_payments
        ),
        SQLAgentIntent.DUPLICATE_POLICY_NUMBERS: (
            build_duplicate_policy_numbers
        ),
        SQLAgentIntent.PAYMENTS_BY_CARRIER: (
            build_payments_by_carrier
        ),
        SQLAgentIntent.COMMISSIONS_BY_AGENT: (
            build_commissions_by_agent
        ),
        SQLAgentIntent.RECENT_POLICIES: (
            build_recent_policies
        ),
    }

    builder = builders[
        intent
    ]

    return builder(
        catalog=catalog,
        workspace_id=workspace_id,
    )


def plan_sql_agent_question(
    *,
    question: str,
    workspace_id: UUID,
    catalog: InsuranceSchemaCatalog,
    max_rows: int | None = None,
) -> SQLAgentPlan:
    """Generate and guardrail-check SQL for a business question."""

    normalized_question = (
        normalize_sql_agent_question(
            question
        )
    )

    intent = detect_sql_agent_intent(
        normalized_question
    )

    generated_sql, explanation = (
        build_sql_for_intent(
            intent=intent,
            catalog=catalog,
            workspace_id=workspace_id,
        )
    )

    validation_result: (
        SafeSQLValidationResult
    ) = validate_sql_agent_query(
        generated_sql,
        max_rows=max_rows,
    )

    return SQLAgentPlan(
        question=question.strip(),
        normalized_question=(
            normalized_question
        ),
        intent=intent,
        explanation=explanation,
        generated_sql=generated_sql,
        normalized_sql=(
            validation_result.normalized_sql
        ),
        executable_sql=(
            validation_result.executable_sql
        ),
        referenced_tables=(
            validation_result.referenced_tables
        ),
        max_rows=(
            validation_result.max_rows
        ),
    )