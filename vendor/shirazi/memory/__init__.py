"""memory package — long-term memory for Shirazi (Phase 3).

normalize.py  Urdu/Arabic-script normalization (write + query time)
schema.py     SQLite DDL (sessions, turns, memories, entities, reminders, FTS5)
secrets.py    redact-before-write
store.py      MemoryStore: remember / recall / forget / export / backup / sessions
extract.py    rule-based fact extraction (no model calls)
"""

from .normalize import normalize  # noqa: F401
from .schema import ensure_schema  # noqa: F401
from .secrets import redact  # noqa: F401
from .store import MemoryStore  # noqa: F401
