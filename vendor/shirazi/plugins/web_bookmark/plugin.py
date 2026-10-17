"""Web-bookmark plugin — save/search/list/delete bookmarks.

Storage: <data_dir>/plugins_data/bookmarks.json (plain JSON).
Permissions used: files:write. URLs are validated with urllib.parse only —
parsing is not network access, so no `network` permission is needed.
"""

import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse


def _store_path():
    base = Path(os.environ.get("SHIRAZI_DATA_DIR",
                               str(Path.home() / ".shirazi")))
    d = base / "plugins_data"
    d.mkdir(parents=True, exist_ok=True)
    return d / "bookmarks.json"


def _load():
    p = _store_path()
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return []


def _save(marks):
    _store_path().write_text(json.dumps(marks, ensure_ascii=False, indent=2),
                             encoding="utf-8")


def _valid_url(url):
    try:
        parts = urlparse(url)
        return parts.scheme in ("http", "https") and bool(parts.netloc)
    except Exception:
        return False


def run_save(args):
    url = str(args.get("url", "")).strip()
    if not _valid_url(url):
        return "That doesn't look like a valid http(s) URL."
    title = str(args.get("title", "")).strip() or url
    marks = _load()
    if any(m["url"] == url for m in marks):
        return f"Already bookmarked: {title}"
    marks.append({"url": url, "title": title[:200],
                  "created": time.time()})
    _save(marks)
    return f"Bookmarked: {title}\n{url}"


def run_list(args):
    marks = _load()
    if not marks:
        return "No bookmarks yet."
    lines = [f"- {m['title']}\n  {m['url']}" for m in marks[-20:]]
    return "Bookmarks:\n" + "\n".join(lines)


def run_search(args):
    q = str(args.get("q", "")).strip().lower()
    if not q:
        return "Give me something to search for."
    hits = [m for m in _load()
            if q in m["title"].lower() or q in m["url"].lower()]
    if not hits:
        return f"No bookmarks mention '{q}'."
    lines = [f"- {m['title']}\n  {m['url']}" for m in hits]
    return f"Bookmarks matching '{q}':\n" + "\n".join(lines)


def run_delete(args):
    url = str(args.get("url", "")).strip()
    marks = _load()
    kept = [m for m in marks if m["url"] != url]
    if len(kept) == len(marks):
        return "No bookmark with that URL."
    _save(kept)
    return f"Deleted bookmark: {url}"


TOOLS = [
    {"name": "bookmark_save",
     "description": "Save a web bookmark (title + URL).",
     "kind": "native", "access": "write",
     "parameters": {"type": "object",
                    "properties": {
                        "url": {"type": "string",
                                "description": "The http(s) URL."},
                        "title": {"type": "string",
                                  "description": "Title (defaults to URL)."}},
                    "required": ["url"]},
     "run": run_save},
    {"name": "bookmark_list",
     "description": "List saved bookmarks.",
     "kind": "native", "access": "read",
     "parameters": {"type": "object", "properties": {}},
     "run": run_list},
    {"name": "bookmark_search",
     "description": "Search bookmarks by title or URL.",
     "kind": "native", "access": "read",
     "parameters": {"type": "object",
                    "properties": {"q": {"type": "string"}},
                    "required": ["q"]},
     "run": run_search},
    {"name": "bookmark_delete",
     "description": "Delete a bookmark by URL. Asks for confirmation first.",
     "kind": "native", "access": "destructive",
     "parameters": {"type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"]},
     "run": run_delete},
]
