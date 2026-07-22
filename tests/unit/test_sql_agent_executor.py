from __future__ import annotations

from datetime import (
    date,
    datetime,
    time,
    timezone,
)
from decimal import Decimal
from uuid import uuid4

import pytest

from apps.api.app.services.sql_agent_executor import (
    InvalidSQLAgentTimeoutError,
    resolve_statement_timeout_ms,
    serialize_sql_row,
    serialize_sql_value,
)


def test_primitive_values_are_serialized() -> None:
    assert serialize_sql_value(
        None
    ) is None

    assert serialize_sql_value(
        True
    ) is True

    assert serialize_sql_value(
        15
    ) == 15

    assert serialize_sql_value(
        12.5
    ) == 12.5

    assert serialize_sql_value(
        "active"
    ) == "active"


def test_decimal_is_serialized_as_string() -> None:
    assert serialize_sql_value(
        Decimal("1250.75")
    ) == "1250.75"


def test_date_and_time_values_are_serialized() -> None:
    timestamp = datetime(
        2026,
        7,
        22,
        12,
        30,
        45,
        tzinfo=timezone.utc,
    )

    assert serialize_sql_value(
        timestamp
    ) == "2026-07-22T12:30:45+00:00"

    assert serialize_sql_value(
        date(2026, 7, 22)
    ) == "2026-07-22"

    assert serialize_sql_value(
        time(12, 30, 45)
    ) == "12:30:45"


def test_uuid_is_serialized_as_string() -> None:
    identifier = uuid4()

    assert serialize_sql_value(
        identifier
    ) == str(identifier)


def test_binary_values_are_serialized_as_hex() -> None:
    assert serialize_sql_value(
        b"\x01\x02"
    ) == "0102"

    assert serialize_sql_value(
        memoryview(b"\x0a\x0b")
    ) == "0a0b"


def test_nested_values_are_serialized() -> None:
    identifier = uuid4()

    result = serialize_sql_value(
        {
            "identifier": identifier,
            "amounts": [
                Decimal("15.25"),
                Decimal("20.00"),
            ],
            "active": True,
        }
    )

    assert result == {
        "identifier": str(identifier),
        "amounts": [
            "15.25",
            "20.00",
        ],
        "active": True,
    }


def test_row_is_serialized() -> None:
    identifier = uuid4()

    row = serialize_sql_row(
        {
            "id": identifier,
            "premium": Decimal(
                "249.99"
            ),
            "effective_date": date(
                2026,
                1,
                1,
            ),
        }
    )

    assert row == {
        "id": str(identifier),
        "premium": "249.99",
        "effective_date": "2026-01-01",
    }


def test_non_finite_float_is_serialized_as_string() -> None:
    assert serialize_sql_value(
        float("nan")
    ) == "nan"

    assert serialize_sql_value(
        float("inf")
    ) == "inf"


def test_statement_timeout_is_validated() -> None:
    assert (
        resolve_statement_timeout_ms(
            5_000
        )
        == 5_000
    )


@pytest.mark.parametrize(
    "timeout_ms",
    [
        0,
        50,
        99,
        60_001,
        100_000,
    ],
)
def test_invalid_statement_timeout_is_rejected(
    timeout_ms: int,
) -> None:
    with pytest.raises(
        InvalidSQLAgentTimeoutError,
    ):
        resolve_statement_timeout_ms(
            timeout_ms
        )