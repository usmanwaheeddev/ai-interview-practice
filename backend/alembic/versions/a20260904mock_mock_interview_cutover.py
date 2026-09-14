"""Replace hiring records with directly owned mock interviews.

Destructive cutover authorized by the project owner. Accounts and resumes
remain; old jobs, applications, recordings metadata and scores are removed.
Restore the pre-cutover database backup to reverse this migration.
"""
from alembic import op
import sqlalchemy as sa

revision = "a20260904mock"
down_revision = "c0d4ed1dc701"
branch_labels = None
depends_on = None

def upgrade():
    for table in ("score_dimensions", "scores", "proctor_events", "media_assets",
                  "interview_turns", "interview_sessions", "applications",
                  "competencies", "jobs", "audit_log"):
        op.drop_table(table)
    op.drop_column("users", "organization_id")
    op.drop_column("users", "role")
    op.drop_column("users", "erased_at")
    op.drop_table("organizations")
    op.drop_index("ix_resumes_candidate_id", table_name="resumes")
    op.alter_column("resumes", "candidate_id", new_column_name="user_id")
    op.create_index("ix_resumes_user_id", "resumes", ["user_id"])
    op.create_table('mock_interviews',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('resume_id', sa.Uuid(), nullable=False),
    sa.Column('job_description', sa.Text(), nullable=False),
    sa.Column('topics', sa.JSON(), nullable=False),
    sa.Column('duration_minutes', sa.Integer(), nullable=False),
    sa.Column('video_enabled', sa.Boolean(), nullable=False),
    sa.Column('state', sa.Enum('preparing', 'ready', 'in_progress', 'disconnected', 'completed', 'scoring', 'scored', 'failed', name='mockinterviewstate', native_enum=False, length=20), nullable=False),
    sa.Column('interview_plan', sa.JSON(), nullable=False),
    sa.Column('consent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('elapsed_s', sa.Integer(), nullable=False),
    sa.Column('failure_reason', sa.Text(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('duration_minutes IN (15, 30)'),
    sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_mock_interviews_user_id'), 'mock_interviews', ['user_id'], unique=False)
    op.create_table('mock_interview_scores',
    sa.Column('interview_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('overall', sa.Numeric(precision=4, scale=2), nullable=True),
    sa.Column('readiness', sa.String(length=30), nullable=True),
    sa.Column('dimensions', sa.JSON(), nullable=False),
    sa.Column('strengths', sa.JSON(), nullable=False),
    sa.Column('weaknesses', sa.JSON(), nullable=False),
    sa.Column('improvements', sa.JSON(), nullable=False),
    sa.Column('model', sa.String(length=100), nullable=True),
    sa.Column('failure_reason', sa.Text(), nullable=True),
    sa.Column('scored_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['interview_id'], ['mock_interviews.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('interview_id')
    )
    op.create_table('mock_interview_turns',
    sa.Column('interview_id', sa.Uuid(), nullable=False),
    sa.Column('turn_index', sa.Integer(), nullable=False),
    sa.Column('speaker', sa.String(length=20), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('ended_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("speaker IN ('agent', 'user')"),
    sa.ForeignKeyConstraint(['interview_id'], ['mock_interviews.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('interview_id', 'turn_index')
    )
    op.create_index(op.f('ix_mock_interview_turns_interview_id'), 'mock_interview_turns', ['interview_id'], unique=False)
    op.create_table('mock_media_assets',
    sa.Column('interview_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.String(length=10), nullable=False),
    sa.Column('chunk_index', sa.Integer(), nullable=False),
    sa.Column('storage_key', sa.String(length=500), nullable=False),
    sa.Column('content_type', sa.String(length=100), nullable=False),
    sa.Column('ready', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['interview_id'], ['mock_interviews.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('interview_id', 'chunk_index')
    )
    op.create_index(op.f('ix_mock_media_assets_interview_id'), 'mock_media_assets', ['interview_id'], unique=False)



def downgrade():
    raise RuntimeError("This cutover deletes legacy data. Restore the pre-cutover database backup.")
