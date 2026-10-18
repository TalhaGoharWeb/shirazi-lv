"""Tests for Stage 3 — unified memory (Mark-LV profile KV + Shirazi episodic FTS)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memory import shirazi_backend as sb


def test_backend_record_and_recall(tmp_path, monkeypatch):
    monkeypatch.setenv("SHIRAZI_DATA_DIR", str(tmp_path))
    sb._store = None
    sb._session_id = None
    sb.record_turn("user", "I love playing cricket on weekends")
    sb.record_turn("assistant", "Noted — cricket on weekends.")
    hits = sb.recall_episodic("cricket", k=5)
    assert any("cricket" in h.lower() for h in hits), f"no hit in {hits}"
    sb.end_episodic_session("user likes cricket")
    assert sb._session_id is None  # session closed
    sb.record_turn("user", "after close")  # starts a fresh session silently
    assert sb._session_id is not None


def test_backend_never_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("SHIRAZI_DATA_DIR", str(tmp_path))
    sb._store = None
    sb.record_turn("user", "")          # empty -> no-op
    sb.record_turn("user", "   ")        # blank -> no-op
    assert sb.recall_episodic("") == []  # empty query -> []
    sb.end_episodic_session(None)        # nothing open -> no-op


def test_search_memory_merges_episodic(tmp_path, monkeypatch):
    monkeypatch.setenv("SHIRAZI_DATA_DIR", str(tmp_path))
    sb._store = None
    sb._session_id = None
    # isolate the JSON profile too
    from memory import memory_manager as mm
    monkeypatch.setattr(mm, "MEMORY_PATH", tmp_path / "long_term.json")
    sb.record_turn("user", "my favourite biryani spot is Burns Road")
    out = mm.search_memory("biryani")
    assert "past conversations" in out.lower(), f"episodic missing in: {out[:200]}"
    assert "burns road" in out.lower()


def test_search_memory_empty_still_honest(tmp_path, monkeypatch):
    monkeypatch.setenv("SHIRAZI_DATA_DIR", str(tmp_path))
    sb._store = None
    sb._session_id = None
    from memory import memory_manager as mm
    monkeypatch.setattr(mm, "MEMORY_PATH", tmp_path / "long_term.json")
    out = mm.search_memory("zzz-no-such-thing-zzz")
    assert "nothing stored" in out.lower()
