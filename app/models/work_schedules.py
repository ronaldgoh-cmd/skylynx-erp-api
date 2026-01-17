import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import Base


class WorkScheduleGroup(Base):
    __tablename__ = "work_schedule_groups"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_work_schedule_group_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    days: Mapped[list["WorkScheduleGroupDay"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )
    employees: Mapped[list["Employee"]] = relationship("Employee", back_populates="work_schedule_group")


class WorkScheduleGroupDay(Base):
    __tablename__ = "work_schedule_group_days"
    __table_args__ = (
        UniqueConstraint("group_id", "day_of_week", name="uq_work_schedule_group_day"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("work_schedule_groups.id"), nullable=False
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    day_type: Mapped[str] = mapped_column(String(10), nullable=False)

    group: Mapped["WorkScheduleGroup"] = relationship(back_populates="days")
