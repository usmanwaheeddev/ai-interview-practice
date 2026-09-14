from app.services.interview import locale


def test_resolve_detected_language_passes_through_supported_languages():
    assert locale.resolve_detected_language("en") == "en"
    assert locale.resolve_detected_language("hi") == "hi"
    assert locale.resolve_detected_language("ur") == "ur"


def test_resolve_detected_language_falls_back_to_english():
    """An unsupported detected language (or no detection at all) must not
    strand the conversation in a language it has no voice or translations
    for — the WS handler's auto-switch relies on this fallback."""
    assert locale.resolve_detected_language("fr") == "en"
    assert locale.resolve_detected_language(None) == "en"
