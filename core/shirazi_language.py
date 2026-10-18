"""Shirazi-origin language support for Shirazi LV.

Mark-LV's prompt already follows the user's most recent message language
(prompt.txt). This module adds an explicit response-language setting so the
user can pin the assistant to Urdu or Roman Urdu regardless of input:

  response_language: "auto" | "english" | "urdu" | "roman_urdu"

- "auto" (default): existing behaviour — reply in the user's message language.
- "urdu": always respond in Urdu (Urdu script).
- "roman_urdu": always respond in Roman Urdu (Urdu in Latin script).
- "english": always respond in English.

Also maps language -> EdgeTTS voice for one-shot speech (the Live voice
timbre itself is fixed by the Gemini Live API; the *words* it speaks follow
the prompt directive below).
"""
from __future__ import annotations

VALID = ("auto", "english", "urdu", "roman_urdu")

# EdgeTTS neural voices (Microsoft, free, no key). Urdu voices are real and
# maintained; Roman Urdu has no dedicated voice — the Urdu voice reads it
# best-effort, which users consistently prefer over an English voice.
VOICES = {
    "urdu": "ur-PK-UzmaNeural",
    "roman_urdu": "ur-PK-AsadNeural",
    "english": "en-US-GuyNeural",
}

_DIRECTIVES = {
    "urdu": (
        "[LANGUAGE]\n"
        "Always respond in Urdu, written in Urdu script. This overrides any "
        "other language instruction. Keep the wording natural everyday Urdu "
        "(not overly formal), the way the user speaks."
    ),
    "roman_urdu": (
        "[LANGUAGE]\n"
        "Always respond in Roman Urdu — Urdu written in Latin script "
        "(e.g. 'aap kaise hain'). This overrides any other language "
        "instruction. Never use Urdu script unless the user explicitly asks."
    ),
    "english": (
        "[LANGUAGE]\n"
        "Always respond in English, regardless of the language of the user's "
        "message. This overrides any other language instruction."
    ),
}


def get_language() -> str:
    """Configured response language; 'auto' when unset/invalid. Never raises."""
    try:
        from memory import config_manager as _cm
        lang = (_cm.load_api_keys().get("response_language") or "auto").lower()
        return lang if lang in VALID else "auto"
    except Exception:
        return "auto"


def prompt_directive() -> str:
    """Extra system-prompt block for a pinned language; '' when 'auto'."""
    return _DIRECTIVES.get(get_language(), "")


def edge_voice_for_language(explicit_voice: str = "") -> str:
    """Pick an EdgeTTS voice: explicit choice wins, else language default."""
    if explicit_voice:
        return explicit_voice
    return VOICES.get(get_language(), VOICES["english"])
