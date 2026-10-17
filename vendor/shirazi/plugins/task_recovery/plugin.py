"""Smart Task Recovery — checkpoint a task, resume it later.

WHO DECIDES WHAT TO SAVE: you do. task_checkpoint stores whatever state
object you pass (current step, partial results, next action); task_resume
loads it back verbatim; task_list shows what is parked. The plugin is a
faithful shelf — it never interprets, merges or "helpfully" edits state.

Checkpoints live at <SHIRAZI_DATA_DIR>/plugins_data/task_recovery/
as plain JSON, yours to inspect and delete.

Permissions used: [files:write] (checkpoint writes; resume/list read).
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

_MAX_ID = 64


def _store_dir() -> Path:
    base = Path(os.environ.get("SHIRAZI_DATA_DIR",
                               str(Path.home() / ".shirazi")))
    d = base / "plugins_data" / "task_recovery"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_id(task_id: str):
    tid = re.sub(r"[^A-Za-z0-9_-]", "_", str(task_id or "").strip())
    tid = re.sub(r"_+", "_", tid).strip("_")[:_MAX_ID]
    return tid or None


def _path_for(tid: str) -> Path:
    return _store_dir() / f"{tid}.json"


def run_checkpoint(args):
    tid = _safe_id(args.get("task_id"))
    if not tid:
        return ("Give the checkpoint a task_id (letters, numbers, dash, "
                "underscore) — e.g. 'etsy-bundle' or 'shirazi-build'.")
    state = args.get("state")
    if state is None:
        return ("Pass `state`: the task's current state as an object — "
                "current step, partial results, next action, anything the "
                "resumed session needs.")
    label = str(args.get("label") or "").strip()[:200]
    record = {
        "task_id": tid,
        "label": label,
        "state": state,
        "updated_at": int(time.time()),
    }
    try:
        with open(_path_for(tid), "w", encoding="utf-8") as fh:
            json.dump(record, fh, ensure_ascii=False, indent=2)
    except OSError as e:
        return f"Could not save the checkpoint: {e}"
    return (f"Checkpoint saved: '{tid}'"
            + (f" ({label})" if label else "")
            + ". Resume it any time with task_resume.")


def run_resume(args):
    tid = _safe_id(args.get("task_id"))
    if not tid:
        return "Pass the task_id you used in task_checkpoint."
    p = _path_for(tid)
    if not p.is_file():
        return (f"No checkpoint named '{tid}'. Call task_list to see what "
                f"is parked.")
    try:
        with open(p, "r", encoding="utf-8") as fh:
            record = json.load(fh)
    except (OSError, ValueError) as e:
        return f"Checkpoint '{tid}' is unreadable: {e}"
    state = record.get("state")
    try:
        shown = json.dumps(state, ensure_ascii=False, indent=2)[:4000]
    except (TypeError, ValueError):
        shown = str(state)[:4000]
    lines = [f"Resuming '{tid}'"
             + (f" ({record.get('label')})" if record.get("label") else "")
             + f" — saved {time.strftime('%Y-%m-%d %H:%M', time.localtime(record.get('updated_at', 0)))}",
             "",
             "Saved state:",
             shown,
             "",
             "Continue from here: verify the state is still true (files "
             "may have changed since), then carry on."]
    return "\n".join(lines)


def run_list(args):
    d = _store_dir()
    try:
        files = sorted(d.glob("*.json"))
    except OSError:
        files = []
    if not files:
        return "No checkpoints parked. task_checkpoint saves one."
    lines = [f"{len(files)} checkpoint(s):"]
    for p in files:
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
            tid = rec.get("task_id", p.stem)
            label = f" ({rec.get('label')})" if rec.get("label") else ""
            when = time.strftime("%Y-%m-%d %H:%M",
                                 time.localtime(rec.get("updated_at", 0)))
        except (OSError, ValueError):
            tid, label, when = p.stem, "", "unreadable"
        lines.append(f"  - {tid}{label} — {when}")
    return "\n".join(lines)


TOOLS = [
    {"name": "task_checkpoint",
     "description": (
         "Park a task's state so it can be resumed later — after a "
         "restart, tomorrow, or mid-interruption. Pass task_id (short "
         "slug) and `state` (object: current step, partial results, next "
         "action). Stored as plain JSON under Shirazi's data dir. "
         "Checkpoint BEFORE risky steps and at every natural pause."),
     "kind": "native", "access": "write",
     "parameters": {
         "type": "object",
         "properties": {
             "task_id": {"type": "string"},
             "state": {"type": "object",
                       "description": "Whatever the resumed session "
                                      "needs: step, partial results, "
                                      "next action."},
             "label": {"type": "string",
                       "description": "Human-readable title."}},
         "required": ["task_id", "state"]},
     "run": run_checkpoint},
    {"name": "task_resume",
     "description": (
         "Load a parked checkpoint back verbatim. Returns the saved "
         "state plus when it was saved. Verify the state is still true "
         "(files may have changed) before continuing."),
     "kind": "native", "access": "read",
     "parameters": {
         "type": "object",
         "properties": {"task_id": {"type": "string"}},
         "required": ["task_id"]},
     "run": run_resume},
    {"name": "task_list",
     "description": "List parked checkpoints with their labels and save times.",
     "kind": "native", "access": "read",
     "parameters": {"type": "object", "properties": {}},
     "run": run_list},
]
