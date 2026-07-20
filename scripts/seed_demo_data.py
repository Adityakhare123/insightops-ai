from __future__ import annotations

import sys
import traceback
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from apps.api.app.core.config import settings
from apps.api.app.core.security import (
    hash_password,
    verify_password,
)
from apps.api.app.db.models import (
    Agent,
    Carrier,
    Commission,
    Customer,
    Payment,
    Plan,
    Policy,
    User,
    Workspace,
)
from apps.api.app.db.session import SessionLocal
from packages.data_engineering.synthetic_data import (
    build_demo_dataset,
)


DEMO_WORKSPACE_NAME = "InsightOps Insurance Demo"


def get_demo_workspace_slug() -> str:
    """Return the normalized configured demo workspace slug."""

    return settings.demo_workspace_slug.strip().lower()


def get_or_create_workspace(
    session: Session,
) -> Workspace:
    """Return the demo workspace, creating it when necessary."""

    workspace_slug = get_demo_workspace_slug()

    workspace = session.scalar(
        select(Workspace).where(
            Workspace.slug == workspace_slug
        )
    )

    if workspace is not None:
        workspace.name = DEMO_WORKSPACE_NAME
        workspace.slug = workspace_slug
        workspace.is_active = True

        session.flush()

        return workspace

    workspace = Workspace(
        name=DEMO_WORKSPACE_NAME,
        slug=workspace_slug,
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
    Remove existing insurance records for the demo workspace.

    Users are intentionally preserved so administrator and frontend
    accounts survive repeated insurance-data reseeding.
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
    """Insert carriers and return them by carrier code."""

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
    """Insert plans and return them by plan code."""

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
    """Insert agents and return them by NPN."""

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
    """Insert customers and return them by customer number."""

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

        customer_lookup[
            customer.customer_number
        ] = customer

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
    """Insert policies and return them by source identity."""

    policy_lookup: dict[tuple[str, str], Policy] = {}

    for policy_data in policy_rows:
        carrier = carriers.get(
            policy_data["carrier_code"]
        )

        plan = plans.get(
            policy_data["plan_code"]
        )

        agent = agents.get(
            policy_data["agent_npn"]
        )

        customer = customers.get(
            policy_data["customer_number"]
        )

        source_record_id = policy_data[
            "source_record_id"
        ]

        if carrier is None:
            raise ValueError(
                "Carrier not found for policy "
                f"{source_record_id}"
            )

        if plan is None:
            raise ValueError(
                "Plan not found for policy "
                f"{source_record_id}"
            )

        if agent is None:
            raise ValueError(
                "Agent not found for policy "
                f"{source_record_id}"
            )

        if customer is None:
            raise ValueError(
                "Customer not found for policy "
                f"{source_record_id}"
            )

        policy = Policy(
            workspace_id=workspace.id,
            source_record_id=source_record_id,
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
    """Insert payment records for generated policies."""

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
    """Insert commission records for generated policies."""

    for commission_data in commission_rows:
        policy_key = (
            commission_data["policy_source_system"],
            commission_data["policy_source_record_id"],
        )

        policy = policies.get(policy_key)
        agent = agents.get(
            commission_data["agent_npn"]
        )

        if policy is None:
            raise ValueError(
                "Policy not found for commission "
                f"{policy_key}"
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


def normalize_demo_admin_email() -> str:
    """Return the configured demo administrator email."""

    return settings.demo_admin_email.strip().lower()


def get_demo_admin(
    session: Session,
    workspace: Workspace,
) -> User | None:
    """Return the configured demo administrator."""

    return session.scalar(
        select(User).where(
            User.workspace_id == workspace.id,
            User.email == normalize_demo_admin_email(),
        )
    )


def create_demo_admin(
    session: Session,
    workspace: Workspace,
) -> User:
    """Create the configured demo administrator."""

    admin = User(
        workspace_id=workspace.id,
        email=normalize_demo_admin_email(),
        full_name=(
            settings.demo_admin_full_name.strip()
        ),
        password_hash=hash_password(
            settings.demo_admin_password
        ),
        role="administrator",
        is_active=True,
    )

    session.add(admin)
    session.flush()

    return admin


def synchronize_demo_admin(
    session: Session,
    workspace: Workspace,
) -> tuple[User, str, list[str]]:
    """
    Create or synchronize the demo administrator.

    Returns the user, action performed, and updated fields.
    """

    admin = get_demo_admin(
        session=session,
        workspace=workspace,
    )

    if admin is None:
        admin = create_demo_admin(
            session=session,
            workspace=workspace,
        )

        return admin, "created", []

    updated_fields: list[str] = []

    expected_full_name = (
        settings.demo_admin_full_name.strip()
    )

    if admin.full_name != expected_full_name:
        admin.full_name = expected_full_name
        updated_fields.append("full_name")

    if admin.role != "administrator":
        admin.role = "administrator"
        updated_fields.append("role")

    if not admin.is_active:
        admin.is_active = True
        updated_fields.append("is_active")

    password_matches = verify_password(
        plain_password=settings.demo_admin_password,
        password_hash=admin.password_hash,
    )

    if not password_matches:
        admin.password_hash = hash_password(
            settings.demo_admin_password
        )

        updated_fields.append("password_hash")

    session.flush()

    if updated_fields:
        return admin, "updated", updated_fields

    return admin, "already synchronized", []


def count_workspace_records(
    session: Session,
    workspace: Workspace,
) -> dict[str, int]:
    """Count insurance records belonging to the demo workspace."""

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
            .where(
                model.workspace_id == workspace.id
            )
        )

        counts[name] = int(count or 0)

    return counts


def count_workspace_users(
    session: Session,
    workspace: Workspace,
) -> int:
    """Count users belonging to the demo workspace."""

    count = session.scalar(
        select(func.count())
        .select_from(User)
        .where(
            User.workspace_id == workspace.id
        )
    )

    return int(count or 0)


def seed_demo_data() -> dict[str, Any]:
    """Seed insurance records and the demo administrator."""

    dataset = build_demo_dataset()

    with SessionLocal() as session:
        try:
            workspace = get_or_create_workspace(
                session
            )

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

            (
                demo_admin,
                demo_admin_status,
                demo_admin_updated_fields,
            ) = synchronize_demo_admin(
                session=session,
                workspace=workspace,
            )

            session.commit()

            record_counts = count_workspace_records(
                session=session,
                workspace=workspace,
            )

            user_count = count_workspace_users(
                session=session,
                workspace=workspace,
            )

            return {
                "workspace_id": str(workspace.id),
                "workspace_name": workspace.name,
                "workspace_slug": workspace.slug,
                "record_counts": record_counts,
                "user_count": user_count,
                "demo_admin": {
                    "id": str(demo_admin.id),
                    "email": demo_admin.email,
                    "full_name": demo_admin.full_name,
                    "role": demo_admin.role,
                    "is_active": demo_admin.is_active,
                    "status": demo_admin_status,
                    "updated_fields": (
                        demo_admin_updated_fields
                    ),
                },
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


def print_seed_result(
    result: dict[str, Any],
) -> None:
    """Print a human-readable seed summary."""

    print()
    print("InsightOps AI demo environment seeded successfully")
    print("=" * 54)

    print(
        f"Workspace:    {result['workspace_slug']}"
    )
    print(
        f"Workspace ID: {result['workspace_id']}"
    )

    print()
    print("Inserted insurance record counts:")

    for name, count in result[
        "record_counts"
    ].items():
        print(f"  {name:<12} {count}")

    print()
    print(
        "Workspace users: "
        f"{result['user_count']}"
    )

    demo_admin = result["demo_admin"]

    print()
    print("Demo administrator:")
    print(
        f"  Status:     {demo_admin['status']}"
    )
    print(
        f"  Email:      {demo_admin['email']}"
    )
    print(
        f"  Full name:  {demo_admin['full_name']}"
    )
    print(
        f"  Role:       {demo_admin['role']}"
    )
    print(
        f"  Active:     {demo_admin['is_active']}"
    )

    if demo_admin["updated_fields"]:
        print(
            "  Updated:    "
            + ", ".join(
                demo_admin["updated_fields"]
            )
        )

    print()
    print(
        "Intentional duplicate policy numbers:"
    )

    for policy_number in result[
        "duplicate_policy_numbers"
    ]:
        print(f"  {policy_number}")

    print()
    print(
        "Intentional missing-payment policies:"
    )

    for policy_number in result[
        "missing_payment_policy_numbers"
    ]:
        print(f"  {policy_number}")

    print()
    print(
        "The demo administrator password was loaded "
        "from DEMO_ADMIN_PASSWORD."
    )


def main() -> int:
    """Run the demo environment seed process."""

    try:
        result = seed_demo_data()
        print_seed_result(result)

        return 0

    except Exception as error:
        print(
            f"Failed to seed demo environment: {error}",
            file=sys.stderr,
        )

        traceback.print_exc()

        return 1


if __name__ == "__main__":
    raise SystemExit(main())