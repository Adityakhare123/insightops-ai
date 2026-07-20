from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.db.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Authenticated InsightOps AI user."""

    __tablename__ = "users"

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "email",
            name="uq_users_workspace_email",
        ),
        Index(
            "ix_users_workspace_role",
            "workspace_id",
            "role",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "workspaces.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default=text("'business_user'"),
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )