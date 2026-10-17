"""
Phase 3.6 — Draft tools: create, list, approve, discard drafts.

Draft-first: content is prepared as a draft for user review; nothing is
sent/saved/published until the user explicitly approves.
"""
from __future__ import annotations

PLUGIN = {
    "name": "shirazi_draft",
    "description": (
        "Create and manage DRAFTS (draft-first workflow). Create a draft for "
        "any note, message, document, or email the user wants — the draft is "
        "saved for review and NOTHING is sent or published until the user "
        "approves it. Actions: create, list, get, approve, discard."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["create", "list", "get", "approve", "discard"],
                "description": "What to do with drafts.",
            },
            "kind": {
                "type": "STRING",
                "enum": ["note", "message", "document", "email"],
                "description": "Draft kind (for create).",
            },
            "title": {
                "type": "STRING",
                "description": "Draft title (for create).",
            },
            "content": {
                "type": "STRING",
                "description": "Draft content (for create).",
            },
            "draft_id": {
                "type": "STRING",
                "description": "Draft ID (for get/approve/discard).",
            },
        },
        "required": ["action"],
    },
}

PLUGIN_SETTINGS = None


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Mark-LV plugin contract: never raise; return a spoken string."""
    try:
        from core import drafts as _d
        params = dict(parameters or {})
        action = (params.get("action") or "list").strip().lower()

        if action == "create":
            kind = (params.get("kind") or "note").strip().lower()
            title = (params.get("title") or "Untitled").strip()
            content = (params.get("content") or "").strip()
            if not content:
                return "Draft khaali nahi ho sakta — content batayen."
            d = _d.create(kind, title, content)
            return (f"Draft tayyar hai: '{title}' (ID: {d['id']}). "
                    f"Maine kuch bheja ya save nahi kiya — aap review kar ke "
                    f"approve karen, phir hi aage barhunga.")

        if action == "list":
            ds = _d.list_drafts(status="draft")
            if not ds:
                return "Koi draft nahi hai."
            lines = ["Drafts (review ke liye):"]
            for x in ds:
                lines.append(f"  • {x['id']}: [{x['kind']}] {x['title']}")
            return "\n".join(lines)

        if action == "get":
            did = (params.get("draft_id") or "").strip()
            d = _d.get(did)
            if not d:
                return f"Draft '{did}' nahi mila."
            return f"[{d['kind']}] {d['title']}:\n{d['content']}"

        if action == "approve":
            did = (params.get("draft_id") or "").strip()
            if _d.set_status(did, "approved"):
                return (f"Draft '{did}' approve ho gaya. Ab aap kahein to "
                        f"use bhejta/save karta hun.")
            return f"Draft '{did}' nahi mila."

        if action == "discard":
            did = (params.get("draft_id") or "").strip()
            if _d.discard(did):
                return f"Draft '{did}' discard kar diya."
            return f"Draft '{did}' nahi mila."

        return f"Unknown action '{action}'."
    except Exception as e:
        return f"Draft mein masla hua: {e}"
