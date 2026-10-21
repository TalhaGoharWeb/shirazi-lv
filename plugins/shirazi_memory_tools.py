"""
Memory tools for the model — Personal Companion, Phase 7.

Gives Shirazi explicit, safe tools to remember, recall, and correct
facts during conversation:

- shirazi_remember: store an explicit fact (secret-shaped values refused,
  duplicates detected, provenance recorded as user_explicit).
- shirazi_recall: search stored memories by keyword and category.
- shirazi_correct_memory: fix a wrong fact (provenance notes the correction).

All LOW risk (memory-only, no external side effects, user-deletable).
"""
from __future__ import annotations

PLUGIN = {
    "name": "shirazi_memory_tools",
    "description": (
        "Remember an explicit fact, search stored memories, or correct a "
        "wrong fact. Use when the user says 'remember this', asks 'what do "
        "you remember about X', or corrects something you recalled."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "One of: remember, recall, correct.",
            },
            "key": {
                "type": "STRING",
                "description": "Short label for the fact (remember/correct).",
            },
            "value": {
                "type": "STRING",
                "description": "The fact itself (remember/correct).",
            },
            "query": {
                "type": "STRING",
                "description": "Search keywords (recall).",
            },
            "category": {
                "type": "STRING",
                "description": ("Memory category: identity, preferences, "
                                "projects, relationships, wishes, notes."),
            },
        },
        "required": ["action"],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        from memory import memory_manager as _mm
    except Exception as e:
        return f"Memory unavailable: {e}"
    p = parameters or {}
    action = str(p.get("action", "")).lower().strip()
    category = str(p.get("category", "notes")).strip() or "notes"

    try:
        if action == "remember":
            key = str(p.get("key", "")).strip()[:60] or "note"
            value = str(p.get("value", "")).strip()
            if not value:
                return "Nothing to remember — no value given."
            return _mm.remember_explicit(key, value, category,
                                         origin="conversation")
        if action == "recall":
            query = str(p.get("query", "")).strip()
            if not query:
                return "Nothing to search for — no query given."
            rows = _mm.search_entries(
                query, category=None if category == "notes" else category,
                limit=8)
            if not rows:
                return f"No memories match '{query}'."
            return "\n".join(
                f"- [{r['category']}] {r['key']}: {r['value']}" for r in rows)
        if action == "correct":
            key = str(p.get("key", "")).strip()
            value = str(p.get("value", "")).strip()
            if not key or not value:
                return "To correct a memory I need both the key and the new value."
            return _mm.edit_entry(key, value, category)
        return f"Unknown action '{action}' — use remember, recall, or correct."
    except Exception as e:
        return f"Memory tool failed: {e}"
