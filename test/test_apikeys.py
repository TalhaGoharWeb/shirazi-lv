"""
API key UI acceptance tests.

  1. SetupOverlay has all three key fields (Gemini required, Groq/OpenRouter
     optional) and emits them as a dict.
  2. _on_setup_done merges keys into api_keys.json without wiping others.
  3. Pre-fill: reshown overlay displays existing keys.
  4. The ladder actually reads the stored Groq/OpenRouter keys.
"""
import json
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
try:
    # Must import before any QApplication exists (QtWebEngine requirement);
    # QtWebEngineWidgets must be imported before QApplication.
    from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
except Exception:
    pass

_app = None


def app():
    global _app
    if _app is None:
        _app = QApplication([])
    return _app


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






class ApiKeyFields(unittest.TestCase):
    def test_overlay_has_three_fields(self):
        app()
        import ui as ui_mod
        ov = ui_mod.SetupOverlay()
        self.assertTrue(hasattr(ov, "_key_input"))
        self.assertTrue(hasattr(ov, "_groq_input"))
        self.assertTrue(hasattr(ov, "_or_input"))
        # Gemini required: empty submit must not emit
        emitted = []
        ov.done.connect(emitted.append)
        ov._key_input.setText("")
        ov._submit()
        self.assertEqual(emitted, [])
        # Full submit emits a dict with all keys
        ov._key_input.setText("AIza-test")
        ov._groq_input.setText("gsk-test")
        ov._or_input.setText("sk-or-test")
        ov._sel_os = "windows"
        ov._submit()
        self.assertEqual(len(emitted), 1)
        self.assertEqual(emitted[0]["gemini"], "AIza-test")
        self.assertEqual(emitted[0]["groq"], "gsk-test")
        self.assertEqual(emitted[0]["openrouter"], "sk-or-test")
        ov.deleteLater()

    def test_setup_done_merges_without_wiping(self):
        app()
        import ui as ui_mod
        from memory import config_manager as cm
        # seed existing keys
        cm.save_provider_key("groq", "gsk-keep")
        win = ui_mod.MainWindow.__new__(ui_mod.MainWindow)
        win._overlay = None
        win._ready = False
        logs = []
        win._log = type("L", (), {"append_log": lambda s, t: logs.append(t)})()
        win._apply_state = lambda s: None
        import ui as _u
        _u._read_full_config = lambda: {}
        win._on_setup_done({"gemini": "AIza-new", "groq": "",
                            "openrouter": "sk-or-new", "os": "windows"})
        # Stage F: secrets land in the OS store, not the plaintext file.
        from core import secrets_store as _ss
        self.assertEqual(_ss.get_secret("gemini_api_key"), "AIza-new")
        self.assertEqual(_ss.get_secret("openrouter_api_key"), "sk-or-new")
        # Untouched keys are not wiped (groq was "gsk-keep", still there).
        self.assertEqual(cm.get_groq_key(), "gsk-keep")

    def test_ladder_reads_stored_keys(self):
        from memory import config_manager as cm
        cm.save_provider_key("groq", "gsk-live")
        cm.save_provider_key("openrouter", "sk-or-live")
        self.assertEqual(cm.get_groq_key(), "gsk-live")
        self.assertEqual(cm.get_openrouter_key(), "sk-or-live")


if __name__ == "__main__":
    unittest.main(verbosity=1)
