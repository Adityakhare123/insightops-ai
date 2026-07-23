from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    Response,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from apps.api.app.api.deps import (
    CurrentUser,
    DatabaseSession,
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
from apps.api.app.db.models.user import User
from apps.api.app.schemas.reconciliation import (
    FindingSeverity,
    FindingStatus,
    PolicyDocumentExtractionRead,
    ReconciliationFindingListResponse,
    ReconciliationFindingRead,
    ReconciliationRunListResponse,
    ReconciliationRunRead,
    ReconciliationRunStatus,
    ReconciliationStartRequest,
    ReconciliationStartResponse,
    ReviewTaskListResponse,
    ReviewTaskPriority,
    ReviewTaskRead,
    ReviewTaskStatus,
    ReviewTaskUpdateRequest,
    ReviewTaskUpdateResponse,
)
from apps.api.app.services.policy_reconciliation import (
    DocumentNotProcessedError,
    DocumentTextUnavailableError,
    PolicyReconciliationError,
    ReconciliationDocumentNotFoundError,
    run_policy_document_reconciliation,
)
from apps.api.app.services.reconciliation_reports import (
    ReconciliationReportFormat,
    ReconciliationReportNotFoundError,
    generate_reconciliation_report,
    load_reconciliation_report_data,
)


router = APIRouter()


RESOLVED_REVIEW_STATUSES = {
    "approved",
    "corrected",
    "rejected",
}


def _build_reconciliation_report_response(
    *,
    database_session: DatabaseSession,
    workspace_id: UUID,
    run_id: UUID,
    report_format: ReconciliationReportFormat,
) -> Response:
    """
    Load and generate one workspace-scoped reconciliation report.
    """

    try:
        report_data = (
            load_reconciliation_report_data(
                database_session,
                workspace_id=workspace_id,
                run_id=run_id,
            )
        )

        report = (
            generate_reconciliation_report(
                report_data,
                report_format=report_format,
            )
        )

    except ReconciliationReportNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_CONTENT
            ),
            detail=str(error),
        ) from error

    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "The reconciliation report "
                "could not be generated."
            ),
        ) from error

    return Response(
        content=report.content,
        media_type=report.media_type,
        headers={
            "Content-Disposition": (
                "attachment; "
                f'filename="{report.filename}"'
            ),
            "Cache-Control": (
                "private, no-store, max-age=0"
            ),
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


def _get_workspace_run(
    *,
    database_session: DatabaseSession,
    workspace_id: UUID,
    run_id: UUID,
) -> ReconciliationRun:
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Reconciliation run was not found."
            ),
        )

    return reconciliation_run


def _get_workspace_review_task(
    *,
    database_session: DatabaseSession,
    workspace_id: UUID,
    task_id: UUID,
) -> ReviewTask:
    review_task = (
        database_session.scalar(
            select(
                ReviewTask
            ).where(
                ReviewTask.id == task_id,
                ReviewTask.workspace_id
                == workspace_id,
            )
        )
    )

    if review_task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review task was not found.",
        )

    return review_task


def _validate_assignee(
    *,
    database_session: DatabaseSession,
    workspace_id: UUID,
    user_id: UUID,
) -> User:
    assigned_user = (
        database_session.scalar(
            select(User).where(
                User.id == user_id,
                User.workspace_id
                == workspace_id,
            )
        )
    )

    if assigned_user is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "The selected assignee does not "
                "belong to this workspace."
            ),
        )

    if not assigned_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "The selected assignee is inactive."
            ),
        )

    return assigned_user


def _validate_status_transition(
    *,
    current_status: str,
    requested_status: str,
) -> None:
    if (
        current_status
        in RESOLVED_REVIEW_STATUSES
        and requested_status
        != current_status
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A resolved review task cannot "
                "be moved to another status."
            ),
        )


@router.post(
    "/documents/{document_id}/run",
    response_model=ReconciliationStartResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_document_reconciliation(
    document_id: UUID,
    request: ReconciliationStartRequest,
    current_user: CurrentUser,
    database_session: DatabaseSession,
) -> ReconciliationStartResponse:
    """
    Run deterministic reconciliation for one processed document.
    """

    try:
        result = (
            run_policy_document_reconciliation(
                database_session,
                workspace_id=(
                    current_user.workspace_id
                ),
                document_id=document_id,
                requested_by_user_id=(
                    current_user.id
                ),
                minimum_confidence=(
                    request.minimum_confidence
                ),
                premium_tolerance=(
                    request.premium_tolerance
                ),
                exclude_cancelled=(
                    request.exclude_cancelled
                ),
            )
        )

        database_session.commit()

        database_session.refresh(
            result.reconciliation_run
        )

        for finding in result.findings:
            database_session.refresh(
                finding
            )

        for review_task in result.review_tasks:
            database_session.refresh(
                review_task
            )

    except ReconciliationDocumentNotFoundError as error:
        database_session.rollback()

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    except DocumentNotProcessedError as error:
        database_session.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    except DocumentTextUnavailableError as error:
        try:
            database_session.commit()
        except SQLAlchemyError:
            database_session.rollback()

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    except ValueError as error:
        database_session.rollback()

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    except PolicyReconciliationError as error:
        try:
            database_session.commit()
        except SQLAlchemyError:
            database_session.rollback()

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    except SQLAlchemyError as error:
        database_session.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "The reconciliation result could "
                "not be saved."
            ),
        ) from error

    return ReconciliationStartResponse(
        message=(
            "Document reconciliation completed."
        ),
        run=ReconciliationRunRead.model_validate(
            result.reconciliation_run
        ),
        findings=[
            ReconciliationFindingRead.model_validate(
                finding
            )
            for finding in result.findings
        ],
        review_tasks=[
            ReviewTaskRead.model_validate(
                review_task
            )
            for review_task
            in result.review_tasks
        ],
        extraction=(
            PolicyDocumentExtractionRead
            .model_validate(
                result.extraction.to_dict()
            )
        ),
    )


@router.get(
    "/runs",
    response_model=ReconciliationRunListResponse,
)
def list_reconciliation_runs(
    current_user: CurrentUser,
    database_session: DatabaseSession,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
        ),
    ] = 20,
    offset: Annotated[
        int,
        Query(
            ge=0,
        ),
    ] = 0,
    run_status: Annotated[
        ReconciliationRunStatus | None,
        Query(
            alias="status",
        ),
    ] = None,
    document_id: Annotated[
        UUID | None,
        Query(),
    ] = None,
) -> ReconciliationRunListResponse:
    filters = [
        ReconciliationRun.workspace_id
        == current_user.workspace_id,
    ]

    if run_status is not None:
        filters.append(
            ReconciliationRun.status
            == run_status
        )

    if document_id is not None:
        filters.append(
            ReconciliationRun.document_id
            == document_id
        )

    total = database_session.scalar(
        select(func.count())
        .select_from(
            ReconciliationRun
        )
        .where(*filters)
    )

    runs = list(
        database_session.scalars(
            select(
                ReconciliationRun
            )
            .where(*filters)
            .order_by(
                ReconciliationRun
                .created_at
                .desc(),
                ReconciliationRun.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()
    )

    return ReconciliationRunListResponse(
        items=[
            ReconciliationRunRead.model_validate(
                reconciliation_run
            )
            for reconciliation_run in runs
        ],
        total=int(total or 0),
        limit=limit,
        offset=offset,
    )


@router.get(
    "/runs/{run_id}",
    response_model=ReconciliationRunRead,
)
def get_reconciliation_run(
    run_id: UUID,
    current_user: CurrentUser,
    database_session: DatabaseSession,
) -> ReconciliationRunRead:
    reconciliation_run = (
        _get_workspace_run(
            database_session=database_session,
            workspace_id=(
                current_user.workspace_id
            ),
            run_id=run_id,
        )
    )

    return ReconciliationRunRead.model_validate(
        reconciliation_run
    )


@router.get(
    "/runs/{run_id}/reports/csv",
    response_class=Response,
    responses={
        200: {
            "description": (
                "CSV reconciliation report."
            ),
            "content": {
                "text/csv": {},
            },
        },
        404: {
            "description": (
                "Reconciliation run not found."
            ),
        },
    },
)
def download_reconciliation_csv_report(
    run_id: UUID,
    current_user: CurrentUser,
    database_session: DatabaseSession,
) -> Response:
    """
    Download a flat CSV reconciliation report.
    """

    return _build_reconciliation_report_response(
        database_session=database_session,
        workspace_id=current_user.workspace_id,
        run_id=run_id,
        report_format="csv",
    )


@router.get(
    "/runs/{run_id}/reports/xlsx",
    response_class=Response,
    responses={
        200: {
            "description": (
                "Formatted Excel reconciliation "
                "report."
            ),
            "content": {
                (
                    "application/vnd.openxmlformats-"
                    "officedocument.spreadsheetml.sheet"
                ): {},
            },
        },
        404: {
            "description": (
                "Reconciliation run not found."
            ),
        },
    },
)
def download_reconciliation_xlsx_report(
    run_id: UUID,
    current_user: CurrentUser,
    database_session: DatabaseSession,
) -> Response:
    """
    Download a formatted Excel reconciliation report.
    """

    return _build_reconciliation_report_response(
        database_session=database_session,
        workspace_id=current_user.workspace_id,
        run_id=run_id,
        report_format="xlsx",
    )


@router.get(
    "/runs/{run_id}/findings",
    response_model=(
        ReconciliationFindingListResponse
    ),
)
def list_reconciliation_findings(
    run_id: UUID,
    current_user: CurrentUser,
    database_session: DatabaseSession,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=500,
        ),
    ] = 100,
    offset: Annotated[
        int,
        Query(
            ge=0,
        ),
    ] = 0,
    finding_status: Annotated[
        FindingStatus | None,
        Query(
            alias="status",
        ),
    ] = None,
    severity: Annotated[
        FindingSeverity | None,
        Query(),
    ] = None,
) -> ReconciliationFindingListResponse:
    _get_workspace_run(
        database_session=database_session,
        workspace_id=current_user.workspace_id,
        run_id=run_id,
    )

    filters = [
        ReconciliationFinding.workspace_id
        == current_user.workspace_id,
        ReconciliationFinding
        .reconciliation_run_id
        == run_id,
    ]

    if finding_status is not None:
        filters.append(
            ReconciliationFinding.status
            == finding_status
        )

    if severity is not None:
        filters.append(
            ReconciliationFinding.severity
            == severity
        )

    total = database_session.scalar(
        select(func.count())
        .select_from(
            ReconciliationFinding
        )
        .where(*filters)
    )

    findings = list(
        database_session.scalars(
            select(
                ReconciliationFinding
            )
            .where(*filters)
            .order_by(
                ReconciliationFinding
                .created_at
                .asc(),
                ReconciliationFinding.id.asc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()
    )

    return ReconciliationFindingListResponse(
        items=[
            ReconciliationFindingRead
            .model_validate(
                finding
            )
            for finding in findings
        ],
        total=int(total or 0),
        limit=limit,
        offset=offset,
    )


@router.get(
    "/review-tasks",
    response_model=ReviewTaskListResponse,
)
def list_review_tasks(
    current_user: CurrentUser,
    database_session: DatabaseSession,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=200,
        ),
    ] = 50,
    offset: Annotated[
        int,
        Query(
            ge=0,
        ),
    ] = 0,
    task_status: Annotated[
        ReviewTaskStatus | None,
        Query(
            alias="status",
        ),
    ] = None,
    priority: Annotated[
        ReviewTaskPriority | None,
        Query(),
    ] = None,
    assigned_to_user_id: Annotated[
        UUID | None,
        Query(),
    ] = None,
    run_id: Annotated[
        UUID | None,
        Query(),
    ] = None,
    document_id: Annotated[
        UUID | None,
        Query(),
    ] = None,
) -> ReviewTaskListResponse:
    filters = [
        ReviewTask.workspace_id
        == current_user.workspace_id,
    ]

    if task_status is not None:
        filters.append(
            ReviewTask.status
            == task_status
        )

    if priority is not None:
        filters.append(
            ReviewTask.priority
            == priority
        )

    if assigned_to_user_id is not None:
        filters.append(
            ReviewTask.assigned_to_user_id
            == assigned_to_user_id
        )

    if run_id is not None:
        filters.append(
            ReviewTask.reconciliation_run_id
            == run_id
        )

    if document_id is not None:
        filters.append(
            ReviewTask.document_id
            == document_id
        )

    total = database_session.scalar(
        select(func.count())
        .select_from(ReviewTask)
        .where(*filters)
    )

    tasks = list(
        database_session.scalars(
            select(ReviewTask)
            .where(*filters)
            .order_by(
                ReviewTask
                .created_at
                .desc(),
                ReviewTask.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()
    )

    return ReviewTaskListResponse(
        items=[
            ReviewTaskRead.model_validate(
                task
            )
            for task in tasks
        ],
        total=int(total or 0),
        limit=limit,
        offset=offset,
    )


@router.get(
    "/review-tasks/{task_id}",
    response_model=ReviewTaskRead,
)
def get_review_task(
    task_id: UUID,
    current_user: CurrentUser,
    database_session: DatabaseSession,
) -> ReviewTaskRead:
    task = _get_workspace_review_task(
        database_session=database_session,
        workspace_id=current_user.workspace_id,
        task_id=task_id,
    )

    return ReviewTaskRead.model_validate(
        task
    )


@router.patch(
    "/review-tasks/{task_id}",
    response_model=ReviewTaskUpdateResponse,
)
def update_review_task(
    task_id: UUID,
    request: ReviewTaskUpdateRequest,
    current_user: CurrentUser,
    database_session: DatabaseSession,
) -> ReviewTaskUpdateResponse:
    if not request.model_fields_set:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "At least one review-task field "
                "must be supplied."
            ),
        )

    task = _get_workspace_review_task(
        database_session=database_session,
        workspace_id=current_user.workspace_id,
        task_id=task_id,
    )

    if (
        "assigned_to_user_id"
        in request.model_fields_set
    ):
        if request.assigned_to_user_id is None:
            task.assigned_to_user_id = None
        else:
            assigned_user = _validate_assignee(
                database_session=database_session,
                workspace_id=(
                    current_user.workspace_id
                ),
                user_id=(
                    request.assigned_to_user_id
                ),
            )

            task.assigned_to_user_id = (
                assigned_user.id
            )

    if "status" in request.model_fields_set:
        if request.status is None:
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_CONTENT
                ),
                detail=(
                    "Review-task status cannot "
                    "be null."
                ),
            )

        _validate_status_transition(
            current_status=task.status,
            requested_status=request.status,
        )

        task.status = request.status

        if (
            request.status
            in RESOLVED_REVIEW_STATUSES
        ):
            task.resolved_by_user_id = (
                current_user.id
            )

            task.resolved_at = _utc_now()

        else:
            task.resolved_by_user_id = None
            task.resolved_at = None

    if (
        "resolution_notes"
        in request.model_fields_set
    ):
        task.resolution_notes = (
            request.resolution_notes.strip()
            if request.resolution_notes
            else None
        )

    if (
        "corrected_value"
        in request.model_fields_set
    ):
        task.corrected_value = (
            request.corrected_value
        )

    if (
        task.status == "corrected"
        and "corrected_value"
        not in request.model_fields_set
        and task.corrected_value is None
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "A corrected value is required "
                "for a corrected task."
            ),
        )

    try:
        database_session.commit()
        database_session.refresh(task)
    except SQLAlchemyError as error:
        database_session.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "The review task could not "
                "be updated."
            ),
        ) from error

    return ReviewTaskUpdateResponse(
        message=(
            "Review task updated successfully."
        ),
        task=ReviewTaskRead.model_validate(
            task
        ),
    )