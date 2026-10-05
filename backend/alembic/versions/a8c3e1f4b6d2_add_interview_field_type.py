"""add interview field type

Revision ID: a8c3e1f4b6d2
Revises: f1a2b3c4d5e6
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a8c3e1f4b6d2"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("mock_interviews", sa.Column("field_type", sa.String(length=40)))
    op.execute(
        "UPDATE mock_interviews SET field_type = 'computer_science' WHERE resume_id IS NOT NULL"
    )
    op.drop_constraint("ck_mock_interviews_exactly_one_mode", "mock_interviews", type_="check")
    op.create_check_constraint(
        "ck_mock_interviews_exactly_one_mode",
        "mock_interviews",
        "(resume_id IS NOT NULL AND field_type IS NOT NULL "
        "AND language IS NULL AND level IS NULL) "
        "OR (resume_id IS NULL AND job_description IS NULL AND field_type IS NULL "
        "AND language IS NOT NULL AND level IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_mock_interviews_exactly_one_mode", "mock_interviews", type_="check")
    op.create_check_constraint(
        "ck_mock_interviews_exactly_one_mode",
        "mock_interviews",
        "(resume_id IS NOT NULL AND language IS NULL AND level IS NULL) "
        "OR (resume_id IS NULL AND job_description IS NULL "
        "AND language IS NOT NULL AND level IS NOT NULL)",
    )
    op.drop_column("mock_interviews", "field_type")
