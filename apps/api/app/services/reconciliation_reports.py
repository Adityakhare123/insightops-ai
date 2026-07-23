from __future__ import annotations

import csv
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

import xlsxwriter
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.db.models.document import (
    Document,
)
from apps.api.app.db.models.reconciliation_finding import (
    ReconciliationFinding,
)
from apps.api.app.db.models.reconciliation_run import (
    ReconciliationRun,
)
from apps.api.app.db.models.review_task import (
    ReviewTask,
)


ReconciliationReportFormat = Literal[
    "csv",
    "xlsx",
]


class ReconciliationReportError(
    RuntimeError
):
    """Base error for reconciliation reports."""


class ReconciliationReportNotFoundError(
    ReconciliationReportError
):
    """Raised when a run is outside the workspace."""


@dataclass(
    frozen=True,
    slots=True,
)
class ReconciliationReportData:
    """
    Workspace-scoped data used to build reconciliation reports.
    """

    run: dict[str, Any]
    document_name: str

    findings: tuple[
        dict[str, Any],
        ...,
    ]

    review_tasks: tuple[
        dict[str, Any],
        ...,
    ]


@dataclass(
    frozen=True,
    slots=True,
)
class GeneratedReconciliationReport:
    """
    Generated downloadable report.
    """

    content: bytes
    filename: str
    media_type: str
    report_format: ReconciliationReportFormat


CSV_COLUMNS = (
    "run_id",
    "document_name",
    "run_status",
    "reconciliation_type",
    "run_created_at",
    "rule_code",
    "finding_type",
    "field_name",
    "finding_status",
    "severity",
    "expected_value",
    "actual_value",
    "message",
    "source_page_number",
    "confidence_score",
    "source_text",
    "business_policy_id",
    "review_task_id",
    "review_status",
    "review_priority",
    "assigned_to_user_id",
    "resolution_notes",
    "corrected_value",
    "resolved_by_user_id",
    "resolved_at",
)


FINDING_COLUMNS = (
    (
        "rule_code",
        "Rule Code",
        12,
    ),
    (
        "finding_type",
        "Finding Type",
        28,
    ),
    (
        "field_name",
        "Field",
        20,
    ),
    (
        "status",
        "Status",
        18,
    ),
    (
        "severity",
        "Severity",
        12,
    ),
    (
        "expected_value",
        "Expected Value",
        22,
    ),
    (
        "actual_value",
        "Actual Value",
        22,
    ),
    (
        "message",
        "Message",
        48,
    ),
    (
        "source_page_number",
        "Source Page",
        12,
    ),
    (
        "confidence_score",
        "Confidence",
        12,
    ),
    (
        "source_text",
        "Source Evidence",
        55,
    ),
    (
        "business_policy_id",
        "Policy ID",
        38,
    ),
    (
        "id",
        "Finding ID",
        38,
    ),
    (
        "created_at",
        "Created At",
        24,
    ),
)


REVIEW_TASK_COLUMNS = (
    (
        "id",
        "Task ID",
        38,
    ),
    (
        "reconciliation_finding_id",
        "Finding ID",
        38,
    ),
    (
        "status",
        "Status",
        16,
    ),
    (
        "priority",
        "Priority",
        12,
    ),
    (
        "title",
        "Title",
        30,
    ),
    (
        "description",
        "Description",
        48,
    ),
    (
        "assigned_to_user_id",
        "Assigned To",
        38,
    ),
    (
        "resolution_notes",
        "Resolution Notes",
        48,
    ),
    (
        "corrected_value",
        "Corrected Value",
        24,
    ),
    (
        "resolved_by_user_id",
        "Resolved By",
        38,
    ),
    (
        "resolved_at",
        "Resolved At",
        24,
    ),
    (
        "created_at",
        "Created At",
        24,
    ),
)


def _serialize_value(
    value: Any,
) -> str:
    if value is None:
        return ""

    if isinstance(
        value,
        bool,
    ):
        return (
            "true"
            if value
            else "false"
        )

    if isinstance(
        value,
        UUID,
    ):
        return str(value)

    if isinstance(
        value,
        datetime,
    ):
        return value.isoformat()

    if isinstance(
        value,
        date,
    ):
        return value.isoformat()

    if isinstance(
        value,
        Decimal,
    ):
        return format(
            value,
            "f",
        )

    if isinstance(
        value,
        (
            dict,
            list,
            tuple,
            set,
        ),
    ):
        return json.dumps(
            value,
            ensure_ascii=False,
            default=str,
            sort_keys=True,
        )

    return str(value)


def _csv_safe_value(
    value: Any,
) -> str:
    """
    Prevent spreadsheet formula injection in exported CSV files.
    """

    serialized = _serialize_value(
        value
    )

    stripped_value = (
        serialized.lstrip()
    )

    if not stripped_value:
        return serialized

    starts_like_formula = (
        stripped_value[0]
        in {
            "=",
            "+",
            "-",
            "@",
        }
    )

    is_numeric_value = bool(
        re.fullmatch(
            r"[+-]?\d+(?:\.\d+)?",
            stripped_value,
        )
    )

    if (
        starts_like_formula
        and not is_numeric_value
    ):
        return (
            "'"
            + serialized
        )

    return serialized


def _run_to_dict(
    run: ReconciliationRun,
) -> dict[str, Any]:
    return {
        "id": run.id,
        "workspace_id":
            run.workspace_id,
        "document_id":
            run.document_id,
        "processing_run_id":
            run.processing_run_id,
        "requested_by_user_id":
            run.requested_by_user_id,
        "reconciliation_type":
            run.reconciliation_type,
        "status":
            run.status,
        "exclude_cancelled":
            run.exclude_cancelled,
        "started_at":
            run.started_at,
        "completed_at":
            run.completed_at,
        "total_checks":
            run.total_checks,
        "passed_checks":
            run.passed_checks,
        "failed_checks":
            run.failed_checks,
        "review_checks":
            run.review_checks,
        "error_message":
            run.error_message,
        "run_parameters":
            run.run_parameters or {},
        "summary_data":
            run.summary_data or {},
        "created_at":
            run.created_at,
        "updated_at":
            run.updated_at,
    }


def _finding_to_dict(
    finding: ReconciliationFinding,
) -> dict[str, Any]:
    return {
        "id": finding.id,
        "reconciliation_run_id":
            finding.reconciliation_run_id,
        "document_id":
            finding.document_id,
        "document_page_id":
            finding.document_page_id,
        "business_policy_id":
            finding.business_policy_id,
        "rule_code":
            finding.rule_code,
        "finding_type":
            finding.finding_type,
        "field_name":
            finding.field_name,
        "status":
            finding.status,
        "severity":
            finding.severity,
        "expected_value":
            finding.expected_value,
        "actual_value":
            finding.actual_value,
        "message":
            finding.message,
        "source_text":
            finding.source_text,
        "source_page_number":
            finding.source_page_number,
        "confidence_score":
            finding.confidence_score,
        "evidence_data":
            finding.evidence_data or {},
        "created_at":
            finding.created_at,
        "updated_at":
            finding.updated_at,
    }


def _review_task_to_dict(
    review_task: ReviewTask,
) -> dict[str, Any]:
    return {
        "id": review_task.id,
        "reconciliation_run_id":
            review_task.reconciliation_run_id,
        "reconciliation_finding_id":
            review_task.reconciliation_finding_id,
        "document_id":
            review_task.document_id,
        "created_by_user_id":
            review_task.created_by_user_id,
        "assigned_to_user_id":
            review_task.assigned_to_user_id,
        "resolved_by_user_id":
            review_task.resolved_by_user_id,
        "status":
            review_task.status,
        "priority":
            review_task.priority,
        "title":
            review_task.title,
        "description":
            review_task.description,
        "resolution_notes":
            review_task.resolution_notes,
        "corrected_value":
            review_task.corrected_value,
        "due_at":
            review_task.due_at,
        "resolved_at":
            review_task.resolved_at,
        "extra_metadata":
            review_task.extra_metadata or {},
        "created_at":
            review_task.created_at,
        "updated_at":
            review_task.updated_at,
    }


def load_reconciliation_report_data(
    database_session: Session,
    *,
    workspace_id: UUID,
    run_id: UUID,
) -> ReconciliationReportData:
    """
    Load a run and its report data inside one workspace.
    """

    reconciliation_run = (
        database_session.scalar(
            select(
                ReconciliationRun
            ).where(
                ReconciliationRun.id
                == run_id,
                ReconciliationRun.workspace_id
                == workspace_id,
            )
        )
    )

    if reconciliation_run is None:
        raise (
            ReconciliationReportNotFoundError(
                "Reconciliation run was not found."
            )
        )

    document_name = (
        database_session.scalar(
            select(
                Document.original_filename
            ).where(
                Document.id
                == reconciliation_run.document_id,
                Document.workspace_id
                == workspace_id,
            )
        )
    )

    findings = list(
        database_session.scalars(
            select(
                ReconciliationFinding
            )
            .where(
                ReconciliationFinding.workspace_id
                == workspace_id,
                ReconciliationFinding
                .reconciliation_run_id
                == run_id,
            )
            .order_by(
                ReconciliationFinding
                .created_at
                .asc(),
                ReconciliationFinding
                .id
                .asc(),
            )
        ).all()
    )

    review_tasks = list(
        database_session.scalars(
            select(
                ReviewTask
            )
            .where(
                ReviewTask.workspace_id
                == workspace_id,
                ReviewTask
                .reconciliation_run_id
                == run_id,
            )
            .order_by(
                ReviewTask
                .created_at
                .asc(),
                ReviewTask.id.asc(),
            )
        ).all()
    )

    return ReconciliationReportData(
        run=_run_to_dict(
            reconciliation_run
        ),
        document_name=(
            document_name
            or "document"
        ),
        findings=tuple(
            _finding_to_dict(
                finding
            )
            for finding in findings
        ),
        review_tasks=tuple(
            _review_task_to_dict(
                review_task
            )
            for review_task
            in review_tasks
        ),
    )


def _build_flat_csv_rows(
    report_data: ReconciliationReportData,
) -> list[dict[str, Any]]:
    run = report_data.run

    review_task_by_finding_id = {
        str(
            review_task[
                "reconciliation_finding_id"
            ]
        ): review_task
        for review_task
        in report_data.review_tasks
    }

    rows: list[
        dict[str, Any]
    ] = []

    for finding in report_data.findings:
        review_task = (
            review_task_by_finding_id.get(
                str(
                    finding["id"]
                )
            )
        )

        rows.append(
            {
                "run_id":
                    run["id"],
                "document_name":
                    report_data.document_name,
                "run_status":
                    run["status"],
                "reconciliation_type":
                    run[
                        "reconciliation_type"
                    ],
                "run_created_at":
                    run["created_at"],
                "rule_code":
                    finding["rule_code"],
                "finding_type":
                    finding["finding_type"],
                "field_name":
                    finding["field_name"],
                "finding_status":
                    finding["status"],
                "severity":
                    finding["severity"],
                "expected_value":
                    finding["expected_value"],
                "actual_value":
                    finding["actual_value"],
                "message":
                    finding["message"],
                "source_page_number":
                    finding[
                        "source_page_number"
                    ],
                "confidence_score":
                    finding[
                        "confidence_score"
                    ],
                "source_text":
                    finding["source_text"],
                "business_policy_id":
                    finding[
                        "business_policy_id"
                    ],
                "review_task_id": (
                    review_task["id"]
                    if review_task
                    else None
                ),
                "review_status": (
                    review_task["status"]
                    if review_task
                    else None
                ),
                "review_priority": (
                    review_task["priority"]
                    if review_task
                    else None
                ),
                "assigned_to_user_id": (
                    review_task[
                        "assigned_to_user_id"
                    ]
                    if review_task
                    else None
                ),
                "resolution_notes": (
                    review_task[
                        "resolution_notes"
                    ]
                    if review_task
                    else None
                ),
                "corrected_value": (
                    review_task[
                        "corrected_value"
                    ]
                    if review_task
                    else None
                ),
                "resolved_by_user_id": (
                    review_task[
                        "resolved_by_user_id"
                    ]
                    if review_task
                    else None
                ),
                "resolved_at": (
                    review_task[
                        "resolved_at"
                    ]
                    if review_task
                    else None
                ),
            }
        )

    return rows


def build_reconciliation_csv(
    report_data: ReconciliationReportData,
) -> bytes:
    """
    Build a flat UTF-8 CSV containing findings and review outcomes.
    """

    output = StringIO(
        newline=""
    )

    writer = csv.DictWriter(
        output,
        fieldnames=list(
            CSV_COLUMNS
        ),
        extrasaction="ignore",
        lineterminator="\n",
    )

    writer.writeheader()

    for row in _build_flat_csv_rows(
        report_data
    ):
        writer.writerow(
            {
                column_name:
                    _csv_safe_value(
                        row.get(
                            column_name
                        )
                    )
                for column_name
                in CSV_COLUMNS
            }
        )

    return output.getvalue().encode(
        "utf-8-sig"
    )


def _truncate_excel_text(
    value: str,
) -> str:
    return value[
        :32_767
    ]


def _write_excel_value(
    worksheet: Any,
    row: int,
    column: int,
    value: Any,
    *,
    cell_format: Any = None,
) -> None:
    if value is None:
        worksheet.write_blank(
            row,
            column,
            None,
            cell_format,
        )

        return

    if isinstance(
        value,
        bool,
    ):
        worksheet.write_boolean(
            row,
            column,
            value,
            cell_format,
        )

        return

    if isinstance(
        value,
        (
            int,
            float,
        ),
    ) and not isinstance(
        value,
        bool,
    ):
        worksheet.write_number(
            row,
            column,
            value,
            cell_format,
        )

        return

    if isinstance(
        value,
        Decimal,
    ):
        worksheet.write_number(
            row,
            column,
            float(value),
            cell_format,
        )

        return

    serialized_value = (
        _truncate_excel_text(
            _serialize_value(
                value
            )
        )
    )

    worksheet.write_string(
        row,
        column,
        serialized_value,
        cell_format,
    )


def _create_excel_formats(
    workbook: Any,
) -> dict[str, Any]:
    return {
        "title": workbook.add_format(
            {
                "bold": True,
                "font_size": 20,
                "font_color": "#FFFFFF",
                "bg_color": "#2B1B4F",
                "align": "left",
                "valign": "vcenter",
            }
        ),
        "subtitle": workbook.add_format(
            {
                "font_size": 10,
                "font_color": "#DDD6FE",
                "bg_color": "#2B1B4F",
                "align": "left",
                "valign": "vcenter",
            }
        ),
        "section": workbook.add_format(
            {
                "bold": True,
                "font_color": "#FFFFFF",
                "bg_color": "#7C3AED",
                "border": 0,
                "align": "left",
                "valign": "vcenter",
            }
        ),
        "label": workbook.add_format(
            {
                "bold": True,
                "font_color": "#475569",
                "bg_color": "#F1F5F9",
                "border": 1,
                "border_color": "#E2E8F0",
            }
        ),
        "value": workbook.add_format(
            {
                "font_color": "#0F172A",
                "bg_color": "#FFFFFF",
                "border": 1,
                "border_color": "#E2E8F0",
                "text_wrap": True,
                "valign": "top",
            }
        ),
        "metric_label": workbook.add_format(
            {
                "bold": True,
                "font_color": "#64748B",
                "bg_color": "#F8FAFC",
                "align": "center",
                "border": 1,
                "border_color": "#E2E8F0",
            }
        ),
        "metric_value": workbook.add_format(
            {
                "bold": True,
                "font_size": 18,
                "font_color": "#2B1B4F",
                "bg_color": "#FFFFFF",
                "align": "center",
                "border": 1,
                "border_color": "#E2E8F0",
            }
        ),
        "header": workbook.add_format(
            {
                "bold": True,
                "font_color": "#FFFFFF",
                "bg_color": "#2B1B4F",
                "border": 1,
                "border_color": "#43386A",
                "align": "center",
                "valign": "vcenter",
                "text_wrap": True,
            }
        ),
        "body": workbook.add_format(
            {
                "font_color": "#1E293B",
                "border": 1,
                "border_color": "#E2E8F0",
                "valign": "top",
            }
        ),
        "body_wrap": workbook.add_format(
            {
                "font_color": "#1E293B",
                "border": 1,
                "border_color": "#E2E8F0",
                "valign": "top",
                "text_wrap": True,
            }
        ),
        "percentage": workbook.add_format(
            {
                "font_color": "#1E293B",
                "border": 1,
                "border_color": "#E2E8F0",
                "num_format": "0.0%",
                "valign": "top",
            }
        ),
        "passed": workbook.add_format(
            {
                "font_color": "#166534",
                "bg_color": "#DCFCE7",
            }
        ),
        "failed": workbook.add_format(
            {
                "font_color": "#991B1B",
                "bg_color": "#FEE2E2",
            }
        ),
        "review": workbook.add_format(
            {
                "font_color": "#92400E",
                "bg_color": "#FEF3C7",
            }
        ),
        "skipped": workbook.add_format(
            {
                "font_color": "#475569",
                "bg_color": "#E2E8F0",
            }
        ),
        "high": workbook.add_format(
            {
                "font_color": "#991B1B",
                "bg_color": "#FEE2E2",
            }
        ),
        "medium": workbook.add_format(
            {
                "font_color": "#92400E",
                "bg_color": "#FEF3C7",
            }
        ),
        "low": workbook.add_format(
            {
                "font_color": "#1D4ED8",
                "bg_color": "#DBEAFE",
            }
        ),
    }


def _write_key_value_section(
    worksheet: Any,
    *,
    start_row: int,
    start_column: int,
    title: str,
    values: list[
        tuple[
            str,
            Any,
        ]
    ],
    formats: dict[str, Any],
) -> int:
    worksheet.merge_range(
        start_row,
        start_column,
        start_row,
        start_column + 1,
        title,
        formats["section"],
    )

    current_row = (
        start_row + 1
    )

    for label, value in values:
        worksheet.write_string(
            current_row,
            start_column,
            label,
            formats["label"],
        )

        _write_excel_value(
            worksheet,
            current_row,
            start_column + 1,
            value,
            cell_format=(
                formats["value"]
            ),
        )

        current_row += 1

    return current_row


def _write_summary_sheet(
    workbook: Any,
    report_data: ReconciliationReportData,
    formats: dict[str, Any],
) -> None:
    worksheet = workbook.add_worksheet(
        "Summary"
    )

    worksheet.hide_gridlines(
        2
    )

    worksheet.set_column(
        "A:A",
        24,
    )

    worksheet.set_column(
        "B:B",
        42,
    )

    worksheet.set_column(
        "C:C",
        3,
    )

    worksheet.set_column(
        "D:E",
        18,
    )

    worksheet.set_column(
        "F:F",
        3,
    )

    worksheet.set_column(
        "G:H",
        20,
    )

    worksheet.merge_range(
        "A1:H1",
        "InsightOps Reconciliation Report",
        formats["title"],
    )

    worksheet.merge_range(
        "A2:H2",
        report_data.document_name,
        formats["subtitle"],
    )

    worksheet.set_row(
        0,
        32,
    )

    worksheet.set_row(
        1,
        22,
    )

    run = report_data.run

    _write_key_value_section(
        worksheet,
        start_row=3,
        start_column=0,
        title="Run Details",
        values=[
            (
                "Run ID",
                run["id"],
            ),
            (
                "Document",
                report_data.document_name,
            ),
            (
                "Status",
                run["status"],
            ),
            (
                "Reconciliation Type",
                run[
                    "reconciliation_type"
                ],
            ),
            (
                "Created At",
                run["created_at"],
            ),
            (
                "Started At",
                run["started_at"],
            ),
            (
                "Completed At",
                run["completed_at"],
            ),
            (
                "Exclude Cancelled",
                run[
                    "exclude_cancelled"
                ],
            ),
        ],
        formats=formats,
    )

    metric_values = (
        (
            "Total Checks",
            run["total_checks"],
        ),
        (
            "Passed",
            run["passed_checks"],
        ),
        (
            "Failed",
            run["failed_checks"],
        ),
        (
            "Needs Review",
            run["review_checks"],
        ),
    )

    for metric_index, (
        metric_label,
        metric_value,
    ) in enumerate(
        metric_values
    ):
        column = (
            3
            + (
                metric_index
                % 2
            )
        )

        row = (
            3
            + (
                metric_index
                // 2
            )
            * 2
        )

        worksheet.write_string(
            row,
            column,
            metric_label,
            formats["metric_label"],
        )

        _write_excel_value(
            worksheet,
            row + 1,
            column,
            metric_value,
            cell_format=(
                formats["metric_value"]
            ),
        )

    status_counts = Counter(
        finding["status"]
        for finding
        in report_data.findings
    )

    worksheet.write_string(
        3,
        6,
        "Finding Status",
        formats["header"],
    )

    worksheet.write_string(
        3,
        7,
        "Count",
        formats["header"],
    )

    status_rows = (
        (
            "Passed",
            status_counts.get(
                "passed",
                0,
            ),
        ),
        (
            "Failed",
            status_counts.get(
                "failed",
                0,
            ),
        ),
        (
            "Needs Review",
            status_counts.get(
                "needs_review",
                0,
            ),
        ),
        (
            "Skipped",
            status_counts.get(
                "skipped",
                0,
            ),
        ),
    )

    for row_offset, (
        status_label,
        status_count,
    ) in enumerate(
        status_rows,
        start=4,
    ):
        worksheet.write_string(
            row_offset,
            6,
            status_label,
            formats["body"],
        )

        worksheet.write_number(
            row_offset,
            7,
            status_count,
            formats["body"],
        )

    chart = workbook.add_chart(
        {
            "type": "column",
        }
    )

    chart.add_series(
        {
            "name": "Findings",
            "categories": [
                "Summary",
                4,
                6,
                7,
                6,
            ],
            "values": [
                "Summary",
                4,
                7,
                7,
                7,
            ],
            "fill": {
                "color": "#8B5CF6",
            },
            "border": {
                "none": True,
            },
        }
    )

    chart.set_title(
        {
            "name": (
                "Findings by Status"
            ),
        }
    )

    chart.set_legend(
        {
            "none": True,
        }
    )

    chart.set_y_axis(
        {
            "major_gridlines": {
                "visible": False,
            },
            "min": 0,
        }
    )

    chart.set_style(
        10
    )

    worksheet.insert_chart(
        "G10",
        chart,
        {
            "x_scale": 1.1,
            "y_scale": 1.0,
        },
    )

    run_parameters = list(
        (
            run.get(
                "run_parameters"
            )
            or {}
        ).items()
    )

    summary_data = list(
        (
            run.get(
                "summary_data"
            )
            or {}
        ).items()
    )

    _write_key_value_section(
        worksheet,
        start_row=14,
        start_column=0,
        title="Run Parameters",
        values=run_parameters
        or [
            (
                "Parameters",
                "None",
            )
        ],
        formats=formats,
    )

    _write_key_value_section(
        worksheet,
        start_row=14,
        start_column=3,
        title="Run Summary",
        values=summary_data
        or [
            (
                "Summary",
                "None",
            )
        ],
        formats=formats,
    )

    worksheet.freeze_panes(
        2,
        0,
    )


def _write_findings_sheet(
    workbook: Any,
    report_data: ReconciliationReportData,
    formats: dict[str, Any],
) -> None:
    worksheet = workbook.add_worksheet(
        "Findings"
    )

    worksheet.hide_gridlines(
        2
    )

    worksheet.freeze_panes(
        1,
        0,
    )

    worksheet.set_row(
        0,
        30,
    )

    for column_index, (
        _,
        header,
        width,
    ) in enumerate(
        FINDING_COLUMNS
    ):
        worksheet.write_string(
            0,
            column_index,
            header,
            formats["header"],
        )

        worksheet.set_column(
            column_index,
            column_index,
            width,
        )

    wrap_columns = {
        "expected_value",
        "actual_value",
        "message",
        "source_text",
    }

    for row_index, finding in enumerate(
        report_data.findings,
        start=1,
    ):
        for column_index, (
            field_name,
            _,
            _,
        ) in enumerate(
            FINDING_COLUMNS
        ):
            value = finding.get(
                field_name
            )

            cell_format = (
                formats["body_wrap"]
                if field_name
                in wrap_columns
                else formats["body"]
            )

            if (
                field_name
                == "confidence_score"
                and value is not None
            ):
                _write_excel_value(
                    worksheet,
                    row_index,
                    column_index,
                    float(value),
                    cell_format=(
                        formats[
                            "percentage"
                        ]
                    ),
                )
            else:
                _write_excel_value(
                    worksheet,
                    row_index,
                    column_index,
                    value,
                    cell_format=cell_format,
                )

        worksheet.set_row(
            row_index,
            38,
        )

    last_row = max(
        1,
        len(
            report_data.findings
        ),
    )

    last_column = (
        len(
            FINDING_COLUMNS
        )
        - 1
    )

    worksheet.autofilter(
        0,
        0,
        last_row,
        last_column,
    )

    if report_data.findings:
        status_column = next(
            index
            for index, column
            in enumerate(
                FINDING_COLUMNS
            )
            if column[0]
            == "status"
        )

        severity_column = next(
            index
            for index, column
            in enumerate(
                FINDING_COLUMNS
            )
            if column[0]
            == "severity"
        )

        worksheet.conditional_format(
            1,
            status_column,
            last_row,
            status_column,
            {
                "type": "text",
                "criteria":
                    "containing",
                "value": "passed",
                "format":
                    formats["passed"],
            },
        )

        worksheet.conditional_format(
            1,
            status_column,
            last_row,
            status_column,
            {
                "type": "text",
                "criteria":
                    "containing",
                "value": "failed",
                "format":
                    formats["failed"],
            },
        )

        worksheet.conditional_format(
            1,
            status_column,
            last_row,
            status_column,
            {
                "type": "text",
                "criteria":
                    "containing",
                "value":
                    "needs_review",
                "format":
                    formats["review"],
            },
        )

        worksheet.conditional_format(
            1,
            status_column,
            last_row,
            status_column,
            {
                "type": "text",
                "criteria":
                    "containing",
                "value": "skipped",
                "format":
                    formats["skipped"],
            },
        )

        worksheet.conditional_format(
            1,
            severity_column,
            last_row,
            severity_column,
            {
                "type": "text",
                "criteria":
                    "containing",
                "value": "high",
                "format":
                    formats["high"],
            },
        )

        worksheet.conditional_format(
            1,
            severity_column,
            last_row,
            severity_column,
            {
                "type": "text",
                "criteria":
                    "containing",
                "value": "medium",
                "format":
                    formats["medium"],
            },
        )

        worksheet.conditional_format(
            1,
            severity_column,
            last_row,
            severity_column,
            {
                "type": "text",
                "criteria":
                    "containing",
                "value": "low",
                "format":
                    formats["low"],
            },
        )


def _write_review_tasks_sheet(
    workbook: Any,
    report_data: ReconciliationReportData,
    formats: dict[str, Any],
) -> None:
    worksheet = workbook.add_worksheet(
        "Review Tasks"
    )

    worksheet.hide_gridlines(
        2
    )

    worksheet.freeze_panes(
        1,
        0,
    )

    worksheet.set_row(
        0,
        30,
    )

    for column_index, (
        _,
        header,
        width,
    ) in enumerate(
        REVIEW_TASK_COLUMNS
    ):
        worksheet.write_string(
            0,
            column_index,
            header,
            formats["header"],
        )

        worksheet.set_column(
            column_index,
            column_index,
            width,
        )

    wrap_columns = {
        "title",
        "description",
        "resolution_notes",
        "corrected_value",
    }

    for row_index, review_task in enumerate(
        report_data.review_tasks,
        start=1,
    ):
        for column_index, (
            field_name,
            _,
            _,
        ) in enumerate(
            REVIEW_TASK_COLUMNS
        ):
            cell_format = (
                formats["body_wrap"]
                if field_name
                in wrap_columns
                else formats["body"]
            )

            _write_excel_value(
                worksheet,
                row_index,
                column_index,
                review_task.get(
                    field_name
                ),
                cell_format=cell_format,
            )

        worksheet.set_row(
            row_index,
            38,
        )

    last_row = max(
        1,
        len(
            report_data.review_tasks
        ),
    )

    last_column = (
        len(
            REVIEW_TASK_COLUMNS
        )
        - 1
    )

    worksheet.autofilter(
        0,
        0,
        last_row,
        last_column,
    )

    if report_data.review_tasks:
        status_column = next(
            index
            for index, column
            in enumerate(
                REVIEW_TASK_COLUMNS
            )
            if column[0]
            == "status"
        )

        priority_column = next(
            index
            for index, column
            in enumerate(
                REVIEW_TASK_COLUMNS
            )
            if column[0]
            == "priority"
        )

        worksheet.conditional_format(
            1,
            status_column,
            last_row,
            status_column,
            {
                "type": "text",
                "criteria":
                    "containing",
                "value": "open",
                "format":
                    formats["review"],
            },
        )

        worksheet.conditional_format(
            1,
            status_column,
            last_row,
            status_column,
            {
                "type": "text",
                "criteria":
                    "containing",
                "value": "corrected",
                "format":
                    formats["passed"],
            },
        )

        worksheet.conditional_format(
            1,
            status_column,
            last_row,
            status_column,
            {
                "type": "text",
                "criteria":
                    "containing",
                "value": "rejected",
                "format":
                    formats["failed"],
            },
        )

        worksheet.conditional_format(
            1,
            priority_column,
            last_row,
            priority_column,
            {
                "type": "text",
                "criteria":
                    "containing",
                "value": "high",
                "format":
                    formats["high"],
            },
        )

        worksheet.conditional_format(
            1,
            priority_column,
            last_row,
            priority_column,
            {
                "type": "text",
                "criteria":
                    "containing",
                "value": "medium",
                "format":
                    formats["medium"],
            },
        )


def build_reconciliation_xlsx(
    report_data: ReconciliationReportData,
) -> bytes:
    """
    Build a formatted Excel workbook containing summary, findings,
    review tasks, filters, conditional formatting, and a chart.
    """

    output = BytesIO()

    workbook = xlsxwriter.Workbook(
        output,
        {
            "in_memory": True,
            "strings_to_formulas": False,
            "strings_to_urls": False,
        },
    )

    try:
        workbook.set_properties(
            {
                "title": (
                    "InsightOps "
                    "Reconciliation Report"
                ),
                "subject": (
                    "Document-to-database "
                    "reconciliation findings"
                ),
                "author": "InsightOps AI",
                "company": "InsightOps AI",
                "comments": (
                    "Generated by the "
                    "InsightOps reconciliation "
                    "report service."
                ),
            }
        )

        formats = (
            _create_excel_formats(
                workbook
            )
        )

        _write_summary_sheet(
            workbook,
            report_data,
            formats,
        )

        _write_findings_sheet(
            workbook,
            report_data,
            formats,
        )

        _write_review_tasks_sheet(
            workbook,
            report_data,
            formats,
        )

    finally:
        workbook.close()

    return output.getvalue()


def _sanitize_filename_part(
    value: str,
) -> str:
    normalized = re.sub(
        r"[^A-Za-z0-9._-]+",
        "-",
        value,
    )

    normalized = normalized.strip(
        "._-"
    )

    return (
        normalized[:80]
        or "document"
    )


def build_report_filename(
    report_data: ReconciliationReportData,
    *,
    report_format: ReconciliationReportFormat,
) -> str:
    document_stem = Path(
        report_data.document_name
    ).stem

    safe_document_name = (
        _sanitize_filename_part(
            document_stem
        )
    )

    run_identifier = str(
        report_data.run["id"]
    )[:8]

    return (
        f"{safe_document_name}-"
        f"reconciliation-"
        f"{run_identifier}."
        f"{report_format}"
    )


def generate_reconciliation_report(
    report_data: ReconciliationReportData,
    *,
    report_format: ReconciliationReportFormat,
) -> GeneratedReconciliationReport:
    if report_format == "csv":
        content = (
            build_reconciliation_csv(
                report_data
            )
        )

        media_type = (
            "text/csv; charset=utf-8"
        )

    elif report_format == "xlsx":
        content = (
            build_reconciliation_xlsx(
                report_data
            )
        )

        media_type = (
            "application/vnd.openxmlformats-"
            "officedocument.spreadsheetml.sheet"
        )

    else:
        raise ValueError(
            "Unsupported reconciliation "
            f"report format: {report_format}"
        )

    return GeneratedReconciliationReport(
        content=content,
        filename=build_report_filename(
            report_data,
            report_format=report_format,
        ),
        media_type=media_type,
        report_format=report_format,
    )