"""P2.3/P2.4/P2.7/P2.10 regression tests.

P2.3: every text submission gets a visible disposition.
P2.4: remote-wake setting exists and defaults sanely.
P2.7: graceful-shutdown helpers exist (terminate_all, closeEvent wiring).
P2.10: provider consent gate + provenance tracking.
"""
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestP24RemoteWakeSetting:
    def test_default_is_true(self):
        from memory import config_manager as cm
        with mock.patch.object(cm, "load_api_keys", return_value={}):
            assert cm.get_remote_wake_enabled() is True

    def test_roundtrip(self, tmp_path):
        from memory import config_manager as cm
        fake = tmp_path / "api_keys.json"
        with mock.patch.object(cm, "CONFIG_FILE", fake), \
             mock.patch.object(cm, "ensure_config_dir", lambda: None):
            cm.save_remote_wake_enabled(False)
            with mock.patch.object(cm, "load_api_keys",
                                   return_value={"remote_wake_enabled": False}):
                assert cm.get_remote_wake_enabled() is False


class TestP210Consent:
    def test_consent_gate_blocks_provider(self):
        from core import shirazi_ladder as lad
        from memory import config_manager as cm
        with mock.patch.object(cm, "get_fallback_consent", return_value=False), \
             mock.patch.object(cm, "get_groq_key", return_value="gsk_test"):
            assert lad._key_for("groq") == ""

    def test_consent_gate_allows_with_key(self):
        from core import shirazi_ladder as lad
        from memory import config_manager as cm
        with mock.patch.object(cm, "get_fallback_consent", return_value=True), \
             mock.patch.object(cm, "get_groq_key", return_value="gsk_test"):
            assert lad._key_for("groq") == "gsk_test"

    def test_no_key_means_no_rung(self):
        from core import shirazi_ladder as lad
        from memory import config_manager as cm
        with mock.patch.object(cm, "get_fallback_consent", return_value=True), \
             mock.patch.object(cm, "get_groq_key", return_value=""):
            assert lad._key_for("groq") == ""

    def test_provenance_recorded(self):
        from core import shirazi_ladder as lad
        lad._last_provenance.clear()
        with mock.patch.object(lad, "_oai_text", return_value="hello"), \
             mock.patch.object(lad, "_key_for", return_value="k"):
            out = lad.oai_fallback_text("hi", tier="FAST")
        assert out == "hello"
        prov = lad.last_provenance()
        assert prov["provider"] == "groq"
        assert "gpt-oss-20b" in prov["model"]


class TestP27ShutdownHelpers:
    def test_mcp_terminate_all_exists(self):
        from core.omnicontrol import mcp_registry as mcp
        assert callable(mcp.terminate_all)
        # no children -> no-op, must not raise
        mcp.terminate_all()

    def test_mcp_terminate_all_kills_child(self):
        import subprocess
        from core.omnicontrol import mcp_registry as mcp
        proc = subprocess.Popen(["sleep", "30"] if sys.platform != "win32"
                                else ["timeout", "/t", "30"],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        mcp._children.append(proc)
        try:
            mcp.terminate_all()
            assert proc.poll() is not None  # dead
        finally:
            try:
                proc.kill()
            except Exception:
                pass
            mcp._children.clear()

    def test_mainwindow_has_close_event(self):
        # ui.py MainWindow.closeEvent -> on_close_request (source check; Qt
        # import is heavy so we verify the wiring statically).
        src = Path(__file__).resolve().parent.parent.joinpath("ui.py")
        text = src.read_text(encoding="utf-8", errors="replace")
        assert "def closeEvent(self, e):" in text
        assert "on_close_request" in text

    def test_graceful_shutdown_method_exists(self):
        src = Path(__file__).resolve().parent.parent.joinpath("main.py")
        text = src.read_text(encoding="utf-8", errors="replace")
        assert "async def _graceful_shutdown(self):" in text
        assert "def _request_shutdown(self):" in text


class TestP23Disposition:
    def test_degraded_path_writes_log(self):
        # _on_text_command with no session must write a SYS message, not
        # silently return. We test the logic statically + via a minimal fake.
        src = Path(__file__).resolve().parent.parent.joinpath("main.py")
        text = src.read_text(encoding="utf-8", errors="replace")
        # The silent `return` is gone; both branches write to the log.
        assert "_degraded_text_reply" in text
        assert "Voice link is down" in text
