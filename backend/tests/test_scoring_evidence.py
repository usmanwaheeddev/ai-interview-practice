from app.services.scoring.evidence import verify_evidence


def test_exact_quote_verifies() -> None:
    transcript = (
        "Interviewer: Tell me more. You: We keyed on the request id and kept a 24 hour window."
    )
    assert verify_evidence("We keyed on the request id and kept a 24 hour window.", transcript)


def test_quote_with_whitespace_and_case_differences_still_verifies() -> None:
    transcript = "Candidate: We   keyed on the REQUEST id and kept a 24 hour window."
    assert verify_evidence("we keyed on the request id and kept a 24 hour window.", transcript)


def test_fabricated_quote_is_rejected() -> None:
    """Phase 5 exit criterion: a fabricated quote is caught, not accepted as
    fact — memory.md ADR-006."""
    transcript = "Candidate: I mostly write Python and some Go for backend services."
    fabricated = "I have ten years of experience leading platform teams at scale."
    assert not verify_evidence(fabricated, transcript)


def test_empty_quote_is_rejected() -> None:
    assert not verify_evidence("", "Candidate: some real answer here.")


def test_minor_paraphrase_within_threshold_still_verifies() -> None:
    transcript = "Candidate: I rolled back the deploy within five minutes and wrote a postmortem."
    # Trivial transcription variance (a instead of the) — still >=90% similar.
    close_paraphrase = "I rolled back the deploy within five minutes and wrote postmortem."
    assert verify_evidence(close_paraphrase, transcript)
