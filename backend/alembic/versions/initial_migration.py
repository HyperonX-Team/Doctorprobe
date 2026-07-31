"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-31

Creates the four core tables: users, checkups, device_readings, share_events.
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("sex", sa.String(length=16), nullable=False),
        sa.Column("height_cm", sa.Float(), nullable=False),
        sa.Column("weight_kg", sa.Float(), nullable=False),
        sa.Column("activity_level", sa.String(length=32), nullable=False),
        sa.Column("share_data", sa.Boolean(), nullable=False),
        sa.Column("token_balance", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "checkups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("overall_risk", sa.String(length=16), nullable=False),
        sa.Column("encrypted_data", sa.Text(), nullable=False),
        sa.Column("is_shared", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_checkups_user_id", "checkups", ["user_id"])
    op.create_table(
        "device_readings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("rgb_r", sa.Integer(), nullable=False),
        sa.Column("rgb_g", sa.Integer(), nullable=False),
        sa.Column("rgb_b", sa.Integer(), nullable=False),
        sa.Column("temperature_c", sa.Float(), nullable=False),
        sa.Column("humidity_pct", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_device_readings_device_id", "device_readings", ["device_id"]
    )
    op.create_table(
        "share_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("checkup_id", sa.Uuid(), nullable=False),
        sa.Column("tokens_awarded", sa.Integer(), nullable=False),
        sa.Column(
            "shared_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["checkup_id"], ["checkups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("checkup_id"),
    )


def downgrade() -> None:
    op.drop_table("share_events")
    op.drop_index("ix_device_readings_device_id", table_name="device_readings")
    op.drop_table("device_readings")
    op.drop_index("ix_checkups_user_id", table_name="checkups")
    op.drop_table("checkups")
    op.drop_table("users")
