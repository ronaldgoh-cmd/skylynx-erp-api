from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.schemas.rbac import (
    PermissionOut,
    RbacMeResponse,
    RoleCreateRequest,
    RoleOut,
    RolePermissionsResponse,
    RolePermissionsUpdateRequest,
    RolePermissionsUpdateResponse,
    RoleSummary,
    RoleUpdateRequest,
    UserListItem,
    UserRoleUpdateRequest,
    UserRoleUpdateResponse,
    UserRolesResponse,
)
from app.security.auth import get_active_tenant_id, get_current_user
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
    tenant_id = get_active_tenant_id(user)
    permissions = get_user_permission_codes(db, user.id, tenant_id)
    return RbacMeResponse(
        user_id=str(user.id),
        tenant_id=str(tenant_id),
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
        select(Role).where(Role.tenant_id == user.active_tenant_id).order_by(Role.name)
    ).all()
    return roles


@router.post(
    "/roles",
    response_model=RoleOut,
    status_code=status.HTTP_201_CREATED,
)
def create_role(
    payload: RoleCreateRequest,
    user: User = Depends(require_permissions("rbac:roles:write")),
    db: Session = Depends(get_db),
) -> RoleOut:
    role = Role(
        tenant_id=user.active_tenant_id,
        name=payload.name,
        description=payload.description,
    )
    db.add(role)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role name already exists for this tenant.",
        ) from exc

    db.refresh(role)
    return role


@router.patch(
    "/roles/{role_id}",
    response_model=RoleOut,
)
def update_role(
    role_id: UUID,
    payload: RoleUpdateRequest,
    user: User = Depends(require_permissions("rbac:roles:write")),
    db: Session = Depends(get_db),
) -> RoleOut:
    role = db.scalar(
        select(Role).where(Role.id == role_id, Role.tenant_id == user.active_tenant_id)
    )
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found.",
        )

    if payload.name is not None:
        role.name = payload.name
    if payload.description is not None:
        role.description = payload.description

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role name already exists for this tenant.",
        ) from exc

    db.refresh(role)
    return role


@router.get(
    "/roles/{role_id}/permissions",
    response_model=RolePermissionsResponse,
)
def get_role_permissions(
    role_id: UUID,
    user: User = Depends(require_permissions("rbac:roles:read")),
    db: Session = Depends(get_db),
) -> RolePermissionsResponse:
    role = db.scalar(
        select(Role).where(Role.id == role_id, Role.tenant_id == user.active_tenant_id)
    )
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found.",
        )

    codes = db.scalars(
        select(Permission.code)
        .join(RolePermission, Permission.id == RolePermission.permission_id)
        .where(RolePermission.role_id == role.id)
        .order_by(Permission.code)
    ).all()
    return RolePermissionsResponse(role_id=str(role.id), permission_codes=codes)


@router.post(
    "/roles/{role_id}/permissions",
    response_model=RolePermissionsUpdateResponse,
)
def replace_role_permissions(
    role_id: UUID,
    payload: RolePermissionsUpdateRequest,
    user: User = Depends(require_permissions("rbac:roles:write")),
    db: Session = Depends(get_db),
) -> RolePermissionsUpdateResponse:
    role = db.scalar(
        select(Role).where(Role.id == role_id, Role.tenant_id == user.active_tenant_id)
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


@router.get(
    "/users",
    response_model=list[UserListItem],
)
def list_users(
    user: User = Depends(require_permissions("rbac:users:assign_roles")),
    db: Session = Depends(get_db),
) -> list[UserListItem]:
    users = db.scalars(
        select(User)
        .where(User.tenant_id == user.active_tenant_id)
        .order_by(User.created_at)
    ).all()
    if not users:
        return []

    user_ids = [user_item.id for user_item in users]
    role_rows = db.execute(
        select(UserRole.user_id, Role.name)
        .join(Role, Role.id == UserRole.role_id)
        .where(UserRole.user_id.in_(user_ids))
        .order_by(Role.name)
    ).all()

    roles_by_user: dict[UUID, list[str]] = {user_id: [] for user_id in user_ids}
    for user_id, role_name in role_rows:
        roles_by_user[user_id].append(role_name)

    return [
        UserListItem(
            id=user_item.id,
            full_name=user_item.full_name,
            email=user_item.email,
            created_at=user_item.created_at,
            roles=roles_by_user.get(user_item.id, []),
        )
        for user_item in users
    ]


@router.get(
    "/users/{user_id}/roles",
    response_model=UserRolesResponse,
)
def get_user_roles(
    user_id: UUID,
    user: User = Depends(require_permissions("rbac:users:assign_roles")),
    db: Session = Depends(get_db),
) -> UserRolesResponse:
    target_user = db.scalar(
        select(User)
        .where(User.id == user_id, User.tenant_id == user.active_tenant_id)
    )
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    roles = db.scalars(
        select(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == target_user.id)
        .order_by(Role.name)
    ).all()
    return UserRolesResponse(
        user_id=str(target_user.id),
        roles=[RoleSummary(id=role.id, name=role.name) for role in roles],
    )


@router.put(
    "/users/{user_id}/roles",
    response_model=UserRoleUpdateResponse,
)
def update_user_roles(
    user_id: UUID,
    payload: UserRoleUpdateRequest,
    user: User = Depends(require_permissions("rbac:users:assign_roles")),
    db: Session = Depends(get_db),
) -> UserRoleUpdateResponse:
    target_user = db.scalar(
        select(User)
        .where(User.id == user_id, User.tenant_id == user.active_tenant_id)
    )
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    role_ids = list({role_id for role_id in payload.role_ids})
    roles: list[Role] = []
    if role_ids:
        roles = db.scalars(
            select(Role).where(
                Role.id.in_(role_ids), Role.tenant_id == user.active_tenant_id
            )
        ).all()
        if len(roles) != len(role_ids):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found.",
            )
    role_id_set = {role.id for role in roles}

    existing_links = db.scalars(
        select(UserRole).where(UserRole.user_id == target_user.id)
    ).all()
    existing_role_ids = {link.role_id for link in existing_links}

    if payload.mode == "replace":
        for link in existing_links:
            db.delete(link)
        for role in roles:
            db.add(UserRole(user_id=target_user.id, role_id=role.id))
    elif payload.mode == "add":
        for role in roles:
            if role.id not in existing_role_ids:
                db.add(UserRole(user_id=target_user.id, role_id=role.id))
    else:
        for link in existing_links:
            if link.role_id in role_id_set:
                db.delete(link)

    db.commit()

    updated_roles = db.scalars(
        select(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == target_user.id)
        .order_by(Role.name)
    ).all()
    return UserRoleUpdateResponse(
        user_id=str(target_user.id),
        roles=[RoleSummary(id=role.id, name=role.name) for role in updated_roles],
    )
