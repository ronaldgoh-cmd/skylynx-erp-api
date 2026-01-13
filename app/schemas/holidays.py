from datetime import date
import uuid

from pydantic import BaseModel, ConfigDict, Field


class HolidayGroupCreateRequest(BaseModel):
    name: str = Field(..., max_length=100)


class HolidayGroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class HolidayCreateRequest(BaseModel):
    name: str = Field(..., max_length=255)
    date: date
    holiday_group_id: uuid.UUID | None = None


class HolidayResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    date: date
    holiday_group_id: uuid.UUID | None = None


class HolidayImportRequest(BaseModel):
    holiday_group_id: uuid.UUID | None = None
    csv_text: str


class HolidayImportResponse(BaseModel):
    inserted: int
    skipped_invalid: int
