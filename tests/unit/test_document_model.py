from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    UniqueConstraint,
)

from apps.api.app.db import models  # noqa: F401
from apps.api.app.db.base import Base


def test_document_table_is_registered() -> None:
    assert "documents" in Base.metadata.tables


def test_document_has_required_columns() -> None:
    document_table = Base.metadata.tables["documents"]

    expected_columns = {
        "id",
        "workspace_id",
        "uploaded_by_user_id",
        "original_filename",
        "storage_bucket",
        "storage_object_name",
        "content_type",
        "file_extension",
        "file_size_bytes",
        "checksum_sha256",
        "source",
        "document_type",
        "status",
        "processing_error",
        "page_count",
        "extra_metadata",
        "created_at",
        "updated_at",
    }

    assert expected_columns.issubset(
        set(document_table.columns.keys())
    )


def test_document_belongs_to_workspace() -> None:
    document_table = Base.metadata.tables["documents"]

    foreign_keys = {
        foreign_key.target_fullname
        for foreign_key in document_table.columns[
            "workspace_id"
        ].foreign_keys
    }

    assert "workspaces.id" in foreign_keys


def test_document_references_uploading_user() -> None:
    document_table = Base.metadata.tables["documents"]

    foreign_keys = {
        foreign_key.target_fullname
        for foreign_key in document_table.columns[
            "uploaded_by_user_id"
        ].foreign_keys
    }

    assert "users.id" in foreign_keys


def test_storage_object_is_unique_inside_workspace() -> None:
    document_table = Base.metadata.tables["documents"]

    unique_constraints = {
        tuple(
            column.name
            for column in constraint.columns
        )
        for constraint in document_table.constraints
        if isinstance(
            constraint,
            UniqueConstraint,
        )
    }

    assert (
        "workspace_id",
        "storage_object_name",
    ) in unique_constraints


def test_document_size_cannot_be_negative() -> None:
    document_table = Base.metadata.tables["documents"]

    check_constraint_names = {
        constraint.name
        for constraint in document_table.constraints
        if isinstance(
            constraint,
            CheckConstraint,
        )
    }

    assert (
        "ck_documents_file_size_non_negative"
        in check_constraint_names
    )


def test_document_status_has_default() -> None:
    document_table = Base.metadata.tables["documents"]

    assert (
        document_table.columns["status"].server_default
        is not None
    )


def test_document_metadata_is_required() -> None:
    document_table = Base.metadata.tables["documents"]

    assert (
        document_table.columns["extra_metadata"].nullable
        is False
    )