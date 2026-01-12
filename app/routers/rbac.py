import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rbac import Permission, Role
from app.schemas.rbac import (
    PermissionOut,
    RbacMeResponse,
    RoleOut,
    RolePermissionsUpdateRequest,
    RolePermissionsUpdateResponse,
)
from app.security.auth import get_current_user
from app.security.rbac import get_user_permission_codes, require_permissions
from app.services.rbac_service import update_role_permissions
from db import get_db
from models import User

router = APIRouter(prefix="/rbac", tags=["rbac"])


@router.get("/me", response_model=RbacMeResponse)
def rbac_me(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RbacMeResponse:
    permissions = get_user_permission_codes(db, user.id)
    return RbacMeResponse(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        permissions=permissions,
    )


@router.get(
    "/permissions",
    response_model=list[PermissionOut],
    dependencies=[Depends(require_permissions("rbac:permissions:read"))],
)
def list_permissions(db: Session = Depends(get_db)) -> list[PermissionOut]:
    permissions = db.scalars(select(Permission).order_by(Permission.code)).all()
    return permissions


@router.get(
    "/roles",
    response_model=list[RoleOut],
)
def list_roles(
    user: User = Depends(require_permissions("rbac:roles:read")),
    db: Session = Depends(get_db),
) -> list[RoleOut]:
    roles = db.scalars(
        select(Role).where(Role.tenant_id == user.tenant_id).order_by(Role.name)
    ).all()
    return roles


@router.post(
    "/roles/{role_id}/permissions",
    response_model=RolePermissionsUpdateResponse,
)
def replace_role_permissions(
    role_id: str,
    payload: RolePermissionsUpdateRequest,
    user: User = Depends(require_permissions("rbac:roles:write")),
    db: Session = Depends(get_db),
) -> RolePermissionsUpdateResponse:
    try:
        role_uuid = uuid.UUID(role_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid role ID.",
        ) from exc

    role = db.scalar(
        select(Role).where(Role.id == role_uuid, Role.tenant_id == user.tenant_id)
    )
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found.",
        )

    try:
        codes = update_role_permissions(db, role, payload.permission_codes)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    db.commit()
    return RolePermissionsUpdateResponse(role_id=str(role.id), permission_codes=codes)
