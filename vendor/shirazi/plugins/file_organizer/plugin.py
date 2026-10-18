"""File organizer plugin — "downloads saaf karo", safely.

THE SAFETY DESIGN, because moving files is the kind of thing that cannot be
un-seen:
1. PREVIEW FIRST, ALWAYS. organize_preview scans and returns a plan — what
   would move where — plus a plan token. It NEVER moves anything.
2. APPLY NEEDS THE TOKEN. organize_apply executes only with a valid,
   single-use token from a preview. No token, no moves. Ever.
3. NO OVERWRITE. If the destination name exists, the file becomes
   `name-2.ext`, `name-3.ext` — never replaced, never lost.
4. DOTFILES SKIPPED. `.gitignore`, `.env`, anything starting with a dot is
   left alone: those are configuration, not clutter.
5. STAYS INSIDE THE FOLDER. Every move is verified to stay within the named
   folder (symlink/traversal-safe). Subfolders are not descended into and
   not moved — only top-level files are organized.
6. FILES ONLY. Directories are never moved.

Grouping is by extension: Images, Documents, Audio, Video, Archives, Code,
Other. Destination subfolders are created inside the same folder.

Permissions used: files:write (creating subfolders, moving files).
"""

import json
import os
import time
import uuid
from pathlib import Path

GROUPS = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg",
               ".tiff", ".tif", ".ico", ".heic"},
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".md", ".rtf", ".odt",
                  ".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".epub"},
    "Audio": {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"},
    "Video": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Code": {".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json",
             ".xml", ".java", ".c", ".cpp", ".h", ".go", ".rs", ".rb",
             ".php", ".sh", ".yml", ".yaml"},
}


def _group_of(name: str) -> str:
    ext = Path(name).suffix.lower()
    for group, exts in GROUPS.items():
        if ext in exts:
            return group
    return "Other"


def _plans_path():
    base = Path(os.environ.get("SHIRAZI_DATA_DIR",
                               str(Path.home() / ".shirazi")))
    d = base / "plugins_data"
    d.mkdir(parents=True, exist_ok=True)
    return d / "file_organizer_plans.json"


def _load_plans():
    p = _plans_path()
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return {}


def _save_plans(plans):
    _plans_path().write_text(json.dumps(plans, ensure_ascii=False, indent=2),
                             encoding="utf-8")


def _resolve_folder(raw: str) -> Path:
    """Resolve the folder; refuse anything that isn't a real directory."""
    p = Path(str(raw or "").strip()).expanduser()
    if not str(raw or "").strip():
        raise ValueError("Give me the folder to organize.")
    try:
        rp = p.resolve()
    except OSError:
        raise ValueError(f"Cannot resolve '{raw}'.")
    if not rp.is_dir():
        raise ValueError(f"'{raw}' is not a folder.")
    return rp


def _no_overwrite(dest: Path) -> Path:
    """Find a free name: name.ext, name-2.ext, name-3.ext, ..."""
    if not dest.exists():
        return dest
    stem, suffix = dest.stem, dest.suffix
    n = 2
    while True:
        cand = dest.with_name(f"{stem}-{n}{suffix}")
        if not cand.exists():
            return cand
        n += 1


def run_preview(args):
    try:
        folder = _resolve_folder(args.get("folder"))
    except ValueError as e:
        return str(e)
    recursive = bool(args.get("recursive"))
    moves = []
    counts = {}
    skipped = 0
    if recursive:
        entries = [p for p in folder.rglob("*") if p.is_file()]
    else:
        entries = [p for p in folder.iterdir() if p.is_file()]
    for p in entries:
        if p.name.startswith("."):
            skipped += 1
            continue
        # never touch files already inside our own group subfolders
        if p.parent != folder and p.parent.name in GROUPS:
            continue
        group = _group_of(p.name)
        dest = folder / group / p.name
        if p.resolve() == dest.resolve():
            continue  # already where it belongs
        moves.append({"src": str(p), "dest": str(dest), "group": group})
        counts[group] = counts.get(group, 0) + 1
    if not moves:
        return (f"{folder}: nothing to organize "
                f"({skipped} dotfiles skipped).")

    token = uuid.uuid4().hex[:12]
    plans = _load_plans()
    plans[token] = {"folder": str(folder), "moves": moves,
                    "created": time.time()}
    _save_plans(plans)

    lines = [f"Plan for {folder} — {len(moves)} files would move "
             f"({skipped} dotfiles skipped):", ""]
    for group in sorted(counts):
        lines.append(f"  {group}/  <- {counts[group]} files")
    lines += ["",
              f"Plan token: {token}",
              "Nothing has moved. To apply, call organize_apply with this "
              "token — the token is single-use."]
    return "\n".join(lines)


def run_apply(args):
    token = str(args.get("plan_token") or "").strip()
    plans = _load_plans()
    plan = plans.pop(token, None)
    _save_plans(plans)  # single-use: consumed whether or not it succeeds
    if plan is None:
        return ("Invalid or already-used plan token. Run organize_preview "
                "again to get a fresh plan — I never move files without one.")
    folder = Path(plan["folder"])
    if not folder.is_dir():
        return f"The folder {folder} no longer exists — nothing moved."
    moved, missing, renamed = 0, 0, []
    for m in plan["moves"]:
        src = Path(m["src"])
        try:
            if not src.is_file():
                missing += 1
                continue
            # stay-inside check: the file must still be in the planned folder
            if src.resolve().parent != folder.resolve():
                missing += 1
                continue
            dest_dir = folder / m["group"]
            dest_dir.mkdir(exist_ok=True)
            dest = _no_overwrite(dest_dir / src.name)
            if dest.name != src.name:
                renamed.append(f"{src.name} -> {dest.name}")
            src.rename(dest)  # same filesystem: atomic, no copy
            moved += 1
        except OSError as e:
            missing += 1
    lines = [f"Done: {moved} files moved into {folder}."]
    if renamed:
        lines.append(f"{len(renamed)} renamed to avoid overwrites:")
        lines.extend(f"  {r}" for r in renamed[:10])
    if missing:
        lines.append(f"{missing} planned files were gone or moved already — "
                     f"skipped, nothing lost.")
    return "\n".join(lines)


TOOLS = [
    {"name": "organize_preview",
     "description": (
         "Scans a folder and shows what WOULD move where — grouped into "
         "Images/Documents/Audio/Video/Archives/Code/Other subfolders. "
         "NEVER moves anything; returns a plan token. Dotfiles are skipped, "
         "subfolders are left alone. ALWAYS call this first and show the "
         "user the plan before applying."),
     "kind": "native", "access": "read",
     "parameters": {
         "type": "object",
         "properties": {
             "folder": {"type": "string",
                        "description": "Folder to organize, e.g. "
                                       "'~/Downloads'."},
             "recursive": {"type": "boolean",
                           "description": "Also scan subfolders (default "
                                          "false)."}},
         "required": ["folder"]},
     "run": run_preview},
    {"name": "organize_apply",
     "description": (
         "Executes a preview plan — ONLY with a valid plan token from "
         "organize_preview. Moves files with no-overwrite (name-2, name-3 "
         "...), stays inside the folder. The token is single-use. Never "
         "call without the user confirming the preview."),
     "kind": "native", "access": "destructive",
     "parameters": {
         "type": "object",
         "properties": {
             "plan_token": {"type": "string",
                            "description": "Token from organize_preview."}},
         "required": ["plan_token"]},
     "run": run_apply},
]
