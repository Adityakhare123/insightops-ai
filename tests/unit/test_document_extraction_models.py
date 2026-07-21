from __future__ import annotations

from sqlalchemy import CheckConstraint
from sqlalchemy import UniqueConstraint

from apps.api.app.db.base import Base
from apps.api.app.db.models.document_page import (
    DocumentPage,
)
from apps.api.app.db.models.document_processing_run import (
    DocumentProcessingRun,
)


def test_processing_run_table_is_registered() -> None:
    assert (
        "document_processing_runs"
        in Base.metadata.tables
    )


def test_document_page_table_is_registered() -> None:
    assert "document_pages" in Base.metadata.tables


def test_processing_run_required_columns() -> None:
    table = DocumentProcessingRun.__table__

    expected_columns = {
        "id",
        "workspace_id",
        "document_id",
        "requested_by_user_id",
        "attempt_number",
        "status",
        "processor_name",
        "processor_version",
        "started_at",
        "completed_at",
        "total_pages",
        "extracted_pages",
        "error_message",
        "extra_metadata",
        "created_at",
        "updated_at",
    }

    assert expected_columns.issubset(
        table.columns.keys()
    )


def test_document_page_required_columns() -> None:
    table = DocumentPage.__table__

    expected_columns = {
        "id",
        "workspace_id",
        "document_id",
        "processing_run_id",
        "page_number",
        "status",
        "extraction_method",
        "language_code",
        "text_content",
        "confidence_score",
        "character_count",
        "word_count",
        "error_message",
        "extra_metadata",
        "created_at",
        "updated_at",
    }

    assert expected_columns.issubset(
        table.columns.keys()
    )


def test_processing_run_has_unique_attempt_constraint() -> None:
    table = DocumentProcessingRun.__table__

    unique_constraints = {
        tuple(
            column.name
            for column in constraint.columns
        )
        for constraint in table.constraints
        if isinstance(
            constraint,
            UniqueConstraint,
        )
    }

    assert (
        "document_id",
        "attempt_number",
    ) in unique_constraints


def test_document_page_has_unique_page_constraint() -> None:
    table = DocumentPage.__table__

    unique_constraints = {
        tuple(
            column.name
            for column in constraint.columns
        )
        for constraint in table.constraints
        if isinstance(
            constraint,
            UniqueConstraint,
        )
    }

    assert (
        "processing_run_id",
        "page_number",
    ) in unique_constraints


def test_processing_run_has_status_constraint() -> None:
    table = DocumentProcessingRun.__table__

    check_constraints = {
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(
            constraint,
            CheckConstraint,
        )
    }

    assert any(
        "queued" in constraint
        and "running" in constraint
        and "completed" in constraint
        and "failed" in constraint
        for constraint in check_constraints
    )


def test_document_page_has_confidence_constraint() -> None:
    table = DocumentPage.__table__

    check_constraints = {
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(
            constraint,
            CheckConstraint,
        )
    }

    assert any(
        "confidence_score" in constraint
        and "BETWEEN 0 AND 1" in constraint
        for constraint in check_constraints
    )