from datetime import datetime
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field


WorkScheduleMode = Literal["group", "custom"]
WorkScheduleDayType = Literal["off", "full", "half"]


class WorkScheduleEntry(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6)
    day_type: WorkScheduleDayType


class WorkScheduleEntriesResponse(BaseModel):
    entries: list[WorkScheduleEntry]


class EmployeeWorkScheduleResponse(BaseModel):
    mode: WorkScheduleMode
    work_schedule_group_id: uuid.UUID | None = None
    days: list[WorkScheduleEntry]


class EmployeeWorkScheduleUpdateRequest(BaseModel):
    mode: WorkScheduleMode
    work_schedule_group_id: uuid.UUID | None = None
    custom_days: list[WorkScheduleEntry] | None = None


class WorkScheduleGroupCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class WorkScheduleGroupUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class WorkScheduleGroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None = None
    created_at: datetime | None = None
