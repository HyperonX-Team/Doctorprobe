"""calibration samples

Revision ID: 0002_calibration_samples
Revises: 0001_initial
Create Date: 2026-08-01

Adds the labeled sensor samples table used to retrain SaliNet on real
data.
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_calibration_samples"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "calibration_samples",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("analyte", sa.String(length=16), nullable=False),
        sa.Column("concentration", sa.Float(), nullable=False),
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
        "ix_calibration_samples_analyte", "calibration_samples", ["analyte"]
    )
    op.create_index(
        "ix_calibration_samples_device_id", "calibration_samples", ["device_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_calibration_samples_device_id", table_name="calibration_samples"
    )
    op.drop_index("ix_calibration_samples_analyte", table_name="calibration_samples")
    op.drop_table("calibration_samples")
