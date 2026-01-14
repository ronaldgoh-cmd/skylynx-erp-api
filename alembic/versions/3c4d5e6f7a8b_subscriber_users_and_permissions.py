"""subscriber users and tenant permissions

Revision ID: 3c4d5e6f7a8b
Revises: 2f6b1d9c3a1e
Create Date: 2026-11-02 09:00:00.000000

"""

from datetime import datetime
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "3c4d5e6f7a8b"
down_revision = "2f6b1d9c3a1e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("first_name", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(length=100), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "account_type",
            sa.String(length=32),
            nullable=False,
            server_default="user",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    user_table = sa.table(
        "users",
        sa.column("account_type", sa.String),
        sa.column("must_change_password", sa.Boolean),
    )
    connection = op.get_bind()
    connection.execute(
        sa.update(user_table)
        .where(user_table.c.account_type.is_(None))
        .values(account_type="user")
    )
    connection.execute(
        sa.update(user_table)
        .where(user_table.c.must_change_password.is_(None))
        .values(must_change_password=False)
    )

    permission_table = sa.table(
        "permissions",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String),
        sa.column("description", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )

    permission_defs = [
        ("tenant_users:read", "Read tenant users"),
        ("tenant_users:write", "Create tenant users"),
        ("tenant_users:reset_password", "Reset tenant user passwords"),
    ]
    permission_codes = [code for code, _ in permission_defs]

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
        "tenant_users:read",
        "tenant_users:write",
        "tenant_users:reset_password",
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

    op.drop_column("users", "must_change_password")
    op.drop_column("users", "account_type")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
