"""The interview engine — orchestrates one session's turn-taking. Pure
turn-taking logic in memory; persistence (Postgres, Redis) is a thin layer
around this, not mixed into it, so the same engine drives both the WebSocket
handler (Phase 3 build item, real audio) and `make interview-sim` (headless,
scripted text turns) — see architecture.md §2's sequence diagram, which this
class implements minus the audio I/O.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from app.services.interview import locale
from app.services.interview.director import Director, DirectorAction, TopicProgress
from app.services.interview.plan import InterviewPlan, TopicProbe

GREETING = (
    "Hi <name>, thanks for joining. This will be a mock interview conversation about "
    "your experience — I'll ask a few questions and follow up where it's "
    "useful. Let's get started."
)
SELF_INTRO_PROMPT = (
    "To start, please introduce yourself — tell me a little about your "
    "background and experience."
)
CLOSING = "That's all my questions — thanks for your time today. This concludes the interview."
CANDIDATE_QUESTIONS_PROMPT = "Before we finish, what would you improve about your answers today?"


class TurnKind(StrEnum):
    GREETING = "greeting"
    SELF_INTRO = "self_intro"
    PRIMARY_QUESTION = "primary_question"
    FOLLOW_UP = "follow_up"
    CLARIFY = "clarify"
    CANDIDATE_QUESTIONS = "candidate_questions"
    CLOSING = "closing"


@dataclass
class AgentUtterance:
    kind: TurnKind
    text: str
    topic_id: str | None = None
    question_source: str | None = None


@dataclass
class EngineState:
    """Everything needed to resume an engine after a restart — the
    Postgres-backed persistence layer (app/services/interview/persistence.py)
    serializes exactly this. See architecture.md §5 "a *server* restart is
    survivable too"."""

    topic_index: int = 0
    question_index: int = 0
    extension_questions_asked: int = 0
    progress: TopicProgress = field(default_factory=TopicProgress)
    elapsed_s: int = 0
    turn_index: int = 0
    self_intro_done: bool = False
    in_candidate_questions: bool = False
    complete: bool = False
    # Real elapsed_s at which the *current* topic block started —
    # tracked explicitly rather than derived from cumulative time_budget_s,
    # since a topic can advance earlier or later than its nominal
    # budget (the Director/hard-constraints decide that, not the plan).
    current_block_started_at_s: int = 0


class InterviewEngine:
    def __init__(
        self,
        plan: InterviewPlan,
        director: Director,
        state: EngineState | None = None,
        spoken_language: str = "en",
        candidate_name: str = "there",
    ) -> None:
        self.plan = plan
        self.director = director
        self.state = state or EngineState()
        self.spoken_language = spoken_language
        self.candidate_name = candidate_name.strip() or "there"

    def _greeting(self) -> str:
        return locale.GREETING.get(self.spoken_language, GREETING).replace(
            "<name>", self.candidate_name
        )

    def _self_intro_prompt(self) -> str:
        return locale.SELF_INTRO_PROMPT.get(self.spoken_language, SELF_INTRO_PROMPT)

    def _closing(self) -> str:
        return locale.CLOSING.get(self.spoken_language, CLOSING)

    def _candidate_questions_prompt(self) -> str:
        return locale.CANDIDATE_QUESTIONS_PROMPT.get(
            self.spoken_language, CANDIDATE_QUESTIONS_PROMPT
        )

    def _continuation_question(self, probe: TopicProbe) -> str:
        hints = probe.follow_up_hints or ["the decisions you made"]
        hint = hints[self.state.extension_questions_asked % len(hints)]
        variants = (
            "Tell me about a different situation where this skill mattered, focusing on {hint}.",
            "Walk me through another challenging example and explain {hint}.",
            "Describe another approach you considered and how it affected {hint}.",
        )
        detail = variants[self.state.extension_questions_asked % len(variants)].format(hint=hint)
        return f"Let's explore {probe.label.lower()} a little further. {detail}"

    @property
    def is_complete(self) -> bool:
        return self.state.complete

    @property
    def remaining_s(self) -> int:
        return max(0, self.plan.duration_s - self.state.elapsed_s)

    @property
    def current_probe(self) -> TopicProbe | None:
        if self.state.topic_index >= len(self.plan.topics):
            return None
        return self.plan.topics[self.state.topic_index]

    def start(self) -> AgentUtterance:
        """The one agent turn before any candidate audio. A professional
        interview opens with a self-introduction, not straight into
        graded topic questions — the candidate's answer here isn't judged
        or scored against any probe, it's warm-up, so it's a distinct turn
        kind rather than the first topic question with the greeting folded
        in."""
        return AgentUtterance(
            kind=TurnKind.SELF_INTRO,
            text=f"{self._greeting()} {self._self_intro_prompt()}",
        )

    async def submit_candidate_answer(
        self, text: str, *, elapsed_s: int, session_history: str = ""
    ) -> AgentUtterance:
        """The one call per candidate turn — architecture.md §2's sequence
        diagram step "WS->>D: decide next move". Server-authoritative clock
        wins over any Director judgment: see the hard-stop checks below."""
        self.state.elapsed_s = elapsed_s
        self.state.turn_index += 1

        candidate_questions_start_s = int(self.plan.duration_s * 0.9)
        if elapsed_s >= self.plan.duration_s:
            self.state.complete = True
            return AgentUtterance(kind=TurnKind.CLOSING, text=self._closing())

        if not self.state.self_intro_done:
            # The self-introduction answer isn't judged by the Director —
            # move straight into the first real topic's question, with that
            # topic's time budget starting now rather than being eaten into
            # by however long the introduction took.
            self.state.self_intro_done = True
            self.state.current_block_started_at_s = elapsed_s
            first_probe = self.plan.topics[0]
            return AgentUtterance(
                kind=TurnKind.PRIMARY_QUESTION,
                text=first_probe.primary_question,
                topic_id=first_probe.id,
                question_source=first_probe.question_source,
            )

        if self.state.in_candidate_questions:
            self.state.complete = True
            return AgentUtterance(kind=TurnKind.CLOSING, text=self._closing())

        probe = self.current_probe
        if probe is None:
            return self._enter_candidate_questions()

        self.state.progress.block_elapsed_s = elapsed_s - self.state.current_block_started_at_s
        topic_time_exhausted = self.state.progress.block_elapsed_s >= probe.time_budget_s
        decision = await self.director.decide(
            probe=probe,
            progress=self.state.progress,
            candidate_answer=text,
            session_history=session_history,
        )

        if decision.action == DirectorAction.FOLLOW_UP:
            self.state.progress.follow_ups_used += 1
            return AgentUtterance(
                kind=TurnKind.FOLLOW_UP,
                text=decision.text,
                topic_id=probe.id,
                question_source=decision.question_source,
            )

        if decision.action == DirectorAction.CLARIFY:
            # CLARIFY consumes the same budget as FOLLOW_UP — architecture.md
            # §2's "max 2 follow-ups per topic" is a cap on extra turns
            # per topic, not specifically on the follow_up action alone.
            # Without this, a model that favours "clarify" (observed with a
            # real LLM in testing — see memory.md) can loop on one
            # topic until the *time* budget eventually saves it, wildly
            # unbalancing the interview. See memory.md's Phase 3 gotchas.
            self.state.progress.follow_ups_used += 1
            return AgentUtterance(
                kind=TurnKind.CLARIFY,
                text=decision.text,
                topic_id=probe.id,
                question_source=decision.question_source,
            )

        # ADVANCE. Move through the pre-generated question bank before
        # leaving this topic, unless its overall time allocation has expired.
        if not topic_time_exhausted and self.state.question_index < len(
            probe.additional_questions
        ):
            self.state.question_index += 1
            self.state.progress = TopicProgress()
            return AgentUtterance(
                kind=TurnKind.PRIMARY_QUESTION,
                text=probe.additional_questions[self.state.question_index - 1],
                topic_id=probe.id,
                question_source=probe.question_source,
            )

        self.state.topic_index += 1
        self.state.question_index = 0
        self.state.progress = TopicProgress()
        self.state.current_block_started_at_s = elapsed_s
        next_probe = self.current_probe
        if next_probe is None:
            if elapsed_s < candidate_questions_start_s:
                # Extremely concise answers can exhaust even the generated
                # bank early. Keep the focused practice useful until the
                # closing window instead of ending a 15/30-minute booking in
                # a few minutes.
                self.state.topic_index -= 1
                self.state.question_index = len(probe.additional_questions)
                question = self._continuation_question(probe)
                self.state.extension_questions_asked += 1
                return AgentUtterance(
                    kind=TurnKind.PRIMARY_QUESTION,
                    text=question,
                    topic_id=probe.id,
                )
            return self._enter_candidate_questions()

        return AgentUtterance(
            kind=TurnKind.PRIMARY_QUESTION,
            text=next_probe.primary_question,
            topic_id=next_probe.id,
            question_source=next_probe.question_source,
        )

    def _enter_candidate_questions(self) -> AgentUtterance:
        self.state.in_candidate_questions = True
        return AgentUtterance(
            kind=TurnKind.CANDIDATE_QUESTIONS, text=self._candidate_questions_prompt()
        )
