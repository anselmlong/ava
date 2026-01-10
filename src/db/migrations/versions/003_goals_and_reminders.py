"""Goals and reminders

Revision ID: 003
Revises: 002
Create Date: 2026-01-10

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "goals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="active"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_goals_user_id", "goals", ["user_id"])
    op.create_index("idx_goals_status", "goals", ["status"])

    op.create_table(
        "reminders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("goal_id", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("schedule_text", sa.Text(), nullable=False),
        sa.Column(
            "schedule_type",
            sa.String(length=20),
            nullable=False,
            server_default="once",
        ),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_reminders_user_id", "reminders", ["user_id"])
    op.create_index("idx_reminders_goal_id", "reminders", ["goal_id"])
    op.create_index("idx_reminders_is_active", "reminders", ["is_active"])
    op.create_index("idx_reminders_schedule_type", "reminders", ["schedule_type"])
    op.create_index("idx_reminders_next_run_at", "reminders", ["next_run_at"])
    op.create_index(
        "idx_reminders_next_run_active",
        "reminders",
        ["user_id", "is_active", "next_run_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_reminders_next_run_active", table_name="reminders")
    op.drop_index("idx_reminders_next_run_at", table_name="reminders")
    op.drop_index("idx_reminders_schedule_type", table_name="reminders")
    op.drop_index("idx_reminders_is_active", table_name="reminders")
    op.drop_index("idx_reminders_goal_id", table_name="reminders")
    op.drop_index("idx_reminders_user_id", table_name="reminders")
    op.drop_table("reminders")

    op.drop_index("idx_goals_status", table_name="goals")
    op.drop_index("idx_goals_user_id", table_name="goals")
    op.drop_table("goals")
