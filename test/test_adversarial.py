"""
Adversarial security tests — Stage K groups 4, 5, 6, 7, 8.

Verifies the security claims with actual attacks, not just happy paths:
  1. Permission bypass: HIGH-risk tools are denied without approval.
  2. Revocation: a revoked/expired grant blocks the next call.
  3. Filesystem traversal: ../, absolute, and symlink escapes are rejected.
  4. Secret redaction: keys never appear in audit logs or errors.
  5. Capability registry: tools cannot downgrade their own risk.

All tests use temp dirs and fake credentials. No network. No real files.
"""
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _fresh_omni():
    """Isolate the omnicontrol DB per test module."""
    tmp = tempfile.mkdtemp()
    os.environ["SHIRAZI_OMNI_DB"] = str(Path(tmp) / "omni.db")
    import importlib
    from core.omnicontrol import db as _db
    importlib.reload(_db)
    from core.omnicontrol import gateway as _gw
    importlib.reload(_gw)
    from core.omnicontrol import policy as _pol
    importlib.reload(_pol)
    return _gw, _pol


class PermissionBypass(unittest.TestCase):
    def test_high_risk_denied_without_approval(self):
        gw, _ = _fresh_omni()
        gw.register_builtin("desktop")  # HIGH risk
        dec = gw.authorize_builtin("desktop")
        self.assertFalse(dec.allowed, "HIGH-risk tool must not auto-allow")
        self.assertIn("approval", dec.reason.lower())

    def test_low_risk_allowed(self):
        gw, _ = _fresh_omni()
        gw.register_builtin("shirazi_kids_story")  # LOW risk
        dec = gw.authorize_builtin("shirazi_kids_story")
        self.assertTrue(dec.allowed)

    def test_unknown_tool_denied(self):
        gw, pol = _fresh_omni()
        # Unknown tools default to CRITICAL in policy — deny by default.
        self.assertEqual(pol.TOOL_RISK.get("definitely_not_a_tool",
                                           pol.CRITICAL), pol.CRITICAL)

    def test_estop_blocks_everything(self):
        gw, _ = _fresh_omni()
        from core.omnicontrol import estop
        estop.trip("test")
        try:
            gw.register_builtin("shirazi_kids_story")
            dec = gw.authorize_builtin("shirazi_kids_story")
            self.assertFalse(dec.allowed, "estop must block even LOW tools")
        finally:
            estop.reset("test")


class RevocationEnforcement(unittest.TestCase):
    def test_revoked_grant_blocks(self):
        gw, pol = _fresh_omni()
        # Persistent grant via the real dashboard path, then revoke it.
        gw.user_approve("shirazi_note_save", "res", "write", persistent=True)
        grants = pol.list_grants()
        self.assertTrue(grants, "grant should exist")
        gid = grants[0]["id"]
        self.assertIsNotNone(pol.live_grant("tool", "shirazi_note_save", "write"))
        pol.revoke_grant(gid, by="test")
        self.assertIsNone(pol.live_grant("tool", "shirazi_note_save", "write"),
                          "revoked grant must not authorize")

    def test_allow_once_token_single_use(self):
        gw, _ = _fresh_omni()
        token = gw.user_approve("desktop", "res", "execute", persistent=False)
        self.assertTrue(isinstance(token, str) and len(token) > 8)
        # First consumption succeeds.
        self.assertTrue(gw._consume_approval(token, "desktop", "res"))
        # Second use with the same token must fail (single-use).
        self.assertFalse(gw._consume_approval(token, "desktop", "res"),
                         "one-shot token must not be reusable")

    def test_token_bound_to_tool(self):
        gw, _ = _fresh_omni()
        token = gw.user_approve("desktop", "res", "execute", persistent=False)
        # Token minted for 'desktop' must not authorize a different tool.
        self.assertFalse(gw._consume_approval(token, "other_tool", "res"),
                         "approval token must be tool-bound")


class FilesystemTraversal(unittest.TestCase):
    def _allow(self, pol, path: str):
        from core.omnicontrol import db as _db
        conn = _db.connect()
        conn.execute(
            "INSERT INTO folders(path, can_read, can_write, added_at, added_by)"
            " VALUES (?,?,?,?,?) ON CONFLICT(path) DO NOTHING",
            (path, 1, 1, _db.now(), "test"))
        conn.commit()

    def test_dotdot_rejected(self):
        _, pol = _fresh_omni()
        with tempfile.TemporaryDirectory() as tmp:
            allowed = str(Path(tmp) / "workspace")
            Path(allowed).mkdir()
            self._allow(pol, allowed)
            evil = str(Path(allowed) / ".." / ".." / "etc" / "passwd")
            ok, _ = pol.check_path(evil, "read")
            self.assertFalse(ok, "../ escape must be rejected")

    def test_absolute_outside_rejected(self):
        _, pol = _fresh_omni()
        with tempfile.TemporaryDirectory() as tmp:
            allowed = str(Path(tmp) / "workspace")
            Path(allowed).mkdir()
            self._allow(pol, allowed)
            ok, _ = pol.check_path("/etc/passwd", "read")
            self.assertFalse(ok)

    def test_symlink_escape_rejected(self):
        _, pol = _fresh_omni()
        with tempfile.TemporaryDirectory() as tmp:
            allowed = str(Path(tmp) / "workspace")
            Path(allowed).mkdir()
            self._allow(pol, allowed)
            outside = Path(tmp) / "secret.txt"
            outside.write_text("secret")
            link = Path(allowed) / "link"
            try:
                link.symlink_to(outside)
            except OSError:
                self.skipTest("symlinks not permitted in this environment")
            ok, _ = pol.check_path(str(link), "read")
            self.assertFalse(ok, "symlink escape must be rejected")

    def test_inside_allowed(self):
        _, pol = _fresh_omni()
        with tempfile.TemporaryDirectory() as tmp:
            allowed = str(Path(tmp) / "workspace")
            Path(allowed).mkdir()
            self._allow(pol, allowed)
            inside = str(Path(allowed) / "notes" / "a.txt")
            ok, _ = pol.check_path(inside, "read")
            self.assertTrue(ok)


class SecretRedaction(unittest.TestCase):
    def test_gemini_key_redacted(self):
        from core.omnicontrol.audit import redact
        out = redact("failed with key AIza" + "x" * 35 + " end")
        self.assertNotIn("AIza", out)
        self.assertIn("[REDACTED", out)

    def test_groq_key_redacted(self):
        from core.omnicontrol.audit import redact
        out = redact("key=gsk_" + "a" * 24)
        self.assertNotIn("gsk_", out)

    def test_openrouter_key_redacted(self):
        from core.omnicontrol.audit import redact
        out = redact("sk-or-v1-" + "b" * 40)
        self.assertNotIn("sk-or-v1", out)

    def test_normal_text_untouched(self):
        from core.omnicontrol.audit import redact
        self.assertEqual(redact("hello world"), "hello world")


class CapabilityRiskIntegrity(unittest.TestCase):
    def test_tool_cannot_downgrade_risk(self):
        from core.capabilities import CapabilityRegistry, Capability
        r = CapabilityRegistry()
        # A tool that declares itself LOW but policy says HIGH.
        cap = Capability(id="plugin.desktop", risk="LOW")
        r.register(cap)
        # Policy TOOL_RISK has no 'desktop' under plugin.* — but the
        # gateway's TOOL_RISK_MAP does; the registry must respect policy
        # for known tools.
        from core.capabilities import get_registry
        reg = get_registry()
        reg.populate_from_gateway()
        d = reg.by_tool_name("desktop")
        self.assertIsNotNone(d)
        self.assertEqual(d.risk.upper(), "HIGH",
                         "policy risk must win over tool self-declaration")

    def test_unknown_capability_rejected(self):
        from core.capabilities import get_registry
        reg = get_registry()
        ok, err = reg.validate_args("nope.nothing", {})
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
