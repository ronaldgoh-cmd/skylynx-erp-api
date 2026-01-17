"""leave foundation and work schedule groups

Revision ID: 4d5e6f7a8b9c
Revises: 1a2b3c4d5e6f
Create Date: 2026-11-17 00:00:00.000000

"""

from datetime import datetime
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "4d5e6f7a8b9c"
down_revision = "1a2b3c4d5e6f"
branch_labels = None
depends_on = None


def _employee_columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns("employees")}


def upgrade() -> None:
    op.create_table(
        "work_schedule_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_work_schedule_group_name"),
    )
    op.create_table(
        "work_schedule_group_days",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("day_type", sa.String(length=10), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["work_schedule_groups.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "day_of_week", name="uq_work_schedule_group_day"),
    )
    op.create_table(
        "leave_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_prorated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "is_annual_reset",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_leave_type_name"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_leave_type_code"),
    )
    op.create_table(
        "leave_default_entitlements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("leave_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_year", sa.Integer(), nullable=False),
        sa.Column("days", sa.Numeric(6, 2), nullable=False),
        sa.ForeignKeyConstraint(["leave_type_id"], ["leave_types.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "leave_type_id",
            "service_year",
            name="uq_leave_default_entitlement",
        ),
    )
    op.create_table(
        "employee_leave_entitlements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("leave_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_year", sa.Integer(), nullable=False),
        sa.Column("entitlement_days", sa.Numeric(6, 2), nullable=False),
        sa.Column(
            "used_days",
            sa.Numeric(6, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "adjusted_days",
            sa.Numeric(6, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["leave_type_id"], ["leave_types.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "employee_id",
            "leave_type_id",
            "service_year",
            name="uq_employee_leave_entitlement",
        ),
    )

    columns = _employee_columns()
    if "work_schedule_group_id" not in columns:
        op.add_column(
            "employees",
            sa.Column(
                "work_schedule_group_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("work_schedule_groups.id"),
                nullable=True,
            ),
        )
    if "work_schedule_mode" not in columns:
        op.add_column(
            "employees",
            sa.Column(
                "work_schedule_mode",
                sa.String(length=10),
                nullable=False,
                server_default=sa.text("'custom'"),
            ),
        )

    permission_table = sa.table(
        "permissions",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String),
        sa.column("description", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    permission_defs = [
        ("work_schedule_groups:read", "Read work schedule groups"),
        ("work_schedule_groups:write", "Manage work schedule groups"),
        ("leave_types:read", "Read leave types"),
        ("leave_types:write", "Manage leave types"),
        ("leave_defaults:read", "Read leave defaults"),
        ("leave_defaults:write", "Manage leave defaults"),
        ("leave_entitlements:read", "Read leave entitlements"),
        ("leave_entitlements:write", "Manage leave entitlements"),
    ]
    permission_codes = [code for code, _ in permission_defs]
    connection = op.get_bind()
    existing_codes = {
        row[0]
        for row in connection.execute(
            sa.select(permission_table.c.code).where(
                permission_table.c.code.in_(permission_codes)
            )
        ).all()
    }
    missing = [item for item in permission_defs if item[0] not in existing_codes]
    if missing:
        now = datetime.utcnow()
        op.bulk_insert(
            permission_table,
            [
                {
                    "id": uuid.uuid4(),
                    "code": code,
                    "description": description,
                    "created_at": now,
                }
                for code, description in missing
            ],
        )

    role_table = sa.table(
        "roles",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
    )
    role_permission_table = sa.table(
        "role_permissions",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("role_id", postgresql.UUID(as_uuid=True)),
        sa.column("permission_id", postgresql.UUID(as_uuid=True)),
    )
    admin_role_ids = [
        row[0]
        for row in connection.execute(
            sa.select(role_table.c.id).where(role_table.c.name == "Admin")
        ).all()
    ]
    manager_role_ids = [
        row[0]
        for row in connection.execute(
            sa.select(role_table.c.id).where(role_table.c.name == "Manager")
        ).all()
    ]
    permission_rows = connection.execute(
        sa.select(permission_table.c.id, permission_table.c.code).where(
            permission_table.c.code.in_(permission_codes)
        )
    ).all()
    permission_by_code = {row[1]: row[0] for row in permission_rows}

    admin_permission_ids = [permission_by_code[code] for code in permission_codes if code in permission_by_code]
    manager_permission_codes = [
        "leave_types:read",
        "leave_defaults:read",
        "leave_entitlements:read",
        "leave_entitlements:write",
        "work_schedule_groups:read",
    ]
    manager_permission_ids = [
        permission_by_code[code]
        for code in manager_permission_codes
        if code in permission_by_code
    ]

    if admin_role_ids and admin_permission_ids:
        existing_pairs = {
            (row[0], row[1])
            for row in connection.execute(
                sa.select(
                    role_permission_table.c.role_id,
                    role_permission_table.c.permission_id,
                ).where(
                    role_permission_table.c.role_id.in_(admin_role_ids),
                    role_permission_table.c.permission_id.in_(admin_permission_ids),
                )
            ).all()
        }
        new_rows = []
        for role_id in admin_role_ids:
            for perm_id in admin_permission_ids:
                if (role_id, perm_id) in existing_pairs:
                    continue
                new_rows.append(
                    {
                        "id": uuid.uuid4(),
                        "role_id": role_id,
                        "permission_id": perm_id,
                    }
                )
        if new_rows:
            op.bulk_insert(role_permission_table, new_rows)

    if manager_role_ids and manager_permission_ids:
        existing_pairs = {
            (row[0], row[1])
            for row in connection.execute(
                sa.select(
                    role_permission_table.c.role_id,
                    role_permission_table.c.permission_id,
                ).where(
                    role_permission_table.c.role_id.in_(manager_role_ids),
                    role_permission_table.c.permission_id.in_(manager_permission_ids),
                )
            ).all()
        }
        new_rows = []
        for role_id in manager_role_ids:
            for perm_id in manager_permission_ids:
                if (role_id, perm_id) in existing_pairs:
                    continue
                new_rows.append(
                    {
                        "id": uuid.uuid4(),
                        "role_id": role_id,
                        "permission_id": perm_id,
                    }
                )
        if new_rows:
            op.bulk_insert(role_permission_table, new_rows)


def downgrade() -> None:
    connection = op.get_bind()
    permission_table = sa.table(
        "permissions",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String),
    )
    role_permission_table = sa.table(
        "role_permissions",
        sa.column("permission_id", postgresql.UUID(as_uuid=True)),
    )
    permission_codes = [
        "work_schedule_groups:read",
        "work_schedule_groups:write",
        "leave_types:read",
        "leave_types:write",
        "leave_defaults:read",
        "leave_defaults:write",
        "leave_entitlements:read",
        "leave_entitlements:write",
    ]
    permission_ids = [
        row[0]
        for row in connection.execute(
            sa.select(permission_table.c.id).where(
                permission_table.c.code.in_(permission_codes)
            )
        ).all()
    ]
    if permission_ids:
        op.execute(
            sa.delete(role_permission_table).where(
                role_permission_table.c.permission_id.in_(permission_ids)
            )
        )
    op.execute(
        sa.delete(permission_table).where(permission_table.c.code.in_(permission_codes))
    )

    columns = _employee_columns()
    if "work_schedule_mode" in columns:
        op.drop_column("employees", "work_schedule_mode")
    if "work_schedule_group_id" in columns:
        op.drop_column("employees", "work_schedule_group_id")

    op.drop_table("employee_leave_entitlements")
    op.drop_table("leave_default_entitlements")
    op.drop_table("leave_types")
    op.drop_table("work_schedule_group_days")
    op.drop_table("work_schedule_groups")
