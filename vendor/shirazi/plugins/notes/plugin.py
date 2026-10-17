"""Notes plugin — save/search/list/delete short local notes.

Storage: <data_dir>/plugins_data/notes.json  (plain JSON, yours to keep).
Permissions used: files:write (creating/changing the JSON file).
"""

import json
import os
import time
from pathlib import Path


def _store_path():
    base = Path(os.environ.get("SHIRAZI_DATA_DIR",
                               str(Path.home() / ".shirazi")))
    d = base / "plugins_data"
    d.mkdir(parents=True, exist_ok=True)
    return d / "notes.json"


def _load():
    p = _store_path()
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return []


def _save(notes):
    _store_path().write_text(json.dumps(notes, ensure_ascii=False, indent=2),
                             encoding="utf-8")


def _fmt(note):
    ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(note["created"]))
    return f"[{note['id']}] {ts} — {note['text']}"


# The TOOL schema's "restore" takes no arguments, so the save handler records
# the id it created in a module global for the restore closure to use.
_last_saved_id = None


def _restore_last_save():
    global _last_saved_id
    if _last_saved_id is None:
        return
    _save([n for n in _load() if n["id"] != _last_saved_id])
    _last_saved_id = None


def run_save(args):
    global _last_saved_id
    text = str(args.get("text", "")).strip()
    if not text:
        return "Nothing to save — the note text was empty."
    notes = _load()
    nid = max([n["id"] for n in notes], default=0) + 1
    notes.append({"id": nid, "text": text[:2000], "created": time.time()})
    _save(notes)
    _last_saved_id = nid
    return f"Saved note [{nid}]: {text[:120]}"


def run_list(args):
    notes = _load()
    if not notes:
        return "No notes yet."
    notes = sorted(notes, key=lambda n: n["id"])[-20:]
    return "Notes:\n" + "\n".join(_fmt(n) for n in notes)


def run_search(args):
    q = str(args.get("q", "")).strip().lower()
    if not q:
        return "Give me something to search for."
    hits = [n for n in _load() if q in n["text"].lower()]
    if not hits:
        return f"No notes mention '{q}'."
    return f"Notes matching '{q}':\n" + "\n".join(_fmt(n) for n in hits)


def run_delete(args):
    try:
        nid = int(args.get("id", 0))
    except (TypeError, ValueError):
        return "Give me the note's [id] to delete."
    notes = _load()
    doomed = [n for n in notes if n["id"] == nid]
    if not doomed:
        return f"No note with id [{nid}]."
    _save([n for n in notes if n["id"] != nid])
    return f"Deleted note [{nid}]: {doomed[0]['text'][:120]}"


TOOLS = [
    {"name": "note_save",
     "description": "Save a short note for later. Say 'note this down' to use it.",
     "kind": "native", "access": "write",
     "parameters": {"type": "object",
                    "properties": {"text": {"type": "string",
                                           "description": "The note text."}},
                    "required": ["text"]},
     "run": run_save,
     "restore": _restore_last_save},
    {"name": "note_list",
     "description": "List saved notes (newest last, up to 20).",
     "kind": "native", "access": "read",
     "parameters": {"type": "object", "properties": {}},
     "run": run_list},
    {"name": "note_search",
     "description": "Search saved notes for a word or phrase.",
     "kind": "native", "access": "read",
     "parameters": {"type": "object",
                    "properties": {"q": {"type": "string",
                                        "description": "Search text."}},
                    "required": ["q"]},
     "run": run_search},
    {"name": "note_delete",
     "description": "Delete a saved note by its [id]. Asks for confirmation first.",
     "kind": "native", "access": "destructive",
     "parameters": {"type": "object",
                    "properties": {"id": {"type": "integer",
                                         "description": "The note id."}},
                    "required": ["id"]},
     "run": run_delete},
]
