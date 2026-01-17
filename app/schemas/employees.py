from datetime import date, datetime
from decimal import Decimal
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.work_schedules import WorkScheduleEntry, WorkScheduleMode


class EmployeeBase(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = None
    contact_number: str | None = Field(default=None, max_length=50)
    address: str | None = None
    id_type: str | None = Field(default=None, max_length=50)
    id_number: str | None = Field(default=None, max_length=100)
    gender: str | None = Field(default=None, max_length=20)
    date_of_birth: date | None = None
    race: str | None = Field(default=None, max_length=50)
    country: str | None = Field(default=None, max_length=50)
    residency: str | None = Field(default=None, max_length=50)
    pr_date: date | None = None
    employment_status: str | None = Field(default=None, max_length=50)
    employment_pass: str | None = Field(default=None, max_length=50)
    work_permit_number: str | None = Field(default=None, max_length=100)
    position: str | None = Field(default=None, max_length=100)
    department: str | None = Field(default=None, max_length=100)
    employment_type: str | None = Field(default=None, max_length=50)
    join_date: date | None = None
    exit_date: date | None = None
    holiday_group_id: uuid.UUID | None = None
    bank_name: str | None = Field(default=None, max_length=100)
    bank_account_number: str | None = Field(default=None, max_length=100)
    payment_method: str | None = Field(default=None, max_length=100)
    incentives: Decimal | None = None
    bonus: Decimal | None = None
    allowance: Decimal | None = None
    overtime_rate: Decimal | None = None
    part_time_rate: Decimal | None = None
    levy: Decimal | None = None
    user_id: uuid.UUID | None = None


class EmployeeCreateRequest(EmployeeBase):
    full_name: str = Field(..., max_length=255)


class EmployeeUpdateRequest(EmployeeBase):
    pass


class EmployeeResponse(EmployeeBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    employee_code: str
    work_schedule_mode: WorkScheduleMode | None = None
    work_schedule_group_id: uuid.UUID | None = None
    work_schedule_days: list[WorkScheduleEntry] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class EmployeeUnlinkedUserResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    employee_code: str


class EmployeeSalaryHistoryCreateRequest(BaseModel):
    amount: Decimal
    start_date: date
    end_date: date | None = None


class EmployeeSalaryHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    amount: Decimal
    start_date: date
    end_date: date | None = None


class EmployeeIdFormatResponse(BaseModel):
    id_prefix: str
    zero_padding: int
    next_sequence: int
    preview_code: str


class EmployeeIdFormatUpdateRequest(BaseModel):
    id_prefix: str | None = Field(default=None, max_length=10)
    zero_padding: int | None = Field(default=None, ge=1)
    next_sequence: int | None = Field(default=None, ge=1)
