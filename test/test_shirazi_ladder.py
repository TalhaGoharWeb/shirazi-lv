"""Tests for core/shirazi_ladder.py — Shirazi-origin provider failover."""
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import shirazi_ladder as lad


# --- contents_to_text -------------------------------------------------------
def test_contents_str_passthrough():
    assert lad.contents_to_text("hello") == "hello"


def test_contents_list_of_str():
    assert lad.contents_to_text(["a", "b"]) == "a\nb"


def test_contents_dict_parts():
    contents = [{"text": "hi"}, {"parts": [{"text": "there"}]}]
    assert lad.contents_to_text(contents) == "hi\nthere"


def test_contents_empty():
    assert lad.contents_to_text([]) == ""
    assert lad.contents_to_text(None) == ""


# --- _check_status ----------------------------------------------------------
class _Resp:
    def __init__(self, status, body=b""):
        self.status = status
        self._body = body

    def read(self, n=-1):
        return self._body


def test_check_status_ok():
    lad._check_status("groq", _Resp(200))  # must not raise


def test_check_status_auth():
    with pytest.raises(lad.AuthError):
        lad._check_status("groq", _Resp(401, b"bad key"))


def test_check_status_retryable():
    with pytest.raises(lad.ProviderError):
        lad._check_status("groq", _Resp(429, b"slow down"))
    with pytest.raises(lad.ProviderError):
        lad._check_status("groq", _Resp(500, b"boom"))


# --- oai_fallback_text ------------------------------------------------------
def test_fallback_no_keys_returns_default(monkeypatch):
    monkeypatch.setattr(lad, "_key_for", lambda p: "")
    assert lad.oai_fallback_text("hi", "FAST", default="dflt") == "dflt"


def test_fallback_uses_first_working_rung(monkeypatch):
    monkeypatch.setattr(lad, "_key_for", lambda p: "k-" + p)
    calls = []

    def fake_oai(provider, model, prompt, key, timeout_s=60):
        calls.append(provider)
        return "answer"

    monkeypatch.setattr(lad, "_oai_text", fake_oai)
    assert lad.oai_fallback_text("hi", "FAST") == "answer"
    assert calls == ["groq"]  # first rung wins


def test_fallback_skips_failed_rung(monkeypatch):
    monkeypatch.setattr(lad, "_key_for", lambda p: "k-" + p)

    def fake_oai(provider, model, prompt, key, timeout_s=60):
        if provider == "groq":
            raise lad.ProviderError("groq", 500, "down")
        return "via-openrouter"

    monkeypatch.setattr(lad, "_oai_text", fake_oai)
    assert lad.oai_fallback_text("hi", "FAST") == "via-openrouter"


def test_fallback_auth_error_moves_on(monkeypatch):
    monkeypatch.setattr(lad, "_key_for", lambda p: "k-" + p)

    def fake_oai(provider, model, prompt, key, timeout_s=60):
        if provider == "groq":
            raise lad.AuthError("groq", 401, "bad key")
        return "via-openrouter"

    monkeypatch.setattr(lad, "_oai_text", fake_oai)
    assert lad.oai_fallback_text("hi", "FAST") == "via-openrouter"


def test_fallback_empty_prompt():
    assert lad.oai_fallback_text("", "FAST", default="d") == "d"


# --- text_with_fallback -----------------------------------------------------
def test_text_with_fallback_prefers_gemini(monkeypatch):
    # Mock BOTH sys.modules and the `core` package attribute: `from core
    # import gemini` prefers the package attribute when the real module was
    # imported by an earlier test (test-isolation fix).
    fake_gemini = types.SimpleNamespace(text=lambda *a, **k: "gemini says hi")
    monkeypatch.setitem(sys.modules, "core.gemini", fake_gemini)
    import core as _core_pkg
    monkeypatch.setattr(_core_pkg, "gemini", fake_gemini, raising=False)
    assert lad.text_with_fallback("hi", "FAST") == "gemini says hi"


def test_text_with_fallback_uses_oai_when_gemini_empty(monkeypatch):
    fake_gemini = types.SimpleNamespace(text=lambda *a, **k: "")
    monkeypatch.setitem(sys.modules, "core.gemini", fake_gemini)
    monkeypatch.setattr(lad, "oai_fallback_text",
                        lambda prompt, tier="FAST", default="": "oai answer")
    assert lad.text_with_fallback("hi", "SMART") == "oai answer"


# --- config key roundtrip (isolated to a tmp config file) --------------------
def test_provider_key_roundtrip(monkeypatch, tmp_path):
    from memory import config_manager as cm
    monkeypatch.setattr(cm, "CONFIG_FILE", tmp_path / "api_keys.json")
    monkeypatch.setattr(cm, "CONFIG_DIR", tmp_path)
    cm.save_provider_key("groq", "  gsk-test  ")
    assert cm.get_groq_key() == "gsk-test"
    assert cm.get_openrouter_key() is None
    with pytest.raises(ValueError):
        cm.save_provider_key("nope", "x")
