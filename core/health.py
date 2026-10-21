"""
Startup health checks + crash recovery — Personal Companion (Phase 8).

run_health_checks() inspects:
  config      — api_keys.json parses; provider keys present (presence only)
  profile     — profile.json parses; schema version current
  memory      — long_term.json readable; episodic SQLite opens
  secrets     — credential-store backend reachable
  providers   — configured providers (no network call; use test_connection)
  audio       — input/output devices enumerated
  dependencies— critical imports available
  backup      — at least one verified backup exists; newest backup age

Each check returns {name, status: ok|warn|fail, detail, fatal: bool}.
Non-fatal failures never block startup — Shirazi opens and reports.

Crash recovery:
  mark_clean_shutdown() / was_clean_shutdown() via a lockfile.
  check_incomplete_tasks() scans the task-checkpoint store for tasks
  left in a non-terminal state and offers resume/inspect/discard.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path


def _app_base() -> Path:
    return Path(__file__).resolve().parent.parent


def _data_dir() -> Path:
    d = Path.home() / ".shirazi"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _check(name: str, fatal: bool = False) -> dict:
    return {"name": name, "status": "ok", "detail": "", "fatal": fatal}


def check_config() -> dict:
    c = _check("config", fatal=True)
    p = _app_base() / "config" / "api_keys.json"
    if not p.exists():
        c["status"] = "fail"
        c["detail"] = "config/api_keys.json missing — open Settings > API KEYS"
        return c
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        c["status"] = "fail"
        c["detail"] = f"config/api_keys.json is not valid JSON: {e}"
        return c
    keys = [k for k in ("gemini_api_key", "groq_api_key", "openrouter_api_key")
            if data.get(k)]
    # Keys may live in the OS credential store instead.
    try:
        from core import secrets_store as _ss
        for k in ("gemini_api_key", "groq_api_key", "openrouter_api_key"):
            if k not in keys and _ss.get_secret(k):
                keys.append(k + " (secure store)")
    except Exception:
        pass
    if not keys:
        c["status"] = "warn"
        c["detail"] = "no provider keys configured"
    else:
        c["detail"] = f"{len(keys)} provider key(s) present"
    return c


def check_profile() -> dict:
    c = _check("profile")
    try:
        from core import profile as _prof
        data = _prof.load_profile()
        if data.get("profile_schema_version") != _prof.SCHEMA_VERSION:
            c["status"] = "warn"
            c["detail"] = "profile schema outdated — will migrate on save"
        elif not data.get("onboarding_completed"):
            c["status"] = "warn"
            c["detail"] = "onboarding not completed"
        else:
            c["detail"] = "profile OK"
    except Exception as e:
        c["status"] = "fail"
        c["detail"] = f"cannot load profile: {e}"
    return c


def check_memory() -> dict:
    c = _check("memory")
    problems = []
    try:
        from memory import memory_manager as _mm
        mem = _mm.load_memory()
        n = sum(len(v) for v in mem.values() if isinstance(v, dict))
        detail_mem = f"{n} semantic entries"
    except Exception as e:
        problems.append(f"semantic memory unreadable: {e}")
        detail_mem = "semantic FAILED"
    try:
        db = _data_dir() / "memory.db"
        if db.exists():
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
            con.execute("PRAGMA integrity_check").fetchall()
            con.close()
            detail_ep = "episodic DB OK"
        else:
            detail_ep = "episodic DB not created yet"
    except Exception as e:
        problems.append(f"episodic DB problem: {e}")
        detail_ep = "episodic FAILED"
    if problems:
        c["status"] = "fail"
        c["detail"] = "; ".join(problems)
    else:
        c["detail"] = f"{detail_mem}; {detail_ep}"
    return c


def check_secrets_store() -> dict:
    c = _check("secrets")
    try:
        from core import secrets_store as _ss
        backend = _ss.backend_name()
        # Round-trip a canary (not a real secret).
        ok = _ss.set_secret("__shirazi_health__", "ok") and \
            _ss.get_secret("__shirazi_health__") == "ok"
        _ss.delete_secret("__shirazi_health__")
        if ok:
            c["detail"] = f"backend: {backend} (write/read verified)"
        else:
            c["status"] = "warn"
            c["detail"] = (f"backend: {backend} — write/read failed; "
                           f"keys fall back to config file")
    except Exception as e:
        c["status"] = "warn"
        c["detail"] = f"secret store unavailable: {e}"
    return c


def check_providers() -> dict:
    c = _check("providers")
    found = []
    try:
        from memory.config_manager import (get_gemini_key, get_groq_key,
                                           get_openrouter_key)
        if get_gemini_key():
            found.append("gemini")
        if get_groq_key():
            found.append("groq")
        if get_openrouter_key():
            found.append("openrouter")
    except Exception:
        pass
    if not found:
        c["status"] = "warn"
        c["detail"] = "no providers configured"
    else:
        c["detail"] = f"configured: {', '.join(found)}"
    return c


def check_audio() -> dict:
    c = _check("audio")
    try:
        from core import audio_devices as _ad
        ins = _ad.list_inputs() if hasattr(_ad, "list_inputs") else []
        outs = _ad.list_outputs() if hasattr(_ad, "list_outputs") else []
        c["detail"] = f"{len(ins)} input(s), {len(outs)} output(s)"
        if not ins and not outs:
            c["status"] = "warn"
            c["detail"] = "no audio devices found"
    except Exception as e:
        c["status"] = "warn"
        c["detail"] = f"audio check unavailable: {e}"
    return c


def check_dependencies() -> dict:
    c = _check("dependencies", fatal=True)
    missing = []
    for mod in ("PyQt6.QtWidgets", "google.genai", "certifi"):
        try:
            __import__(mod)
        except Exception:
            missing.append(mod)
    if missing:
        c["status"] = "fail"
        c["detail"] = f"missing: {', '.join(missing)}"
    else:
        c["detail"] = "core dependencies present"
    return c


def check_backup() -> dict:
    c = _check("backup")
    try:
        from core import backup as _bk
        items = _bk.list_backups()
        valid = [b for b in items if b["ok"]]
        if not valid:
            c["status"] = "warn"
            c["detail"] = "no verified backups — create one in Backup & Restore"
        else:
            newest = valid[0]["created_at"]
            c["detail"] = (f"{len(valid)} verified backup(s); "
                           f"newest: {newest}")
    except Exception as e:
        c["status"] = "warn"
        c["detail"] = f"backup check unavailable: {e}"
    return c


CHECKS = (check_config, check_profile, check_memory, check_secrets_store,
          check_providers, check_audio, check_dependencies, check_backup)


def run_health_checks() -> dict:
    """Run all checks. Returns {checks: [...], fatal: bool, summary: str}."""
    results = []
    for fn in CHECKS:
        try:
            results.append(fn())
        except Exception as e:
            results.append({"name": fn.__name__, "status": "fail",
                            "detail": f"check crashed: {e}", "fatal": False})
    fatal = any(r["status"] == "fail" and r["fatal"] for r in results)
    n_fail = sum(1 for r in results if r["status"] == "fail")
    n_warn = sum(1 for r in results if r["status"] == "warn")
    summary = (f"{len(results) - n_fail - n_warn}/{len(results)} checks OK"
               + (f", {n_warn} warnings" if n_warn else "")
               + (f", {n_fail} failures" if n_fail else ""))
    return {"checks": results, "fatal": fatal, "summary": summary}


# ── crash recovery ────────────────────────────────────────────────────

def _lockfile() -> Path:
    return _data_dir() / "running.lock"


def mark_running() -> None:
    try:
        _lockfile().write_text(str(time.time()), encoding="utf-8")
    except Exception:
        pass


def mark_clean_shutdown() -> None:
    try:
        _lockfile().unlink(missing_ok=True)
    except Exception:
        pass


def was_clean_shutdown() -> bool:
    """False when a previous run did not shut down cleanly (crash)."""
    return not _lockfile().exists()


def check_incomplete_tasks() -> list[dict]:
    """Tasks left in a non-terminal state by a crash.

    Reads the shirazi_task_checkpoint plugin's store without importing
    plugin machinery. Returns [{id, title, state, updated}].
    """
    out = []
    try:
        store = _data_dir() / "plugins_data" / "shirazi_task_checkpoint.json"
        if not store.exists():
            # Fallback: plugin settings namespace file.
            store = _data_dir() / "plugins.json"
        data = json.loads(store.read_text(encoding="utf-8")) \
            if store.exists() else {}
        tasks = data.get("tasks", data) if isinstance(data, dict) else []
        if isinstance(tasks, dict):
            tasks = tasks.values()
        for t in tasks if isinstance(tasks, list) else []:
            if not isinstance(t, dict):
                continue
            state = str(t.get("state", t.get("status", ""))).lower()
            if state and state not in ("done", "completed", "cancelled",
                                       "failed", "discarded"):
                out.append({
                    "id": t.get("id", "?"),
                    "title": t.get("title", t.get("name", "?")),
                    "state": state,
                    "updated": t.get("updated", ""),
                })
    except Exception:
        pass
    return out


def health_report_text() -> str:
    """One-page human-readable report (for the log and diagnostics)."""
    res = run_health_checks()
    lines = [f"Health: {res['summary']}"]
    for r in res["checks"]:
        mark = {"ok": "✓", "warn": "!", "fail": "✕"}[r["status"]]
        lines.append(f"  [{mark}] {r['name']}: {r['detail']}")
    if not was_clean_shutdown():
        lines.append("  [!] previous run did not shut down cleanly")
        tasks = check_incomplete_tasks()
        if tasks:
            lines.append(f"  [!] {len(tasks)} incomplete task(s) found")
    return "\n".join(lines)
