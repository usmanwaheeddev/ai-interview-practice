from app.services.interview.streaming_stt import is_plausible_transcript, merge_transcript_text


def test_merges_overlapping_chunk_words() -> None:
    assert (
        merge_transcript_text("I built a payment service with Python", "with Python and PostgreSQL")
        == "I built a payment service with Python and PostgreSQL"
    )


def test_preserves_non_overlapping_chunks() -> None:
    assert merge_transcript_text("First idea.", "Second idea.") == "First idea. Second idea."


def test_merge_is_case_and_punctuation_insensitive() -> None:
    assert merge_transcript_text("It worked well.", "Well, then we shipped") == (
        "It worked well. then we shipped"
    )


def test_rejects_repetitive_prompt_hallucination() -> None:
    text = "Usman Python Pydantic " + "Pydantic " * 20
    assert not is_plausible_transcript(text)


def test_accepts_normal_technical_answer() -> None:
    text = "I used Python and Pydantic to validate events before publishing them to Redis."
    assert is_plausible_transcript(text)
