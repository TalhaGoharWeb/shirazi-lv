"""
Lets the model read the user's saved profile settings on demand.

When the user asks "repeat my settings", "what do you know about me", or
"what language did I choose", the model calls this instead of guessing.
Returns the non-private profile summary — the actual_name is NEVER
exposed (it is private and never used in conversation).
"""
from __future__ import annotations

PLUGIN = {
    "name": "shirazi_my_settings",
    "description": (
        "Read the user's saved profile settings: what to call them, "
        "languages, communication style, answer length, rules and "
        "boundaries. Call this when the user asks about their settings, "
        "what you remember about them, or how you're configured to talk "
        "to them. Never reveals the private actual name."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {},
        "required": [],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        from core import profile as _prof
        d = _prof.load_profile()
    except Exception as e:
        return f"Profile unavailable: {e}"
    if not d.get("onboarding_completed"):
        return ("No completed profile yet — the user hasn't finished "
                "onboarding. Offer to open it from Settings.")
    lang_name = {"english": "English", "urdu": "Urdu",
                 "roman_urdu": "Roman Urdu", "arabic": "Arabic"}
    lines = []
    addr = d.get("preferred_form_of_address") or d.get("preferred_name")
    lines.append(f"Address the user as: {addr}" if addr
                 else "Address: no name chosen (respectful generic form)")
    cl = d.get("conversation_language", "english")
    wl = d.get("written_language", "english")
    sl = d.get("spoken_language", "english")
    lines.append(f"Conversation language: {lang_name.get(cl, cl)}")
    if wl != cl or sl != cl:
        lines.append(f"Written: {lang_name.get(wl, wl)}; "
                     f"Spoken: {lang_name.get(sl, sl)}")
    lines.append("Style: " + ", ".join(d.get("communication_style",
                                             ["friendly"])))
    lines.append("Answer length: " +
                 d.get("response_length_preference", "balanced"))
    rules = d.get("persistent_instructions", [])
    if rules:
        lines.append("Rules:")
        lines.extend(f"  - {r}" for r in rules[:15])
    bounds = d.get("user_defined_boundaries", [])
    if bounds:
        lines.append("Boundaries (conversational, not permissions):")
        lines.extend(f"  - {b}" for b in bounds[:10])
    return "\n".join(lines)
