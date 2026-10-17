"""MemoryStore — the durable memory layer (SQLite + FTS5, stdlib only).

Write path:  redact secrets -> normalize -> dedupe -> insert (triggers
             keep both FTS tables in sync).
Read path:   normalize query -> search BOTH fts tables -> merge/dedupe by
             id -> top-k.

Thread-safe via a single lock; the server is a ThreadingHTTPServer.
WAL mode is enabled for concurrent readers.
"""

import json
import shutil
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .normalize import normalize
from .schema import ensure_schema
from .secrets import redact

_DB_NAME = "memory.db"
_BACKUP_KEEP = 10


def _utcnow():
    return time.time()


class MemoryStore:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / _DB_NAME
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._closed = False
        with self._lock:
            self._db.execute("PRAGMA journal_mode=WAL")
            ensure_schema(self._db)

    # -- internal ----------------------------------------------------
    # Stopwords removed from recall queries so natural questions like
    # "what's my project?" reduce to their content terms ("project").
    # Without this, FTS5's implicit AND over every word kills recall.
    _STOPWORDS = frozenset("""
        what whats whatever is are was were be been being do does did done
        my your his her its our their the a an of in on at to for about tell
        me i you it this that these those and or not no know remember recall
        what’s do’s
        کیا ہے ہیں کا کی کے میرا میری میرے میں نے کو سے پر اور وہ یہ جو تھا تھی
        تھے ہوں گا گی گے بتاؤ بتائیں یاد کرو
        kya hai hain ka ki ke mera meri mere mein ne ko se par aur woh yeh
        jo tha thi thay hoon ga gi ge batao batayen bataye yaad karo karo
        """.split())

    def _match_query(self, text):
        """Build an AND-of-terms FTS5 query: stopwords dropped, each term
        individually quoted (operator-safe), casefolded for trigram."""
        terms = [t.casefold() for t in text.split()
                 if t.casefold() not in self._STOPWORDS and len(t) > 1]
        if not terms:
            return self._phrase(text)  # degenerate query: exact phrase
        return " ".join('"' + t.replace('"', '""') + '"' for t in terms)

    def _phrase(self, text):
        """Quote user text as an FTS5 phrase so operators can't leak in."""
        return '"' + text.replace('"', '""') + '"'

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._db.commit()
            self._db.close()

    # -- remember / recall / forget -----------------------------------
    def remember(self, content, kind="fact", session_id=None):
        """Store a memory. Returns the row id, or None if deduped/skipped.

        Dedupes on normalized exact-match OR a trigram MATCH hit on the
        same normalized text.
        """
        raw = content if isinstance(content, str) else str(content)
        if not raw.strip():
            return None
        redacted, _kinds = redact(raw)
        norm = normalize(redacted)
        if not norm.strip():
            return None
        now = _utcnow()
        with self._lock:
            row = self._db.execute(
                "SELECT id FROM memories WHERE norm = ? LIMIT 1",
                (norm,)).fetchone()
            if row is None:
                phrase = self._phrase(norm)
                row = self._db.execute(
                    "SELECT rowid FROM memories_fts "
                    "WHERE memories_fts MATCH ? LIMIT 1",
                    (phrase,)).fetchone()
            if row is not None:
                return None  # duplicate of an existing memory
            cur = self._db.execute(
                "INSERT INTO memories "
                "(content, norm, kind, created_at, updated_at, source_session)"
                " VALUES (?,?,?,?,?,?)",
                (redacted, norm, kind, now, now, session_id))
            self._db.commit()
            return cur.lastrowid

    def recall(self, query, k=5):
        """Return up to k [{id, content, kind, created_at, score}]."""
        q = normalize(query if isinstance(query, str) else str(query)).strip()
        if not q:
            return []
        phrase = self._match_query(q)
        merged = {}
        with self._lock:
            for fts in ("memories_fts", "memories_fts_en"):
                try:
                    rows = self._db.execute(
                        f"SELECT rowid AS id, bm25({fts}) AS rank "
                        f"FROM {fts} WHERE {fts} MATCH ? "
                        f"ORDER BY rank LIMIT ?",
                        (phrase, k * 2)).fetchall()
                except sqlite3.OperationalError:
                    continue  # malformed match expression; try next table
                for r in rows:
                    mid = r["id"]
                    score = -float(r["rank"])
                    if mid not in merged or score > merged[mid][0]:
                        merged[mid] = (score, fts)
            out = []
            for mid, (score, _fts) in merged.items():
                m = self._db.execute(
                    "SELECT id, content, kind, created_at FROM memories "
                    "WHERE id = ?", (mid,)).fetchone()
                if m is None:
                    continue
                out.append({"id": m["id"], "content": m["content"],
                            "kind": m["kind"],
                            "created_at": m["created_at"],
                            "score": score})
        out.sort(key=lambda d: d["score"], reverse=True)
        return out[:k]

    def forget(self, mem_id):
        """Hard delete a memory (FTS rows removed by triggers)."""
        with self._lock:
            cur = self._db.execute("DELETE FROM memories WHERE id = ?",
                                   (mem_id,))
            self._db.commit()
            return cur.rowcount > 0

    def forget_query(self, query):
        """Delete the single best recall match for `query`."""
        hits = self.recall(query, k=1)
        if not hits:
            return False
        return self.forget(hits[0]["id"])

    # -- export / backup ----------------------------------------------
    def export(self):
        """Full JSON-serializable dump."""
        with self._lock:
            memories = [dict(r) for r in self._db.execute(
                "SELECT * FROM memories ORDER BY id")]
            entities = [dict(r) for r in self._db.execute(
                "SELECT * FROM entities ORDER BY id")]
            sessions = [dict(r) for r in self._db.execute(
                "SELECT * FROM sessions ORDER BY started_at")]
        return {"memories": memories, "entities": entities,
                "sessions": sessions,
                "exported_at": datetime.now(timezone.utc).isoformat()}

    def backup(self):
        """Timestamped copy of the DB into <datadir>/backups/, keep last 10."""
        bdir = self.data_dir / "backups"
        bdir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        dest = bdir / f"memory-{stamp}.db"
        with self._lock:
            target = sqlite3.connect(str(dest))
            try:
                self._db.backup(target)
            finally:
                target.close()
        snaps = sorted(bdir.glob("memory-*.db"),
                       key=lambda p: p.name, reverse=True)
        for old in snaps[_BACKUP_KEEP:]:
            try:
                old.unlink()
            except OSError:
                pass
        return str(dest)

    # -- entities ------------------------------------------------------
    def add_entity(self, name, kind=None, notes=None, aliases=()):
        with self._lock:
            self._db.execute(
                "INSERT OR IGNORE INTO entities (name, kind, notes)"
                " VALUES (?,?,?)", (name, kind, notes))
            row = self._db.execute("SELECT id FROM entities WHERE name = ?",
                                   (name,)).fetchone()
            eid = row["id"]
            for a in aliases or ():
                self._db.execute(
                    "INSERT OR IGNORE INTO entity_aliases (entity_id, alias)"
                    " VALUES (?,?)", (eid, a))
            self._db.commit()
            return eid

    # -- sessions ------------------------------------------------------
    def start_session(self):
        sid = uuid.uuid4().hex
        with self._lock:
            self._db.execute(
                "INSERT INTO sessions (id, started_at, message_count)"
                " VALUES (?,?,0)", (sid, _utcnow()))
            self._db.commit()
        return sid

    def record_turn(self, session_id, role, content):
        with self._lock:
            self._db.execute(
                "INSERT INTO turns (session_id, role, content, created_at)"
                " VALUES (?,?,?,?)",
                (session_id, role,
                 content if isinstance(content, str) else str(content),
                 _utcnow()))
            self._db.execute(
                "UPDATE sessions SET message_count = message_count + 1"
                " WHERE id = ?", (session_id,))
            self._db.commit()

    def list_sessions(self):
        with self._lock:
            return [dict(r) for r in self._db.execute(
                "SELECT * FROM sessions ORDER BY started_at DESC")]

    def end_session(self, session_id=None, summary=None):
        """Write the auto-summary (deterministic template, no model call)."""
        with self._lock:
            if session_id is None:
                row = self._db.execute(
                    "SELECT id FROM sessions WHERE ended_at IS NULL"
                    " ORDER BY started_at DESC LIMIT 1").fetchone()
                if row is None:
                    return None
                session_id = row["id"]
            s = self._db.execute("SELECT * FROM sessions WHERE id = ?",
                                 (session_id,)).fetchone()
            if s is None:
                return None
            ended = _utcnow()
            turns = self._db.execute(
                "SELECT role, content FROM turns WHERE session_id = ?"
                " ORDER BY id", (session_id,)).fetchall()
            first_user = next((t["content"] for t in turns
                               if t["role"] == "user"), "")
            mems = self._db.execute(
                "SELECT content FROM memories WHERE source_session = ?"
                " ORDER BY id", (session_id,)).fetchall()
            if summary is None:
                started_s = datetime.fromtimestamp(
                    s["started_at"], tz=timezone.utc).isoformat()
                ended_s = datetime.fromtimestamp(
                    ended, tz=timezone.utc).isoformat()
                preview = (first_user[:120] + "…") if len(first_user) > 120 \
                    else first_user
                mem_list = "; ".join(m["content"] for m in mems) or "none"
                summary = (
                    f"Session {session_id[:8]} · started {started_s}, "
                    f"ended {ended_s} · {len(turns)} turns "
                    f"({s['message_count']} recorded) · "
                    f"{len(mems)} memories stored.\n"
                    f"First user message: {preview or '(none)'}\n"
                    f"Memories this session: {mem_list}")
            self._db.execute(
                "UPDATE sessions SET ended_at = ?, summary = ? WHERE id = ?",
                (ended, summary, session_id))
            self._db.commit()
            return summary

    # -- reminders -----------------------------------------------------
    def create_reminder(self, text, fire_at):
        now = _utcnow()
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO reminders (text, fire_at, created_at)"
                " VALUES (?,?,?)", (text, float(fire_at), now))
            self._db.commit()
            return cur.lastrowid

    def due_reminders(self, now=None):
        now = _utcnow() if now is None else now
        with self._lock:
            return [dict(r) for r in self._db.execute(
                "SELECT * FROM reminders WHERE fired = 0 AND dismissed = 0"
                " AND fire_at <= ? ORDER BY fire_at", (now,))]

    def mark_reminder_fired(self, rid):
        with self._lock:
            self._db.execute("UPDATE reminders SET fired = 1 WHERE id = ?",
                             (rid,))
            self._db.commit()

    def dismiss_reminder(self, rid):
        with self._lock:
            cur = self._db.execute(
                "UPDATE reminders SET dismissed = 1 WHERE id = ? AND fired = 0",
                (rid,))
            self._db.commit()
            return cur.rowcount > 0

    def list_reminders(self):
        with self._lock:
            return [dict(r) for r in self._db.execute(
                "SELECT * FROM reminders ORDER BY fire_at")]
