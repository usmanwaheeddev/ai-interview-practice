from app.services.scoring.redaction import redact_transcript


def test_redacts_name_and_email() -> None:
    text = "Interviewer: Hi Casey, thanks for joining. You: Sure, my email is casey@example.com."
    redacted = redact_transcript(
        text, candidate_name="Casey Candidate", candidate_email="casey@example.com"
    )
    assert "Casey" not in redacted
    assert "casey@example.com" not in redacted
    assert "[NAME]" in redacted
    assert "[EMAIL]" in redacted


def test_redacts_phone_number() -> None:
    text = "You: You can reach me at 555-123-4567 anytime."
    redacted = redact_transcript(text, candidate_name="X Y", candidate_email="")
    assert "555-123-4567" not in redacted
    assert "[PHONE]" in redacted


def test_redacts_age_mention() -> None:
    redacted = redact_transcript(
        "You: I'm 29 and have been coding since I was a teenager.",
        candidate_name="X Y",
        candidate_email="",
    )
    assert "29" not in redacted
    assert "[AGE]" in redacted


def test_redacts_university_mention() -> None:
    redacted = redact_transcript(
        "You: I studied at Stanford University before joining the industry.",
        candidate_name="X Y",
        candidate_email="",
    )
    assert "Stanford University" not in redacted
    assert "[SCHOOL]" in redacted


def test_redacts_self_identified_nationality() -> None:
    redacted = redact_transcript(
        "You: I'm Canadian and relocated for this role.",
        candidate_name="X Y",
        candidate_email="",
    )
    assert "Canadian" not in redacted
    assert "[NATIONALITY]" in redacted


def test_does_not_touch_unrelated_pronouns() -> None:
    """Explicitly not in scope — see redaction.py's module docstring: blanket
    pronoun stripping would corrupt legitimate answer content referring to
    someone else, for an unreliable signal anyway."""
    text = "You: She designed the original schema and he reviewed it."
    redacted = redact_transcript(text, candidate_name="Casey Candidate", candidate_email="")
    assert redacted == text


def test_preserves_answer_content_around_redactions() -> None:
    text = "You: I led the migration and cut latency by 40 percent."
    redacted = redact_transcript(
        text, candidate_name="Casey Candidate", candidate_email="c@example.com"
    )
    assert "I led the migration and cut latency by 40 percent." in redacted
