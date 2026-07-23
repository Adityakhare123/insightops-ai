from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from apps.api.app.services.policy_field_extraction import (
    ExtractedPolicyField,
    PolicyDocumentExtraction,
)


@dataclass(
    frozen=True,
    slots=True,
)
class PolicyDatabaseRecord:
    """
    Normalized policy information loaded from the database.

    This object intentionally remains independent of SQLAlchemy so the
    validation engine can be tested without a database connection.
    """

    policy_id: UUID | None
    policy_number: str

    customer_name: str | None = None
    carrier_name: str | None = None
    plan_name: str | None = None

    effective_date: date | datetime | str | None = None
    termination_date: date | datetime | str | None = None
    signature_date: date | datetime | str | None = None

    premium: Decimal | float | int | str | None = None
    policy_status: str | None = None

    has_payment: bool | None = None
    duplicate_policy_count: int = 1

    def __post_init__(self) -> None:
        if self.duplicate_policy_count < 1:
            raise ValueError(
                "duplicate_policy_count must be at least 1."
            )


@dataclass(
    frozen=True,
    slots=True,
)
class ReconciliationRuleResult:
    """
    One deterministic reconciliation result.

    Its fields closely match ReconciliationFinding so results can be
    persisted without losing source evidence or normalized values.
    """

    rule_code: str
    finding_type: str
    field_name: str | None

    status: str
    severity: str

    expected_value: Any | None
    actual_value: Any | None

    message: str

    business_policy_id: UUID | None = None

    source_text: str | None = None
    source_page_number: int | None = None
    confidence_score: float | None = None

    evidence_data: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)

        if payload["business_policy_id"] is not None:
            payload["business_policy_id"] = str(
                payload["business_policy_id"]
            )

        if payload["evidence_data"] is None:
            payload["evidence_data"] = {}

        return payload

    def to_finding_values(self) -> dict[str, Any]:
        """
        Return keyword arguments accepted by ReconciliationFinding.

        Workspace, run, and document identifiers are added by the
        persistence service in Day 8.4.
        """

        return {
            "business_policy_id": self.business_policy_id,
            "rule_code": self.rule_code,
            "finding_type": self.finding_type,
            "field_name": self.field_name,
            "status": self.status,
            "severity": self.severity,
            "expected_value": self.expected_value,
            "actual_value": self.actual_value,
            "message": self.message,
            "source_text": self.source_text,
            "source_page_number": self.source_page_number,
            "confidence_score": self.confidence_score,
            "evidence_data": self.evidence_data or {},
        }


@dataclass(
    frozen=True,
    slots=True,
)
class ReconciliationEvaluation:
    """
    Complete deterministic evaluation for one policy document.
    """

    results: tuple[
        ReconciliationRuleResult,
        ...
    ]

    matched_policy_id: UUID | None

    def count_status(
        self,
        status: str,
    ) -> int:
        return sum(
            result.status == status
            for result in self.results
        )

    @property
    def total_checks(self) -> int:
        return len(self.results)

    @property
    def passed_checks(self) -> int:
        return self.count_status(
            "passed"
        )

    @property
    def failed_checks(self) -> int:
        return self.count_status(
            "failed"
        )

    @property
    def review_checks(self) -> int:
        return self.count_status(
            "needs_review"
        )

    @property
    def skipped_checks(self) -> int:
        return self.count_status(
            "skipped"
        )

    @property
    def overall_status(self) -> str:
        if self.failed_checks > 0:
            return "needs_review"

        if self.review_checks > 0:
            return "needs_review"

        return "completed"

    def to_summary(self) -> dict[str, Any]:
        status_counts = Counter(
            result.status
            for result in self.results
        )

        severity_counts = Counter(
            result.severity
            for result in self.results
        )

        return {
            "overall_status": self.overall_status,
            "matched_policy_id": (
                str(self.matched_policy_id)
                if self.matched_policy_id
                else None
            ),
            "total_checks": self.total_checks,
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "review_checks": self.review_checks,
            "skipped_checks": self.skipped_checks,
            "status_counts": dict(
                status_counts
            ),
            "severity_counts": dict(
                severity_counts
            ),
        }


_STATUS_ALIASES = {
    "active": "active",
    "issued": "active",
    "in force": "active",
    "in-force": "active",
    "cancelled": "cancelled",
    "canceled": "cancelled",
    "terminated": "cancelled",
    "inactive": "cancelled",
    "pending": "pending",
    "pending issue": "pending",
    "not issued": "not_issued",
    "declined": "not_issued",
    "lapsed": "lapsed",
    "pending lapse": "pending_lapse",
    "trumped": "trumped",
}


def _normalize_text(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    normalized = unicodedata.normalize(
        "NFKD",
        value,
    )

    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(
            character
        )
    )

    normalized = normalized.casefold()

    normalized = re.sub(
        r"[^a-z0-9]+",
        " ",
        normalized,
    )

    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    ).strip()

    return normalized or None


def _normalize_identifier(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    normalized = re.sub(
        r"[^A-Z0-9]",
        "",
        value.upper(),
    )

    return normalized or None


def _normalize_status(
    value: str | None,
) -> str | None:
    normalized = _normalize_text(
        value
    )

    if normalized is None:
        return None

    return _STATUS_ALIASES.get(
        normalized,
        normalized.replace(
            " ",
            "_",
        ),
    )


def _normalize_date_value(
    value: date | datetime | str | None,
) -> str | None:
    if value is None:
        return None

    if isinstance(
        value,
        datetime,
    ):
        return value.date().isoformat()

    if isinstance(
        value,
        date,
    ):
        return value.isoformat()

    normalized = value.strip()

    if not normalized:
        return None

    try:
        return date.fromisoformat(
            normalized
        ).isoformat()
    except ValueError:
        pass

    supported_formats = (
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%m/%d/%y",
        "%m-%d-%y",
        "%B %d, %Y",
        "%B %d %Y",
        "%b %d, %Y",
        "%b %d %Y",
    )

    for date_format in supported_formats:
        try:
            return datetime.strptime(
                normalized,
                date_format,
            ).date().isoformat()
        except ValueError:
            continue

    return normalized


def _normalize_money_value(
    value: Decimal | float | int | str | None,
) -> Decimal | None:
    if value is None:
        return None

    if isinstance(
        value,
        Decimal,
    ):
        return value.quantize(
            Decimal("0.01")
        )

    normalized = str(
        value
    ).strip()

    if not normalized:
        return None

    is_negative = (
        normalized.startswith("(")
        and normalized.endswith(")")
    )

    normalized = normalized.replace(
        "USD",
        "",
    )

    normalized = normalized.replace(
        "usd",
        "",
    )

    normalized = normalized.replace(
        "$",
        "",
    )

    normalized = normalized.replace(
        ",",
        "",
    )

    normalized = normalized.strip(
        " ()"
    )

    try:
        amount = Decimal(
            normalized
        )
    except InvalidOperation:
        return None

    if is_negative:
        amount = -abs(
            amount
        )

    return amount.quantize(
        Decimal("0.01")
    )


def _field_source_values(
    field: ExtractedPolicyField,
) -> dict[str, Any]:
    return {
        "source_text": field.source_text,
        "source_page_number": (
            field.page_number
        ),
        "confidence_score": (
            field.confidence_score
        ),
    }


def _build_result(
    *,
    rule_code: str,
    finding_type: str,
    field_name: str | None,
    status: str,
    severity: str,
    expected_value: Any | None,
    actual_value: Any | None,
    message: str,
    policy_id: UUID | None,
    field: ExtractedPolicyField | None = None,
    evidence_data: dict[str, Any] | None = None,
) -> ReconciliationRuleResult:
    source_values = (
        _field_source_values(
            field
        )
        if field is not None
        else {
            "source_text": None,
            "source_page_number": None,
            "confidence_score": None,
        }
    )

    return ReconciliationRuleResult(
        rule_code=rule_code,
        finding_type=finding_type,
        field_name=field_name,
        status=status,
        severity=severity,
        expected_value=expected_value,
        actual_value=actual_value,
        message=message,
        business_policy_id=policy_id,
        source_text=source_values[
            "source_text"
        ],
        source_page_number=source_values[
            "source_page_number"
        ],
        confidence_score=source_values[
            "confidence_score"
        ],
        evidence_data=evidence_data or {},
    )


def _compare_text_field(
    *,
    rule_code: str,
    finding_type: str,
    field_name: str,
    label: str,
    expected_value: str | None,
    field: ExtractedPolicyField,
    policy_id: UUID,
    severity: str,
    required: bool,
) -> ReconciliationRuleResult:
    actual_value = (
        str(field.value)
        if field.value is not None
        else None
    )

    normalized_expected = _normalize_text(
        expected_value
    )

    normalized_actual = _normalize_text(
        actual_value
    )

    if (
        normalized_expected is None
        and normalized_actual is None
    ):
        status = (
            "needs_review"
            if required
            else "skipped"
        )

        return _build_result(
            rule_code=rule_code,
            finding_type=finding_type,
            field_name=field_name,
            status=status,
            severity=(
                severity
                if required
                else "info"
            ),
            expected_value=expected_value,
            actual_value=actual_value,
            message=(
                f"{label} is unavailable in both "
                "the document and database."
            ),
            policy_id=policy_id,
            field=field,
        )

    if normalized_expected is None:
        return _build_result(
            rule_code=rule_code,
            finding_type=finding_type,
            field_name=field_name,
            status="needs_review",
            severity=severity,
            expected_value=expected_value,
            actual_value=actual_value,
            message=(
                f"The document contains {label}, "
                "but the database value is missing."
            ),
            policy_id=policy_id,
            field=field,
        )

    if normalized_actual is None:
        return _build_result(
            rule_code=rule_code,
            finding_type=finding_type,
            field_name=field_name,
            status="needs_review",
            severity=severity,
            expected_value=expected_value,
            actual_value=actual_value,
            message=(
                f"The document does not contain "
                f"a usable {label} value."
            ),
            policy_id=policy_id,
            field=field,
        )

    if normalized_expected == normalized_actual:
        return _build_result(
            rule_code=rule_code,
            finding_type=finding_type,
            field_name=field_name,
            status="passed",
            severity="info",
            expected_value=expected_value,
            actual_value=actual_value,
            message=(
                f"{label} matches the database."
            ),
            policy_id=policy_id,
            field=field,
        )

    return _build_result(
        rule_code=rule_code,
        finding_type=finding_type,
        field_name=field_name,
        status="failed",
        severity=severity,
        expected_value=expected_value,
        actual_value=actual_value,
        message=(
            f"{label} differs between the "
            "document and database."
        ),
        policy_id=policy_id,
        field=field,
        evidence_data={
            "normalized_expected": (
                normalized_expected
            ),
            "normalized_actual": (
                normalized_actual
            ),
        },
    )


def _compare_date_field(
    *,
    rule_code: str,
    finding_type: str,
    field_name: str,
    label: str,
    expected_value: date | datetime | str | None,
    field: ExtractedPolicyField,
    policy_id: UUID,
    severity: str,
    required: bool,
) -> ReconciliationRuleResult:
    actual_value = (
        str(field.value)
        if field.value is not None
        else None
    )

    normalized_expected = _normalize_date_value(
        expected_value
    )

    normalized_actual = _normalize_date_value(
        actual_value
    )

    if (
        normalized_expected is None
        and normalized_actual is None
    ):
        return _build_result(
            rule_code=rule_code,
            finding_type=finding_type,
            field_name=field_name,
            status=(
                "needs_review"
                if required
                else "skipped"
            ),
            severity=(
                severity
                if required
                else "info"
            ),
            expected_value=normalized_expected,
            actual_value=normalized_actual,
            message=(
                f"{label} is unavailable in both "
                "the document and database."
            ),
            policy_id=policy_id,
            field=field,
        )

    if normalized_expected is None:
        return _build_result(
            rule_code=rule_code,
            finding_type=finding_type,
            field_name=field_name,
            status="needs_review",
            severity=severity,
            expected_value=normalized_expected,
            actual_value=normalized_actual,
            message=(
                f"The database does not contain "
                f"a usable {label}."
            ),
            policy_id=policy_id,
            field=field,
        )

    if normalized_actual is None:
        return _build_result(
            rule_code=rule_code,
            finding_type=finding_type,
            field_name=field_name,
            status="needs_review",
            severity=severity,
            expected_value=normalized_expected,
            actual_value=normalized_actual,
            message=(
                f"The document does not contain "
                f"a usable {label}."
            ),
            policy_id=policy_id,
            field=field,
        )

    if normalized_expected == normalized_actual:
        return _build_result(
            rule_code=rule_code,
            finding_type=finding_type,
            field_name=field_name,
            status="passed",
            severity="info",
            expected_value=normalized_expected,
            actual_value=normalized_actual,
            message=(
                f"{label} matches the database."
            ),
            policy_id=policy_id,
            field=field,
        )

    return _build_result(
        rule_code=rule_code,
        finding_type=finding_type,
        field_name=field_name,
        status="failed",
        severity=severity,
        expected_value=normalized_expected,
        actual_value=normalized_actual,
        message=(
            f"{label} differs between the "
            "document and database."
        ),
        policy_id=policy_id,
        field=field,
    )


def _compare_premium(
    *,
    expected_value: Decimal | float | int | str | None,
    field: ExtractedPolicyField,
    policy_id: UUID,
    premium_tolerance: Decimal,
) -> ReconciliationRuleResult:
    normalized_expected = _normalize_money_value(
        expected_value
    )

    normalized_actual = _normalize_money_value(
        field.value
        if field.value is not None
        else None
    )

    serialized_expected = (
        format(
            normalized_expected,
            ".2f",
        )
        if normalized_expected is not None
        else None
    )

    serialized_actual = (
        format(
            normalized_actual,
            ".2f",
        )
        if normalized_actual is not None
        else None
    )

    if normalized_expected is None:
        return _build_result(
            rule_code="REC009",
            finding_type="premium_missing_database",
            field_name="premium",
            status="needs_review",
            severity="high",
            expected_value=serialized_expected,
            actual_value=serialized_actual,
            message=(
                "The database premium is missing "
                "or invalid."
            ),
            policy_id=policy_id,
            field=field,
        )

    if normalized_actual is None:
        return _build_result(
            rule_code="REC009",
            finding_type="premium_missing_document",
            field_name="premium",
            status="needs_review",
            severity="high",
            expected_value=serialized_expected,
            actual_value=serialized_actual,
            message=(
                "The document premium is missing "
                "or invalid."
            ),
            policy_id=policy_id,
            field=field,
        )

    difference = abs(
        normalized_expected
        - normalized_actual
    )

    serialized_difference = format(
        difference,
        ".2f",
    )

    if difference <= premium_tolerance:
        return _build_result(
            rule_code="REC009",
            finding_type="premium_match",
            field_name="premium",
            status="passed",
            severity="info",
            expected_value=serialized_expected,
            actual_value=serialized_actual,
            message=(
                "Premium matches within the "
                "configured tolerance."
            ),
            policy_id=policy_id,
            field=field,
            evidence_data={
                "difference": (
                    serialized_difference
                ),
                "tolerance": format(
                    premium_tolerance,
                    ".2f",
                ),
            },
        )

    return _build_result(
        rule_code="REC009",
        finding_type="premium_mismatch",
        field_name="premium",
        status="failed",
        severity="high",
        expected_value=serialized_expected,
        actual_value=serialized_actual,
        message=(
            "Premium differs by more than the "
            "configured tolerance."
        ),
        policy_id=policy_id,
        field=field,
        evidence_data={
            "difference": serialized_difference,
            "tolerance": format(
                premium_tolerance,
                ".2f",
            ),
        },
    )


def _evaluate_extraction_confidence(
    extraction: PolicyDocumentExtraction,
    *,
    minimum_confidence: float,
) -> ReconciliationRuleResult:
    low_confidence_fields = [
        field.name
        for field in extraction.fields.values()
        if (
            field.found
            and field.confidence_score
            is not None
            and field.confidence_score
            < minimum_confidence
        )
    ]

    if (
        extraction.document_confidence
        >= minimum_confidence
        and not low_confidence_fields
    ):
        return _build_result(
            rule_code="REC012",
            finding_type="extraction_confidence",
            field_name=None,
            status="passed",
            severity="info",
            expected_value=minimum_confidence,
            actual_value=(
                extraction.document_confidence
            ),
            message=(
                "Document extraction confidence "
                "meets the required threshold."
            ),
            policy_id=None,
            evidence_data={
                "low_confidence_fields": [],
            },
        )

    return _build_result(
        rule_code="REC012",
        finding_type="low_extraction_confidence",
        field_name=None,
        status="needs_review",
        severity="medium",
        expected_value=minimum_confidence,
        actual_value=(
            extraction.document_confidence
        ),
        message=(
            "Document extraction confidence is "
            "below the required threshold."
        ),
        policy_id=None,
        evidence_data={
            "low_confidence_fields": (
                low_confidence_fields
            ),
            "extraction_warnings": list(
                extraction.warnings
            ),
        },
    )


def _evaluate_signature(
    *,
    expected_value: date | datetime | str | None,
    field: ExtractedPolicyField,
    policy_id: UUID,
) -> ReconciliationRuleResult:
    normalized_expected = _normalize_date_value(
        expected_value
    )

    normalized_actual = _normalize_date_value(
        str(field.value)
        if field.value is not None
        else None
    )

    if normalized_actual is None:
        return _build_result(
            rule_code="REC008",
            finding_type="missing_signature",
            field_name="signature_date",
            status="needs_review",
            severity="high",
            expected_value=normalized_expected,
            actual_value=None,
            message=(
                "The document does not contain "
                "a valid signature date."
            ),
            policy_id=policy_id,
            field=field,
        )

    if normalized_expected is None:
        return _build_result(
            rule_code="REC008",
            finding_type="signature_present",
            field_name="signature_date",
            status="passed",
            severity="info",
            expected_value=True,
            actual_value=normalized_actual,
            message=(
                "The document contains a valid "
                "signature date."
            ),
            policy_id=policy_id,
            field=field,
            evidence_data={
                "database_signature_date_tracked": False,
            },
        )

    if normalized_expected == normalized_actual:
        return _build_result(
            rule_code="REC008",
            finding_type="signature_date_match",
            field_name="signature_date",
            status="passed",
            severity="info",
            expected_value=normalized_expected,
            actual_value=normalized_actual,
            message=(
                "Signature date matches the database."
            ),
            policy_id=policy_id,
            field=field,
        )

    return _build_result(
        rule_code="REC008",
        finding_type="signature_date_mismatch",
        field_name="signature_date",
        status="failed",
        severity="high",
        expected_value=normalized_expected,
        actual_value=normalized_actual,
        message=(
            "Signature date differs between the "
            "document and database."
        ),
        policy_id=policy_id,
        field=field,
    )


def _evaluate_payment_presence(
    *,
    policy: PolicyDatabaseRecord,
    exclude_cancelled: bool,
) -> ReconciliationRuleResult:
    normalized_status = _normalize_status(
        policy.policy_status
    )

    if (
        exclude_cancelled
        and normalized_status == "cancelled"
    ):
        return _build_result(
            rule_code="REC011",
            finding_type="payment_presence",
            field_name=None,
            status="skipped",
            severity="info",
            expected_value=True,
            actual_value=policy.has_payment,
            message=(
                "Payment validation was skipped "
                "because the policy is cancelled."
            ),
            policy_id=policy.policy_id,
            evidence_data={
                "policy_status": (
                    normalized_status
                ),
            },
        )

    if policy.has_payment is None:
        return _build_result(
            rule_code="REC011",
            finding_type="payment_presence_unknown",
            field_name=None,
            status="needs_review",
            severity="medium",
            expected_value=True,
            actual_value=None,
            message=(
                "Payment availability could not "
                "be determined."
            ),
            policy_id=policy.policy_id,
            evidence_data={
                "policy_status": (
                    normalized_status
                ),
            },
        )

    if policy.has_payment:
        return _build_result(
            rule_code="REC011",
            finding_type="payment_presence",
            field_name=None,
            status="passed",
            severity="info",
            expected_value=True,
            actual_value=True,
            message=(
                "The policy has at least one "
                "associated payment."
            ),
            policy_id=policy.policy_id,
            evidence_data={
                "policy_status": (
                    normalized_status
                ),
            },
        )

    severity = (
        "high"
        if normalized_status == "active"
        else "medium"
    )

    return _build_result(
        rule_code="REC011",
        finding_type="missing_payment",
        field_name=None,
        status="failed",
        severity=severity,
        expected_value=True,
        actual_value=False,
        message=(
            "The policy does not have an "
            "associated payment."
        ),
        policy_id=policy.policy_id,
        evidence_data={
            "policy_status": (
                normalized_status
            ),
        },
    )


def evaluate_policy_reconciliation(
    extraction: PolicyDocumentExtraction,
    policy: PolicyDatabaseRecord | None,
    *,
    minimum_confidence: float = 0.75,
    premium_tolerance: Decimal = Decimal(
        "0.01"
    ),
    exclude_cancelled: bool = True,
) -> ReconciliationEvaluation:
    """
    Compare one extracted policy document with one database policy.

    The function is deterministic and side-effect free. It does not
    perform database queries or persist findings.
    """

    if not (
        0
        <= minimum_confidence
        <= 1
    ):
        raise ValueError(
            "minimum_confidence must be "
            "between 0 and 1."
        )

    normalized_tolerance = (
        _normalize_money_value(
            premium_tolerance
        )
    )

    if (
        normalized_tolerance is None
        or normalized_tolerance < 0
    ):
        raise ValueError(
            "premium_tolerance must be "
            "a non-negative monetary value."
        )

    results: list[
        ReconciliationRuleResult
    ] = [
        _evaluate_extraction_confidence(
            extraction,
            minimum_confidence=(
                minimum_confidence
            ),
        )
    ]

    policy_number_field = (
        extraction.get_field(
            "policy_number"
        )
    )

    extracted_policy_number = (
        str(policy_number_field.value)
        if policy_number_field.value
        is not None
        else None
    )

    if policy is None:
        results.append(
            _build_result(
                rule_code="REC001",
                finding_type="unmatched_policy",
                field_name="policy_number",
                status="failed",
                severity="high",
                expected_value=(
                    "Existing policy record"
                ),
                actual_value=(
                    extracted_policy_number
                ),
                message=(
                    "No database policy matched "
                    "the extracted policy number."
                ),
                policy_id=None,
                field=policy_number_field,
            )
        )

        return ReconciliationEvaluation(
            results=tuple(
                results
            ),
            matched_policy_id=None,
        )

    expected_policy_number = (
        _normalize_identifier(
            policy.policy_number
        )
    )

    actual_policy_number = (
        _normalize_identifier(
            extracted_policy_number
        )
    )

    policy_number_matches = (
        expected_policy_number
        is not None
        and actual_policy_number
        is not None
        and expected_policy_number
        == actual_policy_number
    )

    results.append(
        _build_result(
            rule_code="REC001",
            finding_type=(
                "policy_match"
                if policy_number_matches
                else "policy_number_mismatch"
            ),
            field_name="policy_number",
            status=(
                "passed"
                if policy_number_matches
                else "failed"
            ),
            severity=(
                "info"
                if policy_number_matches
                else "high"
            ),
            expected_value=(
                policy.policy_number
            ),
            actual_value=(
                extracted_policy_number
            ),
            message=(
                "Policy number matches the database."
                if policy_number_matches
                else (
                    "Policy number differs between "
                    "the document and database."
                )
            ),
            policy_id=policy.policy_id,
            field=policy_number_field,
        )
    )

    duplicate_detected = (
        policy.duplicate_policy_count
        > 1
    )

    results.append(
        _build_result(
            rule_code="REC002",
            finding_type=(
                "duplicate_policy_number"
                if duplicate_detected
                else "unique_policy_number"
            ),
            field_name="policy_number",
            status=(
                "needs_review"
                if duplicate_detected
                else "passed"
            ),
            severity=(
                "high"
                if duplicate_detected
                else "info"
            ),
            expected_value=1,
            actual_value=(
                policy.duplicate_policy_count
            ),
            message=(
                (
                    "Multiple database policies "
                    "share this policy number."
                )
                if duplicate_detected
                else (
                    "The policy number identifies "
                    "one database record."
                )
            ),
            policy_id=policy.policy_id,
            field=policy_number_field,
        )
    )

    results.append(
        _compare_text_field(
            rule_code="REC003",
            finding_type="customer_name",
            field_name="customer_name",
            label="Customer name",
            expected_value=(
                policy.customer_name
            ),
            field=extraction.get_field(
                "customer_name"
            ),
            policy_id=policy.policy_id,
            severity="high",
            required=True,
        )
    )

    results.append(
        _compare_text_field(
            rule_code="REC004",
            finding_type="carrier_name",
            field_name="carrier_name",
            label="Carrier name",
            expected_value=(
                policy.carrier_name
            ),
            field=extraction.get_field(
                "carrier_name"
            ),
            policy_id=policy.policy_id,
            severity="medium",
            required=False,
        )
    )

    results.append(
        _compare_text_field(
            rule_code="REC005",
            finding_type="plan_name",
            field_name="plan_name",
            label="Plan name",
            expected_value=(
                policy.plan_name
            ),
            field=extraction.get_field(
                "plan_name"
            ),
            policy_id=policy.policy_id,
            severity="medium",
            required=False,
        )
    )

    results.append(
        _compare_date_field(
            rule_code="REC006",
            finding_type="effective_date",
            field_name="effective_date",
            label="Effective date",
            expected_value=(
                policy.effective_date
            ),
            field=extraction.get_field(
                "effective_date"
            ),
            policy_id=policy.policy_id,
            severity="high",
            required=True,
        )
    )

    results.append(
        _compare_date_field(
            rule_code="REC007",
            finding_type="termination_date",
            field_name="termination_date",
            label="Termination date",
            expected_value=(
                policy.termination_date
            ),
            field=extraction.get_field(
                "termination_date"
            ),
            policy_id=policy.policy_id,
            severity="medium",
            required=False,
        )
    )

    results.append(
        _evaluate_signature(
            expected_value=(
                policy.signature_date
            ),
            field=extraction.get_field(
                "signature_date"
            ),
            policy_id=policy.policy_id,
        )
    )

    results.append(
        _compare_premium(
            expected_value=(
                policy.premium
            ),
            field=extraction.get_field(
                "premium"
            ),
            policy_id=policy.policy_id,
            premium_tolerance=(
                normalized_tolerance
            ),
        )
    )

    results.append(
        _compare_text_field(
            rule_code="REC010",
            finding_type="policy_status",
            field_name="policy_status",
            label="Policy status",
            expected_value=(
                _normalize_status(
                    policy.policy_status
                )
            ),
            field=extraction.get_field(
                "policy_status"
            ),
            policy_id=policy.policy_id,
            severity="medium",
            required=False,
        )
    )

    results.append(
        _evaluate_payment_presence(
            policy=policy,
            exclude_cancelled=(
                exclude_cancelled
            ),
        )
    )

    return ReconciliationEvaluation(
        results=tuple(
            results
        ),
        matched_policy_id=(
            policy.policy_id
        ),
    )