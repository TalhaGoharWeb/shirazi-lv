"""Tests for Stage 4 — Urdu language support + problem_diagnose plugin."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# --- language setting -------------------------------------------------------
def test_language_validation(monkeypatch, tmp_path):
    from memory import config_manager as cm
    monkeypatch.setattr(cm, "CONFIG_FILE", tmp_path / "api_keys.json")
    monkeypatch.setattr(cm, "CONFIG_DIR", tmp_path)
    assert cm.get_response_language() == "auto"
    cm.save_response_language("urdu")
    assert cm.get_response_language() == "urdu"
    cm.save_response_language("ROMAN_URDU")
    assert cm.get_response_language() == "roman_urdu"
    import pytest
    with pytest.raises(ValueError):
        cm.save_response_language("klingon")


def test_prompt_directive_urdu(monkeypatch, tmp_path):
    from memory import config_manager as cm
    from core import shirazi_language as sl
    monkeypatch.setattr(cm, "CONFIG_FILE", tmp_path / "api_keys.json")
    monkeypatch.setattr(cm, "CONFIG_DIR", tmp_path)
    cm.save_response_language("urdu")
    d = sl.prompt_directive()
    assert "Urdu" in d and "Urdu script" in d
    cm.save_response_language("roman_urdu")
    assert "Roman Urdu" in sl.prompt_directive()
    cm.save_response_language("auto")
    assert sl.prompt_directive() == ""


def test_edge_voice_mapping(monkeypatch, tmp_path):
    from memory import config_manager as cm
    from core import shirazi_language as sl
    monkeypatch.setattr(cm, "CONFIG_FILE", tmp_path / "api_keys.json")
    monkeypatch.setattr(cm, "CONFIG_DIR", tmp_path)
    cm.save_response_language("urdu")
    assert sl.edge_voice_for_language() == "ur-PK-UzmaNeural"
    assert sl.edge_voice_for_language("en-US-JennyNeural") == "en-US-JennyNeural"
    cm.save_response_language("auto")
    assert sl.edge_voice_for_language() == "en-US-GuyNeural"


# --- problem_diagnose plugin -------------------------------------------------
def _load_plugin():
    import importlib.util
    f = Path(__file__).resolve().parent.parent / "plugins" / "shirazi_problem_diagnose.py"
    spec = importlib.util.spec_from_file_location("shirazi_problem_diagnose", f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_diagnose_plugin_valid():
    mod = _load_plugin()
    assert mod.PLUGIN["name"] == "shirazi_problem_diagnose"
    assert mod.PLUGIN["parameters"]["type"] == "OBJECT"
    assert "recall" in mod.PLUGIN["parameters"]["properties"]["operation"]["description"]


def test_diagnose_case_lifecycle():
    mod = _load_plugin()
    out = mod.run({"operation": "start", "problem": "printer not found"})
    assert "Case case-" in out
    cid = out.split("Case ")[1].split(" ")[0]
    assert "Evidence logged" in mod.run(
        {"operation": "evidence", "case_id": cid, "kind": "symptom",
         "text": "spooler error 0x123"})
    assert "marked done" in mod.run(
        {"operation": "step", "case_id": cid, "step": "gather", "status": "done"})
    shown = mod.run({"operation": "show", "case_id": cid})
    assert isinstance(shown, str) and len(shown) > 0


def test_diagnose_unknown_case_never_raises():
    mod = _load_plugin()
    out = mod.run({"operation": "step", "case_id": "nope", "step": "plan"})
    assert "start a case" in out
    assert isinstance(mod.run({"operation": "bogus"}), str)
