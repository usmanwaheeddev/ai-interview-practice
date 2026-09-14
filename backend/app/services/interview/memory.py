"""Cross-session candidate memory.

Every question asked and every answer given is already recorded per session
in `MockInterviewTurn`, linked to the candidate through `MockInterview.user_id`
— this is that candidate's full history, not a separate store. What's new
here is *using* it: a condensed transcript of a candidate's own most recent
finished sessions, formatted for direct inclusion in an LLM prompt, so the
Director and the opening-question planner can recognise a returning
candidate and ask informed follow-ups instead of treating every session as
a stranger's.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MockInterview, MockInterviewState, MockInterviewTurn

# Kept small deliberately — this text is prepended to every planning/judging
# prompt for the session, so it has to stay cheap in tokens even for a
# candidate with a long practice history.
MAX_PRIOR_SESSIONS = 2
MAX_TURNS_PER_SESSION = 12

_FINISHED_STATES = (
    MockInterviewState.COMPLETED,
    MockInterviewState.SCORING,
    MockInterviewState.SCORED,
)


async def load_user_memory(
    db: AsyncSession, user_id: uuid.UUID, *, exclude_interview_id: uuid.UUID | None = None
) -> str:
    """A condensed transcript of this candidate's most recent finished
    interviews, oldest of the selected batch first. Empty string for a
    first-time candidate or one with no finished sessions yet."""
    stmt = (
        select(MockInterview)
        .where(MockInterview.user_id == user_id, MockInterview.state.in_(_FINISHED_STATES))
        .order_by(MockInterview.created_at.desc())
        .limit(MAX_PRIOR_SESSIONS + 1)  # +1 headroom in case one is `exclude_interview_id`
    )
    sessions = [
        session
        for session in (await db.scalars(stmt)).all()
        if session.id != exclude_interview_id
    ][:MAX_PRIOR_SESSIONS]
    if not sessions:
        return ""

    blocks = []
    for session in reversed(sessions):  # oldest first, chronological reading order
        turns = (
            await db.scalars(
                select(MockInterviewTurn)
                .where(MockInterviewTurn.interview_id == session.id)
                .order_by(MockInterviewTurn.turn_index)
                .limit(MAX_TURNS_PER_SESSION)
            )
        ).all()
        if not turns:
            continue
        lines = [
            f"{'Interviewer' if turn.speaker == 'agent' else 'Candidate'}: {turn.text}"
            for turn in turns
        ]
        focus = ", ".join(session.topics) if session.topics else (session.language or "general")
        blocks.append(
            f"--- Session on {session.created_at.date().isoformat()} ({focus}) ---\n"
            + "\n".join(lines)
        )
    return "\n\n".join(blocks)
