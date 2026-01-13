from datetime import datetime
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PermissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    description: str | None = None
    created_at: datetime | None = None


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    created_at: datetime | None = None


class RoleSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class RbacMeResponse(BaseModel):
    user_id: str
    tenant_id: str
    permissions: list[str]


class RolePermissionsUpdateRequest(BaseModel):
    permission_codes: list[str] = Field(default_factory=list)


class RolePermissionsUpdateResponse(BaseModel):
    role_id: str
    permission_codes: list[str]


class RoleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)


class RoleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)


class RolePermissionsResponse(BaseModel):
    role_id: str
    permission_codes: list[str]


class UserListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: str
    created_at: datetime | None = None
    roles: list[str] = Field(default_factory=list)


class UserRolesResponse(BaseModel):
    user_id: str
    roles: list[RoleSummary]


class UserRoleUpdateRequest(BaseModel):
    role_ids: list[uuid.UUID] = Field(default_factory=list)
    mode: Literal["replace", "add", "remove"] = "replace"


class UserRoleUpdateResponse(BaseModel):
    user_id: str
    roles: list[RoleSummary]
