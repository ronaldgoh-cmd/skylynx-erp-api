import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import Base


class LeaveType(Base):
    __tablename__ = "leave_types"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_leave_type_name"),
        UniqueConstraint("tenant_id", "code", name="uq_leave_type_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text)
    is_prorated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_annual_reset: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    defaults: Mapped[list["LeaveDefaultEntitlement"]] = relationship(
        back_populates="leave_type", cascade="all, delete-orphan"
    )
    entitlements: Mapped[list["EmployeeLeaveEntitlement"]] = relationship(
        back_populates="leave_type", cascade="all, delete-orphan"
    )


class LeaveDefaultEntitlement(Base):
    __tablename__ = "leave_default_entitlements"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "leave_type_id",
            "service_year",
            name="uq_leave_default_entitlement",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    leave_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leave_types.id"), nullable=False
    )
    service_year: Mapped[int] = mapped_column(Integer, nullable=False)
    days: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)

    leave_type: Mapped["LeaveType"] = relationship(back_populates="defaults")


class EmployeeLeaveEntitlement(Base):
    __tablename__ = "employee_leave_entitlements"
    __table_args__ = (
        UniqueConstraint(
            "employee_id",
            "leave_type_id",
            "service_year",
            name="uq_employee_leave_entitlement",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False
    )
    leave_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leave_types.id"), nullable=False
    )
    service_year: Mapped[int] = mapped_column(Integer, nullable=False)
    entitlement_days: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    used_days: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), default=Decimal("0"), nullable=False
    )
    adjusted_days: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), default=Decimal("0"), nullable=False
    )

    employee: Mapped["Employee"] = relationship("Employee", back_populates="leave_entitlements")
    leave_type: Mapped["LeaveType"] = relationship(back_populates="entitlements")
