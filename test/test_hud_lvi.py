"""Tests for the LVI HUD wave: ProvidersOverlay port + MYRA edge glow.

The config-layer tests run anywhere. The Qt construction tests skip when
PyQt6's Widgets/Gui libraries cannot load (this sandbox lacks libEGL.so.1);
on a normal Windows install they construct the real widgets offscreen.
"""
import ast
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture()
def temp_config(monkeypatch):
    import memory.config_manager as cm
    tmp = Path(tempfile.mkdtemp())
    monkeypatch.setattr(cm, "CONFIG_FILE", tmp / "api_keys.json")
    monkeypatch.setattr(cm, "CONFIG_DIR", tmp)
    return cm


def test_provider_config_roundtrip(temp_config):
    cm = temp_config
    # An untouched config must read as plain Gemini — the providers package
    # costs nothing until somebody configures it.
    assert cm.get_provider_mode() == "gemini"
    assert cm.get_pipeline() == {}
    cm.save_provider_mode("pipeline")
    cm.save_pipeline(stt="whisper", llm="openai_compatible", tts="piper")
    cm.save_provider_config("openai_compatible",
                            {"base_url": "http://localhost:11434/v1"})
    cm.save_sidecar_provider("openai_compatible")
    assert cm.get_provider_mode() == "pipeline"
    assert cm.get_pipeline() == {"stt": "whisper",
                                  "llm": "openai_compatible", "tts": "piper"}
    assert cm.get_provider_config("openai_compatible")["base_url"] \
        == "http://localhost:11434/v1"
    assert cm.get_sidecar_provider() == "openai_compatible"
    cm.save_providers(mode="gemini")
    assert cm.get_provider_mode() == "gemini"


def test_edge_glow_flag_roundtrip(temp_config):
    cm = temp_config
    assert cm.get_edge_glow_enabled() is False
    cm.save_edge_glow_enabled(True)
    assert cm.get_edge_glow_enabled() is True


def test_overlay_source_contract():
    ui_src = (ROOT / "ui.py").read_text(encoding="utf-8")
    assert "class ProvidersOverlay" in ui_src
    assert "class _ScrollSafeCombo" in ui_src
    assert "ENGINE & PROVIDERS" in ui_src
    assert "def _open_providers" in ui_src
    assert "def _on_providers_applied" in ui_src
    # Every config function the overlay imports must exist.
    cm_tree = ast.parse((ROOT / "memory" / "config_manager.py")
                        .read_text(encoding="utf-8"))
    fns = {n.name for n in ast.walk(cm_tree) if isinstance(n, ast.FunctionDef)}
    for name in ("get_pipeline", "get_provider_config", "get_provider_mode",
                 "get_sidecar_first", "get_sidecar_provider",
                 "save_provider_config", "save_providers"):
        assert name in fns, name


def test_edge_glow_palettes_cover_active_states():
    tree = ast.parse((ROOT / "core" / "edge_glow.py").read_text(encoding="utf-8"))
    palettes = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "PALETTES":
            palettes = ast.literal_eval(node.value)
    assert palettes is not None
    for state in ("LISTENING", "THINKING", "SPEAKING", "EXECUTING",
                  "AWAITING_APPROVAL", "ERROR"):
        assert state in palettes, state
    # Idle/offline mean NO glow — they must not have palettes.
    assert "IDLE" not in palettes and "OFFLINE" not in palettes
    # The approval badge is the point of the badge in Shirazi's adaptation.
    assert palettes["AWAITING_APPROVAL"][0]


def test_qt_constructs():
    try:
        from PyQt6.QtWidgets import QApplication, QWidget
    except ImportError:
        pytest.skip("PyQt6 Widgets unavailable in this environment (libEGL)")
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    import ui
    host = QWidget()
    host.resize(1200, 800)
    ov = ui.ProvidersOverlay(parent=host)
    assert ov.width() == ui.ProvidersOverlay._OW
    ov.deleteLater()

    from core.edge_glow import EdgeGlow
    state = {"s": "IDLE"}
    glow = EdgeGlow(state_provider=lambda: state["s"])
    glow._poll_state()
    assert glow.mode is None            # idle -> no glow
    state["s"] = "LISTENING"
    glow._poll_state()
    assert glow.mode == "LISTENING"
    glow.shutdown()
