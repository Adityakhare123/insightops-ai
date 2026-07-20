from __future__ import annotations

import random
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal
from typing import Any


DEFAULT_SEED = 20260720

FIRST_NAMES = [
    "Aarav",
    "Aditi",
    "Akash",
    "Ananya",
    "Arjun",
    "Diya",
    "Harsh",
    "Ishita",
    "Kabir",
    "Kavya",
    "Manav",
    "Meera",
    "Neha",
    "Nikhil",
    "Priya",
    "Rahul",
    "Riya",
    "Rohan",
    "Saanvi",
    "Sneha",
    "Tanvi",
    "Varun",
    "Vivek",
]

LAST_NAMES = [
    "Agarwal",
    "Bansal",
    "Deshmukh",
    "Gupta",
    "Iyer",
    "Jain",
    "Joshi",
    "Kapoor",
    "Khanna",
    "Kulkarni",
    "Mehta",
    "Mishra",
    "Nair",
    "Patel",
    "Rao",
    "Reddy",
    "Shah",
    "Sharma",
    "Singh",
    "Verma",
]

STATES = [
    "CA",
    "FL",
    "GA",
    "IL",
    "NC",
    "NJ",
    "NY",
    "OH",
    "PA",
    "TX",
]


def _policy_status(index: int) -> str:
    """Return a deterministic policy status based on its position."""

    if index <= 90:
        return "active"

    if index <= 110:
        return "cancelled"

    if index <= 125:
        return "pending"

    if index <= 135:
        return "not_issued"

    return "terminated"


def _build_carriers() -> list[dict[str, Any]]:
    """Create the synthetic insurance carrier master data."""

    return [
        {
            "code": "AET",
            "name": "Aetna",
            "is_active": True,
        },
        {
            "code": "HUM",
            "name": "Humana",
            "is_active": True,
        },
        {
            "code": "CIG",
            "name": "Cigna Healthcare",
            "is_active": True,
        },
        {
            "code": "UHC",
            "name": "UnitedHealthcare",
            "is_active": True,
        },
        {
            "code": "WEL",
            "name": "Wellcare",
            "is_active": True,
        },
    ]


def _build_plans() -> list[dict[str, Any]]:
    """Create two synthetic insurance plans for each carrier."""

    plan_definitions = [
        {
            "carrier_code": "AET",
            "code": "AET-HMO-01",
            "name": "Aetna Value HMO",
            "plan_type": "HMO",
            "monthly_premium": Decimal("45.00"),
        },
        {
            "carrier_code": "AET",
            "code": "AET-PPO-01",
            "name": "Aetna Choice PPO",
            "plan_type": "PPO",
            "monthly_premium": Decimal("72.50"),
        },
        {
            "carrier_code": "HUM",
            "code": "HUM-HMO-01",
            "name": "Humana Gold HMO",
            "plan_type": "HMO",
            "monthly_premium": Decimal("39.00"),
        },
        {
            "carrier_code": "HUM",
            "code": "HUM-PPO-01",
            "name": "Humana Choice PPO",
            "plan_type": "PPO",
            "monthly_premium": Decimal("68.00"),
        },
        {
            "carrier_code": "CIG",
            "code": "CIG-HMO-01",
            "name": "Cigna Secure HMO",
            "plan_type": "HMO",
            "monthly_premium": Decimal("42.00"),
        },
        {
            "carrier_code": "CIG",
            "code": "CIG-PPO-01",
            "name": "Cigna Preferred PPO",
            "plan_type": "PPO",
            "monthly_premium": Decimal("70.00"),
        },
        {
            "carrier_code": "UHC",
            "code": "UHC-HMO-01",
            "name": "UHC Complete HMO",
            "plan_type": "HMO",
            "monthly_premium": Decimal("44.00"),
        },
        {
            "carrier_code": "UHC",
            "code": "UHC-PPO-01",
            "name": "UHC Advantage PPO",
            "plan_type": "PPO",
            "monthly_premium": Decimal("75.00"),
        },
        {
            "carrier_code": "WEL",
            "code": "WEL-HMO-01",
            "name": "Wellcare Assist HMO",
            "plan_type": "HMO",
            "monthly_premium": Decimal("36.00"),
        },
        {
            "carrier_code": "WEL",
            "code": "WEL-PPO-01",
            "name": "Wellcare Flex PPO",
            "plan_type": "PPO",
            "monthly_premium": Decimal("64.00"),
        },
    ]

    for plan in plan_definitions:
        plan["is_active"] = True

    return plan_definitions


def _build_agents(
    random_generator: random.Random,
) -> list[dict[str, Any]]:
    """Create deterministic synthetic insurance agents."""

    agents: list[dict[str, Any]] = []

    for index in range(1, 16):
        first_name = FIRST_NAMES[index % len(FIRST_NAMES)]
        last_name = LAST_NAMES[(index * 3) % len(LAST_NAMES)]

        agents.append(
            {
                "npn": str(7000000000 + index),
                "first_name": first_name,
                "last_name": last_name,
                "email": (
                    f"{first_name.lower()}."
                    f"{last_name.lower()}{index}@example.test"
                ),
                "state": random_generator.choice(STATES),
                "is_active": index <= 13,
            }
        )

    return agents


def _build_customers(
    random_generator: random.Random,
) -> list[dict[str, Any]]:
    """Create deterministic synthetic customer records."""

    customers: list[dict[str, Any]] = []
    starting_birth_date = date(1942, 1, 1)

    for index in range(1, 101):
        first_name = random_generator.choice(FIRST_NAMES)
        last_name = random_generator.choice(LAST_NAMES)

        date_of_birth = starting_birth_date + timedelta(
            days=random_generator.randint(0, 58 * 365)
        )

        phone = (
            f"+1"
            f"{random_generator.randint(200, 989):03d}"
            f"{random_generator.randint(200, 989):03d}"
            f"{random_generator.randint(1000, 9999):04d}"
        )

        customers.append(
            {
                "customer_number": f"CUST-2026-{index:05d}",
                "first_name": first_name,
                "last_name": last_name,
                "date_of_birth": date_of_birth,
                "email": (
                    f"{first_name.lower()}."
                    f"{last_name.lower()}{index}@example.test"
                ),
                "phone": phone,
                "state": random_generator.choice(STATES),
            }
        )

    return customers


def _build_policies(
    random_generator: random.Random,
    customers: list[dict[str, Any]],
    plans: list[dict[str, Any]],
    agents: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Create 145 canonical policy records and five intentional duplicate rows.

    The duplicate rows reuse a business policy number but use different source
    record IDs and source systems.
    """

    policies: list[dict[str, Any]] = []

    effective_dates = [
        date(2026, 1, 1),
        date(2026, 2, 1),
        date(2026, 3, 1),
        date(2026, 4, 1),
        date(2026, 5, 1),
        date(2026, 6, 1),
        date(2026, 7, 1),
    ]

    for index in range(1, 146):
        customer = customers[(index * 7 - 1) % len(customers)]
        plan = plans[(index - 1) % len(plans)]
        agent = agents[(index * 3 - 1) % len(agents)]

        effective_date = effective_dates[
            (index - 1) % len(effective_dates)
        ]

        submitted_date = effective_date - timedelta(
            days=random_generator.randint(7, 55)
        )

        premium_adjustment = Decimal(
            random_generator.choice(
                [
                    "0.00",
                    "5.00",
                    "10.00",
                ]
            )
        )

        premium = plan["monthly_premium"] + premium_adjustment

        policies.append(
            {
                "source_record_id": f"POLREC-{index:04d}",
                "policy_number": f"POL-2026-{index:04d}",
                "customer_number": customer["customer_number"],
                "carrier_code": plan["carrier_code"],
                "plan_code": plan["code"],
                "agent_npn": agent["npn"],
                "submitted_date": submitted_date,
                "effective_date": effective_date,
                "status": _policy_status(index),
                "premium": premium,
                "source_system": "synthetic_policy_admin",
            }
        )

    duplicate_policy_numbers = [
        "POL-2026-0011",
        "POL-2026-0035",
        "POL-2026-0070",
        "POL-2026-0094",
        "POL-2026-0122",
    ]

    for duplicate_index, policy_number in enumerate(
        duplicate_policy_numbers,
        start=146,
    ):
        source_policy = next(
            policy
            for policy in policies
            if policy["policy_number"] == policy_number
        )

        duplicate_policy = dict(source_policy)

        duplicate_policy["source_record_id"] = (
            f"POLREC-{duplicate_index:04d}"
        )

        duplicate_policy["source_system"] = "legacy_import"

        policies.append(duplicate_policy)

    return policies, duplicate_policy_numbers


def _build_payments(
    policies: list[dict[str, Any]],
    duplicate_policy_numbers: list[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Create payments for every active policy row except eight intentional cases.

    Duplicate policy rows receive payments when they are active. This prevents
    the duplicate-policy scenario from interfering with the missing-payment
    scenario.
    """

    canonical_active_policies = [
        policy
        for policy in policies[:145]
        if policy["status"] == "active"
        and policy["policy_number"] not in duplicate_policy_numbers
    ]

    missing_payment_policy_numbers = [
        policy["policy_number"]
        for policy in canonical_active_policies[:8]
    ]

    active_policies_with_payments = [
        policy
        for policy in policies
        if policy["status"] == "active"
        and policy["policy_number"]
        not in missing_payment_policy_numbers
    ]

    payments: list[dict[str, Any]] = []

    for index, policy in enumerate(
        active_policies_with_payments,
        start=1,
    ):
        payments.append(
            {
                "source_record_id": f"PAY-{index:05d}",
                "policy_source_record_id": policy[
                    "source_record_id"
                ],
                "policy_source_system": policy[
                    "source_system"
                ],
                "payment_date": (
                    policy["effective_date"]
                    + timedelta(days=5)
                ),
                "payment_type": "initial_premium",
                "amount": policy["premium"],
                "status": "posted",
            }
        )

    return payments, missing_payment_policy_numbers


def _build_commissions(
    policies: list[dict[str, Any]],
    payments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Create one commission record for every generated payment."""

    policy_lookup = {
        (
            policy["source_system"],
            policy["source_record_id"],
        ): policy
        for policy in policies
    }

    commissions: list[dict[str, Any]] = []

    for index, payment in enumerate(payments, start=1):
        policy_key = (
            payment["policy_source_system"],
            payment["policy_source_record_id"],
        )

        policy = policy_lookup.get(policy_key)

        if policy is None:
            raise ValueError(
                "Policy not found while building commission for "
                f"{policy_key}"
            )

        gross_amount = (
            payment["amount"] * Decimal("0.20")
        ).quantize(Decimal("0.01"))

        net_amount = (
            gross_amount * Decimal("0.95")
        ).quantize(Decimal("0.01"))

        commissions.append(
            {
                "source_record_id": f"COM-{index:05d}",
                "policy_source_record_id": policy[
                    "source_record_id"
                ],
                "policy_source_system": policy[
                    "source_system"
                ],
                "agent_npn": policy["agent_npn"],
                "statement_date": (
                    payment["payment_date"]
                    + timedelta(days=10)
                ),
                "commission_type": "new_business",
                "gross_amount": gross_amount,
                "net_amount": net_amount,
                "status": "paid",
            }
        )

    return commissions


def _validate_duplicate_policy_scenario(
    policies: list[dict[str, Any]],
    expected_duplicate_policy_numbers: list[str],
) -> None:
    """Verify that exactly five policy numbers occur twice."""

    policy_number_counts = Counter(
        policy["policy_number"]
        for policy in policies
    )

    actual_duplicate_policy_numbers = sorted(
        policy_number
        for policy_number, record_count
        in policy_number_counts.items()
        if record_count > 1
    )

    expected_duplicates = sorted(
        expected_duplicate_policy_numbers
    )

    if actual_duplicate_policy_numbers != expected_duplicates:
        raise AssertionError(
            "Duplicate-policy scenario does not match expectations. "
            f"Expected {expected_duplicates}, "
            f"received {actual_duplicate_policy_numbers}."
        )

    for policy_number in expected_duplicates:
        record_count = policy_number_counts[policy_number]

        if record_count != 2:
            raise AssertionError(
                f"Expected policy {policy_number} to have 2 rows, "
                f"received {record_count}."
            )


def _validate_missing_payment_scenario(
    policies: list[dict[str, Any]],
    payments: list[dict[str, Any]],
    expected_missing_policy_numbers: list[str],
) -> None:
    """Verify that exactly eight active policy rows have no payment."""

    paid_policy_keys = {
        (
            payment["policy_source_system"],
            payment["policy_source_record_id"],
        )
        for payment in payments
    }

    active_policies_without_payment = [
        policy
        for policy in policies
        if policy["status"] == "active"
        and (
            policy["source_system"],
            policy["source_record_id"],
        )
        not in paid_policy_keys
    ]

    actual_missing_policy_numbers = sorted(
        policy["policy_number"]
        for policy in active_policies_without_payment
    )

    expected_missing = sorted(
        expected_missing_policy_numbers
    )

    if actual_missing_policy_numbers != expected_missing:
        raise AssertionError(
            "Missing-payment scenario does not match expectations. "
            f"Expected {expected_missing}, "
            f"received {actual_missing_policy_numbers}."
        )


def build_demo_dataset(
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    """
    Generate the complete deterministic insurance demonstration dataset.

    Running this function with the same seed always produces the same dataset.
    """

    random_generator = random.Random(seed)

    carriers = _build_carriers()
    plans = _build_plans()
    agents = _build_agents(random_generator)
    customers = _build_customers(random_generator)

    policies, duplicate_policy_numbers = _build_policies(
        random_generator=random_generator,
        customers=customers,
        plans=plans,
        agents=agents,
    )

    payments, missing_payment_policy_numbers = _build_payments(
        policies=policies,
        duplicate_policy_numbers=duplicate_policy_numbers,
    )

    commissions = _build_commissions(
        policies=policies,
        payments=payments,
    )

    expected_counts = {
        "carriers": 5,
        "plans": 10,
        "agents": 15,
        "customers": 100,
        "policies": 150,
        "payments": 85,
        "commissions": 85,
    }

    actual_counts = {
        "carriers": len(carriers),
        "plans": len(plans),
        "agents": len(agents),
        "customers": len(customers),
        "policies": len(policies),
        "payments": len(payments),
        "commissions": len(commissions),
    }

    if actual_counts != expected_counts:
        raise AssertionError(
            "Generated dataset counts do not match expectations. "
            f"Expected {expected_counts}, received {actual_counts}."
        )

    _validate_duplicate_policy_scenario(
        policies=policies,
        expected_duplicate_policy_numbers=duplicate_policy_numbers,
    )

    _validate_missing_payment_scenario(
        policies=policies,
        payments=payments,
        expected_missing_policy_numbers=(
            missing_payment_policy_numbers
        ),
    )

    return {
        "carriers": carriers,
        "plans": plans,
        "agents": agents,
        "customers": customers,
        "policies": policies,
        "payments": payments,
        "commissions": commissions,
        "metadata": {
            "seed": seed,
            "record_counts": actual_counts,
            "duplicate_policy_numbers": duplicate_policy_numbers,
            "missing_payment_policy_numbers": (
                missing_payment_policy_numbers
            ),
        },
    }