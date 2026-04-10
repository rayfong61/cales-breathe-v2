"""baseline schema for current models

Revision ID: 20260409_000001
Revises:
Create Date: 2026-04-09 00:00:01
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260409_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "line_webhook_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_line_webhook_events_event_id"), "line_webhook_events", ["event_id"], unique=True)
    op.create_index(op.f("ix_line_webhook_events_id"), "line_webhook_events", ["id"], unique=False)

    op.create_table(
        "services",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("price", sa.Integer(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_services_category"), "services", ["category"], unique=False)
    op.create_index(op.f("ix_services_id"), "services", ["id"], unique=False)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("contact_mail", sa.String(length=255), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("provider", sa.String(length=20), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("google_user_id", sa.String(length=100), nullable=True),
        sa.Column("line_user_id", sa.String(length=100), nullable=True),
        sa.Column("photo", sa.String(length=2048), nullable=True),
        sa.Column("birthday", sa.Date(), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_contact_mail"), "users", ["contact_mail"], unique=True)
    op.create_index(op.f("ix_users_google_user_id"), "users", ["google_user_id"], unique=True)
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_line_user_id"), "users", ["line_user_id"], unique=True)
    op.create_index(op.f("ix_users_phone"), "users", ["phone"], unique=True)

    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("guest_name", sa.String(length=100), nullable=True),
        sa.Column("guest_phone", sa.String(length=20), nullable=True),
        sa.Column("created_by_owner_id", sa.Integer(), nullable=True),
        sa.Column("booking_date", sa.DateTime(), nullable=False),
        sa.Column("total_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("total_price", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("google_calendar_event_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_owner_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bookings_google_calendar_event_id"), "bookings", ["google_calendar_event_id"], unique=False)
    op.create_index(op.f("ix_bookings_id"), "bookings", ["id"], unique=False)

    op.create_table(
        "booking_services",
        sa.Column("booking_id", sa.Integer(), nullable=False),
        sa.Column("service_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"]),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"]),
        sa.PrimaryKeyConstraint("booking_id", "service_id"),
    )


def downgrade() -> None:
    op.drop_table("booking_services")

    op.drop_index(op.f("ix_bookings_id"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_google_calendar_event_id"), table_name="bookings")
    op.drop_table("bookings")

    op.drop_index(op.f("ix_users_phone"), table_name="users")
    op.drop_index(op.f("ix_users_line_user_id"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_index(op.f("ix_users_google_user_id"), table_name="users")
    op.drop_index(op.f("ix_users_contact_mail"), table_name="users")
    op.drop_table("users")

    op.drop_index(op.f("ix_services_id"), table_name="services")
    op.drop_index(op.f("ix_services_category"), table_name="services")
    op.drop_table("services")

    op.drop_index(op.f("ix_line_webhook_events_id"), table_name="line_webhook_events")
    op.drop_index(op.f("ix_line_webhook_events_event_id"), table_name="line_webhook_events")
    op.drop_table("line_webhook_events")
