from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.schemas.workspaces import (
    WorkspaceCreateRequest,
    WorkspaceCreateResponse,
    WorkspaceListItem,
    WorkspaceSelectRequest,
    WorkspaceSelectResponse,
)
from app.security.auth import get_current_user
from app.security.rbac import require_permissions
from app.services.rbac_service import create_default_roles_for_tenant
from db import get_db
from models import Tenant, User, UserWorkspace
from security import create_access_token

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("", response_model=list[WorkspaceListItem])
def list_workspaces(
    user: User = Depends(require_permissions("workspaces:read")),
    db: Session = Depends(get_db),
) -> list[WorkspaceListItem]:
    rows = db.execute(
        select(UserWorkspace.tenant_id, Tenant.company_name, UserWorkspace.is_owner)
        .join(Tenant, Tenant.id == UserWorkspace.tenant_id)
        .where(UserWorkspace.user_id == user.id)
        .order_by(Tenant.company_name)
    ).all()
    return [
        WorkspaceListItem(
            tenant_id=tenant_id,
            company_name=company_name,
            is_owner=is_owner,
        )
        for tenant_id, company_name, is_owner in rows
    ]


@router.post("", response_model=WorkspaceCreateResponse, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreateRequest,
    user: User = Depends(require_permissions("workspaces:write")),
    db: Session = Depends(get_db),
) -> WorkspaceCreateResponse:
    tenant = Tenant(company_name=payload.company_name)
    db.add(tenant)
    try:
        db.flush()
        db.add(UserWorkspace(user_id=user.id, tenant_id=tenant.id, is_owner=True))
        create_default_roles_for_tenant(db, tenant, user)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to create workspace.",
        ) from exc
    except RuntimeError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return WorkspaceCreateResponse(tenant_id=tenant.id, company_name=tenant.company_name)


@router.post("/select", response_model=WorkspaceSelectResponse)
def select_workspace(
    payload: WorkspaceSelectRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceSelectResponse:
    membership = db.scalar(
        select(UserWorkspace).where(
            UserWorkspace.user_id == user.id,
            UserWorkspace.tenant_id == payload.tenant_id,
        )
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found.",
        )

    token = create_access_token(subject=str(user.id), tenant_id=str(payload.tenant_id))
    return WorkspaceSelectResponse(token=token)
