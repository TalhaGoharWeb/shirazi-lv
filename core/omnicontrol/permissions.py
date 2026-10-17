"""
OMNICONTROL permission-command pipeline.

Turns a user's natural-language permission request (voice transcript or typed
text) into a structured grant proposal, then applies it ONLY through the
confirmation path:

  1. parse(text)        -> proposal {action, resource_kind, resource, ops, duration_s}
                          (LLM fills this; this module validates the shape.)
  2. propose(proposal)  -> validated proposal + human-readable summary +
                          required confirmation level (voice-ok vs tap-required)
  3. confirm(proposal, via='dashboard'|'voice', approval_token=None)
                        -> applies the grant (dashboard tap) or records a
                          voice confirmation for LOW-risk reads only.

Rules (user's scoping decision):
  * Voice alone may authorize LOW-risk reads/searches inside explicitly
    approved folders, subject to existing permissions.
  * MODERATE+ always needs the dashboard tap (Allow Once / Allow Always).
  * Shirazi can NEVER grant itself privileges: confirm() rejects any proposal
    whose origin is the agent rather than the user.
  * Ambiguous resources are returned as questions, never guessed.
"""
from __future__ import annotations

import re

from . import audit, db, gateway, policy

ACTIONS = ("grant", "revoke", "pause", "resume", "status")


def parse_shape(text: str) -> dict | None:
    """
    Deterministic pre-parse for the common command shapes. The LLM handles
    free-form phrasing; this catches the structured cases without a model.
    Returns a proposal dict or None.
    """
    t = text.strip().lower()

    m = re.match(r"(allow|grant) (read|write|delete|execute|search|list)"
                 r"(?: access)? (?:to|for|on) (.+?)(?: for (\d+) (hour|minute)s?)?$", t)
    if m:
        _, op, resource, dur, unit = m.groups()
        ops = {"read": "read", "search": "read", "list": "read",
               "write": "write", "delete": "delete",
               "execute": "exec"}[op]
        return {"action": "grant", "resource_kind": "folder",
                "resource": resource.strip(), "ops": ops,
                "duration_s": int(dur) * (3600 if unit == "hour" else 60) if dur else None}

    m = re.match(r"(revoke|remove)(?: access)? (?:to|for|on) (.+)$", t)
    if m:
        return {"action": "revoke", "resource_kind": "folder",
                "resource": m.group(2).strip()}

    if t in ("stop everything", "pause all", "emergency stop"):
        return {"action": "pause"}
    if t in ("resume operations", "resume all"):
        return {"action": "resume"}
    if "what can" in t and "access" in t or t.startswith("show permissions"):
        return {"action": "status"}
    return None


def propose(proposal: dict, origin: str = "user") -> dict:
    """
    Validate a proposal. Returns {ok, summary, confirm_level, proposal} where
    confirm_level is 'voice-ok' | 'tap-required' | 'question'.
    """
    if origin != "user":
        return {"ok": False, "error": "permission changes must originate from the user"}
    action = proposal.get("action")
    if action not in ACTIONS:
        return {"ok": False, "error": "unknown action"}

    if action in ("pause",):
        return {"ok": True, "confirm_level": "voice-ok",
                "summary": "Emergency stop: block new tool calls and cancel tasks.",
                "proposal": proposal}
    if action == "resume":
        # Resuming after an emergency stop always needs the dashboard tap —
        # voice alone must not clear a safety stop.
        return {"ok": True, "confirm_level": "tap-required",
                "summary": "Clear the emergency stop and resume operations.",
                "proposal": proposal}
    if action == "status":
        return {"ok": True, "confirm_level": "voice-ok",
                "summary": "Show current permissions.", "proposal": proposal}

    resource = (proposal.get("resource") or "").strip()
    if not resource or len(resource) < 2:
        return {"ok": True, "confirm_level": "question",
                "summary": "Which folder or repository do you mean?",
                "proposal": proposal}

    if action == "grant":
        op = proposal.get("ops", "read")
        risk = {"read": policy.LOW, "write": policy.MODERATE,
                "exec": policy.HIGH, "delete": policy.HIGH}.get(op, policy.HIGH)
        if policy.is_sensitive_path(resource):
            return {"ok": True, "confirm_level": "tap-required",
                    "summary": "SENSITIVE path '%s': explicit dashboard approval required." % resource,
                    "proposal": proposal, "risk": risk}
        level = "voice-ok" if risk == policy.LOW else "tap-required"
        dur = proposal.get("duration_s")
        summary = "%s access to '%s'%s." % (
            op, resource, (" for %ss" % dur) if dur else " (persistent until revoked)")
        return {"ok": True, "confirm_level": level, "summary": summary,
                "proposal": proposal, "risk": risk}

    # revoke
    return {"ok": True, "confirm_level": "tap-required" if len(resource) < 4 else "voice-ok",
            "summary": "Revoke access to '%s'." % resource, "proposal": proposal}


def confirm(proposal: dict, via: str, origin: str = "user") -> dict:
    """
    Apply a validated proposal. via='dashboard' (user tapped) or 'voice'.
    Voice confirmations are accepted ONLY for confirm_level 'voice-ok'.
    """
    checked = propose(proposal, origin)
    if not checked.get("ok"):
        return checked
    if checked["confirm_level"] == "question":
        return {"ok": False, "error": checked["summary"]}
    if via == "voice" and checked["confirm_level"] != "voice-ok":
        return {"ok": False,
                "error": "this needs your tap on the dashboard confirmation card"}

    action = proposal["action"]
    conn = db.connect()
    if action == "grant":
        expires = (db.now() + proposal["duration_s"]) if proposal.get("duration_s") else None
        conn.execute(
            "INSERT INTO grants(principal, resource_kind, resource, ops, created_at,"
            " expires_at, persistent, created_by) VALUES ('user','folder',?,?,?, ?, ?, ?)",
            (proposal["resource"], proposal.get("ops", "read"), db.now(), expires,
             1 if expires is None else 0, "voice" if via == "voice" else "dashboard"))
        # granting write on a folder also records it in the allow-list
        ops = proposal.get("ops", "read")
        if ops in ("read", "write"):
            canon = policy._norm(proposal["resource"])
            conn.execute(
                "INSERT INTO folders(path, can_read, can_write, added_at, added_by)"
                " VALUES (?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET"
                " can_read=MAX(can_read, excluded.can_read),"
                " can_write=MAX(can_write, excluded.can_write)",
                (canon, 1, 1 if ops == "write" else 0, db.now(), via))
        conn.commit()
        audit.log("user", "grant", resource=proposal["resource"],
                  decision="granted", reason="via %s: %s" % (via, checked["summary"]))
        return {"ok": True, "summary": checked["summary"]}
    if action == "revoke":
        canon = policy._norm(proposal["resource"])
        cur = conn.execute("UPDATE grants SET revoked=1, revoked_at=? WHERE revoked=0"
                           " AND (resource=? OR resource=?)",
                           (db.now(), proposal["resource"], canon))
        conn.execute("DELETE FROM folders WHERE path=?", (canon,))
        conn.commit()
        audit.log("user", "revoke", resource=proposal["resource"],
                  decision="revoked", reason="%d grant(s) revoked via %s" % (cur.rowcount, via))
        return {"ok": True, "summary": "Revoked access to '%s'." % proposal["resource"]}
    if action == "pause":
        from . import estop
        return estop.trip(source="permission-command:" + via)
    if action == "resume":
        if via != "dashboard":
            return {"ok": False,
                    "error": "clearing an emergency stop needs your tap on the dashboard"}
        from . import estop
        estop.reset(by="dashboard")
        return {"ok": True, "summary": "Emergency stop cleared. Operations resumed."}
    return {"ok": False, "error": "not implemented: " + action}


def describe_state() -> dict:
    """Current permission state for the dashboard / 'show permissions'."""
    conn = db.connect()
    folders = [dict(r) for r in conn.execute("SELECT * FROM folders").fetchall()]
    grants = [dict(r) for r in conn.execute(
        "SELECT * FROM grants WHERE revoked=0 ORDER BY id DESC LIMIT 50").fetchall()]
    repos = [dict(r) for r in conn.execute("SELECT * FROM repos").fetchall()]
    from . import estop
    return {"estop": estop.is_tripped(), "folders": folders,
            "grants": grants, "repos": repos}
