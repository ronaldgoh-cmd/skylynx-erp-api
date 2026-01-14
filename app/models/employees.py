import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import Base


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint("tenant_id", "employee_code", name="uq_employee_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    employee_code: Mapped[str] = mapped_column(String(32), nullable=False)
    # Deprecated: keep for backward compatibility; do not use for auth.
    is_user: Mapped[bool] = mapped_column(Boolean, default=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    contact_number: Mapped[str | None] = mapped_column(String(50))
    address: Mapped[str | None] = mapped_column(Text)
    id_type: Mapped[str | None] = mapped_column(String(50))
    id_number: Mapped[str | None] = mapped_column(String(100))
    gender: Mapped[str | None] = mapped_column(String(20))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    race: Mapped[str | None] = mapped_column(String(50))
    country: Mapped[str | None] = mapped_column(String(50))
    residency: Mapped[str | None] = mapped_column(String(50))
    pr_date: Mapped[date | None] = mapped_column(Date)
    employment_status: Mapped[str | None] = mapped_column(String(50))
    employment_pass: Mapped[str | None] = mapped_column(String(50))
    work_permit_number: Mapped[str | None] = mapped_column(String(100))
    position: Mapped[str | None] = mapped_column(String(100))
    employment_type: Mapped[str | None] = mapped_column(String(50))
    join_date: Mapped[date | None] = mapped_column(Date)
    exit_date: Mapped[date | None] = mapped_column(Date)
    holiday_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("holiday_groups.id")
    )
    bank_name: Mapped[str | None] = mapped_column(String(100))
    bank_account_number: Mapped[str | None] = mapped_column(String(100))
    incentives: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    allowance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    overtime_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    part_time_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    levy: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    salary_history: Mapped[list["EmployeeSalaryHistory"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan"
    )
    work_schedule: Mapped[list["EmployeeWorkSchedule"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan"
    )
    holiday_group: Mapped["HolidayGroup"] = relationship("HolidayGroup")


class EmployeeSalaryHistory(Base):
    __tablename__ = "employee_salary_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)

    employee: Mapped["Employee"] = relationship(back_populates="salary_history")


class EmployeeWorkSchedule(Base):
    __tablename__ = "employee_work_schedule"
    __table_args__ = (
        UniqueConstraint("employee_id", "day_of_week", name="uq_employee_day"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    day_type: Mapped[str] = mapped_column(String(10), nullable=False)

    employee: Mapped["Employee"] = relationship(back_populates="work_schedule")


class EmployeeSettings(Base):
    __tablename__ = "employee_settings"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True
    )
    id_prefix: Mapped[str] = mapped_column(String(10), default="EMP")
    zero_padding: Mapped[int] = mapped_column(Integer, default=5)
    next_sequence: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
