"""
Phase 3.4 — Workspace assistant: searchable workspace.

Searches files across the OMNICONTROL allow-listed folders by filename and
by content. Security: ONLY folders in the allow-list are searched
(policy.check_path); sensitive children never inherit; binary files are
skipped for content search; results are capped.
"""
from __future__ import annotations

import fnmatch
import os
from pathlib import Path

PLUGIN = {
    "name": "shirazi_workspace_search",
    "description": (
        "Search the user's approved workspace folders for files. "
        "Find by filename (glob pattern) or by text inside files. "
        "Only searches folders the user allow-listed in the Permission Center. "
        "Use when the user asks 'where is…', 'find the file…', or wants to "
        "locate something in their workspace."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": "Filename glob (e.g. '*.pdf', 'report*') or text to find inside files.",
            },
            "mode": {
                "type": "STRING",
                "enum": ["filename", "content", "both"],
                "description": "Search filenames, file contents, or both. Default: both.",
            },
            "max_results": {
                "type": "STRING",
                "description": "Max results (default 20, max 50).",
            },
        },
        "required": ["query"],
    },
}

PLUGIN_SETTINGS = None

_TEXT_EXTS = frozenset({
    ".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml", ".toml",
    ".cfg", ".ini", ".csv", ".html", ".htm", ".css", ".xml", ".log",
    ".rst", ".tex", ".sh", ".bat", ".ps1", ".sql", ".java", ".c", ".h",
    ".cpp", ".go", ".rs", ".rb", ".php",
})
_MAX_FILE_BYTES = 2 * 1024 * 1024  # skip files larger than 2MB for content


def _search_roots() -> list[Path]:
    """Allow-listed folders with read permission."""
    from core.omnicontrol import db, policy
    conn = db.connect()
    rows = conn.execute(
        "SELECT path FROM folders WHERE can_read=1").fetchall()
    roots = []
    for r in rows:
        p = Path(r["path"])
        if p.is_dir():
            # check_path enforces canonicalization + sensitive-child rules
            ok, _ = policy.check_path(str(p), "read")
            if ok:
                roots.append(p)
    return roots


def _is_text(path: Path) -> bool:
    if path.suffix.lower() in _TEXT_EXTS:
        return True
    # Heuristic for extensionless text files: read a chunk, check for NUL.
    try:
        if path.stat().st_size > _MAX_FILE_BYTES:
            return False
        with open(path, "rb") as f:
            chunk = f.read(8192)
        return b"\x00" not in chunk
    except OSError:
        return False


def _search_filename(roots: list[Path], pattern: str, limit: int) -> list[str]:
    hits = []
    for root in roots:
        try:
            for dirpath, _dirnames, filenames in os.walk(root):
                for fn in filenames:
                    if fnmatch.fnmatch(fn.lower(), pattern.lower()):
                        hits.append(str(Path(dirpath) / fn))
                        if len(hits) >= limit:
                            return hits
        except OSError:
            continue
    return hits


def _search_content(roots: list[Path], needle: str, limit: int) -> list[str]:
    hits = []
    needle_l = needle.lower()
    for root in roots:
        try:
            for dirpath, _dirnames, filenames in os.walk(root):
                for fn in filenames:
                    fp = Path(dirpath) / fn
                    if not _is_text(fp):
                        continue
                    try:
                        text = fp.read_text(encoding="utf-8", errors="replace")
                    except OSError:
                        continue
                    if needle_l in text.lower():
                        # First matching line as context
                        for line in text.splitlines():
                            if needle_l in line.lower():
                                hits.append(f"{fp}: {line.strip()[:120]}")
                                break
                        if len(hits) >= limit:
                            return hits
        except OSError:
            continue
    return hits


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Mark-LV plugin contract: never raise; return a spoken string."""
    try:
        params = dict(parameters or {})
        query = (params.get("query") or "").strip()
        if not query:
            return "Kya dhoondna hai? Koi naam ya lafz batayen."
        mode = (params.get("mode") or "both").strip().lower()
        try:
            limit = min(50, max(1, int(params.get("max_results") or 20)))
        except (TypeError, ValueError):
            limit = 20

        roots = _search_roots()
        if not roots:
            return ("Workspace mein koi folder allow-listed nahi hai. "
                    "Permission Center (dashboard 🛡) mein folders add karen.")

        out: list[str] = []
        if mode in ("filename", "both"):
            # If the query looks like text (has spaces), also try it as a
            # substring of filenames.
            pattern = query if ("*" in query or "?" in query) else f"*{query}*"
            hits = _search_filename(roots, pattern, limit)
            if hits:
                out.append("Naam se mile:")
                out.extend(f"  • {h}" for h in hits)
        if mode in ("content", "both") and len(out) < limit + 1:
            hits = _search_content(roots, query, limit)
            if hits:
                out.append("Maujud (andar likha mila):")
                out.extend(f"  • {h}" for h in hits[:limit])

        if not out:
            return f"'{query}' workspace mein nahi mila."
        return "\n".join(out[: 2 * limit + 2])
    except Exception as e:
        return f"Search mein masla hua: {e}"
