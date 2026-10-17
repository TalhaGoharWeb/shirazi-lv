"""Clipboard plus plugin — read, write, and remember the clipboard.

Three tools:
- clipboard_get: current clipboard text (truncated to 2000 chars).
- clipboard_set: put text on the clipboard.
- clipboard_history: last 20 entries, auto-recorded on every get/set.

pyperclip is imported INSIDE the functions, never at module scope: plugin
discovery imports every plugin file on launch, and a clipboard library has
no business slowing down a boot where nobody touches the clipboard. If
pyperclip is missing (pip install pyperclip — it's in
requirements-plugins.txt), the tools say so plainly instead of crashing.

History lives in clipboard_history.json (last 20, consecutive duplicates
collapsed). Only text is stored.

Permissions used: clipboard (pyperclip), files:write (the history JSON).
"""

import json
import os
import time
from pathlib import Path

_MAX_TEXT = 2000
_MAX_HISTORY = 20


def _clip():
    """Import pyperclip lazily; return the module or None."""
    try:
        import pyperclip
        return pyperclip
    except ImportError:
        return None


def _history_path():
    base = Path(os.environ.get("SHIRAZI_DATA_DIR",
                               str(Path.home() / ".shirazi")))
    d = base / "plugins_data"
    d.mkdir(parents=True, exist_ok=True)
    return d / "clipboard_history.json"


def _load_history():
    p = _history_path()
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return []


def _save_history(entries):
    _history_path().write_text(
        json.dumps(entries[-_MAX_HISTORY:], ensure_ascii=False, indent=2),
        encoding="utf-8")


def _record(text: str):
    """Append to history; collapse consecutive duplicates."""
    text = str(text or "")
    if not text.strip():
        return
    entries = _load_history()
    if entries and entries[-1].get("text") == text:
        return
    entries.append({"text": text[:_MAX_TEXT], "at": time.time()})
    _save_history(entries)


def run_get(args):
    pc = _clip()
    if pc is None:
        return ("Clipboard access needs the pyperclip library — pip install "
                "pyperclip (it's in shirazi-core/requirements-plugins.txt).")
    try:
        text = pc.paste()
    except Exception as e:
        return f"Couldn't read the clipboard: {e}"
    if not str(text or "").strip():
        return "The clipboard is empty."
    _record(text)
    clipped = str(text)[:_MAX_TEXT]
    more = "" if len(str(text)) <= _MAX_TEXT else " (truncated to 2000 chars)"
    return f"Clipboard{more}:\n{clipped}"


def run_set(args):
    text = str(args.get("text") or "")
    if not text:
        return "Nothing to put on the clipboard — `text` was empty."
    pc = _clip()
    if pc is None:
        return ("Clipboard access needs the pyperclip library — pip install "
                "pyperclip (it's in shirazi-core/requirements-plugins.txt).")
    try:
        pc.copy(text)
    except Exception as e:
        return f"Couldn't write to the clipboard: {e}"
    _record(text)
    return f"Clipboard set ({len(text)} chars)."


def run_history(args):
    entries = _load_history()
    if not entries:
        return "Clipboard history is empty."
    lines = [f"Clipboard history — last {len(entries)}:"]
    for i, e in enumerate(reversed(entries), 1):
        ts = time.strftime("%m-%d %H:%M", time.localtime(e["at"]))
        preview = e["text"][:80].replace("\n", " ")
        lines.append(f"  {i}. [{ts}] {preview}")
    return "\n".join(lines)


TOOLS = [
    {"name": "clipboard_get",
     "description": (
         "Reads the current clipboard text (truncated to 2000 chars). Use "
         "when the user says 'clipboard mein kya hai', or before "
         "transforming text they just copied. Records to history."),
     "kind": "native", "access": "read",
     "parameters": {"type": "object", "properties": {}},
     "run": run_get},
    {"name": "clipboard_set",
     "description": (
         "Puts text on the clipboard. Use after generating/rewriting text "
         "the user wants to paste elsewhere — 'clipboard mein daal do'. "
         "Records to history."),
     "kind": "native", "access": "write",
     "parameters": {
         "type": "object",
         "properties": {
             "text": {"type": "string",
                      "description": "Text to put on the clipboard."}},
         "required": ["text"]},
     "run": run_set},
    {"name": "clipboard_history",
     "description": (
         "Shows the last 20 clipboard entries (auto-recorded on get/set, "
         "newest last). Use when the user lost something they copied — "
         "'wo text dobara dikhao jo maine copy kiya tha'."),
     "kind": "native", "access": "read",
     "parameters": {"type": "object", "properties": {}},
     "run": run_history},
]
