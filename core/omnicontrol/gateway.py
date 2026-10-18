"""
OMNICONTROL Authorization Gateway — the single choke point.

EVERY protected tool call flows through Gateway.execute(), whether it comes
from voice, chat, an autonomous workflow, a plugin, the mobile dashboard or
another agent. There is no second route: core/plugin_loader.py wraps its
tool dispatch with this gateway, and the MCP servers call back into it.

Pipeline per call (§5 of the spec):
  1. Emergency-stop check (local layer, no model).
  2. Tool registration check (unknown tool => deny as CRITICAL).
  3. Resolve resource + required op from the tool's declaration.
  4. Filesystem boundary check (allow-list + sensitive-child rule).
  5. Grant check (deny-by-default; expiry + revocation revalidated now).
  6. Risk-tier approval: HIGH/CRITICAL need a live one-shot approval token
     issued through the dashboard confirmation card — voice alone is not
     enough, and the model can never mint approvals for itself.
  7. Execute via the registered handler.
  8. Audit allow/deny with reason. Secrets never reach the audit log.

Approval tokens: short-lived (default 120 s), single-tool, single-resource,
stored in the DB; consumed on use. Issued ONLY by user_approve() which the
dashboard calls after the user taps Allow Once / Allow Always.
"""
from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass, field

from . import audit, db, estop, policy

_lock = threading.RLock()
_handlers: dict[str, callable] = {}
_approvals: dict[str, dict] = {}  # token -> {tool, resource, op, expires}
_pending: dict[str, dict] = {}    # id -> pending approval request (dashboard)
# tool -> {token, expires}: dashboard "Allow Once" grants waiting to be
# consumed by the agent's retry. Lets the model retry after the user approves
# without the token having to travel through the model itself.
_pending_grants: dict[str, dict] = {}

# ── Real risk tiers (P2.2). Every built-in tool gets its actual tier here.
# LOW: read-only, auto-allow. MODERATE: state-changing but scoped, auto-allow
# with audit. HIGH: needs dashboard approval per call. CRITICAL: blocked.
TOOL_RISK_MAP: dict[str, str] = {
    # — plugins: HIGH (deletion / irreversible) —
    "shirazi_bookmark_delete": policy.HIGH,
    "shirazi_note_delete": policy.HIGH,
    "shirazi_organize_apply": policy.HIGH,
    "shirazi_training_forget": policy.HIGH,
    "shirazi_term_forget": policy.HIGH,
    # — plugins: MODERATE (creates / edits / state changes) —
    "shirazi_bookmark_save": policy.MODERATE,
    "shirazi_note_save": policy.MODERATE,
    "shirazi_clipboard_set": policy.MODERATE,
    "shirazi_excel_create": policy.MODERATE,
    "shirazi_listing_create": policy.MODERATE,
    "shirazi_urdu_draft": policy.MODERATE,
    "shirazi_mcq_generate": policy.MODERATE,
    "shirazi_task_checkpoint": policy.MODERATE,
    "shirazi_task_resume": policy.MODERATE,
    "shirazi_timer_start": policy.MODERATE,
    "shirazi_timer_cancel": policy.MODERATE,
    "shirazi_stopwatch_start": policy.MODERATE,
    "shirazi_stopwatch_stop": policy.MODERATE,
    "shirazi_train_command": policy.MODERATE,
    "shirazi_train_correction": policy.MODERATE,
    "shirazi_train_fact": policy.MODERATE,
    "shirazi_train_preference": policy.MODERATE,
    "shirazi_train_test": policy.MODERATE,
    "shirazi_term_add": policy.MODERATE,
    "shirazi_quiz_start": policy.MODERATE,
    "shirazi_quiz_stop": policy.MODERATE,
    "shirazi_quiz_grade": policy.MODERATE,
    "shirazi_research_add_source": policy.MODERATE,
    "shirazi_research_report": policy.MODERATE,
    "shirazi_research_start": policy.MODERATE,
    "shirazi_build_fix_checklist": policy.MODERATE,
    "shirazi_problem_plan": policy.MODERATE,
    # — actions: HIGH (system control / code exec / file writes) —
    "computer_control": policy.HIGH,
    "computer_settings": policy.HIGH,
    "desktop": policy.HIGH,
    "open_app": policy.HIGH,
    "browser_control": policy.HIGH,
    "file_controller": policy.HIGH,
    "send_message": policy.HIGH,
    "dev_agent": policy.HIGH,
    "code_helper": policy.HIGH,
    # — actions: MODERATE —
    "file_processor": policy.MODERATE,
    "reminder": policy.MODERATE,
    "video_player": policy.MODERATE,
    "game_updater": policy.MODERATE,
    "flight_finder": policy.MODERATE,
    # — inline built-ins (main.py _execute_tool) —
    "shutdown_shirazi": policy.HIGH,
    "undo": policy.HIGH,
    "save_memory": policy.MODERATE,
    "manage_monitor": policy.MODERATE,
    "recall_memory": policy.LOW,
    "screen_process": policy.LOW,
    "close_camera": policy.LOW,
    "system_status": policy.LOW,
}
# Anything not listed here defaults to LOW (read-only tools). Unknown tools
# (not registered at all) are CRITICAL-deny via the registration check.


def request_approval(tool: str, resource: str, op: str, reason: str) -> str:
    """
    Create a pending approval request for the dashboard's Permissions view.
    Returns the request id. The agent's tool call fails with needs_approval;
    the user taps Allow Once / Allow Always / Deny on the dashboard.
    """
    import uuid as _uuid
    pid = "apr-" + _uuid.uuid4().hex[:10]
    with _lock:
        _pending[pid] = {"id": pid, "tool": tool, "resource": resource,
                         "op": op, "risk": policy.TOOL_RISK.get(tool),
                         "reason": reason, "ts": db.now(), "status": "pending"}
    audit.log("gateway", "approval-requested", tool=tool, resource=resource,
              decision="pending", reason=reason)
    return pid


def list_pending() -> list[dict]:
    with _lock:
        return [dict(v) for v in _pending.values() if v["status"] == "pending"]


def resolve_pending(pid: str, decision: str) -> dict:
    """
    Dashboard resolution: 'once' -> one-shot token, 'always' -> persistent
    grant, 'deny' -> denied. Returns {'ok', ...}.
    """
    with _lock:
        req = _pending.get(pid)
        if not req or req["status"] != "pending":
            return {"ok": False, "error": "request not found or already resolved"}
        req["status"] = decision
    if decision == "once":
        token = user_approve(req["tool"], req["resource"], req["op"])
        # Leave the grant where the agent's retry can consume it: the model
        # never sees the token, but its next authorize_builtin() call will.
        with _lock:
            _pending_grants[req["tool"]] = {"token": token,
                                           "expires": db.now() + 120}
        return {"ok": True, "decision": "once", "approval_token": token}
    if decision == "always":
        user_approve(req["tool"], req["resource"], req["op"], persistent=True)
        return {"ok": True, "decision": "always"}
    audit.log("user", "approval-denied", tool=req["tool"],
              resource=req["resource"], decision="deny")
    return {"ok": True, "decision": "deny"}


@dataclass
class Decision:
    allowed: bool
    reason: str
    risk: str = policy.LOW
    grant: dict | None = None
    approval_request_id: str | None = None


def register_tool(name: str, handler: callable, risk: str | None = None) -> None:
    """Register a tool implementation. Risk defaults to policy.TOOL_RISK."""
    with _lock:
        _handlers[name] = handler
        if risk:
            policy.TOOL_RISK[name] = risk


def register_builtin(name: str, risk: str | None = None) -> None:
    """
    Register a built-in product tool. Risk comes from TOOL_RISK_MAP (P2.2);
    an explicit risk argument overrides the map. EVERY call still passes
    the estop check and is audit-logged. HIGH/CRITICAL need dashboard
    approval per call.
    """
    with _lock:
        _handlers[name] = None  # executed by plugin_loader, not here
        policy.TOOL_RISK[name] = risk or TOOL_RISK_MAP.get(name, policy.LOW)


def _consume_pending_grant(tool: str) -> bool:
    """Consume a dashboard "Allow Once" grant left for the agent's retry."""
    with _lock:
        g = _pending_grants.get(tool)
        if not g:
            return False
        if g["expires"] <= db.now():
            _pending_grants.pop(tool, None)
            return False
        _pending_grants.pop(tool, None)  # single use
        return True


def authorize_builtin(name: str, approval_token: str | None = None) -> Decision:
    """Authorize one built-in plugin/action run. Used by the loaders."""
    if estop.is_tripped():
        d = Decision(False, "emergency stop is active", policy.CRITICAL)
    elif name not in _handlers:
        d = Decision(False, "unknown tool '%s' (deny-by-default)" % name,
                     policy.CRITICAL)
    else:
        risk = policy.TOOL_RISK.get(name, policy.CRITICAL)
        if risk == policy.CRITICAL:
            d = Decision(False, "CRITICAL-risk tool '%s' is blocked" % name,
                         risk)
        elif risk == policy.HIGH and not (
                _consume_approval(approval_token, name, "*")
                or _consume_pending_grant(name)):
            pid = request_approval(
                name, "*", "execute",
                "HIGH-risk tool '%s' needs dashboard approval" % name)
            d = Decision(False,
                         "HIGH-risk tool '%s' needs your approval — "
                         "I've sent a request to the dashboard Permissions view. "
                         "Ask the user to tap Allow Once, then try again." % name,
                         risk)
            d.approval_request_id = pid
        else:
            d = Decision(True, "built-in tool authorized", risk)
    audit.log("gateway", "builtin", tool=name,
              decision="allow" if d.allowed else "deny", reason=d.reason)
    return d


def _consume_approval(token: str | None, tool: str, resource: str) -> bool:
    if not token:
        return False
    with _lock:
        ap = _approvals.get(token)
        if not ap:
            return False
        if ap["expires"] <= db.now() or ap["tool"] != tool:
            _approvals.pop(token, None)
            return False
        # resource must match (or approval was '*')
        if ap["resource"] not in ("*", resource):
            return False
        _approvals.pop(token, None)  # single use
        return True


def user_approve(tool: str, resource: str, op: str, ttl_s: int = 120,
                 persistent: bool = False) -> str:
    """
    Called ONLY from the dashboard confirmation path after the user taps
    Allow Once / Allow Always. Mints a one-shot approval token (Allow Once)
    or a persistent grant row (Allow Always).
    """
    if persistent:
        conn = db.connect()
        conn.execute(
            "INSERT INTO grants(principal, resource_kind, resource, ops, created_at,"
            " persistent, created_by) VALUES ('user','tool',?,?,?,1,'dashboard')",
            (tool, op, db.now()))
        conn.commit()
        audit.log("user", "grant", tool=tool, resource=resource,
                  decision="allow-always", reason="dashboard approval")
        return "grant-persistent"
    token = secrets.token_urlsafe(24)
    with _lock:
        _approvals[token] = {"tool": tool, "resource": resource, "op": op,
                             "expires": db.now() + ttl_s}
    audit.log("user", "approve-once", tool=tool, resource=resource,
              decision="allow-once", reason="dashboard approval, %ss TTL" % ttl_s)
    return token


def authorize(tool: str, resource: str, op: str,
              approval_token: str | None = None) -> Decision:
    """Pure policy check — no execution. Every execute() calls this first."""
    # 1. Emergency stop — local layer, model-independent.
    if estop.is_tripped():
        return Decision(False, "emergency stop is active", policy.CRITICAL)

    # 2. Tool must be registered.
    risk = policy.TOOL_RISK.get(tool)
    if tool not in _handlers or risk is None:
        return Decision(False, "unknown tool '%s' (deny-by-default)" % tool,
                        policy.CRITICAL)

    # 3+4. Filesystem boundary for fs_* tools.
    if tool.startswith("fs_"):
        ok, reason = policy.check_path(resource, op)
        if not ok:
            return Decision(False, "filesystem boundary: " + reason, risk)

    # 5. Grant check (deny-by-default; revalidated at call time).
    grant = policy.live_grant("tool", tool, op)
    needs_approval = risk in (policy.HIGH, policy.CRITICAL)

    # 6. Risk-tier approval.
    if risk == policy.CRITICAL:
        return Decision(False, "CRITICAL-risk tool blocked by policy", risk, grant)
    if needs_approval:
        if not _consume_approval(approval_token, tool, resource):
            pid = request_approval(
                tool, resource, op,
                "HIGH-risk tool '%s' needs dashboard approval" % tool)
            d = Decision(False,
                         "HIGH-risk tool '%s' needs your approval — "
                         "check the dashboard Permissions view (Allow Once / "
                         "Allow Always / Deny)" % tool, risk, grant)
            d.approval_request_id = pid
            return d
    elif grant is None:
        # LOW/MODERATE without any grant => deny (deny-by-default).
        # Exception: LOW-risk fs reads inside allow-listed folders are covered
        # by the folder allow-list itself (the user's "voice OK for low-risk
        # reads in approved folders" decision).
        if not (risk == policy.LOW and tool.startswith("fs_")):
            return Decision(False,
                            "no live grant for tool '%s' op '%s'" % (tool, op),
                            risk, grant)
    return Decision(True, "authorized", risk, grant)


def execute(tool: str, resource: str, op: str, params: dict | None = None,
            approval_token: str | None = None, actor: str = "agent",
            timeout_s: float | None = None) -> dict:
    """
    Authorize + execute. Returns {'ok': bool, 'result'|'error': ...}.
    This is the ONLY sanctioned way to run a protected tool.
    timeout_s: if set, the handler must finish within the budget or
    TimeoutError is raised (Phase 3.2 — the orchestrator maps it to TIMED_OUT).
    """
    dec = authorize(tool, resource, op, approval_token)
    audit.log(actor, "execute", tool=tool, resource=resource,
              decision="allow" if dec.allowed else "deny", reason=dec.reason)
    if not dec.allowed:
        out = {"ok": False, "error": dec.reason, "risk": dec.risk}
        if dec.approval_request_id:
            out["needs_approval"] = True
            out["approval_request_id"] = dec.approval_request_id
        return out
    try:
        if timeout_s is not None:
            import concurrent.futures as _cf
            with _cf.ThreadPoolExecutor(max_workers=1) as _ex:
                _fut = _ex.submit(_handlers[tool], resource, op, params or {})
                result = _fut.result(timeout=timeout_s)
        else:
            result = _handlers[tool](resource, op, params or {})
    except TimeoutError:
        raise
    except Exception as exc:
        audit.log(actor, "execute-error", tool=tool, resource=resource,
                  decision="error", reason=str(exc)[:300])
        return {"ok": False, "error": "tool failed: %s" % exc}
    return {"ok": True, "result": result, "risk": dec.risk}
