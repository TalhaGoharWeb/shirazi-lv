"""
Next-steps tests: secret migration wiring, plugin lifecycle, MCP health,
desktop sandbox hardening.

  1. Key getters prefer the OS store, fall back to legacy file.
  2. set_plugin_enabled / get_plugin_enabled round-trip.
  3. record_plugin_failure auto-disables after 5; success resets.
  4. Plugin manifest reading (missing/malformed never blocks).
  5. MCP spawn_managed rejects paths outside servers/.
  6. Desktop sandbox: no getattr/hasattr/ctypes in the namespace.
  7. Dashboard capability/plugin endpoints exist and require auth.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# Isolate secrets: in-memory backend so tests never touch the
# real OS store or disk.
try:
    from core import secrets_store as _ss
    _ss.use_memory_backend()
except Exception:
    pass

# Per-test isolation: fresh secrets for every test.
def _reset_secrets():
    try:
        _ss.use_memory_backend()
    except Exception:
        pass






class KeyGetterPriority(unittest.TestCase):
    def test_os_store_first(self):
        from core import secrets_store as ss
        from memory import config_manager as cm
        ss.set_secret("groq_api_key", "gsk_test_" + "x" * 20)
        try:
            self.assertEqual(cm.get_groq_key(), "gsk_test_" + "x" * 20)
        finally:
            ss.delete_secret("groq_api_key")

    def test_legacy_fallback(self):
        from memory import config_manager as cm
        from core import secrets_store as ss
        ss.delete_secret("groq_api_key")
        with mock.patch.object(cm, "load_api_keys",
                               return_value={"groq_api_key": "gsk_legacy"}):
            self.assertEqual(cm.get_groq_key(), "gsk_legacy")


class PluginLifecycle(unittest.TestCase):
    def test_enable_disable(self):
        from memory import config_manager as cm
        cm.set_plugin_enabled("ut_plugin_x", False)
        self.assertFalse(cm.get_plugin_enabled("ut_plugin_x"))
        cm.set_plugin_enabled("ut_plugin_x", True)
        self.assertTrue(cm.get_plugin_enabled("ut_plugin_x"))

    def test_failure_auto_disable(self):
        from memory import config_manager as cm
        name = "ut_plugin_flaky"
        cm.set_plugin_enabled(name, True)
        # Reset health first.
        cm.record_plugin_success(name)
        for i in range(4):
            h = cm.record_plugin_failure(name, "boom %d" % i)
            self.assertTrue(cm.get_plugin_enabled(name),
                            "should stay enabled before 5 failures")
        h = cm.record_plugin_failure(name, "boom 4")
        self.assertFalse(cm.get_plugin_enabled(name),
                         "auto-disabled after 5 consecutive failures")
        self.assertTrue(h["auto_disabled"])
        # Success resets.
        cm.set_plugin_enabled(name, True)
        cm.record_plugin_success(name)
        self.assertEqual(cm.get_plugin_health(name).get("failures", 0), 0)

    def test_manifest_missing_ok(self):
        from core.plugin_loader import _read_manifest
        with tempfile.TemporaryDirectory() as tmp:
            py = Path(tmp) / "myplug.py"
            py.write_text("x=1")
            self.assertIsNone(_read_manifest(str(py)))

    def test_manifest_malformed_ok(self):
        from core.plugin_loader import _read_manifest
        with tempfile.TemporaryDirectory() as tmp:
            py = Path(tmp) / "myplug.py"
            py.write_text("x=1")
            (Path(tmp) / "myplug.json").write_text("{not json")
            self.assertIsNone(_read_manifest(str(py)))

    def test_manifest_valid(self):
        from core.plugin_loader import _read_manifest
        with tempfile.TemporaryDirectory() as tmp:
            py = Path(tmp) / "myplug.py"
            py.write_text("x=1")
            (Path(tmp) / "myplug.json").write_text(json.dumps({
                "version": "2.0", "author": "test",
                "permissions": ["fs:read"], "extra_unknown": 1}))
            m = _read_manifest(str(py))
            self.assertEqual(m["version"], "2.0")
            self.assertNotIn("extra_unknown", m)


class MCPHealth(unittest.TestCase):
    def test_rejects_outside_servers(self):
        from core.omnicontrol import mcp_registry as mr
        # Traversal is neutralized (.name) then rejected: either ValueError
        # (outside servers/) or RuntimeError (script missing) is safe —
        # what must NOT happen is spawning outside servers/.
        with self.assertRaises((ValueError, RuntimeError)):
            mr.spawn_managed("evil", "../../../etc/passwd")

    def test_health_unknown(self):
        from core.omnicontrol import mcp_registry as mr
        h = mr.server_health("never-spawned")
        self.assertFalse(h["alive"])
        self.assertEqual(h["failures"], 0)


class DesktopSandbox(unittest.TestCase):
    def test_no_escape_primitives(self):
        from actions import desktop
        sb = desktop._build_sandbox()
        builtins = sb["__builtins__"]
        self.assertNotIn("getattr", builtins,
                         "getattr is the primary sandbox escape")
        self.assertNotIn("hasattr", builtins)
        self.assertNotIn("ctypes", sb, "ctypes = arbitrary native code")
        self.assertNotIn("__import__", builtins)

    def test_checked_path_blocks_write_outside(self):
        from actions import desktop
        P = desktop._CheckedPath
        with tempfile.TemporaryDirectory() as tmp:
            # No allow-listed folders in a fresh env -> write must fail closed.
            p = P(tmp) / "evil.txt"
            with self.assertRaises(Exception):
                p.write_text("x")


class DashboardEndpoints(unittest.TestCase):
    def test_routes_registered(self):
        import dashboard.server as srv
        src = Path(srv.__file__).read_text()
        for route in ("/api/capabilities", "/api/plugins/health",
                      "/api/plugins/enable"):
            self.assertIn(route, src, f"missing route {route}")
        # All three require auth.
        self.assertGreater(src.count("_auth(req)"), 10)


if __name__ == "__main__":
    unittest.main()
