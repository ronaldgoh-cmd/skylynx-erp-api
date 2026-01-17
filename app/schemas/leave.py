from datetime import datetime
from decimal import Decimal
import uuid

from pydantic import BaseModel, ConfigDict, Field


class LeaveTypeCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str | None = Field(default=None, max_length=50)
    description: str | None = None
    is_prorated: bool = False
    is_annual_reset: bool = True


class LeaveTypeUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, max_length=50)
    description: str | None = None
    is_prorated: bool | None = None
    is_annual_reset: bool | None = None


class LeaveTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    code: str | None = None
    description: str | None = None
    is_prorated: bool
    is_annual_reset: bool
    created_at: datetime | None = None


class LeaveDefaultRow(BaseModel):
    service_year: int = Field(..., ge=1, le=50)
    days: Decimal = Field(..., ge=0)


class LeaveDefaultBulkUpdateRequest(BaseModel):
    leave_type_id: uuid.UUID
    rows: list[LeaveDefaultRow]


class LeaveDefaultEntitlementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    leave_type_id: uuid.UUID
    service_year: int
    days: Decimal


class EmployeeLeaveEntitlementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    service_year: int
    entitlement_days: Decimal
    used_days: Decimal
    adjusted_days: Decimal


class LeaveEntitlementsLoadResponse(BaseModel):
    created: int
    updated: int
