import uuid

from pydantic import BaseModel, Field


class WorkspaceListItem(BaseModel):
    tenant_id: uuid.UUID
    company_name: str
    is_owner: bool


class WorkspaceCreateRequest(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)


class WorkspaceCreateResponse(BaseModel):
    tenant_id: uuid.UUID
    company_name: str


class WorkspaceSelectRequest(BaseModel):
    tenant_id: uuid.UUID


class WorkspaceSelectResponse(BaseModel):
    token: str
