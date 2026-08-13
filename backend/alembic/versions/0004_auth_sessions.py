"""auth: email/password users, sessions, checkup quality

Revision ID: 0004_auth_sessions
Revises: 0003_device_baselines
Create Date: 2026-08-14

Adds real authentication: email + password hash on ``users``, a
``sessions`` table of opaque bearer tokens (digest stored), and a
measurement-quality grade on ``checkups`` for list views.

Email and password_hash are nullable so rows created under the old
UUID-in-browser identity model keep working; new registrations always
set them.
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_auth_sessions"
down_revision = "0003_device_baselines"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sessions_token_hash", "sessions", ["token_hash"], unique=True)
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    op.add_column(
        "checkups",
        sa.Column("quality_grade", sa.String(length=16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("checkups", "quality_grade")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_index("ix_sessions_token_hash", table_name="sessions")
    op.drop_table("sessions")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_column("users", "password_hash")
    op.drop_column("users", "email")
