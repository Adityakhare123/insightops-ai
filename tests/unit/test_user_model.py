from __future__ import annotations

from sqlalchemy import UniqueConstraint

from apps.api.app.db import models  # noqa: F401
from apps.api.app.db.base import Base


def test_user_table_is_registered() -> None:
    assert "users" in Base.metadata.tables


def test_user_has_required_columns() -> None:
    user_table = Base.metadata.tables["users"]

    expected_columns = {
        "id",
        "workspace_id",
        "email",
        "full_name",
        "password_hash",
        "role",
        "is_active",
        "created_at",
        "updated_at",
    }

    assert expected_columns.issubset(
        set(user_table.columns.keys())
    )


def test_user_email_is_unique_inside_workspace() -> None:
    user_table = Base.metadata.tables["users"]

    unique_constraints = [
        constraint
        for constraint in user_table.constraints
        if isinstance(constraint, UniqueConstraint)
    ]

    constraint_columns = {
        tuple(
            column.name
            for column in constraint.columns
        )
        for constraint in unique_constraints
    }

    assert (
        "workspace_id",
        "email",
    ) in constraint_columns


def test_user_password_hash_is_not_nullable() -> None:
    user_table = Base.metadata.tables["users"]

    assert (
        user_table.columns["password_hash"].nullable
        is False
    )


def test_user_belongs_to_workspace() -> None:
    user_table = Base.metadata.tables["users"]

    workspace_foreign_keys = {
        foreign_key.target_fullname
        for foreign_key in user_table.columns[
            "workspace_id"
        ].foreign_keys
    }

    assert "workspaces.id" in workspace_foreign_keys


def test_user_role_has_default_value() -> None:
    user_table = Base.metadata.tables["users"]
    role_column = user_table.columns["role"]

    assert role_column.server_default is not None


def test_user_is_active_has_default_value() -> None:
    user_table = Base.metadata.tables["users"]
    is_active_column = user_table.columns["is_active"]

    assert is_active_column.server_default is not None