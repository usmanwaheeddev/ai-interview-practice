"""add coding challenges

Revision ID: b3f5a1c8d2e4
Revises: e7c2b8a4f1d6
Create Date: 2026-09-07 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3f5a1c8d2e4"
down_revision: str | None = "e7c2b8a4f1d6"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "coding_questions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column(
            "difficulty",
            sa.Enum("easy", "medium", "hard", name="codingdifficulty", native_enum=False, length=10),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("constraints", sa.JSON(), nullable=False),
        sa.Column("examples", sa.JSON(), nullable=False),
        sa.Column("class_name", sa.String(length=100), nullable=False),
        sa.Column("function_signature", sa.JSON(), nullable=False),
        sa.Column("starter_code", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_coding_questions_slug"), "coding_questions", ["slug"], unique=True)

    op.create_table(
        "coding_test_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("args", sa.JSON(), nullable=False),
        sa.Column("expected_output", sa.JSON(), nullable=False),
        sa.Column("is_sample", sa.Boolean(), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["coding_questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("question_id", "order"),
    )
    op.create_index(
        op.f("ix_coding_test_cases_question_id"), "coding_test_cases", ["question_id"]
    )

    op.create_table(
        "coding_submissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column(
            "language",
            sa.Enum("python", "csharp", "java", name="codinglanguage", native_enum=False, length=10),
            nullable=False,
        ),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "running", "passed", "failed", "error",
                name="codingsubmissionstatus", native_enum=False, length=10,
            ),
            nullable=False,
        ),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["coding_questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_coding_submissions_user_id"), "coding_submissions", ["user_id"])
    op.create_index(
        op.f("ix_coding_submissions_question_id"), "coding_submissions", ["question_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_coding_submissions_question_id"), table_name="coding_submissions")
    op.drop_index(op.f("ix_coding_submissions_user_id"), table_name="coding_submissions")
    op.drop_table("coding_submissions")

    op.drop_index(op.f("ix_coding_test_cases_question_id"), table_name="coding_test_cases")
    op.drop_table("coding_test_cases")

    op.drop_index(op.f("ix_coding_questions_slug"), table_name="coding_questions")
    op.drop_table("coding_questions")
