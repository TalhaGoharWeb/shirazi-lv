"""Duplicate file finder (Shirazi LV plugin).

Another MYRA ULTRA quick-feature: point it at a folder (Downloads by
default) and it finds byte-identical copies eating disk space — size
pre-filter first, SHA-256 only for size collisions, so a big folder scans
fast. STRICTLY read-only: it reports, it never deletes. Deleting stays a
human decision (and Shirazi's organize tools exist for that).
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path

PLUGIN = {
    "name": "shirazi_duplicates",
    "description": (
        "Finds duplicate files in a folder — identical copies wasting disk space. "
        "Read-only: it only reports, never deletes. folder defaults to Downloads. "
        "Use for 'duplicate files dhoondo', 'disk space kahan ja raha hai', "
        "'ek jaisi files'. The reply names the biggest duplicate groups and how "
        "much space the extra copies take."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "folder": {
                "type": "STRING",
                "description": "Folder to scan (full path). Empty = Downloads.",
            },
            "min_size_kb": {
                "type": "INTEGER",
                "description": "Ignore files smaller than this many KB. Default 10.",
            },
        },
    },
}

PLUGIN_SETTINGS = None

_MAX_FILES = 30_000
_MAX_GROUPS_SPOKEN = 5


def _log(player, msg: str) -> None:
    if player:
        try:
            player.write_log(f"SHIRAZI: {msg}")
        except Exception:
            pass


def _fmt_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:,.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{n} B"


def _hash_file(p: Path) -> str | None:
    h = hashlib.sha256()
    try:
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def _scan(folder: Path, min_bytes: int) -> tuple[list, int, bool]:
    """Returns (groups, scanned_count, capped). A group = (size, [paths])."""
    by_size: dict[int, list[Path]] = defaultdict(list)
    scanned = 0
    capped = False
    for p in folder.rglob("*"):
        if scanned >= _MAX_FILES:
            capped = True
            break
        try:
            if not p.is_file() or p.is_symlink():
                continue
            size = p.stat().st_size
        except Exception:
            continue
        scanned += 1
        if size >= min_bytes:
            by_size[size].append(p)

    groups = []
    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        by_hash: dict[str, list[Path]] = defaultdict(list)
        for p in paths:
            digest = _hash_file(p)
            if digest:
                by_hash[digest].append(p)
        for same in by_hash.values():
            if len(same) >= 2:
                groups.append((size, same))
    groups.sort(key=lambda g: g[0] * (len(g[1]) - 1), reverse=True)
    return groups, scanned, capped


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Mark-LV plugin contract: never raise; return a spoken string."""
    try:
        params = dict(parameters or {})
        raw = str(params.get("folder") or "").strip()
        folder = Path(raw).expanduser() if raw else (Path.home() / "Downloads")
        try:
            min_kb = int(params.get("min_size_kb") or 10)
        except Exception:
            min_kb = 10
        if not folder.is_dir():
            return f"Folder nahi mila: {folder}. Sahi path bata dein."
        groups, scanned, capped = _scan(folder, max(0, min_kb) * 1024)
        if not groups:
            note = f" ({scanned} files dekhi)" if scanned else ""
            return (f"{folder.name} mein koi duplicate file nahi mili{note}. "
                    "Disk saaf hai is hisaab se.")
        wasted = sum(size * (len(paths) - 1) for size, paths in groups)
        extra = sum(len(paths) - 1 for _s, paths in groups)
        lines = [f"{folder.name} mein {len(groups)} duplicate "
                 f"group{'s' if len(groups) != 1 else ''} mile — "
                 f"{extra} extra copies, kul {_fmt_size(wasted)} zaya ho raha hai."]
        for size, paths in groups[:_MAX_GROUPS_SPOKEN]:
            lines.append(f"{paths[0].name} x{len(paths)} ({_fmt_size(size)} each)")
        if capped:
            lines.append(f"Scan {_MAX_FILES} files par rok diya tha — folder bohot bara hai.")
        lines.append("Main ne kuch delete nahi kiya — sirf report hai.")
        _log(player, "Duplicates: " + " | ".join(lines))
        return " ".join(lines)
    except Exception as e:
        return f"Duplicate scan failed: {e}"
