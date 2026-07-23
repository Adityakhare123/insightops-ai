from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.app.db.models.document import (
    Document,
)
from apps.api.app.db.models.document_page import (
    DocumentPage,
)
from apps.api.app.db.models.document_processing_run import (
    DocumentProcessingRun,
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
from apps.api.app.db.models.workspace import (
    Carrier,
    Customer,
    Payment,
    Plan,
    Policy,
)
from apps.api.app.services.policy_field_extraction import (
    PolicyDocumentExtraction,
    PolicySourcePage,
    extract_policy_fields,
)
from apps.api.app.services.reconciliation_rules import (
    PolicyDatabaseRecord,
    ReconciliationEvaluation,
    ReconciliationRuleResult,
    evaluate_policy_reconciliation,
)


class PolicyReconciliationError(
    RuntimeError
):
    """Base error for policy reconciliation."""


class ReconciliationDocumentNotFoundError(
    PolicyReconciliationError
):
    """Raised when the document is outside the workspace."""


class DocumentNotProcessedError(
    PolicyReconciliationError
):
    """Raised when no completed processing run exists."""


class DocumentTextUnavailableError(
    PolicyReconciliationError
):
    """Raised when completed pages contain no usable text."""


@dataclass(
    frozen=True,
    slots=True,
)
class PolicyReconciliationResult:
    """
    Result returned after reconciliation records are persisted.

    The surrounding API layer owns the final database commit.
    """

    reconciliation_run: ReconciliationRun

    findings: tuple[
        ReconciliationFinding,
        ...,
    ]

    review_tasks: tuple[
        ReviewTask,
        ...,
    ]

    extraction: PolicyDocumentExtraction
    evaluation: ReconciliationEvaluation

    processing_run_id: UUID

    @property
    def matched_policy_id(
        self,
    ) -> UUID | None:
        return (
            self.evaluation
            .matched_policy_id
        )


def _utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


def _get_workspace_document(
    database_session: Session,
    *,
    workspace_id: UUID,
    document_id: UUID,
) -> Document:
    document = database_session.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.workspace_id
            == workspace_id,
        )
    )

    if document is None:
        raise (
            ReconciliationDocumentNotFoundError(
                "The document was not found "
                "in the current workspace."
            )
        )

    return document


def _get_latest_completed_processing_run(
    database_session: Session,
    *,
    workspace_id: UUID,
    document_id: UUID,
) -> DocumentProcessingRun:
    processing_run = database_session.scalar(
        select(
            DocumentProcessingRun
        )
        .where(
            DocumentProcessingRun.workspace_id
            == workspace_id,
            DocumentProcessingRun.document_id
            == document_id,
            DocumentProcessingRun.status
            == "completed",
        )
        .order_by(
            DocumentProcessingRun
            .attempt_number
            .desc(),
            DocumentProcessingRun
            .created_at
            .desc(),
            DocumentProcessingRun
            .id
            .desc(),
        )
        .limit(1)
    )

    if processing_run is None:
        raise DocumentNotProcessedError(
            "The document does not have a "
            "completed processing run."
        )

    return processing_run


def _get_completed_document_pages(
    database_session: Session,
    *,
    workspace_id: UUID,
    document_id: UUID,
    processing_run_id: UUID,
) -> list[DocumentPage]:
    pages = list(
        database_session.scalars(
            select(DocumentPage)
            .where(
                DocumentPage.workspace_id
                == workspace_id,
                DocumentPage.document_id
                == document_id,
                DocumentPage.processing_run_id
                == processing_run_id,
                DocumentPage.status
                == "completed",
            )
            .order_by(
                DocumentPage.page_number,
                DocumentPage.id,
            )
        ).all()
    )

    usable_pages = [
        page
        for page in pages
        if (
            page.text_content
            and page.text_content.strip()
        )
    ]

    if not usable_pages:
        raise DocumentTextUnavailableError(
            "The completed processing run "
            "does not contain usable page text."
        )

    return usable_pages


def _build_extraction_pages(
    document_pages: Sequence[
        DocumentPage
    ],
) -> list[PolicySourcePage]:
    return [
        PolicySourcePage(
            page_number=page.page_number,
            text=page.text_content or "",
            confidence_score=(
                float(
                    page.confidence_score
                )
                if (
                    page.confidence_score
                    is not None
                )
                else None
            ),
        )
        for page in document_pages
    ]


def _extract_policy_number(
    extraction: PolicyDocumentExtraction,
) -> str | None:
    extracted_value = (
        extraction.get_value(
            "policy_number"
        )
    )

    if extracted_value is None:
        return None

    normalized_value = str(
        extracted_value
    ).strip()

    return normalized_value or None


def _find_matching_policies(
    database_session: Session,
    *,
    workspace_id: UUID,
    policy_number: str | None,
) -> list[Policy]:
    if not policy_number:
        return []

    return list(
        database_session.scalars(
            select(Policy)
            .where(
                Policy.workspace_id
                == workspace_id,
                func.upper(
                    Policy.policy_number
                )
                == policy_number.upper(),
            )
            .order_by(
                Policy.source_system.asc(),
                Policy.created_at.asc(),
                Policy.id.asc(),
            )
        ).all()
    )


def _load_customer_name(
    database_session: Session,
    *,
    workspace_id: UUID,
    customer_id: UUID,
) -> str | None:
    customer = database_session.scalar(
        select(Customer).where(
            Customer.id == customer_id,
            Customer.workspace_id
            == workspace_id,
        )
    )

    if customer is None:
        return None

    full_name = " ".join(
        value.strip()
        for value in (
            customer.first_name,
            customer.last_name,
        )
        if value and value.strip()
    )

    return full_name or None


def _load_carrier_name(
    database_session: Session,
    *,
    workspace_id: UUID,
    carrier_id: UUID,
) -> str | None:
    carrier = database_session.scalar(
        select(Carrier).where(
            Carrier.id == carrier_id,
            Carrier.workspace_id
            == workspace_id,
        )
    )

    if carrier is None:
        return None

    return carrier.name


def _load_plan_name(
    database_session: Session,
    *,
    workspace_id: UUID,
    plan_id: UUID,
) -> str | None:
    plan = database_session.scalar(
        select(Plan).where(
            Plan.id == plan_id,
            Plan.workspace_id
            == workspace_id,
        )
    )

    if plan is None:
        return None

    return plan.name


def _policy_has_posted_payment(
    database_session: Session,
    *,
    workspace_id: UUID,
    policy_id: UUID,
) -> bool:
    payment_count = database_session.scalar(
        select(
            func.count(
                Payment.id
            )
        ).where(
            Payment.workspace_id
            == workspace_id,
            Payment.policy_id
            == policy_id,
            func.lower(
                Payment.status
            )
            == "posted",
        )
    )

    return int(
        payment_count or 0
    ) > 0


def _build_policy_database_record(
    database_session: Session,
    *,
    workspace_id: UUID,
    policies: Sequence[Policy],
) -> PolicyDatabaseRecord | None:
    if not policies:
        return None

    canonical_policy = policies[0]

    customer_name = (
        _load_customer_name(
            database_session,
            workspace_id=workspace_id,
            customer_id=(
                canonical_policy.customer_id
            ),
        )
    )

    carrier_name = (
        _load_carrier_name(
            database_session,
            workspace_id=workspace_id,
            carrier_id=(
                canonical_policy.carrier_id
            ),
        )
    )

    plan_name = (
        _load_plan_name(
            database_session,
            workspace_id=workspace_id,
            plan_id=canonical_policy.plan_id,
        )
    )

    has_payment = (
        _policy_has_posted_payment(
            database_session,
            workspace_id=workspace_id,
            policy_id=canonical_policy.id,
        )
    )

    return PolicyDatabaseRecord(
        policy_id=canonical_policy.id,
        policy_number=(
            canonical_policy.policy_number
        ),
        customer_name=customer_name,
        carrier_name=carrier_name,
        plan_name=plan_name,
        effective_date=(
            canonical_policy.effective_date
        ),

        # The current synthetic policy table
        # does not track these two dates.
        termination_date=None,
        signature_date=None,

        premium=canonical_policy.premium,
        policy_status=(
            canonical_policy.status
        ),
        has_payment=has_payment,
        duplicate_policy_count=len(
            policies
        ),
    )


def _review_priority(
    result: ReconciliationRuleResult,
) -> str:
    if result.severity == "high":
        return "high"

    if result.severity == "medium":
        return "medium"

    return "low"


def _should_create_review_task(
    result: ReconciliationRuleResult,
) -> bool:
    return (
        result.status
        in {
            "failed",
            "needs_review",
        }
        and result.severity
        in {
            "high",
            "medium",
        }
    )


def _build_review_title(
    result: ReconciliationRuleResult,
) -> str:
    readable_type = (
        result.finding_type
        .replace("_", " ")
        .strip()
        .title()
    )

    return (
        readable_type
        or "Reconciliation Review"
    )[:255]


def _persist_evaluation(
    database_session: Session,
    *,
    workspace_id: UUID,
    document_id: UUID,
    requested_by_user_id: UUID | None,
    reconciliation_run: ReconciliationRun,
    evaluation: ReconciliationEvaluation,
    document_pages: Sequence[
        DocumentPage
    ],
) -> tuple[
    tuple[
        ReconciliationFinding,
        ...,
    ],
    tuple[
        ReviewTask,
        ...,
    ],
]:
    pages_by_number = {
        page.page_number: page
        for page in document_pages
    }

    persisted_findings: list[
        ReconciliationFinding
    ] = []

    review_tasks: list[
        ReviewTask
    ] = []

    for result in evaluation.results:
        source_page = (
            pages_by_number.get(
                result.source_page_number
            )
            if (
                result.source_page_number
                is not None
            )
            else None
        )

        finding = ReconciliationFinding(
            workspace_id=workspace_id,
            reconciliation_run_id=(
                reconciliation_run.id
            ),
            document_id=document_id,
            document_page_id=(
                source_page.id
                if source_page
                else None
            ),
            **result.to_finding_values(),
        )

        database_session.add(
            finding
        )

        database_session.flush()

        persisted_findings.append(
            finding
        )

        if not _should_create_review_task(
            result
        ):
            continue

        review_task = ReviewTask(
            workspace_id=workspace_id,
            reconciliation_run_id=(
                reconciliation_run.id
            ),
            reconciliation_finding_id=(
                finding.id
            ),
            document_id=document_id,
            created_by_user_id=(
                requested_by_user_id
            ),
            assigned_to_user_id=None,
            resolved_by_user_id=None,
            status="open",
            priority=_review_priority(
                result
            ),
            title=_build_review_title(
                result
            ),
            description=result.message,
            resolution_notes=None,
            corrected_value=None,
            due_at=None,
            resolved_at=None,
            extra_metadata={
                "rule_code":
                    result.rule_code,
                "finding_type":
                    result.finding_type,
                "field_name":
                    result.field_name,
                "severity":
                    result.severity,
            },
        )

        database_session.add(
            review_task
        )

        database_session.flush()

        review_tasks.append(
            review_task
        )

    return (
        tuple(
            persisted_findings
        ),
        tuple(
            review_tasks
        ),
    )


def run_policy_document_reconciliation(
    database_session: Session,
    *,
    workspace_id: UUID,
    document_id: UUID,
    requested_by_user_id: UUID | None,
    minimum_confidence: float = 0.75,
    premium_tolerance: Decimal = Decimal(
        "0.01"
    ),
    exclude_cancelled: bool = True,
) -> PolicyReconciliationResult:
    """
    Reconcile one processed policy document with workspace data.

    This function flushes database changes but does not commit them.
    The API or worker calling it owns commit and rollback handling.
    """

    document = _get_workspace_document(
        database_session,
        workspace_id=workspace_id,
        document_id=document_id,
    )

    processing_run = (
        _get_latest_completed_processing_run(
            database_session,
            workspace_id=workspace_id,
            document_id=document_id,
        )
    )

    reconciliation_run = (
        ReconciliationRun(
            workspace_id=workspace_id,
            document_id=document.id,
            processing_run_id=(
                processing_run.id
            ),
            requested_by_user_id=(
                requested_by_user_id
            ),
            reconciliation_type=(
                "policy_document"
            ),
            status="running",
            exclude_cancelled=(
                exclude_cancelled
            ),
            started_at=_utc_now(),
            completed_at=None,
            total_checks=0,
            passed_checks=0,
            failed_checks=0,
            review_checks=0,
            error_message=None,
            run_parameters={
                "minimum_confidence":
                    minimum_confidence,
                "premium_tolerance":
                    format(
                        premium_tolerance,
                        ".2f",
                    ),
                "exclude_cancelled":
                    exclude_cancelled,
            },
            summary_data={},
        )
    )

    database_session.add(
        reconciliation_run
    )

    database_session.flush()

    try:
        with database_session.begin_nested():
            document_pages = (
                _get_completed_document_pages(
                    database_session,
                    workspace_id=workspace_id,
                    document_id=document.id,
                    processing_run_id=(
                        processing_run.id
                    ),
                )
            )

            extraction_pages = (
                _build_extraction_pages(
                    document_pages
                )
            )

            extraction = (
                extract_policy_fields(
                    extraction_pages,
                    minimum_confidence=(
                        minimum_confidence
                    ),
                )
            )

            policy_number = (
                _extract_policy_number(
                    extraction
                )
            )

            matching_policies = (
                _find_matching_policies(
                    database_session,
                    workspace_id=workspace_id,
                    policy_number=policy_number,
                )
            )

            database_policy = (
                _build_policy_database_record(
                    database_session,
                    workspace_id=workspace_id,
                    policies=matching_policies,
                )
            )

            evaluation = (
                evaluate_policy_reconciliation(
                    extraction,
                    database_policy,
                    minimum_confidence=(
                        minimum_confidence
                    ),
                    premium_tolerance=(
                        premium_tolerance
                    ),
                    exclude_cancelled=(
                        exclude_cancelled
                    ),
                )
            )

            (
                persisted_findings,
                review_tasks,
            ) = _persist_evaluation(
                database_session,
                workspace_id=workspace_id,
                document_id=document.id,
                requested_by_user_id=(
                    requested_by_user_id
                ),
                reconciliation_run=(
                    reconciliation_run
                ),
                evaluation=evaluation,
                document_pages=document_pages,
            )

            reconciliation_run.status = (
                evaluation.overall_status
            )

            reconciliation_run.completed_at = (
                _utc_now()
            )

            reconciliation_run.total_checks = (
                evaluation.total_checks
            )

            reconciliation_run.passed_checks = (
                evaluation.passed_checks
            )

            reconciliation_run.failed_checks = (
                evaluation.failed_checks
            )

            reconciliation_run.review_checks = (
                evaluation.review_checks
            )

            reconciliation_run.summary_data = {
                **evaluation.to_summary(),
                "processing_run_id": str(
                    processing_run.id
                ),
                "document_id": str(
                    document.id
                ),
                "document_filename": (
                    document.original_filename
                ),
                "extracted_policy_number": (
                    policy_number
                ),
                "document_confidence": (
                    extraction
                    .document_confidence
                ),
                "extraction_warnings": list(
                    extraction.warnings
                ),
                "matched_policy_count": len(
                    matching_policies
                ),
                "review_task_count": len(
                    review_tasks
                ),
            }

            database_session.flush()

        return PolicyReconciliationResult(
            reconciliation_run=(
                reconciliation_run
            ),
            findings=(
                persisted_findings
            ),
            review_tasks=review_tasks,
            extraction=extraction,
            evaluation=evaluation,
            processing_run_id=(
                processing_run.id
            ),
        )

    except Exception as error:
        reconciliation_run.status = "failed"

        reconciliation_run.completed_at = (
            _utc_now()
        )

        reconciliation_run.error_message = (
            str(error)[:4_000]
        )

        reconciliation_run.summary_data = {
            "document_id": str(
                document.id
            ),
            "processing_run_id": str(
                processing_run.id
            ),
            "error_type": (
                type(error).__name__
            ),
        }

        database_session.flush()

        raise