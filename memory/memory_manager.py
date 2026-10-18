import json
import re
from datetime import datetime
from threading import Lock
from pathlib import Path
import sys


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR         = get_base_dir()
MEMORY_PATH      = BASE_DIR / "memory" / "long_term.json"
_lock            = Lock()
MAX_VALUE_LENGTH = 380

# ── Why there are two very different numbers here ────────────────────────────
#
# There used to be one: MEMORY_MAX_CHARS = 2200, applied to the whole store. It
# was a *storage* limit, and it existed only because the entire memory was
# pasted into the system prompt on every connect — so growing the memory grew
# every single request. When it filled, _trim_to_limit() deleted the oldest
# entries and printed one line to a console nobody reads. A memory described as
# "deeply remembers projects, preferences and personal context" was in practice
# two pages long, and quietly forgot your sister's name after a few weeks.
#
# Storage and prompt budget are now separate concerns:
#
#   MEMORY_MAX_CHARS  — a runaway guard, not a feature limit. Nothing normal
#                       reaches it; a bug writing in a loop does.
#   PROMPT_CORE_CHARS — what actually rides in the system prompt every session.
#                       Smaller than the old whole-memory dump, so sessions
#                       start *faster* than before, not slower.
#
# Everything above the core stays on disk and is fetched on demand by the
# recall_memory tool — see search_memory() and format_memory_for_prompt().
MEMORY_MAX_CHARS  = 200_000
PROMPT_CORE_CHARS = 900
PROMPT_INDEX_CHARS = 420
# Most entries any one category may contribute to the core block, so a person
# with forty stored preferences still gets their sister into the prompt.
PROMPT_MAX_PER_CATEGORY = 6

def _empty_memory() -> dict:
    return {
        "identity":      {},
        "preferences":   {},
        "projects":      {},
        "relationships": {},
        "wishes":        {},
        "notes":         {},
    }

def load_memory() -> dict:
    if not MEMORY_PATH.exists():
        return _empty_memory()
    with _lock:
        try:
            data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                base = _empty_memory()
                for key in base:
                    if key not in data:
                        data[key] = {}
                return data
            return _empty_memory()
        except Exception as e:
            print(f"[Memory] ⚠️ Load error: {e}")
            return _empty_memory()

def _all_entries(memory: dict) -> list[tuple]:
    entries = []
    for cat, items in memory.items():
        if not isinstance(items, dict):
            continue
        for key, entry in items.items():
            if isinstance(entry, dict) and "value" in entry:
                entries.append((cat, key, entry))
    return entries


# Set by main.py so a trim can reach the activity log. Deleting something a
# person told you and mentioning it only on stdout is how a memory loses trust.
_trim_notifier = None


def set_trim_notifier(fn) -> None:
    """Register a callable(str) that surfaces trims to the user."""
    global _trim_notifier
    _trim_notifier = fn


def _trim_to_limit(memory: dict) -> dict:
    if len(json.dumps(memory, ensure_ascii=False)) <= MEMORY_MAX_CHARS:
        return memory
    entries = _all_entries(memory)
    entries.sort(key=lambda t: t[2].get("updated", "0000-00-00"))
    dropped = []
    for cat, key, _ in entries:
        if len(json.dumps(memory, ensure_ascii=False)) <= MEMORY_MAX_CHARS:
            break
        del memory[cat][key]
        dropped.append(f"{cat}/{key}")
        print(f"[Memory] 🗑️  Trimmed {cat}/{key}")
    if dropped and _trim_notifier:
        try:
            _trim_notifier(
                f"SYS: Memory full — forgot {len(dropped)} oldest entries "
                f"({', '.join(dropped[:3])}{'…' if len(dropped) > 3 else ''})"
            )
        except Exception:
            pass
    return memory

def save_memory(memory: dict) -> None:
    if not isinstance(memory, dict):
        return
    memory = _trim_to_limit(memory)
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        MEMORY_PATH.write_text(
            json.dumps(memory, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def _truncate_value(val: str) -> str:
    if isinstance(val, str) and len(val) > MAX_VALUE_LENGTH:
        return val[:MAX_VALUE_LENGTH].rstrip() + "…"
    return val


def _recursive_update(target: dict, updates: dict) -> bool:
    changed = False
    for key, value in updates.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, dict) and "value" not in value:
            if key not in target or not isinstance(target[key], dict):
                target[key] = {}
                changed = True
            if _recursive_update(target[key], value):
                changed = True
        else:
            new_val  = _truncate_value(str(value["value"] if isinstance(value, dict) else value))
            existing = target.get(key, {})
            # Personal Companion: preserve provenance across updates.
            entry = {"value": new_val,
                     "updated": datetime.now().strftime("%Y-%m-%d")}
            if isinstance(existing, dict):
                for f in ("created", "source", "origin"):
                    if existing.get(f):
                        entry[f] = existing[f]
            if isinstance(value, dict):
                for f in ("source", "origin"):
                    if value.get(f):
                        entry[f] = value[f]
            entry.setdefault("created", entry["updated"])
            if not isinstance(existing, dict) or existing.get("value") != new_val:
                target[key] = entry
                changed = True
    return changed


def update_memory(memory_update: dict) -> dict:
    if not isinstance(memory_update, dict) or not memory_update:
        return load_memory()
    memory = load_memory()
    if _recursive_update(memory, memory_update):
        save_memory(memory)
        print(f"[Memory] 💾 Saved: {list(memory_update.keys())}")
    return memory

def _entry_value(entry) -> str:
    """Accept both the {'value': ..., 'updated': ...} shape and a bare string,
    because early versions of the store wrote plain strings."""
    if isinstance(entry, dict):
        return str(entry.get("value", "") or "").strip()
    return str(entry or "").strip()


def _pretty(key: str) -> str:
    return key.replace("_", " ").strip()


# Identity is always in the prompt; these categories compete for the remaining
# budget by recency.
_CATEGORY_LABELS = {
    "preferences":   "Preferences",
    "projects":      "Active projects / goals",
    "relationships": "People in their life",
    "wishes":        "Wishes / plans",
    "notes":         "Notes",
}

_IDENTITY_FIELDS = ["name", "age", "birthday", "city", "job",
                    "language", "school", "nationality"]


def format_memory_for_prompt(memory: dict | None) -> str:
    """Build the memory block that goes into the system prompt.

    This used to dump everything. It now sends three things:

      1. IDENTITY  - always, in full. It is small, and it is wrong for the
         assistant to have to look up your name.
      2. RECENT    - the most recently updated entries from every other
         category, up to PROMPT_CORE_CHARS. Recency is the cheapest useful
         relevance signal available without embeddings.
      3. AN INDEX  - the *keys* of everything else, values omitted.

    Point 3 is what makes recall work at all. A model cannot decide to look
    something up if it does not know the thing exists: with only points 1 and 2,
    "who is Ayse?" would get "I don't know" while ayse_sister sat on disk
    unread. The index costs a few hundred characters and turns recall from a
    gamble into a lookup.

    Net effect on latency: this block is SMALLER than the old full dump, so
    every session connects with fewer tokens. Occasionally the model spends one
    extra round trip on recall_memory - covered by the acknowledgment it
    already speaks before any slow step."""
    if not memory:
        return ""

    core_lines: list[str] = []

    # 1. Identity - always, in full
    identity = memory.get("identity", {}) or {}
    for field in _IDENTITY_FIELDS:
        val = _entry_value(identity.get(field))
        if not val:
            continue
        if field == "language":
            # Labelled as an observation, not a setting. A bare "Language:
            # English" line written months ago reads like a standing order and
            # was one of the reasons a Turkish question came back in English.
            core_lines.append(
                f"Has spoken to you in: {val} (an observation about the past — "
                f"always answer in the language of their CURRENT message)")
        else:
            core_lines.append(f"{field.title()}: {val}")
    for key, entry in identity.items():
        if key in _IDENTITY_FIELDS:
            continue
        val = _entry_value(entry)
        if val:
            core_lines.append(f"{_pretty(key).title()}: {val}")

    # 2. Everything else, most recently updated first
    rest: list[tuple[str, str, str, str]] = []   # (updated, cat, key, value)
    for cat in _CATEGORY_LABELS:
        for key, entry in (memory.get(cat, {}) or {}).items():
            val = _entry_value(entry)
            if not val:
                continue
            updated = (entry.get("updated", "") if isinstance(entry, dict) else "") or "0000-00-00"
            rest.append((updated, cat, key, val))
    rest.sort(key=lambda t: t[0], reverse=True)

    used    = sum(len(l) + 1 for l in core_lines)
    shown: dict[str, list[str]] = {}
    overflow: dict[str, list[str]] = {}

    # Recency decides order, but no single category may take the whole budget.
    # Without the cap, someone with forty stored preferences gets a prompt that
    # is forty preferences and not one person's name — the categories that
    # matter most in conversation are also the ones that change least often, so
    # pure recency systematically buries them.
    per_cat_used: dict[str, int] = {}
    for _updated, cat, key, val in rest:
        line = f"  - {_pretty(key).title()}: {val}"
        if (per_cat_used.get(cat, 0) < PROMPT_MAX_PER_CATEGORY
                and used + len(line) + 1 <= PROMPT_CORE_CHARS):
            shown.setdefault(cat, []).append(line)
            per_cat_used[cat] = per_cat_used.get(cat, 0) + 1
            used += len(line) + 1
        else:
            overflow.setdefault(cat, []).append(_pretty(key))

    # The index is a table of contents, so it is interleaved across categories
    # rather than continuing in recency order. Sorted by recency it would list
    # twenty-four preferences before the first relationship, and the one entry
    # the index exists for — the old fact the model has no other way to know
    # about — would fall off the end.
    indexed: list[str] = []
    if overflow:
        cats  = [c for c in _CATEGORY_LABELS if overflow.get(c)]
        cursor = {c: 0 for c in cats}
        while cats:
            for cat in list(cats):
                i = cursor[cat]
                if i >= len(overflow[cat]):
                    cats.remove(cat)
                    continue
                indexed.append(overflow[cat][i])
                cursor[cat] = i + 1

    for cat, label in _CATEGORY_LABELS.items():
        if shown.get(cat):
            core_lines.append("")
            core_lines.append(f"{label}:")
            core_lines.extend(shown[cat])

    if not core_lines and not indexed:
        return ""

    out = [
        "[WHAT YOU KNOW ABOUT THIS PERSON — use naturally, never recite like a list]",
        *core_lines,
    ]

    # 3. The index of what is on disk but not in this prompt
    if indexed:
        budget, names = PROMPT_INDEX_CHARS, []
        for n in indexed:
            if budget - len(n) - 2 < 0:
                break
            names.append(n)
            budget -= len(n) + 2
        if names:
            out.append("")
            out.append(
                "[ALSO REMEMBERED — values not shown here. Call recall_memory "
                "with a keyword to read any of these before saying you do not know]"
            )
            out.append(", ".join(names)
                       + (f" (+{len(indexed) - len(names)} more)"
                          if len(indexed) > len(names) else ""))

    return "\n".join(out) + "\n"


# ── Recall ────────────────────────────────────────────────────────────────────

def _score(query_words: list[str], cat: str, key: str, value: str) -> int:
    """Cheap lexical relevance. No embeddings, no network, no model call - this
    runs in well under a millisecond, which is the entire point: recall must
    cost one model round trip, never two."""
    hay_key = _pretty(key).lower()
    hay_val = value.lower()
    score   = 0
    for w in query_words:
        if not w:
            continue
        if w == hay_key:
            score += 10
        elif w in hay_key:
            score += 6
        if w in hay_val:
            score += 3
        if w in cat:
            score += 1
    return score


def search_memory(query: str, limit: int = 8) -> str:
    """Find stored facts matching `query`. Backs the recall_memory tool.

    An empty query is treated as "show me everything you know", capped - the
    model asks that when the user says "what do you remember about me?"."""
    memory = load_memory()
    words  = [w for w in re.split(r"[^\w]+", (query or "").lower()) if len(w) > 1]

    rows: list[tuple[int, str, str, str]] = []
    for cat, items in memory.items():
        if not isinstance(items, dict):
            continue                     # skip 'sessions', which is a list
        for key, entry in items.items():
            val = _entry_value(entry)
            if not val:
                continue
            s = _score(words, cat, key, val) if words else 1
            if s > 0:
                rows.append((s, cat, key, val))

    rows.sort(key=lambda r: (-r[0], r[2]))
    lines = [f"{cat}/{_pretty(key)}: {val}" for _s, cat, key, val in rows[:max(1, limit)]]
    head  = (f"Stored facts matching '{query}':" if query
             else "Everything currently stored:")
    more  = (f"\n(+{len(rows) - len(lines)} more — search with a narrower keyword)"
             if len(rows) > len(lines) else "")
    out = head + "\n" + "\n".join(lines) + more if lines else ""
    # Shirazi-origin: episodic recall (past conversation turns, BM25-ranked).
    # Merged with profile hits; never raises into the caller.
    try:
        from memory import shirazi_backend as _sb
        epi = _sb.recall_episodic(query or "", k=max(2, limit // 2))
    except Exception:
        epi = []
    if epi:
        epi_lines = "\n".join(f"- {e[:300]}" for e in epi)
        epi_head = "\n\nFrom past conversations:"
        out = (out + epi_head + "\n" + epi_lines) if out else ("Past conversations:" + "\n" + epi_lines)
    if not out:
        return (f"Nothing stored about '{query}'." if query
                else "I have not stored anything about this person yet.")
    return out


def all_entries_for_ui() -> list[dict]:
    """Flat list for the memory panel: what SHIRAZI knows, and when it learned it.
    Sorted newest first so the panel opens on what changed most recently."""
    memory = load_memory()
    rows = []
    for cat, items in memory.items():
        if not isinstance(items, dict):
            continue
        for key, entry in items.items():
            val = _entry_value(entry)
            if not val:
                continue
            rows.append({
                "category": cat,
                "key":      key,
                "value":    val,
                "updated":  (entry.get("updated", "") if isinstance(entry, dict) else ""),
            })
    rows.sort(key=lambda r: (r["updated"] or "0000-00-00"), reverse=True)
    return rows

def remember(key: str, value: str, category: str = "notes") -> str:
    valid = {"identity", "preferences", "projects", "relationships", "wishes", "notes"}
    if category not in valid:
        category = "notes"
    update_memory({category: {key: {"value": value}}})
    return f"Remembered: {category}/{key} = {value}"


def forget(key: str, category: str = "notes") -> str:
    memory = load_memory()
    cat    = memory.get(category, {})
    if key in cat:
        del cat[key]
        memory[category] = cat
        save_memory(memory)
        return f"Forgotten: {category}/{key}"
    return f"Not found: {category}/{key}"


forget_memory = forget


# ── Session memory ─────────────────────────────────────────────────────────────

_SESSION_MAX = 3   # safety cap — in practice 0-1 entries after pop


def save_session_summary(summary: str, language: str = "") -> None:
    """Append a 1-2 sentence session summary to long_term.json['sessions']."""
    summary = (summary or "").strip()
    if not summary:
        return
    memory   = load_memory()
    sessions = memory.get("sessions", [])
    if not isinstance(sessions, list):
        sessions = []
    entry: dict = {
        "date":    datetime.now().strftime("%Y-%m-%d"),
        "summary": summary[:280],
    }
    if language:
        entry["language"] = language
    sessions.append(entry)
    memory["sessions"] = sessions[-_SESSION_MAX:]
    with _lock:
        MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        MEMORY_PATH.write_text(
            json.dumps(memory, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    print(f"[Memory] 📝 Session saved ({entry['date']}): {summary[:60]}…")


def pop_last_session() -> dict | None:
    """
    Return AND remove the most recent session entry.
    Calling this consumes the entry so it is never repeated in future briefings.
    """
    with _lock:
        if not MEMORY_PATH.exists():
            return None
        try:
            memory   = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
            sessions = memory.get("sessions", [])
            if not isinstance(sessions, list) or not sessions:
                return None
            entry = sessions.pop()          # remove the last entry
            memory["sessions"] = sessions
            MEMORY_PATH.write_text(
                json.dumps(memory, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return entry
        except Exception as e:
            print(f"[Memory] ⚠️ pop_last_session error: {e}")
            return None

# ── Personal Companion: provenance, dedup, and Memory Center support ──
# Entries gain: created (ISO), source (user_explicit | inferred | onboarding |
# import | legacy), origin (free-text detail). Old entries without these
# fields are treated as source="legacy".

_VALID_SOURCES = {"user_explicit", "inferred", "onboarding", "import",
                  "legacy", "system"}


def _stamp_entry(entry: dict, source: str = "legacy") -> dict:
    """Ensure an entry dict has provenance fields. Never raises."""
    try:
        if not isinstance(entry, dict):
            entry = {"value": entry}
        now = datetime.now().isoformat(timespec="seconds")
        entry.setdefault("created", entry.get("updated", now))
        if entry.get("source") not in _VALID_SOURCES:
            entry["source"] = source if source in _VALID_SOURCES else "legacy"
        entry.setdefault("origin", "")
        return entry
    except Exception:
        return {"value": str(entry), "created": "", "source": "legacy",
                "origin": ""}


def remember_explicit(key: str, value: str, category: str = "notes",
                      origin: str = "") -> str:
    """Remember something the user explicitly asked to store.

    Refuses to store anything that looks like a secret.
    Returns a human-readable result string.
    """
    if _looks_like_secret(key, value):
        return ("Not stored: that looks like a password, API key, or token. "
                "Secrets are never kept in ordinary memory.")
    valid = {"identity", "preferences", "projects", "relationships",
             "wishes", "notes"}
    if category not in valid:
        category = "notes"
    dup = find_similar(value, category)
    if dup:
        return (f"Already remembered as {dup['category']}/{dup['key']}: "
                f"\"{dup['value'][:80]}\" — not duplicated.")
    update_memory({category: {key: {
        "value": value,
        "source": "user_explicit",
        "origin": origin[:200],
    }}})
    return f"Remembered: {category}/{key}"


def _looks_like_secret(key: str, value: str) -> bool:
    text = f"{key} {value}".lower()
    patterns = ("api_key", "apikey", "password", "passwd", "secret",
                "token", "bearer", "private_key", "privatekey",
                "client_secret", "auth_key")
    if any(p in text for p in patterns):
        return True
    v = str(value).strip()
    # Long opaque strings are key-shaped.
    if len(v) >= 24 and re.fullmatch(r"[A-Za-z0-9_\-]{24,}", v):
        return True
    return False


def find_similar(value: str, category: str = "notes",
                 threshold: float = 0.55) -> dict | None:
    """Duplicate detection via word-overlap. Returns the best match or None."""
    words = set(re.findall(r"\w+", str(value).lower()))
    words = {w for w in words if len(w) > 2}
    if not words:
        return None
    memory = load_memory()
    best, best_score = None, 0.0
    for key, entry in memory.get(category, {}).items():
        ev = _entry_value(entry)
        ewords = {w for w in re.findall(r"\w+", ev.lower()) if len(w) > 2}
        if not ewords:
            continue
        score = len(words & ewords) / max(len(words), len(ewords))
        if score > best_score:
            best, best_score = {"category": category, "key": key,
                                "value": ev}, score
    return best if best_score >= threshold else None


def edit_entry(key: str, value: str, category: str = "notes") -> str:
    """Correct a remembered fact. Keeps provenance; bumps updated."""
    memory = load_memory()
    cat = memory.get(category, {})
    if key not in cat:
        return f"Not found: {category}/{key}"
    entry = _stamp_entry(cat[key])
    entry["value"] = value
    entry["updated"] = datetime.now().isoformat(timespec="seconds")
    entry["origin"] = (entry.get("origin", "") + " [corrected by user]").strip()[:200]
    cat[key] = entry
    memory[category] = cat
    save_memory(memory)
    return f"Updated: {category}/{key}"


def search_entries(query: str, category: str | None = None,
                   limit: int = 20) -> list[dict]:
    """Search entries by keyword, optionally filtered to a category."""
    qwords = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 2]
    memory = load_memory()
    rows = []
    for cat, items in memory.items():
        if not isinstance(items, dict):
            continue
        if category and cat != category:
            continue
        for key, entry in items.items():
            entry = _stamp_entry(entry)
            val = _entry_value(entry)
            hay = f"{key} {val}".lower()
            score = sum(1 for w in qwords if w in hay)
            if score or not qwords:
                rows.append({
                    "category": cat, "key": key, "value": val,
                    "source": entry.get("source", "legacy"),
                    "origin": entry.get("origin", ""),
                    "created": entry.get("created", ""),
                    "updated": entry.get("updated", ""),
                    "score": score,
                })
    rows.sort(key=lambda r: (-r["score"], r["updated"] or ""), reverse=False)
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows[:limit]


def entries_by_category() -> dict[str, list[dict]]:
    """All entries grouped by category, newest first. For the Memory Center."""
    memory = load_memory()
    out: dict[str, list[dict]] = {}
    for cat, items in memory.items():
        if not isinstance(items, dict):
            continue
        rows = []
        for key, entry in items.items():
            entry = _stamp_entry(entry)
            rows.append({
                "category": cat, "key": key, "value": _entry_value(entry),
                "source": entry.get("source", "legacy"),
                "origin": entry.get("origin", ""),
                "created": entry.get("created", ""),
                "updated": entry.get("updated", ""),
            })
        rows.sort(key=lambda r: r["updated"] or "", reverse=True)
        out[cat] = rows
    return out


def delete_category(category: str) -> int:
    """Delete every entry in a category. Returns the count removed."""
    memory = load_memory()
    items = memory.get(category, {})
    n = len(items) if isinstance(items, dict) else 0
    memory[category] = {}
    save_memory(memory)
    return n


def memory_change_history(limit: int = 30) -> list[dict]:
    """Recent memory changes, newest first (for the Memory Center)."""
    rows = []
    for cat_rows in entries_by_category().values():
        rows.extend(cat_rows)
    rows.sort(key=lambda r: r["updated"] or "", reverse=True)
    return rows[:limit]
