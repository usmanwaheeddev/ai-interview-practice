"""add language practice mode

Revision ID: d4a1f7b2c9e3
Revises: a20260904mock
Create Date: 2026-09-05 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4a1f7b2c9e3"
down_revision: str | None = "a20260904mock"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_EXACTLY_ONE_MODE = (
    "(resume_id IS NOT NULL AND job_description IS NOT NULL "
    "AND language IS NULL AND level IS NULL) "
    "OR (resume_id IS NULL AND job_description IS NULL "
    "AND language IS NOT NULL AND level IS NOT NULL)"
)


def upgrade() -> None:
    op.add_column(
        "mock_interviews",
        sa.Column(
            "language",
            sa.Enum("python", "java", "csharp", name="mockinterviewlanguage", native_enum=False, length=10),
            nullable=True,
        ),
    )
    op.add_column(
        "mock_interviews",
        sa.Column(
            "level",
            sa.Enum("basic", "advanced", "practical", name="mockinterviewlevel", native_enum=False, length=10),
            nullable=True,
        ),
    )
    op.alter_column("mock_interviews", "resume_id", existing_type=sa.Uuid(), nullable=True)
    op.alter_column("mock_interviews", "job_description", existing_type=sa.Text(), nullable=True)
    op.create_check_constraint("ck_mock_interviews_exactly_one_mode", "mock_interviews", _EXACTLY_ONE_MODE)


def downgrade() -> None:
    op.drop_constraint("ck_mock_interviews_exactly_one_mode", "mock_interviews", type_="check")
    op.alter_column("mock_interviews", "job_description", existing_type=sa.Text(), nullable=False)
    op.alter_column("mock_interviews", "resume_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_column("mock_interviews", "level")
    op.drop_column("mock_interviews", "language")
