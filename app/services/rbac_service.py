from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rbac import Permission, Role, RolePermission, UserRole
from models import Tenant, User

DEFAULT_MANAGER_PERMISSIONS = {
    "erp:dashboard:read",
    "rbac:permissions:read",
    "rbac:roles:read",
}
DEFAULT_STAFF_PERMISSIONS = {"erp:dashboard:read"}


def create_default_roles_for_tenant(db: Session, tenant: Tenant, user: User) -> None:
    permissions = db.scalars(select(Permission)).all()
    if not permissions:
        raise RuntimeError("No permissions found; run RBAC migrations first.")

    permission_map = {perm.code: perm for perm in permissions}

    missing_manager = DEFAULT_MANAGER_PERMISSIONS - set(permission_map.keys())
    missing_staff = DEFAULT_STAFF_PERMISSIONS - set(permission_map.keys())
    if missing_manager or missing_staff:
        missing = sorted(missing_manager | missing_staff)
        raise RuntimeError(f"Missing permissions: {', '.join(missing)}")

    admin_role = Role(
        tenant_id=tenant.id,
        name="Admin",
        description="Full access",
    )
    manager_role = Role(
        tenant_id=tenant.id,
        name="Manager",
        description="Operational access",
    )
    staff_role = Role(
        tenant_id=tenant.id,
        name="Staff",
        description="Limited access",
    )

    db.add_all([admin_role, manager_role, staff_role])

    admin_permissions = [
        RolePermission(role=admin_role, permission=perm) for perm in permissions
    ]
    manager_permissions = [
        RolePermission(role=manager_role, permission=permission_map[code])
        for code in sorted(DEFAULT_MANAGER_PERMISSIONS)
    ]
    staff_permissions = [
        RolePermission(role=staff_role, permission=permission_map[code])
        for code in sorted(DEFAULT_STAFF_PERMISSIONS)
    ]

    db.add_all(admin_permissions + manager_permissions + staff_permissions)
    db.add(UserRole(user=user, role=admin_role))


def update_role_permissions(
    db: Session, role: Role, permission_codes: list[str]
) -> list[str]:
    desired_codes = sorted({code.strip() for code in permission_codes if code.strip()})
    if not desired_codes:
        role.permissions = []
        return []

    permissions = db.scalars(
        select(Permission).where(Permission.code.in_(desired_codes))
    ).all()
    permission_map = {perm.code: perm for perm in permissions}
    missing = [code for code in desired_codes if code not in permission_map]
    if missing:
        raise ValueError(f"Unknown permission codes: {', '.join(missing)}")

    role.permissions = [
        RolePermission(permission=permission_map[code]) for code in desired_codes
    ]
    return desired_codes
