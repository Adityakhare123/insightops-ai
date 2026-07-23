from __future__ import annotations

import csv
from datetime import datetime, timezone
from io import BytesIO, StringIO
from uuid import uuid4
from zipfile import ZipFile

import pytest

from apps.api.app.services.reconciliation_reports import (
    ReconciliationReportData,
    build_reconciliation_csv,
    build_reconciliation_xlsx,
    build_report_filename,
    generate_reconciliation_report,
)


def build_report_data() -> (
    ReconciliationReportData
):
    run_id = uuid4()
    finding_id = uuid4()
    task_id = uuid4()

    created_at = datetime(
        2026,
        7,
        23,
        12,
        0,
        tzinfo=timezone.utc,
    )

    return ReconciliationReportData(
        run={
            "id": run_id,
            "workspace_id": uuid4(),
            "document_id": uuid4(),
            "processing_run_id": uuid4(),
            "requested_by_user_id":
                uuid4(),
            "reconciliation_type":
                "policy_document",
            "status": "needs_review",
            "exclude_cancelled": True,
            "started_at": created_at,
            "completed_at": created_at,
            "total_checks": 2,
            "passed_checks": 1,
            "failed_checks": 1,
            "review_checks": 0,
            "error_message": None,
            "run_parameters": {
                "minimum_confidence":
                    0.75,
                "premium_tolerance":
                    "0.01",
            },
            "summary_data": {
                "document_confidence":
                    0.98,
                "matched_policy_count":
                    1,
            },
            "created_at": created_at,
            "updated_at": created_at,
        },
        document_name=(
            "Policy Declaration.pdf"
        ),
        findings=(
            {
                "id": finding_id,
                "reconciliation_run_id":
                    run_id,
                "document_id": uuid4(),
                "document_page_id":
                    uuid4(),
                "business_policy_id":
                    uuid4(),
                "rule_code": "REC001",
                "finding_type":
                    "policy_match",
                "field_name":
                    "policy_number",
                "status": "passed",
                "severity": "info",
                "expected_value":
                    "POL-2026-0001",
                "actual_value":
                    "POL-2026-0001",
                "message": (
                    "Policy number matches "
                    "the database."
                ),
                "source_text": (
                    "Policy Number: "
                    "POL-2026-0001"
                ),
                "source_page_number": 1,
                "confidence_score": 0.98,
                "evidence_data": {},
                "created_at": created_at,
                "updated_at": created_at,
            },
            {
                "id": uuid4(),
                "reconciliation_run_id":
                    run_id,
                "document_id": uuid4(),
                "document_page_id":
                    uuid4(),
                "business_policy_id":
                    uuid4(),
                "rule_code": "REC006",
                "finding_type":
                    "effective_date",
                "field_name":
                    "effective_date",
                "status": "failed",
                "severity": "high",
                "expected_value":
                    "2026-01-01",
                "actual_value":
                    "2026-01-02",
                "message": (
                    "=HYPERLINK("
                    "\"https://example.com\","
                    "\"Unsafe\")"
                ),
                "source_text": (
                    "Effective Date: "
                    "01/02/2026"
                ),
                "source_page_number": 1,
                "confidence_score": 0.97,
                "evidence_data": {},
                "created_at": created_at,
                "updated_at": created_at,
            },
        ),
        review_tasks=(
            {
                "id": task_id,
                "reconciliation_run_id":
                    run_id,
                "reconciliation_finding_id":
                    finding_id,
                "document_id": uuid4(),
                "created_by_user_id":
                    uuid4(),
                "assigned_to_user_id":
                    uuid4(),
                "resolved_by_user_id":
                    None,
                "status": "open",
                "priority": "high",
                "title":
                    "Effective Date Mismatch",
                "description":
                    "Review the date mismatch.",
                "resolution_notes": None,
                "corrected_value": None,
                "due_at": None,
                "resolved_at": None,
                "extra_metadata": {
                    "rule_code": "REC006",
                },
                "created_at": created_at,
                "updated_at": created_at,
            },
        ),
    )


def test_builds_csv_report() -> None:
    report_data = (
        build_report_data()
    )

    content = build_reconciliation_csv(
        report_data
    )

    decoded_content = content.decode(
        "utf-8-sig"
    )

    rows = list(
        csv.DictReader(
            StringIO(
                decoded_content
            )
        )
    )

    assert len(rows) == 2

    assert (
        rows[0]["rule_code"]
        == "REC001"
    )

    assert (
        rows[1]["rule_code"]
        == "REC006"
    )

    assert (
        rows[0]["document_name"]
        == "Policy Declaration.pdf"
    )


def test_csv_prevents_formula_injection() -> None:
    report_data = (
        build_report_data()
    )

    content = build_reconciliation_csv(
        report_data
    )

    decoded_content = content.decode(
        "utf-8-sig"
    )

    rows = list(
        csv.DictReader(
            StringIO(
                decoded_content
            )
        )
    )

    assert rows[1]["message"].startswith(
        "'=HYPERLINK"
    )


def test_builds_valid_xlsx_workbook() -> None:
    report_data = (
        build_report_data()
    )

    content = build_reconciliation_xlsx(
        report_data
    )

    assert content.startswith(
        b"PK"
    )

    with ZipFile(
        BytesIO(
            content
        )
    ) as workbook_archive:
        workbook_xml = (
            workbook_archive
            .read(
                "xl/workbook.xml"
            )
            .decode(
                "utf-8"
            )
        )

    assert (
        'name="Summary"'
        in workbook_xml
    )

    assert (
        'name="Findings"'
        in workbook_xml
    )

    assert (
        'name="Review Tasks"'
        in workbook_xml
    )


def test_builds_safe_report_filename() -> None:
    report_data = (
        build_report_data()
    )

    filename = build_report_filename(
        report_data,
        report_format="xlsx",
    )

    assert filename.startswith(
        "Policy-Declaration-"
    )

    assert filename.endswith(
        ".xlsx"
    )

    assert " " not in filename


@pytest.mark.parametrize(
    (
        "report_format",
        "expected_media_type",
    ),
    [
        (
            "csv",
            "text/csv; charset=utf-8",
        ),
        (
            "xlsx",
            (
                "application/vnd.openxmlformats-"
                "officedocument.spreadsheetml.sheet"
            ),
        ),
    ],
)
def test_generates_requested_report_format(
    report_format: str,
    expected_media_type: str,
) -> None:
    report = (
        generate_reconciliation_report(
            build_report_data(),
            report_format=report_format,
        )
    )

    assert report.content
    assert (
        report.media_type
        == expected_media_type
    )

    assert report.filename.endswith(
        f".{report_format}"
    )


def test_rejects_unsupported_format() -> None:
    with pytest.raises(
        ValueError,
        match="Unsupported",
    ):
        generate_reconciliation_report(
            build_report_data(),
            report_format="pdf",
        )


class StringIOBytes:
    """
    Minimal BytesIO-compatible wrapper used by ZipFile.
    """

    def __init__(
        self,
        content: bytes,
    ) -> None:
        from io import BytesIO

        self._stream = BytesIO(
            content
        )

    def read(
        self,
        size: int = -1,
    ) -> bytes:
        return self._stream.read(
            size
        )

    def seek(
        self,
        offset: int,
        whence: int = 0,
    ) -> int:
        return self._stream.seek(
            offset,
            whence,
        )

    def tell(self) -> int:
        return self._stream.tell()

    def close(self) -> None:
        self._stream.close()