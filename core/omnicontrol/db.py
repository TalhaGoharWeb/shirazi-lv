"""
OMNICONTROL database layer.

Single SQLite file (``~/.shirazi/omnicontrol.db``) holding the security-critical
state that the authorization gateway depends on:

* ``grants``      — permission grants (deny-by-default; no row = no access)
* ``folders``     — filesystem allow-list with per-operation flags
* ``repos``       — approved GitHub repositories and their granted ops
* ``tasks``       — orchestrator task records
* ``audit_log``   — append-only record of every gateway decision
* ``kv``          — emergency-stop flag, emergency phrase, misc switches

The DB file itself lives under the user's Shirazi data dir with owner-only
permissions (0600) where the platform supports it.
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS grants (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    principal     TEXT NOT NULL DEFAULT 'user',
    resource_kind TEXT NOT NULL,            -- 'folder' | 'repo' | 'tool' | 'device'
    resource      TEXT NOT NULL,            -- path, repo full name, tool name...
    ops           TEXT NOT NULL,            -- comma-separated ops, e.g. 'read,search'
    scope_path    TEXT,                     -- canonical path scope, if any
    project       TEXT,
    created_at    REAL NOT NULL,
    expires_at    REAL,                     -- NULL = persistent until revoked
    persistent    INTEGER NOT NULL DEFAULT 0,
    needs_approval INTEGER NOT NULL DEFAULT 0,
    revoked       INTEGER NOT NULL DEFAULT 0,
    revoked_at    REAL,
    created_by    TEXT NOT NULL DEFAULT 'user'  -- 'user' | 'dashboard' | 'voice+tap'
);

CREATE TABLE IF NOT EXISTS folders (
    path       TEXT PRIMARY KEY,           -- canonical absolute path
    can_read   INTEGER NOT NULL DEFAULT 1,
    can_write  INTEGER NOT NULL DEFAULT 0,
    can_exec   INTEGER NOT NULL DEFAULT 0,
    can_delete INTEGER NOT NULL DEFAULT 0,
    added_at   REAL NOT NULL,
    added_by   TEXT NOT NULL DEFAULT 'user'
);

CREATE TABLE IF NOT EXISTS repos (
    full_name  TEXT PRIMARY KEY,           -- 'owner/repo'
    can_read   INTEGER NOT NULL DEFAULT 1,
    can_write  INTEGER NOT NULL DEFAULT 0,  -- stays 0 until separately authorized
    added_at   REAL NOT NULL,
    added_by   TEXT NOT NULL DEFAULT 'user'
);

CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    state       TEXT NOT NULL DEFAULT 'QUEUED',
    workspace   TEXT,
    plan_json   TEXT,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    result_json TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        REAL NOT NULL,
    actor     TEXT NOT NULL,               -- 'gateway' | 'user' | 'orchestrator' | tool name
    action    TEXT NOT NULL,               -- 'allow' | 'deny' | 'grant' | 'revoke' | 'estop' ...
    tool      TEXT,
    resource  TEXT,
    decision  TEXT,
    reason    TEXT,
    details   TEXT                          -- MUST be secret-free (enforced by audit.py)
);

CREATE TABLE IF NOT EXISTS kv (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None
_db_path: Path | None = None
_override: Path | None = None  # set by reset_for_tests; tests only


def default_path() -> Path:
    return Path(os.path.expanduser("~")) / ".shirazi" / "omnicontrol.db"


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    """Open (and migrate) the DB. Safe to call repeatedly; returns a singleton."""
    global _conn, _db_path
    with _lock:
        p = Path(path) if path else (_override or default_path())
        if _conn is not None and _db_path == p:
            return _conn
        # switching paths: close the old handle first
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass
            _conn = None
        p.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(p), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(_SCHEMA)
        _conn.execute(
            "INSERT OR IGNORE INTO kv(key, value) VALUES ('estop', '0')"
        )
        _conn.commit()
        _db_path = p
        try:
            os.chmod(p, 0o600)
        except OSError:
            pass  # Windows: ACLs, best effort
        return _conn


def reset_for_tests(path: Path | str) -> sqlite3.Connection:
    """Throw away the singleton and open a fresh DB (tests only)."""
    global _override
    with _lock:
        _override = Path(path)
        return connect(_override)


def clear_test_override() -> None:
    global _override
    with _lock:
        _override = None


def now() -> float:
    return time.time()
