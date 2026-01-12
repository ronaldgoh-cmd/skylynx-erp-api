from datetime import datetime
import uuid

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


class RbacMeResponse(BaseModel):
    user_id: str
    tenant_id: str
    permissions: list[str]


class RolePermissionsUpdateRequest(BaseModel):
    permission_codes: list[str] = Field(default_factory=list)


class RolePermissionsUpdateResponse(BaseModel):
    role_id: str
    permission_codes: list[str]
