"""allow resume-only mock interviews

Revision ID: f1a2b3c4d5e6
Revises: c4d6e8f0a2b1
"""
from collections.abc import Sequence

from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "c4d6e8f0a2b1"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_mock_interviews_exactly_one_mode", "mock_interviews", type_="check")
    op.create_check_constraint(
        "ck_mock_interviews_exactly_one_mode",
        "mock_interviews",
        "(resume_id IS NOT NULL AND language IS NULL AND level IS NULL) "
        "OR (resume_id IS NULL AND job_description IS NULL "
        "AND language IS NOT NULL AND level IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_mock_interviews_exactly_one_mode", "mock_interviews", type_="check")
    op.create_check_constraint(
        "ck_mock_interviews_exactly_one_mode",
        "mock_interviews",
        "(resume_id IS NOT NULL AND job_description IS NOT NULL "
        "AND language IS NULL AND level IS NULL) "
        "OR (resume_id IS NULL AND job_description IS NULL "
        "AND language IS NOT NULL AND level IS NOT NULL)",
    )
