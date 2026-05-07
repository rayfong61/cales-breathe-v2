"""relax users phone uniqueness

Revision ID: 20260507_000002
Revises: 20260507_000001
Create Date: 2026-05-07
"""

from alembic import op


revision = "20260507_000002"
down_revision = "20260507_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(op.f("ix_users_phone"), table_name="users")
    op.create_index(op.f("ix_users_phone"), "users", ["phone"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_phone"), table_name="users")
    op.create_index(op.f("ix_users_phone"), "users", ["phone"], unique=True)
