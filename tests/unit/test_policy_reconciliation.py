from __future__ import annotations

from apps.api.app.services.policy_reconciliation import (
    _build_review_title,
    _review_priority,
    _should_create_review_task,
)
from apps.api.app.services.reconciliation_rules import (
    ReconciliationRuleResult,
)


def build_result(
    *,
    status: str,
    severity: str,
    finding_type: str = (
        "effective_date_mismatch"
    ),
) -> ReconciliationRuleResult:
    return ReconciliationRuleResult(
        rule_code="REC006",
        finding_type=finding_type,
        field_name="effective_date",
        status=status,
        severity=severity,
        expected_value="2026-01-01",
        actual_value="2026-02-01",
        message=(
            "Effective date differs between "
            "the document and database."
        ),
    )


def test_failed_high_finding_creates_review() -> None:
    result = build_result(
        status="failed",
        severity="high",
    )

    assert (
        _should_create_review_task(
            result
        )
        is True
    )


def test_review_medium_finding_creates_review() -> None:
    result = build_result(
        status="needs_review",
        severity="medium",
    )

    assert (
        _should_create_review_task(
            result
        )
        is True
    )


def test_passed_finding_does_not_create_review() -> None:
    result = build_result(
        status="passed",
        severity="info",
    )

    assert (
        _should_create_review_task(
            result
        )
        is False
    )


def test_skipped_finding_does_not_create_review() -> None:
    result = build_result(
        status="skipped",
        severity="info",
    )

    assert (
        _should_create_review_task(
            result
        )
        is False
    )


def test_low_severity_failure_does_not_create_review() -> None:
    result = build_result(
        status="failed",
        severity="low",
    )

    assert (
        _should_create_review_task(
            result
        )
        is False
    )


def test_high_severity_maps_to_high_priority() -> None:
    result = build_result(
        status="failed",
        severity="high",
    )

    assert (
        _review_priority(
            result
        )
        == "high"
    )


def test_medium_severity_maps_to_medium_priority() -> None:
    result = build_result(
        status="needs_review",
        severity="medium",
    )

    assert (
        _review_priority(
            result
        )
        == "medium"
    )


def test_other_severity_maps_to_low_priority() -> None:
    result = build_result(
        status="failed",
        severity="low",
    )

    assert (
        _review_priority(
            result
        )
        == "low"
    )


def test_builds_readable_review_title() -> None:
    result = build_result(
        status="failed",
        severity="high",
        finding_type=(
            "effective_date_mismatch"
        ),
    )

    assert (
        _build_review_title(
            result
        )
        == "Effective Date Mismatch"
    )


def test_review_title_respects_database_limit() -> None:
    result = build_result(
        status="failed",
        severity="high",
        finding_type=(
            "x" * 400
        ),
    )

    assert len(
        _build_review_title(
            result
        )
    ) == 255