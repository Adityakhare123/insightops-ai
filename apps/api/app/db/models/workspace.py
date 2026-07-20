from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Numeric,
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


class Workspace(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Represents an organization using InsightOps AI."""

    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        unique=True,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )


class Carrier(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Insurance carrier master data."""

    __tablename__ = "insurance_carriers"

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "code",
            name="uq_insurance_carriers_workspace_code",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )


class Plan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Insurance plan offered by a carrier."""

    __tablename__ = "insurance_plans"

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "code",
            name="uq_insurance_plans_workspace_code",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    carrier_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("insurance_carriers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    plan_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    monthly_premium: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )


class Agent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Insurance agent responsible for policy sales."""

    __tablename__ = "insurance_agents"

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "npn",
            name="uq_insurance_agents_workspace_npn",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    npn: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    first_name: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    last_name: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    state: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )


class Customer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Synthetic insurance customer."""

    __tablename__ = "insurance_customers"

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "customer_number",
            name="uq_insurance_customers_workspace_number",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    customer_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    first_name: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    last_name: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    date_of_birth: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    phone: Mapped[str] = mapped_column(
        String(25),
        nullable=False,
    )

    state: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
    )


class Policy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Policy record imported from a business data source."""

    __tablename__ = "insurance_policies"

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "source_system",
            "source_record_id",
            name="uq_insurance_policies_workspace_source_record",
        ),
        Index(
            "ix_insurance_policies_workspace_policy_number",
            "workspace_id",
            "policy_number",
        ),
        Index(
            "ix_insurance_policies_workspace_status",
            "workspace_id",
            "status",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )

    source_record_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    policy_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    customer_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("insurance_customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    carrier_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("insurance_carriers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    plan_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("insurance_plans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    agent_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("insurance_agents.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    submitted_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    effective_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    premium: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    source_system: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )


class Payment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Premium payment received for a policy."""

    __tablename__ = "insurance_payments"

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "source_record_id",
            name="uq_insurance_payments_workspace_source_record",
        ),
        Index(
            "ix_insurance_payments_workspace_policy",
            "workspace_id",
            "policy_id",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )

    source_record_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    policy_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("insurance_policies.id", ondelete="CASCADE"),
        nullable=False,
    )

    payment_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    payment_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )


class Commission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Commission earned by an agent for a policy."""

    __tablename__ = "insurance_commissions"

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "source_record_id",
            name="uq_insurance_commissions_workspace_source_record",
        ),
        Index(
            "ix_insurance_commissions_workspace_policy",
            "workspace_id",
            "policy_id",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )

    source_record_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    policy_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("insurance_policies.id", ondelete="CASCADE"),
        nullable=False,
    )

    agent_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("insurance_agents.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    statement_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    commission_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    gross_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    net_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )