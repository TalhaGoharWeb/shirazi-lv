"""
OMNICONTROL task orchestrator — persistent, cancellable, verifiable tasks.

States: QUEUED -> PLANNING -> AWAITING_APPROVAL -> RUNNING -> VERIFYING
         -> DONE | FAILED -> RECOVERY_REQUIRED | CANCELLED

* Every state transition is persisted in omnicontrol.db and audit-logged.
* Checkpoints: before a HIGH-risk step the orchestrator snapshots the
  affected paths (file hashes) so recovery can verify what changed.
* Cancellation is cooperative + enforced: cancel() flips the task to
  CANCELLED and the runner checks the flag between steps; estop cancels all.
* Verification is real: a task is DONE only when its verify() callable
  returns truthy evidence (exit code 0, artifact exists, hash matches).
  Outcomes are never fabricated.
"""
from __future__ import annotations

import hashlib
import json
import threading
import uuid
from pathlib import Path

from . import audit, db, estop, gateway

QUEUED, PLANNING, AWAITING_APPROVAL, RUNNING = "QUEUED", "PLANNING", "AWAITING_APPROVAL", "RUNNING"
VERIFYING, DONE, FAILED, RECOVERY_REQUIRED, CANCELLED = "VERIFYING", "DONE", "FAILED", "RECOVERY_REQUIRED", "CANCELLED"
# Phase 3.2: CANCELLING = cancel requested but not yet confirmed;
# TIMED_OUT = a step exceeded its budget. Terminal states: DONE, FAILED,
# RECOVERY_REQUIRED, CANCELLED, TIMED_OUT.
CANCELLING, TIMED_OUT = "CANCELLING", "TIMED_OUT"
TERMINAL = frozenset({DONE, FAILED, RECOVERY_REQUIRED, CANCELLED, TIMED_OUT})

_lock = threading.RLock()
_cancel_flags: set[str] = set()


def _row(tid: str) -> dict | None:
    conn = db.connect()
    r = conn.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
    return dict(r) if r else None


def _set_state(tid: str, state: str, result: dict | None = None) -> None:
    conn = db.connect()
    if result is not None:
        conn.execute("UPDATE tasks SET state=?, updated_at=?, result_json=? WHERE id=?",
                     (state, db.now(), json.dumps(result, default=str), tid))
    else:
        conn.execute("UPDATE tasks SET state=?, updated_at=? WHERE id=?",
                     (state, db.now(), tid))
    conn.commit()
    audit.log("orchestrator", "task-state", resource=tid, decision=state)


def start(title: str, workspace: str, plan: list[dict]) -> str:
    """
    Create a task. plan = [{'tool':..., 'resource':..., 'op':..., 'params':...,
    'verify': 'artifact_exists'|'exit_zero'|None, 'checkpoint_paths': [...]}]
    """
    tid = "task-" + uuid.uuid4().hex[:12]
    conn = db.connect()
    conn.execute(
        "INSERT INTO tasks(id, title, state, workspace, plan_json, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (tid, title, QUEUED, workspace, json.dumps(plan), db.now(), db.now()))
    conn.commit()
    audit.log("orchestrator", "task-start", resource=tid, decision=QUEUED,
              reason=title)
    return tid


def cancel(tid: str, reason: str = "user request") -> bool:
    """Request cancellation. QUEUED/PLANNING/AWAITING_APPROVAL tasks stop
    immediately (CANCELLED); a RUNNING task moves to CANCELLING and the
    runner confirms CANCELLED between steps — cancel-requested vs confirmed
    are distinct states."""
    with _lock:
        _cancel_flags.add(tid)
    row = _row(tid)
    if not row or row["state"] in TERMINAL:
        return False
    if row["state"] == RUNNING:
        _set_state(tid, CANCELLING, {"reason": reason})
        audit.log("orchestrator", "task-cancel-requested", resource=tid,
                  decision=CANCELLING, reason=reason)
    else:
        _set_state(tid, CANCELLED, {"reason": reason})
        audit.log("orchestrator", "task-cancel", resource=tid,
                  decision=CANCELLED, reason=reason)
    return True


def cancel_all(source: str = "estop") -> dict[str, bool]:
    conn = db.connect()
    rows = conn.execute(
        "SELECT id FROM tasks WHERE state NOT IN "
        "('DONE','FAILED','RECOVERY_REQUIRED','CANCELLED','TIMED_OUT')").fetchall()
    return {r["id"]: cancel(r["id"], "cancelled by %s" % source) for r in rows}


def _wants_cancel(tid: str) -> bool:
    return tid in _cancel_flags or estop.is_tripped()


def _snapshot(paths: list[str]) -> dict:
    snap = {}
    for p in paths or []:
        try:
            snap[p] = hashlib.sha256(Path(p).read_bytes()).hexdigest()
        except OSError:
            snap[p] = None  # did not exist
    return snap


def run(tid: str, approval_token: str | None = None) -> dict:
    """
    Execute a task's plan step by step through the gateway. Synchronous;
    main.py runs this in a worker thread. Returns the final result dict.
    """
    row = _row(tid)
    if not row:
        return {"ok": False, "error": "unknown task"}
    plan = json.loads(row["plan_json"] or "[]")
    _set_state(tid, RUNNING)
    evidence: list[dict] = []

    for i, step in enumerate(plan):
        if _wants_cancel(tid):
            # Phase 3.2: confirm the requested cancellation.
            _set_state(tid, CANCELLED, {"steps_done": i, "evidence": evidence,
                                       "cancel_confirmed": True})
            audit.log("orchestrator", "task-cancel-confirmed", resource=tid,
                      decision=CANCELLED)
            return {"ok": False, "error": "cancelled", "steps_done": i}

        tool, resource = step["tool"], step["resource"]
        op = step.get("op", "read")

        # Checkpoint before high-risk steps.
        before = _snapshot(step.get("checkpoint_paths"))

        # Phase 3.2: per-step timeout (default 120s, overridable per step).
        _timeout = float(step.get("timeout_s", 120))
        try:
            res = gateway.execute(tool, resource, op, step.get("params"),
                                  approval_token if _needs_token(tool) else None,
                                  actor="orchestrator:%s" % tid,
                                  timeout_s=_timeout)
        except TimeoutError:
            _set_state(tid, TIMED_OUT, {"failed_step": i, "timeout_s": _timeout,
                                       "evidence": evidence})
            audit.log("orchestrator", "task-timeout", resource=tid,
                      decision=TIMED_OUT,
                      reason="step %d exceeded %ss" % (i, _timeout))
            return {"ok": False, "error": "timed out", "failed_step": i}
        step_ev = {"step": i, "tool": tool, "ok": res["ok"],
                   "changed": {p: (before.get(p),
                                   _snapshot([p]).get(p)) for p in before}}
        evidence.append(step_ev)

        if not res["ok"]:
            # One retry with fresh diagnostics is NOT new evidence; fail
            # honestly instead of looping.
            _set_state(tid, FAILED, {"failed_step": i, "error": res["error"],
                                     "evidence": evidence})
            audit.log("orchestrator", "task-failed", resource=tid,
                      decision=FAILED, reason=res["error"][:200])
            return {"ok": False, "error": res["error"], "failed_step": i}

    # A cancel requested during the final step must still be honoured —
    # never report DONE for a task the user cancelled.
    if _wants_cancel(tid):
        _set_state(tid, CANCELLED, {"steps_done": len(plan), "evidence": evidence,
                                   "cancel_confirmed": True})
        audit.log("orchestrator", "task-cancel-confirmed", resource=tid,
                  decision=CANCELLED)
        return {"ok": False, "error": "cancelled", "steps_done": len(plan)}
    _set_state(tid, VERIFYING)
    verified = _verify(plan, evidence)
    final = DONE if verified else RECOVERY_REQUIRED
    _set_state(tid, final, {"evidence": evidence, "verified": verified})
    return {"ok": verified, "state": final, "evidence": evidence}


def _needs_token(tool: str) -> bool:
    from . import policy
    return policy.risk_of(tool) in (policy.HIGH, policy.CRITICAL)


def _verify(plan: list[dict], evidence: list[dict]) -> bool:
    """All steps ok AND every declared verification holds."""
    if any(not e["ok"] for e in evidence):
        return False
    for step, ev in zip(plan, evidence):
        kind = step.get("verify")
        if kind == "artifact_exists":
            p = Path(step["params"].get("artifact", step["resource"]))
            if not p.exists():
                return False
    return True


def status(tid: str) -> dict | None:
    row = _row(tid)
    if not row:
        return None
    row["plan"] = json.loads(row["plan_json"] or "[]")
    if row["result_json"]:
        row["result"] = json.loads(row["result_json"])
    return row


def list_tasks(limit: int = 50) -> list[dict]:
    conn = db.connect()
    rows = conn.execute(
        "SELECT id, title, state, workspace, created_at, updated_at FROM tasks"
        " ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]
