"""P2.1/P2.2/F-013/F-014 regression tests: unified authorization gateway.

Covers: real risk tiers (no more all-LOW), actions gated, inline built-ins
gated, HIGH-risk approval flow (request -> dashboard allow -> retry works),
estop blocks everything, unknown tools denied, audit logging.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.omnicontrol import audit, db, estop, gateway, policy


@pytest.fixture(autouse=True)
def _clean_state():
    """Reset gateway + estop state around each test."""
    _baseline_risk = dict(policy.TOOL_RISK)
    gateway._handlers.clear()
    gateway._approvals.clear()
    gateway._pending.clear()
    gateway._pending_grants.clear()
    estop.reset()
    yield
    gateway._handlers.clear()
    gateway._approvals.clear()
    gateway._pending.clear()
    gateway._pending_grants.clear()
    # Restore instead of clear: other modules depend on the baseline map.
    policy.TOOL_RISK.clear()
    policy.TOOL_RISK.update(_baseline_risk)
    estop.reset()


def _reg(name):
    gateway.register_builtin(name)


class TestRiskTiers:
    def test_high_risk_tools_not_low(self):
        """F-002: dangerous tools must not be LOW."""
        for name in ("desktop", "computer_control", "file_controller",
                     "open_app", "browser_control", "computer_settings",
                     "shirazi_note_delete", "shirazi_organize_apply"):
            _reg(name)
            assert policy.TOOL_RISK[name] == policy.HIGH, name

    def test_readonly_tools_are_low(self):
        for name in ("shirazi_note_list", "shirazi_kids_story",
                     "recall_memory", "screen_process"):
            _reg(name)
            assert policy.TOOL_RISK[name] == policy.LOW, name

    def test_moderate_tools(self):
        for name in ("shirazi_note_save", "shirazi_excel_create",
                     "save_memory", "file_processor"):
            _reg(name)
            assert policy.TOOL_RISK[name] == policy.MODERATE, name

    def test_unknown_tool_denied_as_critical(self):
        d = gateway.authorize_builtin("no_such_tool_xyz")
        assert not d.allowed
        assert d.risk == policy.CRITICAL


class TestLowModerateAutoAllow:
    def test_low_allowed_with_audit(self):
        _reg("shirazi_note_list")
        d = gateway.authorize_builtin("shirazi_note_list")
        assert d.allowed
        assert d.risk == policy.LOW

    def test_moderate_allowed_with_audit(self):
        _reg("shirazi_note_save")
        d = gateway.authorize_builtin("shirazi_note_save")
        assert d.allowed
        assert d.risk == policy.MODERATE


class TestHighRiskApprovalFlow:
    def test_high_denied_without_approval_and_creates_request(self):
        _reg("desktop")
        d = gateway.authorize_builtin("desktop")
        assert not d.allowed
        assert "approval" in d.reason.lower()
        assert d.approval_request_id is not None
        # dashboard can see it
        pending = gateway.list_pending()
        assert any(p["id"] == d.approval_request_id for p in pending)

    def test_dashboard_allow_once_enables_retry(self):
        """User taps Allow Once -> agent retries -> allowed (token consumed)."""
        _reg("desktop")
        d1 = gateway.authorize_builtin("desktop")
        assert not d1.allowed
        # dashboard resolves
        res = gateway.resolve_pending(d1.approval_request_id, "once")
        assert res["ok"] and res["decision"] == "once"
        # agent retries (no token passed — grant was left for the retry)
        d2 = gateway.authorize_builtin("desktop")
        assert d2.allowed
        # single use: third call denied again
        d3 = gateway.authorize_builtin("desktop")
        assert not d3.allowed

    def test_dashboard_deny_blocks(self):
        _reg("desktop")
        d1 = gateway.authorize_builtin("desktop")
        res = gateway.resolve_pending(d1.approval_request_id, "deny")
        assert res["ok"] and res["decision"] == "deny"
        d2 = gateway.authorize_builtin("desktop")
        assert not d2.allowed

    def test_explicit_token_still_works(self):
        _reg("open_app")
        token = gateway.user_approve("open_app", "*", "execute")
        d = gateway.authorize_builtin("open_app", approval_token=token)
        assert d.allowed
        # single-use
        d2 = gateway.authorize_builtin("open_app", approval_token=token)
        assert not d2.allowed


class TestEstop:
    def test_estop_blocks_low_tools(self):
        _reg("shirazi_note_list")
        estop.trip("test")
        d = gateway.authorize_builtin("shirazi_note_list")
        assert not d.allowed
        assert "emergency stop" in d.reason.lower()

    def test_estop_blocks_high_tools(self):
        _reg("desktop")
        estop.trip("test")
        d = gateway.authorize_builtin("desktop")
        assert not d.allowed


class TestAudit:
    def test_denials_are_audited(self):
        _reg("desktop")
        gateway.authorize_builtin("desktop")
        # audit.log writes to the DB; check it doesn't raise and records
        conn = db.connect()
        conn.row_factory = None
        rows = conn.execute(
            "SELECT tool, decision FROM audit_log ORDER BY rowid DESC LIMIT 5"
        ).fetchall()
        assert any(r[0] == "desktop" and r[1] == "deny" for r in rows)
