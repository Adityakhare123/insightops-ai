from __future__ import annotations

from uuid import uuid4

import pytest

from apps.api.app.services.storage import (
    StorageError,
    build_storage_object_name,
    sanitize_filename,
    upload_bytes,
)


def test_sanitize_filename_preserves_safe_characters() -> None:
    filename = "policy_report-2026_07.pdf"

    assert sanitize_filename(filename) == filename


def test_sanitize_filename_removes_directory_path() -> None:
    filename = "../../private/customer-report.pdf"

    assert sanitize_filename(filename) == (
        "customer-report.pdf"
    )


def test_sanitize_filename_replaces_unsafe_characters() -> None:
    filename = "Policy Report (Final) #1.pdf"

    assert sanitize_filename(filename) == (
        "Policy-Report-Final-1.pdf"
    )


def test_sanitize_filename_collapses_repeated_dashes() -> None:
    filename = "policy   report---final.pdf"

    assert sanitize_filename(filename) == (
        "policy-report-final.pdf"
    )


@pytest.mark.parametrize(
    "filename",
    [
        "",
        "   ",
        "...",
        "---",
        "___",
    ],
)
def test_sanitize_filename_returns_fallback(
    filename: str,
) -> None:
    assert sanitize_filename(filename) == "uploaded-file"


def test_build_storage_object_name_is_workspace_scoped() -> None:
    workspace_id = uuid4()
    document_id = uuid4()

    object_name = build_storage_object_name(
        workspace_id=workspace_id,
        document_id=document_id,
        filename="Policy Report.pdf",
    )

    expected_prefix = (
        f"workspaces/{workspace_id}/"
        f"documents/{document_id}/"
    )

    assert object_name.startswith(expected_prefix)
    assert object_name.endswith(
        "-Policy-Report.pdf"
    )


def test_build_storage_object_name_is_unique() -> None:
    workspace_id = uuid4()
    document_id = uuid4()

    first_object_name = build_storage_object_name(
        workspace_id=workspace_id,
        document_id=document_id,
        filename="report.pdf",
    )

    second_object_name = build_storage_object_name(
        workspace_id=workspace_id,
        document_id=document_id,
        filename="report.pdf",
    )

    assert first_object_name != second_object_name


def test_upload_bytes_rejects_empty_file_before_storage_call() -> None:
    with pytest.raises(
        StorageError,
        match="Cannot upload an empty object",
    ):
        upload_bytes(
            data=b"",
            object_name="documents/empty.pdf",
            content_type="application/pdf",
        )