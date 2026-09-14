"""Centralized translations for the fixed (non-LLM-generated) strings the
interview conversation ever speaks or shows, plus the instruction appended to
every LLM prompt that produces spoken/feedback text. English is never listed
here — callers fall back to their existing English constant via `.get`, so
English behavior is byte-for-byte unchanged from before multilingual support.
"""

LANGUAGE_NAMES = {"en": "English", "hi": "Hindi", "ur": "Urdu"}

SUPPORTED_SPOKEN_LANGUAGES = frozenset(LANGUAGE_NAMES)


def resolve_detected_language(detected: str | None) -> str:
    """Maps a raw STT-detected language code to one of the interview's
    supported spoken languages, falling back to English for anything else
    (no match, or a language we have no voice/translations for) — used by
    the WS handler's per-turn auto-switch so an unsupported guess never
    leaves the conversation stuck in a language nothing else understands."""
    if detected in SUPPORTED_SPOKEN_LANGUAGES:
        return detected
    return "en"


def language_instruction(language: str) -> str:
    name = LANGUAGE_NAMES.get(language)
    if not name or language == "en":
        return ""
    return f" Respond entirely in {name}."


GREETING = {
    "hi": (
        "नमस्ते, शामिल होने के लिए धन्यवाद। यह आपके अनुभव के बारे में एक मॉक "
        "इंटरव्यू होगा — मैं कुछ सवाल पूछूँगा और जहाँ ज़रूरत होगी वहाँ आगे भी "
        "पूछूँगा। चलिए शुरू करते हैं।"
    ),
    "ur": (
        "السلام علیکم، شامل ہونے کا شکریہ۔ یہ آپ کے تجربے کے بارے میں ایک "
        "مشقی انٹرویو ہوگا — میں چند سوالات پوچھوں گا اور جہاں ضرورت ہو وہاں "
        "مزید بھی پوچھوں گا۔ چلیے شروع کرتے ہیں۔"
    ),
}

SELF_INTRO_PROMPT = {
    "hi": (
        "शुरू करने के लिए, कृपया अपना परिचय दें — अपने अनुभव और पृष्ठभूमि के "
        "बारे में थोड़ा बताएं।"
    ),
    "ur": (
        "شروع کرنے کے لیے، براہ کرم اپنا تعارف کروائیں — اپنے تجربے اور پس "
        "منظر کے بارے میں کچھ بتائیں۔"
    ),
}

CLOSING = {
    "hi": "बस इतने ही सवाल थे — आज आपके समय के लिए धन्यवाद। यह इंटरव्यू यहीं समाप्त होता है।",
    "ur": "بس اتنے ہی سوالات تھے — آج آپ کے وقت کا شکریہ۔ یہ انٹرویو یہیں ختم ہوتا ہے۔",
}

CANDIDATE_QUESTIONS_PROMPT = {
    "hi": "समाप्त करने से पहले, आज अपने जवाबों में आप क्या सुधार करना चाहेंगे?",
    "ur": "ختم کرنے سے پہلے، آج آپ اپنے جوابات میں کیا بہتری لانا چاہیں گے؟",
}

# plan.py's resume/job-description-mode fallback question, keyed by language.
# `{prefix}` and `{label}` are substituted by the caller (same shape as the
# existing English f-string).
RESUME_FALLBACK_QUESTION = {
    "hi": (
        "{prefix}इस भूमिका से जुड़े {label} कौशल का उपयोग करने वाले किसी "
        "प्रोजेक्ट का वर्णन करें। अपना तरीका और उसके ट्रेड-ऑफ़ बताएं।"
    ),
    "ur": (
        "{prefix}اس کردار سے متعلق {label} کی مہارتوں کا استعمال کرنے والے "
        "کسی پروجیکٹ کی وضاحت کریں۔ اپنا طریقہ کار اور اس کے ٹریڈ آفس بتائیں۔"
    ),
}

# plan.py's language-practice-mode fallback question.
LANGUAGE_PRACTICE_FALLBACK_QUESTION = {
    "hi": (
        "{level_label} स्तर पर, {language_label} में {description} को समझाएं। "
        "एक उदाहरण और उसके ट्रेड-ऑफ़ के साथ बताएं।"
    ),
    "ur": (
        "{level_label} سطح پر، {language_label} میں {description} کی وضاحت "
        "کریں۔ ایک مثال اور اس کے ٹریڈ آفس کے ساتھ بتائیں۔"
    ),
}

# Default follow-up hints used whenever a provider doesn't return usable ones.
DEFAULT_FOLLOW_UP_HINTS = {
    "hi": ["एक विशिष्ट उदाहरण", "आपने जिन ट्रेड-ऑफ़ पर विचार किया", "आप क्या बेहतर करेंगे"],
    "ur": ["ایک مخصوص مثال", "وہ ٹریڈ آفس جن پر آپ نے غور کیا", "آپ کیا بہتر کریں گے"],
}

# director.py's fallback follow-up phrasing. `{hint}` is substituted.
DIRECTOR_FALLBACK_FOLLOW_UP = {
    "hi": "क्या आप {hint} के बारे में थोड़ा और बता सकते हैं?",
    "ur": "کیا آپ {hint} کے بارے میں کچھ مزید بتا سکتے ہیں؟",
}
DEFAULT_FOLLOW_UP_HINT_TEXT = {
    "hi": "उसे और विस्तार से",
    "ur": "اسے مزید تفصیل سے",
}

# scorer.py's fallback improvement phrasing when the LLM omits one.
# `{topic}` is substituted (lowercased topic label, same as the English text).
SCORER_FALLBACK_IMPROVEMENT = {
    "hi": "{topic} का एक उदाहरण अभ्यास करें और विकल्पों को समझाएं।",
    "ur": "{topic} کی ایک مثال کی مشق کریں اور متبادل کی وضاحت کریں۔",
}
