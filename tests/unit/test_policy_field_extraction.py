from __future__ import annotations

import pytest

from apps.api.app.services.policy_field_extraction import (
    PolicySourcePage,
    extract_policy_fields,
    get_policy_field_names,
)


def test_extracts_complete_policy_document() -> None:
    page = PolicySourcePage(
        page_number=1,
        confidence_score=0.98,
        text="""
        Policy Number: POL-2026-0001
        Policyholder Name: Jane Doe
        Carrier: Aetna
        Plan Name: Aetna Gold PPO
        Effective Date: January 1, 2026
        Termination Date: 12/31/2026
        Signature Date: 12/15/2025
        Premium Amount: $1,250.50
        Policy Status: Active
        """,
    )

    result = extract_policy_fields(
        [page]
    )

    assert (
        result.get_value(
            "policy_number"
        )
        == "POL-2026-0001"
    )

    assert (
        result.get_value(
            "customer_name"
        )
        == "Jane Doe"
    )

    assert (
        result.get_value(
            "carrier_name"
        )
        == "Aetna"
    )

    assert (
        result.get_value(
            "plan_name"
        )
        == "Aetna Gold PPO"
    )

    assert (
        result.get_value(
            "effective_date"
        )
        == "2026-01-01"
    )

    assert (
        result.get_value(
            "termination_date"
        )
        == "2026-12-31"
    )

    assert (
        result.get_value(
            "signature_date"
        )
        == "2025-12-15"
    )

    assert (
        result.get_value(
            "premium"
        )
        == "1250.50"
    )

    assert (
        result.get_value(
            "policy_status"
        )
        == "active"
    )

    assert result.page_count == 1

    assert (
        result.document_confidence
        > 0.90
    )


def test_extracts_value_from_next_line() -> None:
    page = PolicySourcePage(
        page_number=1,
        confidence_score=0.95,
        text="""
        Policy Number:
        POL-2026-0042

        Policyholder Name:
        John Smith

        Effective Date:
        02/01/2026

        Premium:
        $875.00
        """,
    )

    result = extract_policy_fields(
        [page]
    )

    policy_number = result.get_field(
        "policy_number"
    )

    assert (
        policy_number.value
        == "POL-2026-0042"
    )

    assert (
        policy_number.extraction_method
        == "labeled_next_line"
    )

    assert (
        result.get_value(
            "customer_name"
        )
        == "John Smith"
    )

    assert (
        result.get_value(
            "effective_date"
        )
        == "2026-02-01"
    )

    assert (
        result.get_value(
            "premium"
        )
        == "875.00"
    )


@pytest.mark.parametrize(
    (
        "raw_date",
        "expected_date",
    ),
    [
        (
            "2026-03-14",
            "2026-03-14",
        ),
        (
            "03/14/2026",
            "2026-03-14",
        ),
        (
            "March 14, 2026",
            "2026-03-14",
        ),
        (
            "Mar 14 2026",
            "2026-03-14",
        ),
        (
            "14 March 2026",
            "2026-03-14",
        ),
    ],
)
def test_normalizes_supported_dates(
    raw_date: str,
    expected_date: str,
) -> None:
    page = PolicySourcePage(
        page_number=1,
        text=f"""
        Policy Number: POL-2026-0100
        Policyholder Name: Date Test
        Effective Date: {raw_date}
        Premium: $100.00
        """,
    )

    result = extract_policy_fields(
        [page]
    )

    assert (
        result.get_value(
            "effective_date"
        )
        == expected_date
    )


@pytest.mark.parametrize(
    (
        "raw_value",
        "expected_value",
    ),
    [
        (
            "$1,250",
            "1250.00",
        ),
        (
            "USD 99.5",
            "99.50",
        ),
        (
            "$0.00",
            "0.00",
        ),
        (
            "($25.75)",
            "-25.75",
        ),
    ],
)
def test_normalizes_money_values(
    raw_value: str,
    expected_value: str,
) -> None:
    page = PolicySourcePage(
        page_number=1,
        text=f"""
        Policy Number: POL-2026-0110
        Policyholder Name: Money Test
        Effective Date: 01/01/2026
        Premium Amount: {raw_value}
        """,
    )

    result = extract_policy_fields(
        [page]
    )

    assert (
        result.get_value(
            "premium"
        )
        == expected_value
    )


@pytest.mark.parametrize(
    (
        "raw_status",
        "expected_status",
    ),
    [
        (
            "Active",
            "active",
        ),
        (
            "In Force",
            "active",
        ),
        (
            "Canceled",
            "cancelled",
        ),
        (
            "Not Issued",
            "not_issued",
        ),
        (
            "Pending Lapse",
            "pending_lapse",
        ),
        (
            "Trumped",
            "trumped",
        ),
    ],
)
def test_normalizes_policy_status(
    raw_status: str,
    expected_status: str,
) -> None:
    page = PolicySourcePage(
        page_number=1,
        text=f"""
        Policy Number: POL-2026-0200
        Policyholder Name: Status Test
        Effective Date: 01/01/2026
        Premium: $100
        Policy Status: {raw_status}
        """,
    )

    result = extract_policy_fields(
        [page]
    )

    assert (
        result.get_value(
            "policy_status"
        )
        == expected_status
    )


def test_selects_highest_confidence_candidate() -> None:
    pages = [
        PolicySourcePage(
            page_number=1,
            confidence_score=0.60,
            text="""
            Policy Number: POL-LOW-001
            Policyholder Name: Conflict Test
            Effective Date: 01/01/2026
            Premium: $100
            """,
        ),
        PolicySourcePage(
            page_number=2,
            confidence_score=0.97,
            text="""
            Policy Number: POL-HIGH-002
            """,
        ),
    ]

    result = extract_policy_fields(
        pages
    )

    assert (
        result.get_value(
            "policy_number"
        )
        == "POL-HIGH-002"
    )

    assert any(
        (
            "Conflicting values found "
            "for policy_number"
        )
        in warning
        for warning in result.warnings
    )


def test_adds_low_confidence_warning() -> None:
    page = PolicySourcePage(
        page_number=1,
        confidence_score=0.51,
        text="""
        Policy Number: POL-2026-0300
        Policyholder Name: OCR Test
        Effective Date: 01/01/2026
        Premium: $100
        """,
    )

    result = extract_policy_fields(
        [page],
        minimum_confidence=0.75,
    )

    assert any(
        (
            "Low-confidence extraction "
            "for policy_number"
        )
        in warning
        for warning in result.warnings
    )


def test_reports_missing_required_fields() -> None:
    result = extract_policy_fields(
        [
            PolicySourcePage(
                page_number=1,
                text=(
                    "Carrier: Aetna\n"
                    "Plan Name: Silver PPO"
                ),
            )
        ]
    )

    assert (
        result.get_field(
            "policy_number"
        ).found
        is False
    )

    assert (
        result.get_field(
            "customer_name"
        ).found
        is False
    )

    assert any(
        (
            "Required field "
            "policy_number "
            "was not found."
        )
        == warning
        for warning in result.warnings
    )

    assert any(
        (
            "Required field "
            "premium "
            "was not found."
        )
        == warning
        for warning in result.warnings
    )


def test_reports_invalid_labeled_value() -> None:
    page = PolicySourcePage(
        page_number=1,
        text="""
        Policy Number: POL-2026-0400
        Policyholder Name: Invalid Date
        Effective Date: unknown
        Premium: $100.00
        """,
    )

    result = extract_policy_fields(
        [page]
    )

    assert (
        result.get_value(
            "effective_date"
        )
        is None
    )

    assert any(
        (
            "Could not normalize "
            "effective_date value"
        )
        in warning
        for warning in result.warnings
    )


def test_uses_policy_number_fallback() -> None:
    page = PolicySourcePage(
        page_number=1,
        confidence_score=0.90,
        text="""
        INSURANCE POLICY DECLARATION

        POL-2026-0500

        Policyholder Name: Fallback Test
        Effective Date: 01/01/2026
        Premium: $250
        """,
    )

    result = extract_policy_fields(
        [page]
    )

    field = result.get_field(
        "policy_number"
    )

    assert (
        field.value
        == "POL-2026-0500"
    )

    assert (
        field.extraction_method
        == "fallback_pattern"
    )


def test_serializes_extraction_to_dictionary() -> None:
    result = extract_policy_fields(
        [
            PolicySourcePage(
                page_number=1,
                text="""
                Policy Number: POL-2026-0600
                Policyholder Name: JSON Test
                Effective Date: 01/01/2026
                Premium: $500
                """,
            )
        ]
    )

    payload = result.to_dict()

    assert (
        payload["fields"][
            "policy_number"
        ]["value"]
        == "POL-2026-0600"
    )

    assert payload["page_count"] == 1

    assert isinstance(
        payload["warnings"],
        list,
    )


def test_returns_expected_field_names() -> None:
    assert get_policy_field_names() == (
        "policy_number",
        "customer_name",
        "carrier_name",
        "plan_name",
        "effective_date",
        "termination_date",
        "signature_date",
        "premium",
        "policy_status",
    )


def test_rejects_invalid_page_number() -> None:
    with pytest.raises(
        ValueError,
        match="page_number",
    ):
        PolicySourcePage(
            page_number=0,
            text="Invalid page",
        )


def test_rejects_invalid_page_confidence() -> None:
    with pytest.raises(
        ValueError,
        match="confidence_score",
    ):
        PolicySourcePage(
            page_number=1,
            text="Invalid confidence",
            confidence_score=1.5,
        )


def test_rejects_invalid_minimum_confidence() -> None:
    with pytest.raises(
        ValueError,
        match="minimum_confidence",
    ):
        extract_policy_fields(
            [],
            minimum_confidence=1.5,
        )