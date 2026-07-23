from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from apps.api.app.services.policy_field_extraction import (
    PolicySourcePage,
    extract_policy_fields,
)
from apps.api.app.services.reconciliation_rules import (
    PolicyDatabaseRecord,
    evaluate_policy_reconciliation,
)


def build_extraction(
    *,
    policy_number: str = "POL-2026-0001",
    customer_name: str = "Jane Doe",
    carrier_name: str = "Aetna",
    plan_name: str = "Aetna Gold PPO",
    effective_date: str = "01/01/2026",
    termination_date: str = "12/31/2026",
    signature_date: str | None = "12/15/2025",
    premium: str = "$1,250.00",
    policy_status: str = "Active",
    confidence_score: float = 0.98,
):
    signature_line = (
        f"Signature Date: {signature_date}"
        if signature_date is not None
        else ""
    )

    return extract_policy_fields(
        [
            PolicySourcePage(
                page_number=1,
                confidence_score=(
                    confidence_score
                ),
                text=f"""
                Policy Number: {policy_number}
                Policyholder Name: {customer_name}
                Carrier: {carrier_name}
                Plan Name: {plan_name}
                Effective Date: {effective_date}
                Termination Date: {termination_date}
                {signature_line}
                Premium Amount: {premium}
                Policy Status: {policy_status}
                """,
            )
        ]
    )


def build_policy(
    **overrides,
) -> PolicyDatabaseRecord:
    values = {
        "policy_id": uuid4(),
        "policy_number": "POL-2026-0001",
        "customer_name": "Jane Doe",
        "carrier_name": "Aetna",
        "plan_name": "Aetna Gold PPO",
        "effective_date": date(
            2026,
            1,
            1,
        ),
        "termination_date": date(
            2026,
            12,
            31,
        ),
        "signature_date": date(
            2025,
            12,
            15,
        ),
        "premium": Decimal(
            "1250.00"
        ),
        "policy_status": "active",
        "has_payment": True,
        "duplicate_policy_count": 1,
    }

    values.update(
        overrides
    )

    return PolicyDatabaseRecord(
        **values
    )


def get_result(
    evaluation,
    rule_code: str,
):
    return next(
        result
        for result in evaluation.results
        if result.rule_code
        == rule_code
    )


def test_matching_policy_passes_rules() -> None:
    evaluation = (
        evaluate_policy_reconciliation(
            build_extraction(),
            build_policy(),
        )
    )

    assert evaluation.failed_checks == 0
    assert evaluation.review_checks == 0
    assert evaluation.overall_status == "completed"

    assert (
        get_result(
            evaluation,
            "REC001",
        ).status
        == "passed"
    )

    assert (
        get_result(
            evaluation,
            "REC009",
        ).status
        == "passed"
    )

    assert (
        get_result(
            evaluation,
            "REC011",
        ).status
        == "passed"
    )


def test_unmatched_policy_fails() -> None:
    evaluation = (
        evaluate_policy_reconciliation(
            build_extraction(),
            None,
        )
    )

    result = get_result(
        evaluation,
        "REC001",
    )

    assert result.status == "failed"
    assert result.severity == "high"

    assert (
        result.finding_type
        == "unmatched_policy"
    )

    assert (
        evaluation.matched_policy_id
        is None
    )


def test_duplicate_policy_requires_review() -> None:
    evaluation = (
        evaluate_policy_reconciliation(
            build_extraction(),
            build_policy(
                duplicate_policy_count=3,
            ),
        )
    )

    result = get_result(
        evaluation,
        "REC002",
    )

    assert (
        result.status
        == "needs_review"
    )

    assert result.severity == "high"
    assert result.actual_value == 3


def test_customer_name_is_case_and_punctuation_insensitive() -> None:
    evaluation = (
        evaluate_policy_reconciliation(
            build_extraction(
                customer_name="JANE  DOE",
            ),
            build_policy(
                customer_name="Jane-Doe",
            ),
        )
    )

    assert (
        get_result(
            evaluation,
            "REC003",
        ).status
        == "passed"
    )


def test_customer_name_mismatch_fails() -> None:
    evaluation = (
        evaluate_policy_reconciliation(
            build_extraction(
                customer_name="John Smith",
            ),
            build_policy(),
        )
    )

    result = get_result(
        evaluation,
        "REC003",
    )

    assert result.status == "failed"
    assert result.severity == "high"


def test_effective_date_mismatch_fails() -> None:
    evaluation = (
        evaluate_policy_reconciliation(
            build_extraction(
                effective_date="02/01/2026",
            ),
            build_policy(),
        )
    )

    result = get_result(
        evaluation,
        "REC006",
    )

    assert result.status == "failed"

    assert (
        result.expected_value
        == "2026-01-01"
    )

    assert (
        result.actual_value
        == "2026-02-01"
    )


def test_premium_within_tolerance_passes() -> None:
    evaluation = (
        evaluate_policy_reconciliation(
            build_extraction(
                premium="$1,250.03",
            ),
            build_policy(),
            premium_tolerance=Decimal(
                "0.05"
            ),
        )
    )

    result = get_result(
        evaluation,
        "REC009",
    )

    assert result.status == "passed"

    assert (
        result.evidence_data[
            "difference"
        ]
        == "0.03"
    )


def test_premium_outside_tolerance_fails() -> None:
    evaluation = (
        evaluate_policy_reconciliation(
            build_extraction(
                premium="$1,300.00",
            ),
            build_policy(),
            premium_tolerance=Decimal(
                "0.01"
            ),
        )
    )

    result = get_result(
        evaluation,
        "REC009",
    )

    assert result.status == "failed"
    assert result.severity == "high"

    assert (
        result.finding_type
        == "premium_mismatch"
    )


def test_missing_signature_requires_review() -> None:
    evaluation = (
        evaluate_policy_reconciliation(
            build_extraction(
                signature_date=None,
            ),
            build_policy(),
        )
    )

    result = get_result(
        evaluation,
        "REC008",
    )

    assert (
        result.status
        == "needs_review"
    )

    assert result.severity == "high"

    assert (
        result.finding_type
        == "missing_signature"
    )


def test_active_policy_without_payment_fails() -> None:
    evaluation = (
        evaluate_policy_reconciliation(
            build_extraction(),
            build_policy(
                has_payment=False,
                policy_status="active",
            ),
        )
    )

    result = get_result(
        evaluation,
        "REC011",
    )

    assert result.status == "failed"
    assert result.severity == "high"

    assert (
        result.finding_type
        == "missing_payment"
    )


def test_cancelled_policy_payment_check_is_skipped() -> None:
    evaluation = (
        evaluate_policy_reconciliation(
            build_extraction(
                policy_status="Cancelled",
            ),
            build_policy(
                has_payment=False,
                policy_status="cancelled",
            ),
            exclude_cancelled=True,
        )
    )

    result = get_result(
        evaluation,
        "REC011",
    )

    assert result.status == "skipped"


def test_cancelled_policy_can_still_require_payment_check() -> None:
    evaluation = (
        evaluate_policy_reconciliation(
            build_extraction(
                policy_status="Cancelled",
            ),
            build_policy(
                has_payment=False,
                policy_status="cancelled",
            ),
            exclude_cancelled=False,
        )
    )

    result = get_result(
        evaluation,
        "REC011",
    )

    assert result.status == "failed"
    assert result.severity == "medium"


def test_low_extraction_confidence_requires_review() -> None:
    evaluation = (
        evaluate_policy_reconciliation(
            build_extraction(
                confidence_score=0.55,
            ),
            build_policy(),
            minimum_confidence=0.75,
        )
    )

    result = get_result(
        evaluation,
        "REC012",
    )

    assert (
        result.status
        == "needs_review"
    )

    assert (
        result.finding_type
        == "low_extraction_confidence"
    )


def test_optional_missing_values_are_skipped() -> None:
    extraction = extract_policy_fields(
        [
            PolicySourcePage(
                page_number=1,
                text="""
                Policy Number: POL-2026-0001
                Policyholder Name: Jane Doe
                Effective Date: 01/01/2026
                Signature Date: 12/15/2025
                Premium: $1,250
                Policy Status: Active
                """,
            )
        ]
    )

    evaluation = (
        evaluate_policy_reconciliation(
            extraction,
            build_policy(
                carrier_name=None,
                plan_name=None,
                termination_date=None,
            ),
        )
    )

    assert (
        get_result(
            evaluation,
            "REC004",
        ).status
        == "skipped"
    )

    assert (
        get_result(
            evaluation,
            "REC005",
        ).status
        == "skipped"
    )

    assert (
        get_result(
            evaluation,
            "REC007",
        ).status
        == "skipped"
    )


def test_one_sided_optional_value_requires_review() -> None:
    evaluation = (
        evaluate_policy_reconciliation(
            build_extraction(
                carrier_name="Aetna",
            ),
            build_policy(
                carrier_name=None,
            ),
        )
    )

    result = get_result(
        evaluation,
        "REC004",
    )

    assert (
        result.status
        == "needs_review"
    )


def test_summary_contains_expected_counts() -> None:
    evaluation = (
        evaluate_policy_reconciliation(
            build_extraction(),
            build_policy(
                has_payment=False,
            ),
        )
    )

    summary = evaluation.to_summary()

    assert (
        summary["total_checks"]
        == len(
            evaluation.results
        )
    )

    assert (
        summary["failed_checks"]
        >= 1
    )

    assert (
        summary["overall_status"]
        == "needs_review"
    )


def test_result_can_build_finding_values() -> None:
    evaluation = (
        evaluate_policy_reconciliation(
            build_extraction(),
            build_policy(),
        )
    )

    result = get_result(
        evaluation,
        "REC001",
    )

    payload = (
        result.to_finding_values()
    )

    assert (
        payload["rule_code"]
        == "REC001"
    )

    assert (
        payload["business_policy_id"]
        == result.business_policy_id
    )

    assert "evidence_data" in payload


def test_rejects_invalid_minimum_confidence() -> None:
    with pytest.raises(
        ValueError,
        match="minimum_confidence",
    ):
        evaluate_policy_reconciliation(
            build_extraction(),
            build_policy(),
            minimum_confidence=1.5,
        )


def test_rejects_negative_premium_tolerance() -> None:
    with pytest.raises(
        ValueError,
        match="premium_tolerance",
    ):
        evaluate_policy_reconciliation(
            build_extraction(),
            build_policy(),
            premium_tolerance=Decimal(
                "-0.01"
            ),
        )


def test_rejects_invalid_duplicate_count() -> None:
    with pytest.raises(
        ValueError,
        match="duplicate_policy_count",
    ):
        build_policy(
            duplicate_policy_count=0,
        )
        
def test_signature_passes_when_database_does_not_track_date() -> None:
    evaluation = (
        evaluate_policy_reconciliation(
            build_extraction(
                signature_date="12/15/2025",
            ),
            build_policy(
                signature_date=None,
            ),
        )
    )

    result = get_result(
        evaluation,
        "REC008",
    )

    assert result.status == "passed"

    assert (
        result.finding_type
        == "signature_present"
    )

    assert (
        result.actual_value
        == "2025-12-15"
    )

    assert (
        result.evidence_data[
            "database_signature_date_tracked"
        ]
        is False
    )