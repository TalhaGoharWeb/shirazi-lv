"""
First-run onboarding — Personal Companion upgrade (Phase 2).

A conversational, offline-capable onboarding flow. Question 3 (assistant
name choice) was removed per the user's directive — the assistant stays
"Shirazi".

The flow is data-driven: STEPS defines each step; the UI renders them one
at a time. Progress is saved to the profile after every answer, so an
interrupted onboarding resumes where it left off.

Step ids:
  welcome → actual_name → preferred_name → conversation_language
  → language_scope → (written_language → spoken_language →
  interface_language)? → communication_style → response_length
  → voice_mode → speech_rate → memory_categories → rules
  → customize → summary
"""
from __future__ import annotations

LANGUAGES = [
    ("english", "English"),
    ("urdu", "Urdu"),
    ("roman_urdu", "Roman Urdu"),
    ("arabic", "Arabic"),
]

STYLES = [
    ("friendly", "Friendly and conversational"),
    ("professional", "Professional and concise"),
    ("detailed", "Detailed and explanatory"),
    ("scholarly", "Scholarly and research-oriented"),
    ("technical", "Technical and developer-focused"),
]

LENGTHS = [
    ("short", "Short and direct"),
    ("balanced", "Balanced"),
    ("detailed", "Detailed"),
    ("adaptive", "Detailed by default, concise when the task is simple"),
]

VOICE_MODES = [
    ("both", "Text and voice"),
    ("text_first", "Text by default, voice when I ask"),
    ("voice_focused", "Voice-focused interaction"),
]

MEMORY_CATS = [
    ("personal_preferences", "Personal preferences"),
    ("projects", "Important projects"),
    ("work_tasks", "Work and recurring tasks"),
    ("frequent_instructions", "Frequently used instructions"),
    ("technical_environment", "Technical environment and decisions"),
    ("long_term_goals", "Long-term goals"),
]

RULE_PRESETS = [
    "Always use my selected language unless I ask otherwise.",
    "Follow my chosen communication style.",
    "Do not ask me questions my profile already answers.",
    "Do not delete files without my approval.",
    "Do not publish code or send messages without my authorization.",
    "Do not install software without my authorization.",
    "Do not change security settings without my authorization.",
    "Do not access unapproved folders.",
    "Ask for clarification before making important assumptions.",
]


def build_steps() -> list[dict]:
    """Ordered step definitions. The UI renders them; logic stays here."""
    return [
        {"id": "welcome", "kind": "intro", "skippable": False,
         "title": "Welcome to Shirazi",
         "text": ("I'm Shirazi, your personal AI companion. Let me ask a few "
                  "quick questions so I can talk to you the way you like. "
                  "You can skip anything, go back, or finish later — "
                  "nothing here needs the internet.")},
        {"id": "actual_name", "kind": "text", "skippable": True,
         "title": "Your name",
         "text": ("What is your actual name? This stays private in your "
                  "profile — I won't use it in conversation unless you ask."),
         "field": "actual_name", "placeholder": "e.g. Muhammad Talha Gohar"},
        {"id": "preferred_name", "kind": "text", "skippable": True,
         "title": "What should I call you?",
         "text": ("What should I call you? A name, nickname, or title — "
                  "whatever feels right. (You can also choose no name.)"),
         "field": "preferred_name", "placeholder": "e.g. Talha"},
        {"id": "form_of_address", "kind": "text", "skippable": True,
         "title": "Form of address",
         "text": ("Is there a form of address you prefer — like 'Brother "
                  "Talha'? Leave blank and I'll just use the name above."),
         "field": "preferred_form_of_address", "placeholder": "e.g. Brother Talha"},
        {"id": "conversation_language", "kind": "choice", "skippable": False,
         "title": "Language",
         "text": "Which language should I use when talking to you?",
         "field": "conversation_language", "options": LANGUAGES},
        {"id": "language_scope", "kind": "choice", "skippable": False,
         "title": "Language scope",
         "text": ("Use the same language for my written replies, my spoken "
                  "voice, and the app interface?"),
         "options": [("same", "Yes — same everywhere"),
                     ("separate", "No — let me set each separately")]},
        {"id": "written_language", "kind": "choice", "skippable": False,
         "title": "Written language", "text": "Language for written replies?",
         "field": "written_language", "options": LANGUAGES,
         "condition": "separate_languages"},
        {"id": "spoken_language", "kind": "choice", "skippable": False,
         "title": "Spoken language", "text": "Language for my spoken voice?",
         "field": "spoken_language", "options": LANGUAGES,
         "condition": "separate_languages"},
        {"id": "interface_language", "kind": "choice", "skippable": False,
         "title": "Interface language", "text": "Language for the app interface?",
         "field": "interface_language", "options": LANGUAGES,
         "condition": "separate_languages"},
        {"id": "communication_style", "kind": "multichoice", "skippable": False,
         "title": "Communication style",
         "text": ("How should I communicate with you? Pick any that fit — "
                  "they combine."),
         "field": "communication_style", "options": STYLES},
        {"id": "response_length", "kind": "choice", "skippable": False,
         "title": "Answer length",
         "text": "How long should my answers usually be?",
         "field": "response_length_preference", "options": LENGTHS},
        {"id": "voice_mode", "kind": "choice", "skippable": False,
         "title": "Voice interaction",
         "text": "How should voice interaction work?",
         "field": "voice_mode", "options": VOICE_MODES,
         "note": "Voice is a profile preference only — the microphone is "
                 "never enabled without your explicit action."},
        {"id": "speech_rate", "kind": "slider", "skippable": True,
         "title": "Speech rate",
         "text": "How fast should I speak? (You can change this later.)",
         "field": "speech_rate", "min": 0.5, "max": 2.0, "default": 1.0},
        {"id": "memory_categories", "kind": "toggles", "skippable": False,
         "title": "What should I remember?",
         "text": ("Choose what I'm allowed to remember about you. You can "
                  "change this anytime, and I never store passwords or keys."),
         "field": "memory_preferences", "options": MEMORY_CATS},
        {"id": "rules", "kind": "rules", "skippable": True,
         "title": "Rules I should always follow",
         "text": ("Pick the rules I must always follow. These guide how I "
                  "talk to you — they never grant me permissions; the "
                  "authorization system handles that separately."),
         "field": "persistent_instructions", "options": RULE_PRESETS},
        {"id": "customize", "kind": "choice", "skippable": True,
         "title": "Anything else?",
         "text": ("Want to customize anything else right now — theme, "
                  "floating companion, notifications?"),
         "options": [("done", "No, I'm good"),
                     ("theme", "Theme and appearance"),
                     ("companion", "Floating companion"),
                     ("later", "I'll do it later in Settings")]},
        {"id": "summary", "kind": "summary", "skippable": False,
         "title": "Your profile",
         "text": ("Here's what I learned. Confirm and I'll remember it — "
                  "you can edit everything later in Settings.")},
    ]


def visible_steps(answers: dict) -> list[dict]:
    """Steps to show given answers so far (handles the language branch)."""
    separate = answers.get("language_scope") == "separate"
    out = []
    for s in build_steps():
        if s.get("condition") == "separate_languages" and not separate:
            continue
        out.append(s)
    return out


def apply_answer(step_id: str, answer, profile: dict) -> dict:
    """Validate an answer and return profile updates. Pure function."""
    updates: dict = {}
    steps = {s["id"]: s for s in build_steps()}
    step = steps.get(step_id)
    if not step:
        return updates
    field = step.get("field")

    if step["kind"] == "text":
        v = str(answer or "").strip()
        if field:
            updates[field] = v[:80]
    elif step["kind"] == "choice":
        valid = [o[0] for o in step["options"]]
        if answer in valid:
            if field:
                updates[field] = answer
            elif step_id == "language_scope" and answer == "same":
                lang = profile.get("conversation_language", "english")
                updates["written_language"] = lang
                updates["spoken_language"] = lang
                updates["interface_language"] = lang
    elif step["kind"] == "multichoice":
        valid = {o[0] for o in step["options"]}
        picked = [a for a in (answer or []) if a in valid]
        if field and picked:
            updates[field] = picked
    elif step["kind"] == "slider":
        try:
            updates[field] = min(2.0, max(0.5, float(answer)))
        except (TypeError, ValueError):
            pass
    elif step["kind"] == "toggles":
        prefs = dict(profile.get("memory_preferences", {}))
        for key, enabled in (answer or {}).items():
            if key in prefs:
                prefs[key] = bool(enabled)
        updates["memory_preferences"] = prefs
    elif step["kind"] == "rules":
        preset = [r for r in (answer or {}).get("preset", []) if r in RULE_PRESETS]
        custom = str((answer or {}).get("custom", "")).strip()
        rules = list(preset)
        if custom:
            rules.append(custom[:200])
        updates["persistent_instructions"] = rules[:50]
        # The fixed security boundaries are always on.
        updates["user_defined_boundaries"] = [
            "Do not delete files without the required approval.",
            "Do not publish code or send messages without authorization.",
            "Do not install software without authorization.",
            "Do not change security settings without authorization.",
            "Do not access unapproved folders.",
        ]
    return updates


def progress(current_idx: int, total: int) -> tuple[int, int]:
    return current_idx + 1, total
