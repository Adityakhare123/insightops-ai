from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


ReconciliationRunStatus = Literal[
    "queued",
    "running",
    "completed",
    "needs_review",
    "failed",
    "cancelled",
]

FindingStatus = Literal[
    "passed",
    "failed",
    "needs_review",
    "skipped",
]

FindingSeverity = Literal[
    "high",
    "medium",
    "low",
    "info",
]

ReviewTaskStatus = Literal[
    "open",
    "in_progress",
    "approved",
    "corrected",
    "rejected",
]

ReviewTaskPriority = Literal[
    "high",
    "medium",
    "low",
]


class ReconciliationStartRequest(
    BaseModel
):
    minimum_confidence: float = Field(
        default=0.75,
        ge=0,
        le=1,
    )

    premium_tolerance: Decimal = Field(
        default=Decimal("0.01"),
        ge=0,
        decimal_places=2,
    )

    exclude_cancelled: bool = True


class ExtractedPolicyFieldRead(
    BaseModel
):
    name: str
    value: Any | None
    raw_value: str | None

    found: bool

    page_number: int | None
    source_text: str | None

    confidence_score: float | None
    extraction_method: str | None


class PolicyDocumentExtractionRead(
    BaseModel
):
    fields: dict[
        str,
        ExtractedPolicyFieldRead,
    ]

    warnings: list[str]

    document_confidence: float
    page_count: int


class ReconciliationRunRead(
    BaseModel
):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    workspace_id: UUID
    document_id: UUID

    processing_run_id: UUID | None
    requested_by_user_id: UUID | None

    reconciliation_type: str
    status: ReconciliationRunStatus

    exclude_cancelled: bool

    started_at: datetime | None
    completed_at: datetime | None

    total_checks: int
    passed_checks: int
    failed_checks: int
    review_checks: int

    error_message: str | None

    run_parameters: dict[str, Any]
    summary_data: dict[str, Any]

    created_at: datetime
    updated_at: datetime


class ReconciliationFindingRead(
    BaseModel
):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    workspace_id: UUID

    reconciliation_run_id: UUID
    document_id: UUID
    document_page_id: UUID | None

    business_policy_id: UUID | None

    rule_code: str
    finding_type: str
    field_name: str | None

    status: FindingStatus
    severity: FindingSeverity

    expected_value: Any | None
    actual_value: Any | None

    message: str

    source_text: str | None
    source_page_number: int | None
    confidence_score: float | None

    evidence_data: dict[str, Any]

    created_at: datetime
    updated_at: datetime


class ReviewTaskRead(
    BaseModel
):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    workspace_id: UUID

    reconciliation_run_id: UUID
    reconciliation_finding_id: UUID
    document_id: UUID

    created_by_user_id: UUID | None
    assigned_to_user_id: UUID | None
    resolved_by_user_id: UUID | None

    status: ReviewTaskStatus
    priority: ReviewTaskPriority

    title: str
    description: str | None

    resolution_notes: str | None
    corrected_value: Any | None

    due_at: datetime | None
    resolved_at: datetime | None

    extra_metadata: dict[str, Any]

    created_at: datetime
    updated_at: datetime


class ReconciliationStartResponse(
    BaseModel
):
    message: str

    run: ReconciliationRunRead

    findings: list[
        ReconciliationFindingRead
    ]

    review_tasks: list[
        ReviewTaskRead
    ]

    extraction: PolicyDocumentExtractionRead


class ReconciliationRunListResponse(
    BaseModel
):
    items: list[
        ReconciliationRunRead
    ]

    total: int
    limit: int
    offset: int


class ReconciliationFindingListResponse(
    BaseModel
):
    items: list[
        ReconciliationFindingRead
    ]

    total: int
    limit: int
    offset: int


class ReviewTaskListResponse(
    BaseModel
):
    items: list[
        ReviewTaskRead
    ]

    total: int
    limit: int
    offset: int


class ReviewTaskUpdateRequest(
    BaseModel
):
    status: ReviewTaskStatus | None = None

    assigned_to_user_id: UUID | None = None

    resolution_notes: str | None = Field(
        default=None,
        max_length=4_000,
    )

    corrected_value: Any | None = None

    @model_validator(
        mode="after",
    )
    def validate_resolution(
        self,
    ) -> Self:
        resolved_statuses = {
            "approved",
            "corrected",
            "rejected",
        }

        if self.status in resolved_statuses:
            if (
                "resolution_notes"
                not in self.model_fields_set
                or not self.resolution_notes
                or not self.resolution_notes.strip()
            ):
                raise ValueError(
                    "Resolution notes are required "
                    "when resolving a review task."
                )

        if (
            self.status == "corrected"
            and "corrected_value"
            not in self.model_fields_set
        ):
            raise ValueError(
                "A corrected value is required "
                "when marking a task corrected."
            )

        return self


class ReviewTaskUpdateResponse(
    BaseModel
):
    message: str
    task: ReviewTaskRead