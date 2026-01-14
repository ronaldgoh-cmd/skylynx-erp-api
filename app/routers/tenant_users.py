import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.rbac import Role, UserRole
from app.schemas.tenant_users import (
    TenantUserCreateRequest,
    TenantUserCreateResponse,
    TenantUserListItem,
    TenantUserResetPasswordResponse,
)
from app.security.rbac import require_permissions
from db import get_db
from models import User
from security import PasswordTooLongError, generate_temporary_password, hash_password

router = APIRouter(prefix="/tenant/users", tags=["tenant-users"])
DEFAULT_TENANT_USER_ROLE = os.getenv("DEFAULT_TENANT_USER_ROLE", "Staff")


def _build_full_name(first_name: str, last_name: str) -> str:
    parts = [first_name.strip(), last_name.strip()]
    return " ".join([part for part in parts if part])


@router.get("", response_model=list[TenantUserListItem])
def list_tenant_users(
    user: User = Depends(require_permissions("tenant_users:read")),
    db: Session = Depends(get_db),
) -> list[TenantUserListItem]:
    users = db.scalars(
        select(User).where(User.tenant_id == user.tenant_id).order_by(User.created_at)
    ).all()
    if not users:
        return []

    user_ids = [user_item.id for user_item in users]
    role_rows = db.execute(
        select(UserRole.user_id, Role.name)
        .join(Role, Role.id == UserRole.role_id)
        .where(UserRole.user_id.in_(user_ids))
    ).all()
    roles_by_user: dict[UUID, list[str]] = {user_id: [] for user_id in user_ids}
    for user_id, role_name in role_rows:
        roles_by_user[user_id].append(role_name)

    return [
        TenantUserListItem(
            id=user_item.id,
            first_name=user_item.first_name,
            last_name=user_item.last_name,
            email=user_item.email,
            account_type=user_item.account_type,
            created_at=user_item.created_at,
            roles=roles_by_user.get(user_item.id, []),
            must_change_password=user_item.must_change_password,
        )
        for user_item in users
    ]


@router.post("", response_model=TenantUserCreateResponse, status_code=status.HTTP_201_CREATED)
def create_tenant_user(
    payload: TenantUserCreateRequest,
    user: User = Depends(require_permissions("tenant_users:write")),
    db: Session = Depends(get_db),
) -> TenantUserCreateResponse:
    staff_role = db.scalar(
        select(Role).where(Role.tenant_id == user.tenant_id, Role.name == DEFAULT_TENANT_USER_ROLE)
    )
    if not staff_role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Default role '{DEFAULT_TENANT_USER_ROLE}' not found for tenant.",
        )

    temp_password = generate_temporary_password()
    try:
        password_hash = hash_password(temp_password)
    except PasswordTooLongError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    new_user = User(
        tenant_id=user.tenant_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        full_name=_build_full_name(payload.first_name, payload.last_name),
        email=payload.email,
        account_type="user",
        must_change_password=True,
        password_hash=password_hash,
    )
    db.add(new_user)
    try:
        db.flush()
        db.add(UserRole(user_id=new_user.id, role_id=staff_role.id))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered.",
        ) from exc

    return TenantUserCreateResponse(
        id=new_user.id,
        email=new_user.email,
        temp_password=temp_password,
    )


@router.post(
    "/{user_id}/reset-password",
    response_model=TenantUserResetPasswordResponse,
)
def reset_tenant_user_password(
    user_id: UUID,
    user: User = Depends(require_permissions("tenant_users:reset_password")),
    db: Session = Depends(get_db),
) -> TenantUserResetPasswordResponse:
    target_user = db.scalar(
        select(User).where(User.id == user_id, User.tenant_id == user.tenant_id)
    )
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    temp_password = generate_temporary_password()
    try:
        target_user.password_hash = hash_password(temp_password)
    except PasswordTooLongError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    target_user.must_change_password = True
    db.commit()

    return TenantUserResetPasswordResponse(
        user_id=target_user.id,
        temp_password=temp_password,
    )
