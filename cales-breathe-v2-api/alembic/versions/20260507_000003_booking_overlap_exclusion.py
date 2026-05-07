"""add bookings overlap exclusion constraint

Revision ID: 20260507_000003
Revises: 20260507_000002
Create Date: 2026-05-07
"""

from alembic import op


revision = "20260507_000003"
down_revision = "20260507_000002"
branch_labels = None
depends_on = None


CONSTRAINT_NAME = "bookings_no_time_overlap_excl"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        f"""
        ALTER TABLE bookings
        ADD CONSTRAINT {CONSTRAINT_NAME}
        EXCLUDE USING gist (
            tsrange(
                booking_date,
                booking_date + (total_duration_minutes * interval '1 minute'),
                '[)'
            ) WITH &&
        )
        WHERE (status IN ('pending', 'confirmed'))
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        f"ALTER TABLE bookings DROP CONSTRAINT IF EXISTS {CONSTRAINT_NAME}"
    )
