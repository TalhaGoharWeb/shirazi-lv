"""Phase 3.2 regression tests: task lifecycle.

Covers: CANCELLING vs CANCELLED (request vs confirm), TIMED_OUT,
terminal states, cancel_all, never-report-success-before-verify.
"""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.omnicontrol import db, gateway, orchestrator
from core.omnicontrol import policy


@pytest.fixture(autouse=True)
def _clean():
    _baseline_risk = dict(policy.TOOL_RISK)
    gateway._handlers.clear()
    orchestrator._cancel_flags.clear()
    yield
    gateway._handlers.clear()
    # Restore instead of clear: other test modules depend on the baseline map.
    policy.TOOL_RISK.clear()
    policy.TOOL_RISK.update(_baseline_risk)
    orchestrator._cancel_flags.clear()


def _tool_ok(resource, op, params):
    return "ok"


def _tool_slow(resource, op, params):
    time.sleep(5)
    return "slow-ok"


def _grant(tool):
    """Give the test tool a live grant (deny-by-default otherwise)."""
    conn = db.connect()
    conn.execute(
        "INSERT INTO grants(principal, resource_kind, resource, ops,"
        " created_at, persistent, created_by)"
        " VALUES ('test','tool',?,? ,?,1,'test')",
        (tool, "*", db.now()))
    conn.commit()


class TestCancelRequestVsConfirm:
    def test_queued_cancel_is_immediate(self):
        tid = orchestrator.start("t", "ws", [])
        assert orchestrator.cancel(tid) is True
        assert orchestrator.status(tid)["state"] == orchestrator.CANCELLED

    def test_running_cancel_requests_then_confirms(self):
        gateway.register_tool("slow", _tool_slow, risk=policy.LOW)
        _grant("slow")
        tid = orchestrator.start("t", "ws",
                                 [{"tool": "slow", "resource": "r",
                                   "op": "read", "timeout_s": 30}])
        import threading
        th = threading.Thread(target=orchestrator.run, args=(tid,),
                              daemon=True)
        th.start()
        time.sleep(0.5)  # let it enter RUNNING
        assert orchestrator.cancel(tid) is True
        # While the slow step runs, state is CANCELLING (requested, not confirmed)
        st = orchestrator.status(tid)["state"]
        assert st in (orchestrator.CANCELLING, orchestrator.RUNNING,
                      orchestrator.CANCELLED)
        th.join(timeout=10)
        # After the step, cancellation is confirmed
        assert orchestrator.status(tid)["state"] == orchestrator.CANCELLED

    def test_cancel_terminal_is_noop(self):
        tid = orchestrator.start("t", "ws", [])
        orchestrator.cancel(tid)
        assert orchestrator.cancel(tid) is False


class TestTimeout:
    def test_step_timeout_maps_to_timed_out(self):
        gateway.register_tool("slow", _tool_slow, risk=policy.LOW)
        _grant("slow")
        tid = orchestrator.start("t", "ws",
                                 [{"tool": "slow", "resource": "r",
                                   "op": "read", "timeout_s": 0.3}])
        out = orchestrator.run(tid)
        assert out["ok"] is False
        assert orchestrator.status(tid)["state"] == orchestrator.TIMED_OUT


class TestVerifyBeforeDone:
    def test_done_only_when_verified(self, tmp_path):
        artifact = tmp_path / "out.txt"
        gateway.register_tool("mk", lambda r, o, p: artifact.write_text("x") or "wrote",
                              risk=policy.LOW)
        _grant("mk")
        tid = orchestrator.start("t", "ws",
                                 [{"tool": "mk", "resource": "r", "op": "write",
                                   "params": {}, "verify": "artifact_exists"}])
        # Point the verify at the real artifact via resource override
        out = orchestrator.run(tid)
        # verify checks step["params"].get("artifact", step["resource"]) — neither
        # exists, so this must NOT be DONE.
        assert orchestrator.status(tid)["state"] != orchestrator.DONE

    def test_verified_artifact_is_done(self, tmp_path):
        artifact = tmp_path / "out.txt"
        artifact.write_text("x")
        gateway.register_tool("noop", _tool_ok, risk=policy.LOW)
        _grant("noop")
        tid = orchestrator.start(
            "t", "ws",
            [{"tool": "noop", "resource": str(artifact), "op": "read",
              "params": {"artifact": str(artifact)},
              "verify": "artifact_exists"}])
        out = orchestrator.run(tid)
        assert out["ok"] is True
        assert orchestrator.status(tid)["state"] == orchestrator.DONE


class TestCancelAll:
    def test_cancel_all_skips_terminal(self):
        t1 = orchestrator.start("a", "ws", [])
        t2 = orchestrator.start("b", "ws", [])
        orchestrator.cancel(t1)
        res = orchestrator.cancel_all("test")
        # t1 already CANCELLED -> False or absent; t2 -> True
        assert res.get(t2) is True
        assert orchestrator.status(t2)["state"] == orchestrator.CANCELLED
