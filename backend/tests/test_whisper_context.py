from app.services.interview.whisper_context import (
    MAX_HOTWORDS_CHARACTERS,
    build_whisper_hotwords,
    build_whisper_initial_prompt,
)


def test_builds_hotwords_from_name_and_ai_parsed_resume() -> None:
    parsed = {
        "skills": ["Python", "Django, FastAPI", "AI chatbots", "LLM"],
        "experience": [
            {"employer": "Acme AI", "title": "Backend Engineer", "dates": "2022-2025"}
        ],
        "email": "private@example.com",
    }
    result = build_whisper_hotwords("Mubashir Shaheen", parsed)

    assert result.startswith("Mubashir Shaheen")
    assert "Python" in result
    assert "FastAPI" in result
    assert "Acme AI" in result
    assert "Backend Engineer" in result
    assert "private@example.com" not in result


def test_hotwords_are_deduplicated_and_bounded() -> None:
    parsed = {"skills": ["Python", "python", *[f"Technology {i}" for i in range(100)]]}
    result = build_whisper_hotwords("Candidate Name", parsed)

    assert result.casefold().count("python") == 1
    assert len(result) <= MAX_HOTWORDS_CHARACTERS


def test_initial_prompt_includes_hotwords_and_recent_transcript_only() -> None:
    previous = " ".join(f"word{i}" for i in range(80))
    prompt = build_whisper_initial_prompt("Mubashir Shaheen, FastAPI", previous)

    assert prompt is not None
    assert "Mubashir Shaheen" in prompt
    assert "word79" in prompt
    assert "word0" not in prompt


def test_adds_technical_terms_from_interview_context() -> None:
    result = build_whisper_hotwords(
        "Candidate Name",
        {"skills": ["Python"]},
        "Architect a HIPAA-compliant ETL pipeline from S3 through Spark into Redshift.",
    )

    assert "HIPAA" in result
    assert "ETL" in result
    assert "S3" in result
    assert "Spark" in result
    assert "Redshift" in result
    assert len(result) <= MAX_HOTWORDS_CHARACTERS
