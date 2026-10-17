"""
OMNICONTROL emergency stop — implemented in the LOCAL control layer.

The user's scoping decision: emergency stop "must not depend on the AI model
responding". So this module touches no model, no network, no plugin: it flips
a flag in the local SQLite DB (plus an in-process latch for speed) that the
gateway checks on EVERY tool call before anything else.

Triggers (all three call trip()):
  * voice:   the configurable emergency phrase, matched in main.py's voice
             session handler — no LLM call, just string matching.
  * dashboard: prominent "Stop All Tasks" button -> POST /api/omni/estop
  * HUD:     configurable global hotkey -> trip()

trip() also cancels orchestrator tasks and invalidates one-shot execution
approvals; anything it could not stop is audit-logged as such.
"""
from __future__ import annotations

import threading

from . import audit, db

_lock = threading.RLock()
_latched = False  # in-process fast path; DB is the durable source of truth


def is_tripped() -> bool:
    """True if emergency stop is active. Pure local check — no model involved."""
    global _latched
    with _lock:
        if _latched:
            return True
        conn = db.connect()
        row = conn.execute("SELECT value FROM kv WHERE key='estop'").fetchone()
        tripped = row is not None and row["value"] == "1"
        if tripped:
            _latched = True
        return tripped


def trip(source: str = "unknown") -> dict:
    """Engage emergency stop. Returns what was stopped / what could not be."""
    global _latched
    with _lock:
        conn = db.connect()
        conn.execute("INSERT OR REPLACE INTO kv(key, value) VALUES ('estop','1')")
        # Invalidate one-shot approvals: revoke non-persistent live grants.
        cur = conn.execute(
            "UPDATE grants SET revoked=1, revoked_at=? "
            "WHERE revoked=0 AND persistent=0", (db.now(),))
        approvals_invalidated = cur.rowcount
        conn.commit()
        _latched = True

    # Cancel orchestrator tasks (best effort; failures are logged, not hidden).
    unstoppable: list[str] = []
    cancelled: list[str] = []
    try:
        from . import orchestrator
        for tid, outcome in orchestrator.cancel_all(source="estop").items():
            (cancelled if outcome else unstoppable).append(tid)
    except Exception as exc:  # orchestrator must never break estop
        unstoppable.append("orchestrator-error: %s" % exc)

    audit.log("estop", "trip", decision="engaged",
              reason="triggered via %s" % source,
              details={"approvals_invalidated": approvals_invalidated,
                       "tasks_cancelled": cancelled,
                       "not_stopped": unstoppable})
    return {"tripped": True, "source": source,
            "approvals_invalidated": approvals_invalidated,
            "tasks_cancelled": cancelled, "not_stopped": unstoppable}


def reset(by: str = "user") -> None:
    """Clear emergency stop. Requires an explicit user/dashboard action."""
    global _latched
    with _lock:
        conn = db.connect()
        conn.execute("INSERT OR REPLACE INTO kv(key, value) VALUES ('estop','0')")
        conn.commit()
        _latched = False
    audit.log("estop", "reset", decision="cleared", reason="reset by %s" % by)


def emergency_phrase() -> str:
    conn = db.connect()
    row = conn.execute("SELECT value FROM kv WHERE key='emergency_phrase'").fetchone()
    return row["value"] if row else "stop everything"


def set_emergency_phrase(phrase: str) -> None:
    conn = db.connect()
    conn.execute("INSERT OR REPLACE INTO kv(key, value) VALUES ('emergency_phrase',?)",
                 (phrase.strip().lower(),))
    conn.commit()
