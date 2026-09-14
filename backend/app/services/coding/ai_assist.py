"""AI review/hint prompt building and hint-limit bookkeeping for the
coding-challenge feature (Phase 2). Streaming generation itself goes through
the existing LLM provider layer's `stream_complete_with_fallback` (see
app/providers/llm/__init__.py, backed by FallbackLLMProvider in
app/providers/llm/fallback.py) — this module only builds prompts and manages
the DB-backed hint limit/usage, per app/api/coding.py's review/hint routes.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.coding import CodingHintConfig, CodingHintUsage, CodingQuestion

REVIEW_SYSTEM_PROMPT = (
    "You are a senior software engineer giving a candidate quick, focused feedback on "
    "their in-progress solution to a coding exercise. Respond ONLY in prose — plain "
    "English sentences. Do not include any code, code blocks, backticks, pseudocode, or "
    "a corrected/rewritten solution, under any circumstances — describe issues and "
    "suggestions in words only.\n\n"
    "Keep it SHORT: at most 3-4 sentences total, no headers, no bullet points. Cover "
    "exactly these, briefly and in this order: (1) in one clause, what the problem is "
    "asking for; (2) what the candidate's current code actually does relative to that, "
    "including anything obviously missing or wrong; (3) the single most important thing "
    "to fix or confirm next. Do not try to list every possible issue — pick what matters "
    "most right now, and don't restate the full question or constraints."
)

# Below this many non-boilerplate lines, there's nothing concrete to review yet —
# see count_authored_lines and app/api/coding.py's review endpoint, which skips
# the LLM call entirely (and just asks the candidate to write some code first)
# rather than having the model invent feedback on an empty/near-empty solution.
MIN_REVIEW_AUTHORED_LINES = 2

HINT_SYSTEM_PROMPT = (
    "You are helping a candidate who is stuck on a coding exercise. Given the question, "
    "their current code, and their cursor position, respond with EXACTLY the single next "
    "line of code that belongs at the cursor — nothing else. No explanation, no markdown "
    "code fences, no multiple lines of code. Just that one line, as plain text."
)


def count_authored_lines(starter_code: str, code: str) -> int:
    """How many non-blank lines in `code` aren't already present verbatim
    (ignoring surrounding whitespace) in the starter skeleton — a cheap
    proxy for "did the candidate actually write anything besides the
    boilerplate", used to skip a review request that has nothing to say yet
    rather than asking the model to invent feedback on an empty solution."""
    boilerplate = {line.strip() for line in starter_code.splitlines() if line.strip()}
    return sum(
        1
        for line in code.splitlines()
        if line.strip() and line.strip() not in boilerplate
    )


def _question_context(question: CodingQuestion) -> str:
    signature = question.function_signature
    params = ", ".join(f"{p['name']}: {p['type']}" for p in signature["params"])
    lines = [
        f"Question: {question.title} ({question.difficulty})",
        f"Description: {question.description}",
    ]
    if question.constraints:
        lines.append("Constraints: " + "; ".join(question.constraints))
    lines.append(
        f"Function signature: {question.class_name}.{signature['name']}({params}) "
        f"-> {signature['return_type']}"
    )
    return "\n".join(lines)


def build_review_prompt(question: CodingQuestion, language: str, code: str) -> str:
    return (
        f"{_question_context(question)}\n\n"
        f"Candidate's language: {language}\n"
        f"Candidate's current code:\n{code}\n\n"
        "Give your short code review feedback now, in prose only."
    )


def build_hint_prompt(
    question: CodingQuestion,
    language: str,
    code: str,
    cursor_line: int | None,
    cursor_column: int | None,
) -> str:
    cursor_desc = (
        f"The candidate's cursor is at line {cursor_line}, column {cursor_column}."
        if cursor_line is not None
        else "No cursor position was given — assume the end of the code."
    )
    return (
        f"{_question_context(question)}\n\n"
        f"Candidate's language: {language}\n"
        f"Candidate's current code:\n{code}\n\n"
        f"{cursor_desc}\n"
        "Respond with exactly the next single line of code they should write there."
    )


async def get_hint_limit(db: AsyncSession) -> int:
    """Reads the single CodingHintConfig row, lazily creating it with the
    model default if `make seed` hasn't run yet (e.g. a fresh test DB) —
    see CodingHintConfig's docstring for why this is a table, not a
    hardcoded constant."""
    config = await db.scalar(select(CodingHintConfig).limit(1))
    if config is None:
        config = CodingHintConfig()
        db.add(config)
        await db.flush()
    return config.default_hint_limit


async def get_or_create_hint_usage(
    db: AsyncSession, user_id: uuid.UUID, question_id: uuid.UUID
) -> CodingHintUsage:
    usage = await db.scalar(
        select(CodingHintUsage).where(
            CodingHintUsage.user_id == user_id, CodingHintUsage.question_id == question_id
        )
    )
    if usage is None:
        usage = CodingHintUsage(user_id=user_id, question_id=question_id, hints_used=0)
        db.add(usage)
        await db.flush()
    return usage
