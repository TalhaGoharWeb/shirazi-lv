"""
Persistent instruction enforcement — Personal Companion upgrade (Phase 4).

The profile is enforced through application state and request-building,
not by hoping the model remembers the onboarding conversation.

Instruction hierarchy (enforced by construction):
  1. Platform safety requirements and application security controls.
  2. Developer-defined restrictions and mandatory application policies.
  3. User's saved persistent preferences and instructions.
  4. Current-session instructions (temporary overrides).
  5. Default assistant behavior.

Key rules:
- Temporary overrides ("answer this one in English") never rewrite the profile.
- Language/style preferences are re-applied on every request, so provider
  failover cannot drop them.
- user_defined_boundaries are conversational rules ONLY — they never grant
  tool permissions (the OmniControl gateway owns authorization).
- actual_name is never placed in model context without explicit consent.
- Untrusted content (webpages, tool output, documents) can never modify
  the profile — only explicit user turns handled by authorized code paths.
"""
from __future__ import annotations

import re

from core import profile as _prof

# Temporary-override patterns: "for this answer", "just this once", etc.
# When matched, the override applies to the current turn only.
_TEMP_PATTERNS = [
    (re.compile(r"\bjust (this|for this) (once|time|answer|question)\b", re.I), "once"),
    (re.compile(r"\bfor this (answer|response|question|one)\b", re.I), "once"),
    (re.compile(r"\bthis time (only|just)\b", re.I), "once"),
]

_LANG_WORDS = {
    "english": ("english",),
    "urdu": ("urdu",),
    "roman urdu": ("roman_urdu",),
    "roman_urdu": ("roman_urdu",),
    "arabic": ("arabic",),
}


def detect_temp_override(text: str) -> dict:
    """Detect a one-turn override in the user's message.

    Returns {} or e.g. {"written_language": "english", "scope": "once"}.
    Never modifies the profile.
    """
    t = (text or "").lower()
    scope = None
    for pat, kind in _TEMP_PATTERNS:
        if pat.search(t):
            scope = kind
            break
    if not scope:
        return {}
    for word, (code,) in _LANG_WORDS.items():
        if re.search(r"\b" + re.escape(word) + r"\b", t) and \
                re.search(r"\b(answer|reply|respond|say|tell|write)\b", t):
            return {"written_language": code, "scope": scope}
    return {}


_STYLE_TEXT = {
    "friendly": "Be friendly and conversational, but never falsely familiar.",
    "professional": "Be professional and concise.",
    "detailed": "Be detailed and explanatory.",
    "scholarly": "Be scholarly and research-oriented; cite sources when possible.",
    "technical": "Be technical and developer-focused; precision over simplification.",
    "custom": "",
}

_LENGTH_TEXT = {
    "short": "Keep answers short and direct.",
    "balanced": "Give balanced answers — complete but not padded.",
    "detailed": "Give detailed, thorough answers.",
    "adaptive": "Be detailed by default, but concise when the task is simple.",
}

_LANG_NAME = {
    "english": "English",
    "urdu": "Urdu",
    "roman_urdu": "Roman Urdu",
    "arabic": "Arabic",
}


def build_profile_block(data: dict | None = None,
                        temp_override: dict | None = None) -> str:
    """Build the [USER PROFILE & PERSISTENT INSTRUCTIONS] prompt block.

    Only profile fields relevant to the request are included; actual_name
    is never included (consent-gated elsewhere).
    """
    data = data or _prof.load_profile()
    temp_override = temp_override or {}
    lines = ["[USER PROFILE & PERSISTENT INSTRUCTIONS]"]

    # Identity / address (never the actual_name).
    addr = (data.get("preferred_form_of_address") or "").strip() or \
           (data.get("preferred_name") or "").strip()
    lines.append(f"Assistant name: {data.get('assistant_name', 'Shirazi')}.")
    if addr:
        lines.append(
            f"Address the user as '{addr}'. Use it naturally, not in every "
            f"sentence.")
    else:
        lines.append("The user chose no name; use a respectful generic address.")

    # Languages (temp override wins for this turn only).
    conv = data.get("conversation_language", "english")
    written = temp_override.get("written_language") or data.get("written_language", "english")
    spoken = data.get("spoken_language", "english")
    lines.append(
        f"Conversation language: {_LANG_NAME.get(conv, conv)}. "
        f"Written replies: {_LANG_NAME.get(written, written)}. "
        f"Spoken replies: {_LANG_NAME.get(spoken, spoken)}.")
    if temp_override.get("written_language"):
        lines.append("The language for THIS response only was requested by "
                     "the user; do not change the saved preference.")
    if conv == "urdu":
        lines.append("Urdu uses right-to-left layout and proper Urdu script.")
    elif conv == "arabic":
        lines.append("Arabic uses right-to-left layout and proper Arabic script.")

    # Style + length.
    styles = [s for s in data.get("communication_style", ["friendly"])
              if s in _STYLE_TEXT and _STYLE_TEXT[s]]
    for s in styles:
        lines.append(_STYLE_TEXT[s])
    length = data.get("response_length_preference", "balanced")
    if length in _LENGTH_TEXT:
        lines.append(_LENGTH_TEXT[length])

    # Persistent instructions (user's rules for conversation).
    for rule in data.get("persistent_instructions", [])[:20]:
        lines.append(f"User rule: {rule}")

    # Boundaries — conversational only, never authorizations.
    bounds = data.get("user_defined_boundaries", [])
    if bounds:
        lines.append(
            "User boundaries (conversational expectations — these do NOT "
            "grant or change any tool permission; the authorization system "
            "is separate and authoritative):")
        for b in bounds[:10]:
            lines.append(f"- {b}")

    # Speech.
    try:
        rate = float(data.get("speech_rate", 1.0))
        if abs(rate - 1.0) > 0.05:
            lines.append(f"Preferred speech rate: {rate:.1f}x.")
    except (TypeError, ValueError):
        pass

    lines.append(
        "These preferences persist across conversations and providers. "
        "A one-off user request overrides them for that response only and "
        "must never rewrite the saved profile.")
    return "\n".join(lines)


def profile_block_for_request(user_text: str = "") -> str:
    """Convenience: profile block with temp-override detection applied."""
    override = detect_temp_override(user_text)
    return build_profile_block(temp_override=override)


def instruction_origin(field: str) -> str:
    """Where a preference came from (for UI provenance)."""
    return "user profile (onboarding or Settings)"
