"""add spoken language

Revision ID: e7c2b8a4f1d6
Revises: d4a1f7b2c9e3
Create Date: 2026-09-06 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7c2b8a4f1d6"
down_revision: str | None = "d4a1f7b2c9e3"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "mock_interviews",
        sa.Column(
            "spoken_language",
            sa.Enum("en", "hi", "ur", name="spokenlanguage", native_enum=False, length=5),
            nullable=False,
            server_default="en",
        ),
    )
    op.alter_column("mock_interviews", "spoken_language", server_default=None)


def downgrade() -> None:
    op.drop_column("mock_interviews", "spoken_language")
