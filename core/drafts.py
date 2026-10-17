"""
Phase 3.6 — Draft-first productivity workflows.

Principle: anything that creates external effects (sending a message,
saving a file, publishing) starts as a DRAFT. The user reviews the draft
in the HUD/dashboard; only explicit approval finalizes it.

Drafts live in ~/.shirazi/drafts/ as JSON. Each draft has:
  id, kind ('note'|'message'|'document'|'email'), title, content,
  created_at, status ('draft'|'approved'|'discarded'|'sent')
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path

_lock = threading.Lock()


def _drafts_dir() -> Path:
    d = Path(os.environ.get("SHIRAZI_DATA_DIR", str(Path.home() / ".shirazi")))
    d = d / "drafts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(did: str) -> Path:
    # Sanitize: only hex + dashes from our own uuids.
    safe = "".join(c for c in did if c.isalnum() or c == "-")[:40]
    return _drafts_dir() / f"{safe}.json"


def create(kind: str, title: str, content: str) -> dict:
    """Create a draft. Returns the draft dict (status='draft')."""
    did = "draft-" + uuid.uuid4().hex[:12]
    draft = {
        "id": did,
        "kind": kind,
        "title": title,
        "content": content,
        "created_at": time.time(),
        "status": "draft",
    }
    with _lock:
        _path(did).write_text(json.dumps(draft, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    return draft


def get(did: str) -> dict | None:
    p = _path(did)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def list_drafts(status: str | None = None, limit: int = 20) -> list[dict]:
    """List drafts, newest first. Optionally filter by status."""
    drafts = []
    for p in _drafts_dir().glob("draft-*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if status is None or d.get("status") == status:
                drafts.append(d)
        except Exception:
            continue
    drafts.sort(key=lambda d: d.get("created_at", 0), reverse=True)
    return drafts[:limit]


def set_status(did: str, status: str) -> bool:
    """Set draft status: 'approved' | 'discarded' | 'sent'. Returns success."""
    if status not in ("approved", "discarded", "sent", "draft"):
        return False
    with _lock:
        d = get(did)
        if not d:
            return False
        d["status"] = status
        _path(did).write_text(json.dumps(d, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    return True


def discard(did: str) -> bool:
    return set_status(did, "discarded")
