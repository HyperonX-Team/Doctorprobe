"""device baselines

Revision ID: 0003_device_baselines
Revises: 0002_calibration_samples
Create Date: 2026-08-02

Adds per-device blank-pad calibration (white balance) storage.
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_device_baselines"
down_revision = "0002_calibration_samples"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_baselines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("rgb_r", sa.Integer(), nullable=False),
        sa.Column("rgb_g", sa.Integer(), nullable=False),
        sa.Column("rgb_b", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_device_baselines_device_id", "device_baselines", ["device_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index(
        "ix_device_baselines_device_id", table_name="device_baselines"
    )
    op.drop_table("device_baselines")
