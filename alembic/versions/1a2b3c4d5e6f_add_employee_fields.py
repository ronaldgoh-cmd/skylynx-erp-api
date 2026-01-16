"""add employee fields

Revision ID: 1a2b3c4d5e6f
Revises: 9f1a6b7c8d9e
Create Date: 2026-11-16 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "1a2b3c4d5e6f"
down_revision = "9f1a6b7c8d9e"
branch_labels = None
depends_on = None


def _employee_columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns("employees")}


def upgrade() -> None:
    columns = _employee_columns()
    if "department" not in columns:
        op.add_column("employees", sa.Column("department", sa.Text(), nullable=True))
    if "payment_method" not in columns:
        op.add_column("employees", sa.Column("payment_method", sa.Text(), nullable=True))
    if "bonus" not in columns:
        op.add_column("employees", sa.Column("bonus", sa.Numeric(12, 2), nullable=True))
    if "allowance" not in columns:
        op.add_column("employees", sa.Column("allowance", sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    columns = _employee_columns()
    if "bonus" in columns:
        op.drop_column("employees", "bonus")
    if "payment_method" in columns:
        op.drop_column("employees", "payment_method")
    if "department" in columns:
        op.drop_column("employees", "department")
