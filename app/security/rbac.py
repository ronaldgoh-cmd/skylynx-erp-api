import uuid

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.security.auth import get_current_user
from db import get_db
from models import User


class MissingPermissionsError(Exception):
    def __init__(self, missing_permissions: list[str]) -> None:
        super().__init__("Missing permissions.")
        self.missing_permissions = missing_permissions


def get_user_permission_codes(db: Session, user_id: uuid.UUID) -> list[str]:
    stmt = (
        select(Permission.code)
        .join(RolePermission, Permission.id == RolePermission.permission_id)
        .join(Role, Role.id == RolePermission.role_id)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )
    codes = db.scalars(stmt).all()
    return sorted(set(codes))


def require_permissions(*codes: str):
    required = [code for code in codes if code]

    def _dependency(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if not required:
            return user

        user_codes = get_user_permission_codes(db, user.id)
        missing = [code for code in required if code not in user_codes]
        if missing:
            raise MissingPermissionsError(missing)
        return user

    return _dependency
