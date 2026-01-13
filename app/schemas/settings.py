from datetime import datetime
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field


class CompanySettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: uuid.UUID
    company_name: str
    details_line1: str | None = None
    details_line2: str | None = None
    logo_url: str | None = None
    about_text: str | None = None
    version: str | None = None
    updated_at: datetime | None = None


class CompanySettingsUpdateRequest(BaseModel):
    company_name: str | None = Field(default=None, max_length=255)
    details_line1: str | None = Field(default=None, max_length=255)
    details_line2: str | None = Field(default=None, max_length=255)
    logo_url: str | None = Field(default=None, max_length=512)
    about_text: str | None = None
    version: str | None = Field(default=None, max_length=50)


class UserSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    timezone: str
    theme: str
    updated_at: datetime | None = None


class UserSettingsUpdateRequest(BaseModel):
    timezone: str | None = Field(default=None, max_length=64)
    theme: Literal["light", "dark"] | None = None
