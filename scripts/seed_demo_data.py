from __future__ import annotations

import sys
import traceback
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from apps.api.app.db.models import (
    Agent,
    Carrier,
    Commission,
    Customer,
    Payment,
    Plan,
    Policy,
    Workspace,
)
from apps.api.app.db.session import SessionLocal
from packages.data_engineering.synthetic_data import build_demo_dataset


DEMO_WORKSPACE_NAME = "InsightOps Insurance Demo"
DEMO_WORKSPACE_SLUG = "insightops-insurance-demo"


def get_or_create_workspace(session: Session) -> Workspace:
    """Return the portfolio demo workspace, creating it when necessary."""

    workspace = session.scalar(
        select(Workspace).where(
            Workspace.slug == DEMO_WORKSPACE_SLUG
        )
    )

    if workspace is not None:
        workspace.name = DEMO_WORKSPACE_NAME
        workspace.is_active = True
        session.flush()
        return workspace

    workspace = Workspace(
        name=DEMO_WORKSPACE_NAME,
        slug=DEMO_WORKSPACE_SLUG,
        is_active=True,
    )

    session.add(workspace)
    session.flush()

    return workspace


def clear_existing_demo_data(
    session: Session,
    workspace_id: Any,
) -> None:
    """
    Remove existing insurance records for only the demo workspace.

    Deletion order respects foreign-key relationships.
    """

    deletion_order = [
        Commission,
        Payment,
        Policy,
        Customer,
        Agent,
        Plan,
        Carrier,
    ]

    for model in deletion_order:
        session.execute(
            delete(model).where(
                model.workspace_id == workspace_id
            )
        )

    session.flush()


def insert_carriers(
    session: Session,
    workspace: Workspace,
    carrier_rows: list[dict[str, Any]],
) -> dict[str, Carrier]:
    carrier_lookup: dict[str, Carrier] = {}

    for carrier_data in carrier_rows:
        carrier = Carrier(
            workspace_id=workspace.id,
            code=carrier_data["code"],
            name=carrier_data["name"],
            is_active=carrier_data["is_active"],
        )

        session.add(carrier)
        carrier_lookup[carrier.code] = carrier

    session.flush()

    return carrier_lookup


def insert_plans(
    session: Session,
    workspace: Workspace,
    plan_rows: list[dict[str, Any]],
    carriers: dict[str, Carrier],
) -> dict[str, Plan]:
    plan_lookup: dict[str, Plan] = {}

    for plan_data in plan_rows:
        carrier_code = plan_data["carrier_code"]
        carrier = carriers.get(carrier_code)

        if carrier is None:
            raise ValueError(
                f"Carrier code not found for plan: {carrier_code}"
            )

        plan = Plan(
            workspace_id=workspace.id,
            carrier_id=carrier.id,
            code=plan_data["code"],
            name=plan_data["name"],
            plan_type=plan_data["plan_type"],
            monthly_premium=plan_data["monthly_premium"],
            is_active=plan_data["is_active"],
        )

        session.add(plan)
        plan_lookup[plan.code] = plan

    session.flush()

    return plan_lookup


def insert_agents(
    session: Session,
    workspace: Workspace,
    agent_rows: list[dict[str, Any]],
) -> dict[str, Agent]:
    agent_lookup: dict[str, Agent] = {}

    for agent_data in agent_rows:
        agent = Agent(
            workspace_id=workspace.id,
            npn=agent_data["npn"],
            first_name=agent_data["first_name"],
            last_name=agent_data["last_name"],
            email=agent_data["email"],
            state=agent_data["state"],
            is_active=agent_data["is_active"],
        )

        session.add(agent)
        agent_lookup[agent.npn] = agent

    session.flush()

    return agent_lookup


def insert_customers(
    session: Session,
    workspace: Workspace,
    customer_rows: list[dict[str, Any]],
) -> dict[str, Customer]:
    customer_lookup: dict[str, Customer] = {}

    for customer_data in customer_rows:
        customer = Customer(
            workspace_id=workspace.id,
            customer_number=customer_data["customer_number"],
            first_name=customer_data["first_name"],
            last_name=customer_data["last_name"],
            date_of_birth=customer_data["date_of_birth"],
            email=customer_data["email"],
            phone=customer_data["phone"],
            state=customer_data["state"],
        )

        session.add(customer)
        customer_lookup[customer.customer_number] = customer

    session.flush()

    return customer_lookup


def insert_policies(
    session: Session,
    workspace: Workspace,
    policy_rows: list[dict[str, Any]],
    carriers: dict[str, Carrier],
    plans: dict[str, Plan],
    agents: dict[str, Agent],
    customers: dict[str, Customer],
) -> dict[tuple[str, str], Policy]:
    policy_lookup: dict[tuple[str, str], Policy] = {}

    for policy_data in policy_rows:
        carrier = carriers.get(policy_data["carrier_code"])
        plan = plans.get(policy_data["plan_code"])
        agent = agents.get(policy_data["agent_npn"])
        customer = customers.get(
            policy_data["customer_number"]
        )

        if carrier is None:
            raise ValueError(
                "Carrier not found for policy "
                f"{policy_data['source_record_id']}"
            )

        if plan is None:
            raise ValueError(
                "Plan not found for policy "
                f"{policy_data['source_record_id']}"
            )

        if agent is None:
            raise ValueError(
                "Agent not found for policy "
                f"{policy_data['source_record_id']}"
            )

        if customer is None:
            raise ValueError(
                "Customer not found for policy "
                f"{policy_data['source_record_id']}"
            )

        policy = Policy(
            workspace_id=workspace.id,
            source_record_id=policy_data[
                "source_record_id"
            ],
            policy_number=policy_data["policy_number"],
            customer_id=customer.id,
            carrier_id=carrier.id,
            plan_id=plan.id,
            agent_id=agent.id,
            submitted_date=policy_data["submitted_date"],
            effective_date=policy_data["effective_date"],
            status=policy_data["status"],
            premium=policy_data["premium"],
            source_system=policy_data["source_system"],
        )

        session.add(policy)

        lookup_key = (
            policy.source_system,
            policy.source_record_id,
        )

        policy_lookup[lookup_key] = policy

    session.flush()

    return policy_lookup


def insert_payments(
    session: Session,
    workspace: Workspace,
    payment_rows: list[dict[str, Any]],
    policies: dict[tuple[str, str], Policy],
) -> None:
    for payment_data in payment_rows:
        policy_key = (
            payment_data["policy_source_system"],
            payment_data["policy_source_record_id"],
        )

        policy = policies.get(policy_key)

        if policy is None:
            raise ValueError(
                f"Policy not found for payment {policy_key}"
            )

        payment = Payment(
            workspace_id=workspace.id,
            source_record_id=payment_data[
                "source_record_id"
            ],
            policy_id=policy.id,
            payment_date=payment_data["payment_date"],
            payment_type=payment_data["payment_type"],
            amount=payment_data["amount"],
            status=payment_data["status"],
        )

        session.add(payment)

    session.flush()


def insert_commissions(
    session: Session,
    workspace: Workspace,
    commission_rows: list[dict[str, Any]],
    policies: dict[tuple[str, str], Policy],
    agents: dict[str, Agent],
) -> None:
    for commission_data in commission_rows:
        policy_key = (
            commission_data["policy_source_system"],
            commission_data["policy_source_record_id"],
        )

        policy = policies.get(policy_key)
        agent = agents.get(commission_data["agent_npn"])

        if policy is None:
            raise ValueError(
                f"Policy not found for commission {policy_key}"
            )

        if agent is None:
            raise ValueError(
                "Agent not found for commission "
                f"{commission_data['source_record_id']}"
            )

        commission = Commission(
            workspace_id=workspace.id,
            source_record_id=commission_data[
                "source_record_id"
            ],
            policy_id=policy.id,
            agent_id=agent.id,
            statement_date=commission_data[
                "statement_date"
            ],
            commission_type=commission_data[
                "commission_type"
            ],
            gross_amount=commission_data["gross_amount"],
            net_amount=commission_data["net_amount"],
            status=commission_data["status"],
        )

        session.add(commission)

    session.flush()


def count_workspace_records(
    session: Session,
    workspace: Workspace,
) -> dict[str, int]:
    models = {
        "carriers": Carrier,
        "plans": Plan,
        "agents": Agent,
        "customers": Customer,
        "policies": Policy,
        "payments": Payment,
        "commissions": Commission,
    }

    counts: dict[str, int] = {}

    for name, model in models.items():
        count = session.scalar(
            select(func.count())
            .select_from(model)
            .where(model.workspace_id == workspace.id)
        )

        counts[name] = int(count or 0)

    return counts


def seed_demo_data() -> dict[str, Any]:
    dataset = build_demo_dataset()

    with SessionLocal() as session:
        try:
            workspace = get_or_create_workspace(session)

            clear_existing_demo_data(
                session=session,
                workspace_id=workspace.id,
            )

            carriers = insert_carriers(
                session=session,
                workspace=workspace,
                carrier_rows=dataset["carriers"],
            )

            plans = insert_plans(
                session=session,
                workspace=workspace,
                plan_rows=dataset["plans"],
                carriers=carriers,
            )

            agents = insert_agents(
                session=session,
                workspace=workspace,
                agent_rows=dataset["agents"],
            )

            customers = insert_customers(
                session=session,
                workspace=workspace,
                customer_rows=dataset["customers"],
            )

            policies = insert_policies(
                session=session,
                workspace=workspace,
                policy_rows=dataset["policies"],
                carriers=carriers,
                plans=plans,
                agents=agents,
                customers=customers,
            )

            insert_payments(
                session=session,
                workspace=workspace,
                payment_rows=dataset["payments"],
                policies=policies,
            )

            insert_commissions(
                session=session,
                workspace=workspace,
                commission_rows=dataset["commissions"],
                policies=policies,
                agents=agents,
            )

            session.commit()

            counts = count_workspace_records(
                session=session,
                workspace=workspace,
            )

            return {
                "workspace_id": str(workspace.id),
                "workspace_slug": workspace.slug,
                "record_counts": counts,
                "duplicate_policy_numbers": dataset[
                    "metadata"
                ]["duplicate_policy_numbers"],
                "missing_payment_policy_numbers": dataset[
                    "metadata"
                ]["missing_payment_policy_numbers"],
            }

        except Exception:
            session.rollback()
            raise


def main() -> int:
    try:
        result = seed_demo_data()

        print()
        print("InsightOps AI demo data seeded successfully")
        print("=" * 50)
        print(f"Workspace: {result['workspace_slug']}")
        print(f"Workspace ID: {result['workspace_id']}")
        print()

        print("Inserted record counts:")

        for name, count in result["record_counts"].items():
            print(f"  {name:<12} {count}")

        print()
        print("Intentional duplicate policy numbers:")

        for policy_number in result[
            "duplicate_policy_numbers"
        ]:
            print(f"  {policy_number}")

        print()
        print("Intentional missing-payment policies:")

        for policy_number in result[
            "missing_payment_policy_numbers"
        ]:
            print(f"  {policy_number}")

        return 0

    except Exception as error:
        print(
            f"Failed to seed demo data: {error}",
            file=sys.stderr,
        )
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())