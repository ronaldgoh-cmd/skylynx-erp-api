import uuid

from pydantic import BaseModel, ConfigDict, Field


class DropdownOptionCreateRequest(BaseModel):
    category: str = Field(..., max_length=100)
    value: str = Field(..., max_length=255)
    sort_order: int = 0


class DropdownOptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: str
    value: str
    sort_order: int
