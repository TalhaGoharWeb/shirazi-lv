"""SQLite schema for Shirazi long-term memory (Phase 3).

Tables:
    sessions        chat sessions (boot -> shutdown)
    turns           individual user/assistant messages per session
    memories        long-term facts (content = RAW redacted text; norm = normalized)
    entities        named things the user mentions
    entity_aliases  alternate names -> entity
    reminders       scheduled nudges (fire_at = unix epoch)

FTS:
    memories_fts     trigram tokenizer, diacritics-stripped (Urdu-tuned),
                     external-content on memories (indexes `norm`)
    memories_fts_en  unicode61 tokenizer, diacritics-stripped (English),
                     external-content on memories (indexes `norm`)

Both FTS tables index the NORMALIZED text; the raw redacted text stays in
memories.content. INSERT/UPDATE/DELETE triggers keep both in sync.
"""

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id           TEXT PRIMARY KEY,
    started_at   REAL NOT NULL,
    ended_at     REAL,
    summary      TEXT,
    message_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS turns (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id);

CREATE TABLE IF NOT EXISTS memories (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    content        TEXT NOT NULL,
    norm           TEXT NOT NULL,
    kind           TEXT NOT NULL DEFAULT 'fact',
    created_at     REAL NOT NULL,
    updated_at     REAL NOT NULL,
    source_session TEXT
);
CREATE INDEX IF NOT EXISTS idx_memories_kind ON memories(kind);
CREATE INDEX IF NOT EXISTS idx_memories_norm ON memories(norm);

CREATE TABLE IF NOT EXISTS entities (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT NOT NULL UNIQUE,
    kind  TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS entity_aliases (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER NOT NULL,
    alias     TEXT NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_aliases_entity ON entity_aliases(entity_id);

CREATE TABLE IF NOT EXISTS reminders (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    text       TEXT NOT NULL,
    fire_at    REAL NOT NULL,
    created_at REAL NOT NULL,
    fired      INTEGER NOT NULL DEFAULT 0,
    dismissed  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_reminders_due ON reminders(fired, dismissed, fire_at);

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    norm, content='memories', content_rowid='id',
    tokenize='trigram remove_diacritics 1');

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts_en USING fts5(
    norm, content='memories', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2');

CREATE TRIGGER IF NOT EXISTS memories_fts_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, norm) VALUES (new.id, new.norm);
    INSERT INTO memories_fts_en(rowid, norm) VALUES (new.id, new.norm);
END;

CREATE TRIGGER IF NOT EXISTS memories_fts_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, norm)
        VALUES ('delete', old.id, old.norm);
    INSERT INTO memories_fts_en(memories_fts_en, rowid, norm)
        VALUES ('delete', old.id, old.norm);
END;

CREATE TRIGGER IF NOT EXISTS memories_fts_au AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, norm)
        VALUES ('delete', old.id, old.norm);
    INSERT INTO memories_fts_en(memories_fts_en, rowid, norm)
        VALUES ('delete', old.id, old.norm);
    INSERT INTO memories_fts(rowid, norm) VALUES (new.id, new.norm);
    INSERT INTO memories_fts_en(rowid, norm) VALUES (new.id, new.norm);
END;
"""


def ensure_schema(db):
    """Create all tables/triggers if missing. Idempotent."""
    db.executescript(_SCHEMA)
    db.commit()
