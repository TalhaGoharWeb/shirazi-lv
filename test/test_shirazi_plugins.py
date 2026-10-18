"""Tests for the Shirazi plugin port (tools/port_shirazi_plugins.py output).

Verifies that every generated plugins/shirazi_*.py file:
1. passes Mark-LV's own plugin validator,
2. exposes a run() that returns a non-empty string and never raises,
3. shares module state with sibling files from the same Shirazi plugin.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.plugin_loader import discover_plugins

PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"


def _registry():
    return discover_plugins(PLUGINS_DIR, set(), lambda m: None, None)


def test_all_shirazi_plugins_valid():
    reg = _registry()
    recs = [r for r in reg._all_records if r.name.startswith("shirazi_")]
    assert len(recs) >= 50, f"expected 50+ ported tools, got {len(recs)}"
    bad = [(r.file, r.error) for r in recs if not r.valid]
    assert not bad, f"invalid plugins: {bad}"


def test_all_run_return_strings():
    import importlib
    reg = _registry()
    bad = []
    for r in reg._all_records:
        if not (r.valid and r.name.startswith("shirazi_")):
            continue
        mod = importlib.import_module(f"plugins.{Path(r.file).stem}")
        try:
            out = mod.run({})
        except Exception as e:  # contract: never raise
            bad.append((r.name, f"raised {type(e).__name__}: {e}"))
            continue
        if not isinstance(out, str) or not out:
            bad.append((r.name, "empty/non-string return"))
    assert not bad, f"run() contract violations: {bad}"


def test_parameter_types_uppercase():
    reg = _registry()
    for r in reg._all_records:
        if not (r.valid and r.name.startswith("shirazi_")):
            continue
        assert r.parameters.get("type") == "OBJECT", r.name


def test_shared_state_across_sibling_tools():
    """timer_start + timer_list must share one backend (not N copies)."""
    import importlib
    ms = importlib.import_module("plugins.shirazi_timer_start")
    ml = importlib.import_module("plugins.shirazi_timer_list")
    mc = importlib.import_module("plugins.shirazi_timer_cancel")
    label = "port-test-timer"
    ms.run({"seconds": 120, "label": label})
    try:
        assert label in ml.run({}), "sibling tool did not see the timer"
    finally:
        mc.run({"label": label})
