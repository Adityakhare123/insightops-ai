from __future__ import annotations

from uuid import uuid4

import pytest

from apps.api.app.services.sql_agent_planner import (
    SQLAgentIntent,
    UnsupportedSQLAgentQuestionError,
    plan_sql_agent_question,
)
from apps.api.app.services.sql_agent_schema import (
    build_schema_catalog_from_mapping,
)


@pytest.fixture
def insurance_catalog():
    return build_schema_catalog_from_mapping(
        {
            "insurance_carriers": (
                "id",
                "workspace_id",
                "name",
            ),
            "insurance_plans": (
                "id",
                "workspace_id",
                "carrier_id",
                "name",
            ),
            "insurance_agents": (
                "id",
                "workspace_id",
                "first_name",
                "last_name",
                "email",
            ),
            "insurance_customers": (
                "id",
                "workspace_id",
                "first_name",
                "last_name",
            ),
            "insurance_policies": (
                "id",
                "workspace_id",
                "carrier_id",
                "plan_id",
                "agent_id",
                "customer_id",
                "policy_number",
                "status",
                "effective_date",
                "premium",
            ),
            "insurance_payments": (
                "id",
                "workspace_id",
                "policy_id",
                "amount",
                "payment_date",
            ),
            "insurance_commissions": (
                "id",
                "workspace_id",
                "policy_id",
                "agent_id",
                "amount",
                "commission_date",
            ),
        }
    )


def test_plans_policy_status_summary(
    insurance_catalog,
) -> None:
    workspace_id = uuid4()

    plan = plan_sql_agent_question(
        question=(
            "Show me the policy status breakdown"
        ),
        workspace_id=workspace_id,
        catalog=insurance_catalog,
        max_rows=100,
    )

    assert (
        plan.intent
        == SQLAgentIntent.POLICY_STATUS_SUMMARY
    )

    assert (
        "GROUP BY p.status"
        in plan.generated_sql
    )

    assert str(workspace_id) in (
        plan.generated_sql
    )

    assert plan.referenced_tables == (
        "public.insurance_policies",
    )


def test_plans_active_policy_count(
    insurance_catalog,
) -> None:
    plan = plan_sql_agent_question(
        question=(
            "How many active policies are there?"
        ),
        workspace_id=uuid4(),
        catalog=insurance_catalog,
    )

    assert (
        plan.intent
        == SQLAgentIntent.ACTIVE_POLICY_COUNT
    )

    assert (
        "active_policy_count"
        in plan.generated_sql
    )


def test_plans_policies_by_carrier(
    insurance_catalog,
) -> None:
    plan = plan_sql_agent_question(
        question="Show policies by carrier",
        workspace_id=uuid4(),
        catalog=insurance_catalog,
    )

    assert (
        plan.intent
        == SQLAgentIntent.POLICIES_BY_CARRIER
    )

    assert plan.referenced_tables == (
        "public.insurance_carriers",
        "public.insurance_policies",
    )


def test_plans_active_policies_without_payments(
    insurance_catalog,
) -> None:
    plan = plan_sql_agent_question(
        question=(
            "Find active policies without payments"
        ),
        workspace_id=uuid4(),
        catalog=insurance_catalog,
    )

    assert (
        plan.intent
        == SQLAgentIntent
        .ACTIVE_POLICIES_WITHOUT_PAYMENTS
    )

    assert (
        "LEFT JOIN public.insurance_payments"
        in plan.generated_sql
    )

    assert (
        "pay.id IS NULL"
        in plan.generated_sql
    )


def test_plans_duplicate_policy_numbers(
    insurance_catalog,
) -> None:
    plan = plan_sql_agent_question(
        question=(
            "Show duplicate policy numbers"
        ),
        workspace_id=uuid4(),
        catalog=insurance_catalog,
    )

    assert (
        plan.intent
        == SQLAgentIntent.DUPLICATE_POLICY_NUMBERS
    )

    assert (
        "HAVING COUNT(*) > 1"
        in plan.generated_sql
    )


def test_plans_payments_by_carrier(
    insurance_catalog,
) -> None:
    plan = plan_sql_agent_question(
        question=(
            "Show total payments by carrier"
        ),
        workspace_id=uuid4(),
        catalog=insurance_catalog,
    )

    assert (
        plan.intent
        == SQLAgentIntent.PAYMENTS_BY_CARRIER
    )

    assert (
        "total_payment_amount"
        in plan.generated_sql
    )


def test_plans_commissions_by_agent(
    insurance_catalog,
) -> None:
    plan = plan_sql_agent_question(
        question=(
            "Show commissions by agent"
        ),
        workspace_id=uuid4(),
        catalog=insurance_catalog,
    )

    assert (
        plan.intent
        == SQLAgentIntent.COMMISSIONS_BY_AGENT
    )

    assert (
        "total_commission_amount"
        in plan.generated_sql
    )


def test_plans_recent_policies(
    insurance_catalog,
) -> None:
    plan = plan_sql_agent_question(
        question="Show recent policies",
        workspace_id=uuid4(),
        catalog=insurance_catalog,
    )

    assert (
        plan.intent
        == SQLAgentIntent.RECENT_POLICIES
    )

    assert (
        "ORDER BY"
        in plan.generated_sql
    )


def test_workspace_scope_is_always_present(
    insurance_catalog,
) -> None:
    workspace_id = uuid4()

    plan = plan_sql_agent_question(
        question="Show policies by carrier",
        workspace_id=workspace_id,
        catalog=insurance_catalog,
    )

    assert (
        plan.generated_sql.count(
            str(workspace_id)
        )
        >= 2
    )


def test_unsupported_question_is_rejected(
    insurance_catalog,
) -> None:
    with pytest.raises(
        UnsupportedSQLAgentQuestionError,
        match="not yet supported",
    ):
        plan_sql_agent_question(
            question=(
                "Which customer has the best future?"
            ),
            workspace_id=uuid4(),
            catalog=insurance_catalog,
        )