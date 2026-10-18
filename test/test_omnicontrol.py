"""
OMNICONTROL MVP acceptance tests.

The MVP is ready for expansion ONLY when these pass:
  1. Unauthorized operations are denied (deny-by-default).
  2. Permissions are enforced on every MCP tool call.
  3. Revocation takes effect promptly.
  4. Path escapes are blocked (traversal, symlink/junction, sensitive children).
  5. Emergency stop works independently of the AI model.
  6. Audit logs never contain secrets.
"""
import os
import tempfile
import unittest
from pathlib import Path

from core.omnicontrol import audit, db, estop, gateway, orchestrator, permissions, policy
from core.omnicontrol import fs_tools, github_tools


# Static risk map shipped in policy.TOOL_RISK. Other suites (e.g. the P2
# gateway tests) clear it as a side effect; snapshot at import so fresh_db()
# can restore a known-good baseline regardless of test ordering.
_BASELINE_TOOL_RISK = dict(policy.TOOL_RISK)


def fresh_db():
    tmp = tempfile.mkdtemp(prefix="omni-test-")
    db.reset_for_tests(Path(tmp) / "omni.db")
    # reset in-process latches
    estop._latched = False
    gateway._handlers.clear()
    gateway._approvals.clear()
    gateway._pending.clear()
    gateway._pending_grants.clear()
    orchestrator._cancel_flags.clear()
    # restore the static risk map (may have been cleared by another suite)
    policy.TOOL_RISK.clear()
    policy.TOOL_RISK.update(_BASELINE_TOOL_RISK)
    fs_tools.register()
    github_tools.register()
    return tmp


class DenyByDefault(unittest.TestCase):
    def setUp(self): fresh_db()

    def test_unknown_tool_denied(self):
        d = gateway.authorize("no_such_tool", "x", "read")
        self.assertFalse(d.allowed)
        self.assertIn("deny-by-default", d.reason)

    def test_fs_without_allowlist_denied(self):
        r = gateway.execute("fs_list", "/tmp", "read")
        self.assertFalse(r["ok"])

    def test_unregistered_tool_execute_denied(self):
        r = gateway.execute("evil_tool", "x", "read")
        self.assertFalse(r["ok"])
        self.assertEqual(r["risk"], "critical")

    def test_high_risk_needs_approval(self):
        tmp = tempfile.mkdtemp()
        conn = db.connect()
        conn.execute("INSERT INTO folders(path, can_read, can_write, can_delete, added_at)"
                     " VALUES (?,?,?,1,?)", (tmp, 1, 1, db.now()))
        conn.commit()
        target = os.path.join(tmp, "doomed.txt")
        Path(target).write_text("x")
        r = gateway.execute("fs_delete", target, "delete")
        self.assertFalse(r["ok"])
        self.assertTrue(r.get("needs_approval"))
        self.assertTrue(Path(target).exists())  # not deleted


class PathEscapes(unittest.TestCase):
    def setUp(self): self.tmp = fresh_db()

    def _allow(self, path, **flags):
        conn = db.connect()
        conn.execute(
            "INSERT INTO folders(path, can_read, can_write, can_exec, can_delete, added_at)"
            " VALUES (?,?,?,?,?,?)",
            (policy._norm(path), int(flags.get("read", True)),
             int(flags.get("write", False)), int(flags.get("exec", False)),
             int(flags.get("delete", False)), db.now()))
        conn.commit()

    def test_traversal_blocked(self):
        base = tempfile.mkdtemp()
        self._allow(base, read=True)
        evil = os.path.join(base, "..", "etc", "passwd")
        ok, _ = policy.check_path(evil, "read")
        # /tmp/etc/passwd doesn't exist, but the point is the canonical path
        # escapes `base` -> must be denied
        self.assertFalse(ok)

    def test_symlink_escape_blocked(self):
        base = tempfile.mkdtemp()
        outside = tempfile.mkdtemp()
        secret = os.path.join(outside, "secret.txt")
        Path(secret).write_text("topsecret")
        link = os.path.join(base, "link")
        try:
            os.symlink(outside, link)
        except OSError:
            self.skipTest("symlinks unavailable")
        self._allow(base, read=True)
        ok, reason = policy.check_path(os.path.join(link, "secret.txt"), "read")
        self.assertFalse(ok, "symlink escape must be blocked: %s" % reason)

    def test_sensitive_child_never_inherits(self):
        base = tempfile.mkdtemp()
        ssh = os.path.join(base, ".ssh")
        os.makedirs(ssh, exist_ok=True)
        self._allow(base, read=True, write=True)
        ok, _ = policy.check_path(os.path.join(ssh, "id_rsa"), "read")
        self.assertFalse(ok)

    def test_sibling_not_covered(self):
        base = tempfile.mkdtemp()
        sib = base + "-sibling"
        os.makedirs(sib, exist_ok=True)
        self._allow(base, read=True)
        ok, _ = policy.check_path(os.path.join(sib, "f.txt"), "read")
        self.assertFalse(ok)


class Revocation(unittest.TestCase):
    def setUp(self): fresh_db()

    def test_revoke_takes_effect_immediately(self):
        tmp = tempfile.mkdtemp()
        f = os.path.join(tmp, "n.txt")
        Path(f).write_text("hello")
        r = permissions.confirm(
            {"action": "grant", "resource_kind": "folder",
             "resource": tmp, "ops": "read", "duration_s": 3600},
            via="dashboard", origin="user")
        self.assertTrue(r["ok"])
        self.assertTrue(gateway.execute("fs_read", f, "read")["ok"])
        r2 = permissions.confirm(
            {"action": "revoke", "resource_kind": "folder", "resource": tmp},
            via="dashboard", origin="user")
        self.assertTrue(r2["ok"])
        r3 = gateway.execute("fs_read", f, "read")
        self.assertFalse(r3["ok"], "revoked access must deny immediately")

    def test_expired_grant_denied(self):
        conn = db.connect()
        conn.execute(
            "INSERT INTO grants(principal, resource_kind, resource, ops, created_at,"
            " expires_at, persistent) VALUES ('user','tool','fs_write','write',?, ?, 0)",
            (db.now() - 100, db.now() - 1))
        conn.commit()
        tmp = tempfile.mkdtemp()
        conn.execute("INSERT INTO folders(path, can_read, can_write, added_at)"
                     " VALUES (?,?,1,?)", (policy._norm(tmp), 1, db.now()))
        conn.commit()
        d = gateway.authorize("fs_write", os.path.join(tmp, "x.txt"), "write")
        self.assertFalse(d.allowed)


class EmergencyStop(unittest.TestCase):
    def setUp(self): fresh_db()

    def test_estop_blocks_without_model(self):
        # No model, no network, no LLM — pure local calls.
        tmp = tempfile.mkdtemp()
        f = os.path.join(tmp, "n.txt")
        Path(f).write_text("hello")
        conn = db.connect()
        conn.execute("INSERT INTO folders(path, can_read, added_at) VALUES (?,1,?)",
                     (policy._norm(tmp), db.now()))
        conn.commit()
        self.assertTrue(gateway.execute("fs_read", f, "read")["ok"])
        estop.trip(source="test")
        r = gateway.execute("fs_read", f, "read")
        self.assertFalse(r["ok"])
        self.assertIn("emergency stop", r["error"])
        estop.reset(by="test")
        self.assertTrue(gateway.execute("fs_read", f, "read")["ok"])

    def test_estop_cancels_tasks(self):
        tid = orchestrator.start("t", "/tmp", [])
        estop.trip(source="test")
        row = orchestrator.status(tid)
        self.assertEqual(row["state"], "CANCELLED")
        estop.reset(by="test")

    def test_voice_phrase_trips_locally(self):
        from core.omnicontrol import voice_hooks
        resp = voice_hooks.maybe_handle("stop everything", origin="user")
        self.assertIsNotNone(resp)
        self.assertTrue(estop.is_tripped())
        estop.reset(by="test")


class AuditRedaction(unittest.TestCase):
    def setUp(self): fresh_db()

    def test_no_secrets_in_audit(self):
        audit.log("test", "execute", tool="t", resource="r", decision="deny",
                  reason="x",
                  details={"token": "ghp_abcdefghijklmnopqrstuv123456",
                           "key": "sk-abcdefghijklmnopqrstuv1234567890",
                           "pem": "-----BEGIN RSA PRIVATE KEY-----\nABC\n-----END RSA PRIVATE KEY-----",
                           "pw": "password: hunter2hunter"})
        entries = audit.recent(5)
        blob = str(entries)
        self.assertNotIn("ghp_abcdefghijklmnopqrstuv123456", blob)
        self.assertNotIn("sk-abcdefghijklmnopqrstuv1234567890", blob)
        self.assertNotIn("BEGIN RSA PRIVATE KEY", blob)
        self.assertIn("[REDACTED", blob)


class ApprovalFlow(unittest.TestCase):
    def setUp(self): fresh_db()

    def test_allow_once_single_use(self):
        tok = gateway.user_approve("fs_delete", "/tmp/x", "delete", ttl_s=60)
        self.assertTrue(gateway._consume_approval(tok, "fs_delete", "/tmp/x"))
        # second use fails
        self.assertFalse(gateway._consume_approval(tok, "fs_delete", "/tmp/x"))

    def test_pending_resolve_deny(self):
        pid = gateway.request_approval("fs_delete", "/tmp/x", "delete", "test")
        self.assertEqual(len(gateway.list_pending()), 1)
        r = gateway.resolve_pending(pid, "deny")
        self.assertTrue(r["ok"])
        self.assertEqual(len(gateway.list_pending()), 0)

    def test_voice_cannot_confirm_high_risk(self):
        prop = {"action": "grant", "resource_kind": "folder",
                "resource": "/tmp", "ops": "delete"}
        r = permissions.confirm(prop, via="voice", origin="user")
        self.assertFalse(r["ok"])
        self.assertIn("tap", r["error"])

    def test_agent_cannot_self_grant(self):
        prop = {"action": "grant", "resource_kind": "folder",
                "resource": "/tmp", "ops": "read"}
        r = permissions.confirm(prop, via="dashboard", origin="agent")
        self.assertFalse(r["ok"])


class OrchestratorTest(unittest.TestCase):
    def setUp(self): fresh_db()

    def test_task_runs_through_gateway(self):
        tmp = tempfile.mkdtemp()
        f = os.path.join(tmp, "out.txt")
        conn = db.connect()
        conn.execute("INSERT INTO folders(path, can_read, can_write, added_at)"
                     " VALUES (?,?,1,?)", (policy._norm(tmp), 1, db.now()))
        conn.commit()
        # fs_write is MODERATE: needs a grant
        conn.execute("INSERT INTO grants(principal, resource_kind, resource, ops,"
                     " created_at, persistent) VALUES ('user','tool','fs_write','write',?,1)",
                     (db.now(),))
        conn.commit()
        tid = orchestrator.start("write file", tmp, [
            {"tool": "fs_write", "resource": f, "op": "write",
             "params": {"content": "hello", "artifact": f},
             "verify": "artifact_exists"}])
        res = orchestrator.run(tid)
        self.assertTrue(res["ok"], res)
        self.assertEqual(orchestrator.status(tid)["state"], "DONE")
        self.assertEqual(Path(f).read_text(), "hello")

    def test_task_denied_step_fails_honestly(self):
        tid = orchestrator.start("nope", "/tmp", [
            {"tool": "fs_read", "resource": "/definitely/not/allowed/x.txt",
             "op": "read", "params": {}}])
        res = orchestrator.run(tid)
        self.assertFalse(res["ok"])
        self.assertEqual(orchestrator.status(tid)["state"], "FAILED")


if __name__ == "__main__":
    unittest.main(verbosity=1)
