"""PLUGIN_SETTINGS: declared schemas reach the settings UI; _apply_settings
pushes saved values to the vendored tool via env vars."""
import sys, os
sys.path.insert(0, '.')
from pathlib import Path
from core.plugin_loader import discover_plugins
import importlib.util


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, Path(f"plugins/{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_excel_writer_declares_settings():
    mod = _load("shirazi_excel_create")
    ps = mod.PLUGIN_SETTINGS
    assert isinstance(ps, dict)
    assert ps["namespace"] == "shirazi_excel"
    assert any(f["key"] == "save_folder" for f in ps["fields"])


def test_other_plugins_declare_no_settings():
    mod = _load("shirazi_timer_start")
    assert mod.PLUGIN_SETTINGS is None


def test_settings_schemas_lists_excel():
    reg = discover_plugins(Path("plugins"), set(), logger=lambda m: None)
    schemas = reg.settings_schemas()
    ns = [s["namespace"] for s in schemas]
    assert "shirazi_excel" in ns


def test_apply_settings_sets_env(monkeypatch):
    mod = _load("shirazi_excel_create")
    monkeypatch.setattr("memory.config_manager.get_plugin_config",
                        lambda ns: {"save_folder": "C:/tmp/xl"} if ns == "shirazi_excel" else {})
    # make sure the real config_manager is importable for the patch target
    import memory.config_manager  # noqa
    monkeypatch.setenv("SHIRAZI_EXCEL_DIR", "")
    if "SHIRAZI_EXCEL_DIR" in os.environ:
        del os.environ["SHIRAZI_EXCEL_DIR"]
    # patch via sys.modules since _apply_settings imports it lazily
    import types
    fake_cm = types.ModuleType("memory.config_manager")
    fake_cm.get_plugin_config = lambda ns: {"save_folder": "C:/tmp/xl"}
    monkeypatch.setitem(sys.modules, "memory.config_manager", fake_cm)
    mod._apply_settings()
    assert os.environ.get("SHIRAZI_EXCEL_DIR") == "C:/tmp/xl"
    # empty setting clears the var (default Desktop behavior returns)
    fake_cm.get_plugin_config = lambda ns: {}
    mod._apply_settings()
    assert "SHIRAZI_EXCEL_DIR" not in os.environ
