"""add coding ai assist (hint config/usage/log, review log)

Revision ID: c4d6e8f0a2b1
Revises: b3f5a1c8d2e4
Create Date: 2026-09-08 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4d6e8f0a2b1"
down_revision: str | None = "b3f5a1c8d2e4"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_LANGUAGE_ENUM = sa.Enum(
    "python", "csharp", "java", name="codinglanguage", native_enum=False, length=10
)


def upgrade() -> None:
    op.create_table(
        "coding_hint_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("default_hint_limit", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "coding_hint_usages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("hints_used", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["coding_questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "question_id"),
    )
    op.create_index(op.f("ix_coding_hint_usages_user_id"), "coding_hint_usages", ["user_id"])
    op.create_index(
        op.f("ix_coding_hint_usages_question_id"), "coding_hint_usages", ["question_id"]
    )

    op.create_table(
        "coding_hint_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("language", _LANGUAGE_ENUM, nullable=False),
        sa.Column("code_before", sa.Text(), nullable=False),
        sa.Column("hint_line", sa.Text(), nullable=False),
        sa.Column("cursor_line", sa.Integer(), nullable=True),
        sa.Column("cursor_column", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["coding_questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_coding_hint_logs_user_id"), "coding_hint_logs", ["user_id"])
    op.create_index(op.f("ix_coding_hint_logs_question_id"), "coding_hint_logs", ["question_id"])

    op.create_table(
        "coding_review_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("language", _LANGUAGE_ENUM, nullable=False),
        sa.Column("code_reviewed", sa.Text(), nullable=False),
        sa.Column("review_text", sa.Text(), nullable=False),
        sa.Column("contained_code", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["coding_questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_coding_review_logs_user_id"), "coding_review_logs", ["user_id"])
    op.create_index(
        op.f("ix_coding_review_logs_question_id"), "coding_review_logs", ["question_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_coding_review_logs_question_id"), table_name="coding_review_logs")
    op.drop_index(op.f("ix_coding_review_logs_user_id"), table_name="coding_review_logs")
    op.drop_table("coding_review_logs")

    op.drop_index(op.f("ix_coding_hint_logs_question_id"), table_name="coding_hint_logs")
    op.drop_index(op.f("ix_coding_hint_logs_user_id"), table_name="coding_hint_logs")
    op.drop_table("coding_hint_logs")

    op.drop_index(op.f("ix_coding_hint_usages_question_id"), table_name="coding_hint_usages")
    op.drop_index(op.f("ix_coding_hint_usages_user_id"), table_name="coding_hint_usages")
    op.drop_table("coding_hint_usages")

    op.drop_table("coding_hint_configs")
