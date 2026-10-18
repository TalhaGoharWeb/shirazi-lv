"""Bachon ki Dunya — moral storyteller for kids (Shirazi LV plugin).

Tells original sabaq-amoz kahaniyan in simple Roman Urdu, personalised with
the child's name when given. Every story ends with its sabaq (moral).

All story content lives in plugins/_kids_content.py (original writing, no
copyright issues) and grows by appending there.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _kids_content import THEMES, format_story, pick_story  # noqa: E402

PLUGIN = {
    "name": "shirazi_kids_story",
    "description": (
        "Bachon ko pyari sabaq-amoz kahani sunao. Simple Roman Urdu mein original "
        "moral stories (sach, meherbani, sabr, shukr, safai, walidain ki khidmat, "
        "Seerat-un-Nabi ke waqiat) — har kahani ke aakhir mein sabaq. Bachay ka naam "
        "do to kahani usi ke naam se shuru hoti hai. Use jab koi bacha kahani sunna chahe."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "theme": {
                "type": "STRING",
                "enum": ["sach", "meherbani", "sabr", "shukr", "safai",
                         "walidain", "eman", "himmat", "maafi", "mehnat",
                         "namaz", "koi bhi"],
                "description": "Kahani ka mauzu. 'koi bhi' par koi achi kahani.",
            },
            "child_name": {
                "type": "STRING",
                "description": "Bachay ka naam (optional) — kahani isi naam se shuru hogi.",
            },
        },
    },
}

PLUGIN_SETTINGS = None


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Mark-LV plugin contract: never raise; return a spoken string."""
    try:
        params = dict(parameters or {})
        theme = (params.get("theme") or "koi bhi").strip().lower()
        if theme not in THEMES:
            theme = "koi bhi"
        child = (params.get("child_name") or "").strip() or None
        story = pick_story(theme if theme != "koi bhi" else None)
        return format_story(story, child)
    except Exception as e:
        return f"Kahani sunane mein masla hua: {e}"
