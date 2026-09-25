"""Language support: script-based detection and response-language instructions.

Detection is deterministic (Unicode script ranges), so it is instant and works
offline. Answer quality in each language depends on the local model; larger
multilingual models handle Indian languages better than 1.5B–4B models.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Language:
    code: str
    name: str
    native: str
    speech: str  # BCP-47 tag for browser speech recognition / synthesis
    script_start: int = 0
    script_end: int = 0


LANGUAGES: dict[str, Language] = {
    lang.code: lang
    for lang in [
        Language("en", "English", "English", "en-IN"),
        Language("hi", "Hindi", "हिन्दी", "hi-IN", 0x0900, 0x097F),
        Language("mr", "Marathi", "मराठी", "mr-IN"),  # Devanagari; detected as Hindi unless chosen
        Language("bn", "Bengali", "বাংলা", "bn-IN", 0x0980, 0x09FF),
        Language("pa", "Punjabi", "ਪੰਜਾਬੀ", "pa-IN", 0x0A00, 0x0A7F),
        Language("gu", "Gujarati", "ગુજરાતી", "gu-IN", 0x0A80, 0x0AFF),
        Language("or", "Odia", "ଓଡ଼ିଆ", "or-IN", 0x0B00, 0x0B7F),
        Language("ta", "Tamil", "தமிழ்", "ta-IN", 0x0B80, 0x0BFF),
        Language("te", "Telugu", "తెలుగు", "te-IN", 0x0C00, 0x0C7F),
        Language("kn", "Kannada", "ಕನ್ನಡ", "kn-IN", 0x0C80, 0x0CFF),
        Language("ml", "Malayalam", "മലയാളം", "ml-IN", 0x0D00, 0x0D7F),
    ]
}


def detect_language(text: str) -> str:
    counts: dict[str, int] = {}
    letters = 0
    for ch in text:
        cp = ord(ch)
        if ch.isalpha():
            letters += 1
        for lang in LANGUAGES.values():
            if lang.script_start and lang.script_start <= cp <= lang.script_end:
                counts[lang.code] = counts.get(lang.code, 0) + 1
                break
    if not counts or not letters:
        return "en"
    code, n = max(counts.items(), key=lambda kv: kv[1])
    return code if n / letters >= 0.2 else "en"


def resolve_language(requested: str | None, text: str) -> tuple[Language, bool]:
    """Returns (language, was_auto_detected)."""
    if requested and requested != "auto" and requested in LANGUAGES:
        return LANGUAGES[requested], False
    return LANGUAGES[detect_language(text)], True


def response_instruction(lang: Language) -> str:
    if lang.code == "en":
        return "Respond in English."
    return (
        f"Respond in {lang.name} ({lang.native}). Keep code, gene/protein names, part numbers, "
        "units, formulas and standard technical terms in English where that is clearer."
    )


def public_languages() -> list[dict]:
    return [{k: v for k, v in asdict(lang).items() if not k.startswith("script")} for lang in LANGUAGES.values()]
