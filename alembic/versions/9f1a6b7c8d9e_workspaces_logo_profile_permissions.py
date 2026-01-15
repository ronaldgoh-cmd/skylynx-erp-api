"""workspaces logo profile permissions

Revision ID: 9f1a6b7c8d9e
Revises: 3c4d5e6f7a8b
Create Date: 2026-11-03 09:00:00.000000

"""

from datetime import datetime
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "9f1a6b7c8d9e"
down_revision = "3c4d5e6f7a8b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_owner", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "tenant_id", name="uq_user_workspace"),
    )

    op.add_column(
        "company_settings", sa.Column("logo_bytes", postgresql.BYTEA(), nullable=True)
    )
    op.add_column(
        "company_settings", sa.Column("logo_mime", sa.String(length=100), nullable=True)
    )

    permission_table = sa.table(
        "permissions",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String),
        sa.column("description", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    permission_defs = [
        ("workspaces:read", "Read workspaces"),
        ("workspaces:write", "Manage workspaces"),
        ("profile:read", "Read profile"),
        ("profile:write", "Update profile"),
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
    permission_rows = connection.execute(
        sa.select(permission_table.c.id, permission_table.c.code).where(
            permission_table.c.code.in_(permission_codes)
        )
    ).all()
    permission_ids = [row[0] for row in permission_rows]
    if admin_role_ids and permission_ids:
        existing_pairs = {
            (row[0], row[1])
            for row in connection.execute(
                sa.select(
                    role_permission_table.c.role_id,
                    role_permission_table.c.permission_id,
                ).where(
                    role_permission_table.c.role_id.in_(admin_role_ids),
                    role_permission_table.c.permission_id.in_(permission_ids),
                )
            ).all()
        }
        new_rows = []
        for role_id in admin_role_ids:
            for perm_id in permission_ids:
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

    user_workspace_table = sa.table(
        "user_workspaces",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("user_id", postgresql.UUID(as_uuid=True)),
        sa.column("tenant_id", postgresql.UUID(as_uuid=True)),
        sa.column("is_owner", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    user_table = sa.table(
        "users",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("tenant_id", postgresql.UUID(as_uuid=True)),
        sa.column("account_type", sa.String),
    )
    existing_links = {
        (row[0], row[1])
        for row in connection.execute(
            sa.select(user_workspace_table.c.user_id, user_workspace_table.c.tenant_id)
        ).all()
    }
    user_rows = connection.execute(
        sa.select(
            user_table.c.id,
            user_table.c.tenant_id,
            user_table.c.account_type,
        )
    ).all()
    new_links = []
    now = datetime.utcnow()
    for user_id, tenant_id, account_type in user_rows:
        if not user_id or not tenant_id:
            continue
        if (user_id, tenant_id) in existing_links:
            continue
        new_links.append(
            {
                "id": uuid.uuid4(),
                "user_id": user_id,
                "tenant_id": tenant_id,
                "is_owner": account_type == "subscriber",
                "created_at": now,
            }
        )
    if new_links:
        op.bulk_insert(user_workspace_table, new_links)


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
        "workspaces:read",
        "workspaces:write",
        "profile:read",
        "profile:write",
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

    op.drop_column("company_settings", "logo_mime")
    op.drop_column("company_settings", "logo_bytes")
    op.drop_table("user_workspaces")
