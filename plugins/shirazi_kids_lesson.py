"""Bachon ki Dunya — Islamic teacher for kids (Shirazi LV plugin).

Teaches children simple Islamic things in warm Roman Urdu: choti duain,
Seerat-un-Nabi ﷺ ke pyare waqiat, achay akhlaq, namaz, Nabiyon ke qissay,
Quran ki baatein. All content is original and age-appropriate (~4-10).

Content lives in plugins/_kids_content.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _kids_content import LESSON_TOPICS, LESSONS, format_lesson  # noqa: E402

PLUGIN = {
    "name": "shirazi_kids_lesson",
    "description": (
        "Bachon ko achi islami baatein sikhayo: choti duain, Nabi ﷺ ki seerat ke "
        "pyare waqiat, achay akhlaq ki aadatain, namaz ka tareeqa, Nabiyon ke qissay, "
        "Quran ki baatein. Simple Roman Urdu mein, choton ke liye aasan alfaaz. "
        "Use jab bacha deen ki koi baat seekhna chahe taake wo acha bacha ban sake."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "topic": {
                "type": "STRING",
                "enum": ["dua", "seerah", "akhlaq", "namaz", "prophets", "quran"],
                "description": "Kya sikhana hai: dua=choti duain, seerah=Nabi ﷺ ki baatein, "
                               "akhlaq=achi aadatain, namaz=namaz ka tareeqa, "
                               "prophets=Nabiyon ke qissay, quran=Quran ki baatein.",
            },
            "child_name": {
                "type": "STRING",
                "description": "Bachay ka naam (optional) — sabaq isi naam se shuru hoga.",
            },
        },
        "required": ["topic"],
    },
}

PLUGIN_SETTINGS = None


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Mark-LV plugin contract: never raise; return a spoken string."""
    try:
        params = dict(parameters or {})
        topic = (params.get("topic") or "akhlaq").strip().lower()
        if topic not in LESSONS:
            topic = "akhlaq"
        child = (params.get("child_name") or "").strip() or None
        greeting = f"{child}, " if child else ""
        return f"{greeting}{format_lesson(topic)}"
    except Exception as e:
        return f"Sabaq dene mein masla hua: {e}"
