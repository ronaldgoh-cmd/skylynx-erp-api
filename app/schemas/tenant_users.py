from datetime import datetime
from typing import Literal
import uuid

from pydantic import BaseModel, EmailStr, Field

AccountType = Literal["subscriber", "user"]


class TenantUserListItem(BaseModel):
    id: uuid.UUID
    first_name: str | None = None
    last_name: str | None = None
    email: str
    account_type: AccountType
    created_at: datetime | None = None
    roles: list[str] = Field(default_factory=list)
    must_change_password: bool


class TenantUserCreateRequest(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    employee_id: uuid.UUID | None = None


class TenantUserCreateResponse(BaseModel):
    id: uuid.UUID
    email: str
    temp_password: str


class TenantUserResetPasswordResponse(BaseModel):
    user_id: uuid.UUID
    temp_password: str


class TenantUserEmployeeSummary(BaseModel):
    id: uuid.UUID
    full_name: str
    employee_code: str


class TenantUserUpdateRequest(BaseModel):
    employee_id: uuid.UUID | None = None


class TenantUserResponse(BaseModel):
    id: uuid.UUID
    first_name: str | None = None
    last_name: str | None = None
    email: str
    account_type: AccountType
    created_at: datetime | None = None
    roles: list[str] = Field(default_factory=list)
    must_change_password: bool
    employee: TenantUserEmployeeSummary | None = None
