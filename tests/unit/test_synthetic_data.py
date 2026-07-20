from __future__ import annotations

from collections import Counter

from packages.data_engineering.synthetic_data import (
    DEFAULT_SEED,
    build_demo_dataset,
)


EXPECTED_COUNTS = {
    "carriers": 5,
    "plans": 10,
    "agents": 15,
    "customers": 100,
    "policies": 150,
    "payments": 85,
    "commissions": 85,
}

EXPECTED_DUPLICATE_POLICY_NUMBERS = {
    "POL-2026-0011",
    "POL-2026-0035",
    "POL-2026-0070",
    "POL-2026-0094",
    "POL-2026-0122",
}

EXPECTED_MISSING_PAYMENT_POLICY_NUMBERS = {
    "POL-2026-0001",
    "POL-2026-0002",
    "POL-2026-0003",
    "POL-2026-0004",
    "POL-2026-0005",
    "POL-2026-0006",
    "POL-2026-0007",
    "POL-2026-0008",
}


def test_demo_dataset_has_expected_record_counts() -> None:
    dataset = build_demo_dataset()

    assert dataset["metadata"]["record_counts"] == EXPECTED_COUNTS


def test_demo_dataset_is_deterministic() -> None:
    first_dataset = build_demo_dataset(seed=DEFAULT_SEED)
    second_dataset = build_demo_dataset(seed=DEFAULT_SEED)

    assert first_dataset == second_dataset


def test_demo_dataset_has_expected_duplicate_policies() -> None:
    dataset = build_demo_dataset()

    policy_number_counts = Counter(
        policy["policy_number"]
        for policy in dataset["policies"]
    )

    duplicate_policy_numbers = {
        policy_number
        for policy_number, record_count
        in policy_number_counts.items()
        if record_count > 1
    }

    assert duplicate_policy_numbers == (
        EXPECTED_DUPLICATE_POLICY_NUMBERS
    )

    for policy_number in EXPECTED_DUPLICATE_POLICY_NUMBERS:
        assert policy_number_counts[policy_number] == 2


def test_exactly_eight_active_policies_have_no_payment() -> None:
    dataset = build_demo_dataset()

    paid_policy_keys = {
        (
            payment["policy_source_system"],
            payment["policy_source_record_id"],
        )
        for payment in dataset["payments"]
    }

    active_policies_without_payment = [
        policy
        for policy in dataset["policies"]
        if policy["status"] == "active"
        and (
            policy["source_system"],
            policy["source_record_id"],
        )
        not in paid_policy_keys
    ]

    missing_policy_numbers = {
        policy["policy_number"]
        for policy in active_policies_without_payment
    }

    assert len(active_policies_without_payment) == 8
    assert missing_policy_numbers == (
        EXPECTED_MISSING_PAYMENT_POLICY_NUMBERS
    )