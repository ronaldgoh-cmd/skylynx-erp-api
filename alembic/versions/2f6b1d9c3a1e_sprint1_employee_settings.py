"""sprint1 employee settings

Revision ID: 2f6b1d9c3a1e
Revises: 8b9a2c0d1e7f
Create Date: 2026-11-01 18:10:00.000000

"""

from datetime import datetime
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "2f6b1d9c3a1e"
down_revision = "8b9a2c0d1e7f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_settings",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("details_line1", sa.String(length=255), nullable=True),
        sa.Column("details_line2", sa.String(length=255), nullable=True),
        sa.Column("logo_url", sa.String(length=512), nullable=True),
        sa.Column("about_text", sa.Text(), nullable=True),
        sa.Column("version", sa.String(length=50), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("tenant_id"),
    )
    op.create_table(
        "user_settings",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("theme", sa.String(length=10), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "employee_settings",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id_prefix", sa.String(length=10), nullable=True),
        sa.Column("zero_padding", sa.Integer(), nullable=True),
        sa.Column("next_sequence", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("tenant_id"),
    )
    op.create_table(
        "holiday_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "employees",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_code", sa.String(length=32), nullable=False),
        sa.Column("is_user", sa.Boolean(), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("contact_number", sa.String(length=50), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("id_type", sa.String(length=50), nullable=True),
        sa.Column("id_number", sa.String(length=100), nullable=True),
        sa.Column("gender", sa.String(length=20), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("race", sa.String(length=50), nullable=True),
        sa.Column("country", sa.String(length=50), nullable=True),
        sa.Column("residency", sa.String(length=50), nullable=True),
        sa.Column("pr_date", sa.Date(), nullable=True),
        sa.Column("employment_status", sa.String(length=50), nullable=True),
        sa.Column("employment_pass", sa.String(length=50), nullable=True),
        sa.Column("work_permit_number", sa.String(length=100), nullable=True),
        sa.Column("position", sa.String(length=100), nullable=True),
        sa.Column("employment_type", sa.String(length=50), nullable=True),
        sa.Column("join_date", sa.Date(), nullable=True),
        sa.Column("exit_date", sa.Date(), nullable=True),
        sa.Column("holiday_group_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("bank_name", sa.String(length=100), nullable=True),
        sa.Column("bank_account_number", sa.String(length=100), nullable=True),
        sa.Column("incentives", sa.Numeric(12, 2), nullable=True),
        sa.Column("allowance", sa.Numeric(12, 2), nullable=True),
        sa.Column("overtime_rate", sa.Numeric(12, 2), nullable=True),
        sa.Column("part_time_rate", sa.Numeric(12, 2), nullable=True),
        sa.Column("levy", sa.Numeric(12, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["holiday_group_id"], ["holiday_groups.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "employee_code", name="uq_employee_code"),
    )
    op.create_table(
        "employee_salary_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "employee_work_schedule",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("day_type", sa.String(length=10), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", "day_of_week", name="uq_employee_day"),
    )
    op.create_table(
        "holidays",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("holiday_group_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["holiday_group_id"], ["holiday_groups.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "dropdown_options",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    permission_table = sa.table(
        "permissions",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String),
        sa.column("description", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )

    permission_codes = [
        "settings:company:read",
        "settings:company:write",
        "employee_settings:read",
        "employee_settings:write",
        "employees:read",
        "employees:write",
        "holidays:read",
        "holidays:write",
        "dropdowns:read",
        "dropdowns:write",
    ]

    connection = op.get_bind()
    existing = {
        row[0]
        for row in connection.execute(
            sa.select(permission_table.c.code).where(
                permission_table.c.code.in_(permission_codes)
            )
        ).all()
    }
    missing = [code for code in permission_codes if code not in existing]
    if missing:
        now = datetime.utcnow()
        op.bulk_insert(
            permission_table,
            [
                {
                    "id": uuid.uuid4(),
                    "code": code,
                    "description": None,
                    "created_at": now,
                }
                for code in missing
            ],
        )


def downgrade() -> None:
    permission_table = sa.table("permissions", sa.column("code", sa.String))
    permission_codes = [
        "settings:company:read",
        "settings:company:write",
        "employee_settings:read",
        "employee_settings:write",
        "employees:read",
        "employees:write",
        "holidays:read",
        "holidays:write",
        "dropdowns:read",
        "dropdowns:write",
    ]
    op.execute(sa.delete(permission_table).where(permission_table.c.code.in_(permission_codes)))

    op.drop_table("dropdown_options")
    op.drop_table("holidays")
    op.drop_table("employee_work_schedule")
    op.drop_table("employee_salary_history")
    op.drop_table("employees")
    op.drop_table("holiday_groups")
    op.drop_table("employee_settings")
    op.drop_table("user_settings")
    op.drop_table("company_settings")
