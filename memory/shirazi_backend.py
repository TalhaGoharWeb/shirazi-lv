"""Shirazi-origin episodic memory backend for Shirazi LV.

One memory system, two backends, one API surface (memory_manager):
- Profile KV (Mark-LV-origin, JSON): identity / preferences / projects /
  relationships / wishes / notes — unchanged behaviour.
- Episodic FTS (Shirazi-origin, SQLite + FTS5/BM25): every conversation turn,
  entities, and session auto-summaries — full-text recall with ranking.

The Shirazi store is loaded from the shirazi-core tree by file path (stdlib
sqlite3 only); nothing is imported at module load — get_store() is lazy and
every public helper is best-effort (never raises into the caller).
"""
from __future__ import annotations

import importlib.util
import os
import threading
from pathlib import Path

_SHIRAZI_MEMORY_PKG = (Path(__file__).resolve().parent.parent
                         / "vendor" / "shirazi" / "memory")

_lock = threading.Lock()
_store = None
_session_id = None


def _data_dir() -> Path:
    base = Path(os.environ.get("SHIRAZI_DATA_DIR", str(Path.home() / ".shirazi")))
    d = base / "shirazi_lv_memory"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_store():
    """Lazy singleton Shirazi MemoryStore. Returns None (never raises) on failure."""
    global _store
    with _lock:
        if _store is not None:
            return _store
        try:
            init = _SHIRAZI_MEMORY_PKG / "__init__.py"
            spec = importlib.util.spec_from_file_location(
                "shirazi_memory_pkg", init,
                submodule_search_locations=[str(_SHIRAZI_MEMORY_PKG)])
            pkg = importlib.util.module_from_spec(spec)
            import sys
            sys.modules["shirazi_memory_pkg"] = pkg
            spec.loader.exec_module(pkg)
            from shirazi_memory_pkg.store import MemoryStore
            _store = MemoryStore(str(_data_dir()))
        except Exception as e:
            print(f"[Memory] episodic backend unavailable: {e}")
            _store = False  # remember the failure; don't retry every turn
        return _store if _store is not False else None


def record_turn(role: str, text: str) -> None:
    """Append one conversation turn to the episodic store. Never raises."""
    global _session_id
    if not text or not text.strip():
        return
    try:
        store = get_store()
        if store is None:
            return
        with _lock:
            if _session_id is None:
                _session_id = store.start_session()
            sid = _session_id
        store.record_turn(sid, role, text.strip()[:4000])
        # Also index into the FTS memories table (kind="turn"): the store's
        # recall() only searches memories_fts, so without this, past turns
        # would be recorded but never recallable.
        store.remember(f"{role}: {text.strip()[:4000]}", kind="turn",
                       session_id=sid)
    except Exception:
        pass


def recall_episodic(query: str, k: int = 5) -> list[str]:
    """BM25-ranked past turns/notes matching query. Never raises."""
    try:
        store = get_store()
        if store is None:
            return []
        out = []
        for hit in store.recall(query, k=k):
            content = (hit.get("content") or "").strip()
            if content:
                out.append(content)
        return out
    except Exception:
        return []


def episodic_stats() -> dict:
    """Phase 3.5: counts for the Memory Manager UI. Never raises."""
    try:
        store = get_store()
        if store is None:
            return {"available": False}
        # Query the store's SQLite directly for counts.
        import sqlite3
        db_path = str(_data_dir() / "memory.db")
        # The store may use a different filename; try common ones.
        for name in ("memory.db", "episodic.db", "store.db"):
            p = _data_dir() / name
            if p.exists():
                db_path = str(p)
                break
        conn = sqlite3.connect(db_path)
        try:
            turns = conn.execute(
                "SELECT COUNT(*) FROM turns").fetchone()[0]
        except Exception:
            turns = 0
        try:
            mems = conn.execute(
                "SELECT COUNT(*) FROM memories").fetchone()[0]
        except Exception:
            mems = 0
        conn.close()
        return {"available": True, "turns": turns, "memories": mems}
    except Exception:
        return {"available": False}


def clear_episodic() -> bool:
    """Phase 3.5: delete ALL episodic data. Returns True on success.
    Never raises."""
    try:
        store = get_store()
        if store is None:
            return False
        import sqlite3
        for name in ("memory.db", "episodic.db", "store.db"):
            p = _data_dir() / name
            if p.exists():
                conn = sqlite3.connect(str(p))
                try:
                    for tbl in ("turns", "memories", "memories_fts",
                                "sessions"):
                        try:
                            conn.execute(f"DELETE FROM {tbl}")
                        except Exception:
                            pass
                    conn.commit()
                finally:
                    conn.close()
        global _session_id
        with _lock:
            _session_id = None
        return True
    except Exception:
        return False


def end_episodic_session(summary: str | None = None) -> None:
    """Close the current episodic session (stores the auto-summary). Never raises."""
    global _session_id
    try:
        store = get_store()
        with _lock:
            sid, _session_id = _session_id, None
        if store is not None and sid is not None:
            store.end_session(sid, summary=summary)
    except Exception:
        pass
