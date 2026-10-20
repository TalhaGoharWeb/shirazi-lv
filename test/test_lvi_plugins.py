"""Tests for the Shirazi LVI wave: MYRA-learned plugins + gateway tiers.

Each new plugin must satisfy the Mark-LV plugin contract (valid discovery,
run() returns a non-empty string and never raises) AND its core behaviour
must actually work — these tests exercise the real logic on temp dirs.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"
NEW_PLUGINS = {
    "shirazi_spotify", "shirazi_qr", "shirazi_ppt_create",
    "shirazi_website", "shirazi_expense", "shirazi_duplicates",
}


def _registry():
    from core.plugin_loader import discover_plugins

    return discover_plugins(PLUGINS_DIR, set(), lambda m: None, None)


def test_new_plugins_discovered_and_valid():
    reg = _registry()
    recs = {r.name: r for r in reg._all_records if r.name in NEW_PLUGINS}
    assert set(recs) == NEW_PLUGINS, f"missing: {NEW_PLUGINS - set(recs)}"
    bad = [(n, r.error) for n, r in recs.items() if not r.valid]
    assert not bad, f"invalid plugins: {bad}"


def test_new_plugins_in_gateway_risk_map():
    from core.omnicontrol import gateway, policy

    for name in NEW_PLUGINS - {"shirazi_duplicates"}:
        assert gateway.TOOL_RISK_MAP.get(name) == policy.MODERATE, name
    assert gateway.TOOL_RISK_MAP.get("shirazi_duplicates") == policy.LOW


def test_spotify_run_contract_off_windows():
    import importlib

    sp = importlib.import_module("plugins.shirazi_spotify")
    assert sp.run({}).strip()
    out = sp.run({"action": "now_playing"})
    assert isinstance(out, str) and out
    out = sp.run({"action": "play"})  # no query -> asks, must not launch
    assert "which song" in out.lower()


def test_expense_roundtrip(tmp_path, monkeypatch):
    import importlib

    monkeypatch.setenv("SHIRAZI_DATA_DIR", str(tmp_path))
    ex = importlib.import_module("plugins.shirazi_expense")
    out = ex.run({"action": "add", "item": "petrol", "amount": 500,
                  "category": "safar"})
    assert "Rs 500" in out
    ex.run({"action": "add", "item": "sabzi", "amount": 1200,
            "category": "khana"})
    summary = ex.run({"action": "summary"})
    assert "1,700" in summary and "khana" in summary
    assert "1,700" in ex.run({"action": "today"})
    assert "petrol" in ex.run({"action": "recent"})
    assert ex.run({"action": "add", "item": "", "amount": 10}).strip()


def test_duplicates_finds_group(tmp_path):
    import importlib

    dup = importlib.import_module("plugins.shirazi_duplicates")
    (tmp_path / "a.bin").write_bytes(b"z" * 6000)
    (tmp_path / "b.bin").write_bytes(b"z" * 6000)
    (tmp_path / "only.bin").write_bytes(b"q" * 7000)
    out = dup.run({"folder": str(tmp_path), "min_size_kb": 1})
    assert "duplicate group" in out and "delete nahi" in out
    assert dup.run({"folder": str(tmp_path / "nope")}).strip()


def test_qr_create_read_roundtrip(tmp_path, monkeypatch):
    qrcode = pytest.importorskip("qrcode")
    cv2 = pytest.importorskip("cv2")
    import importlib

    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "Desktop").mkdir()
    qr = importlib.import_module("plugins.shirazi_qr")
    out = qr.run({"action": "create", "text": "https://example.com/x"})
    assert "saved" in out.lower()
    pngs = list((tmp_path / "Desktop").glob("QR_*.png"))
    assert len(pngs) == 1
    back = qr.run({"action": "read", "image_path": str(pngs[0])})
    assert "https://example.com/x" in back
    wifi = qr.run({"action": "wifi", "ssid": "HomeNet", "password": "pw12345"})
    assert "saved" in wifi.lower()


def test_ppt_create_builds_valid_deck(tmp_path, monkeypatch):
    pytest.importorskip("pptx")
    import importlib

    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "Desktop").mkdir()
    pp = importlib.import_module("plugins.shirazi_ppt_create")
    out = pp.run({
        "title": "Water Cycle",
        "slides": [
            {"heading": "Evaporation", "bullets": ["Sun heats water"]},
            {"heading": "Rain", "bullets": ["Clouds cool", "Rain falls"]},
        ],
    })
    assert "ready" in out.lower()
    decks = list((tmp_path / "Desktop").glob("*.pptx"))
    assert len(decks) == 1
    from pptx import Presentation

    prs = Presentation(str(decks[0]))
    assert len(prs.slides._sldIdLst) == 4  # title + 2 content + closing
    assert pp.run({}).strip()


def test_website_fallback_template(tmp_path, monkeypatch):
    import importlib

    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "Documents").mkdir()
    import core.shirazi_ladder as ladder

    monkeypatch.setattr(ladder, "text_with_fallback",
                        lambda *a, **k: "")
    ws = importlib.import_module("plugins.shirazi_website")
    out = ws.run({"description": "Site for Noor Madrassa", "name": "noor-test"})
    assert "ready" in out.lower() and "template" in out.lower()
    index = tmp_path / "Documents" / "Shirazi Websites" / "noor-test" / "index.html"
    assert index.is_file()
    assert index.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")


def test_website_extract_html():
    import importlib

    ws = importlib.import_module("plugins.shirazi_website")
    fenced = "sure!\n```html\n<!DOCTYPE html><html><body>x</body></html>\n```"
    assert ws._extract_html(fenced).startswith("<!DOCTYPE html>")
    assert ws._extract_html("no html here") == ""
    assert ws._extract_html("") == ""


def test_prompt_has_vision_honesty_rule():
    text = (Path(__file__).resolve().parent.parent / "core" / "prompt.txt") \
        .read_text(encoding="utf-8")
    assert "Describe only what the current frame actually shows" in text
