"""Timer plugin — countdowns and a stopwatch.

No permissions needed (stdlib time/threading only). When a countdown fires,
the module calls its notify hook (wired by the server at boot to surface a
proactive card). If the hook is unset, firings accumulate in FIRED so nothing
is silently lost. All timer threads are daemon threads — they never block exit.
"""

import threading
import time
import uuid

_timers = {}          # timer_id -> {"label", "ends_at", "timer", "fired"}
_stopwatch_start = None
_notify = None        # set by server via _set_notify(fn)
_lock = threading.Lock()


def _set_notify(fn):
    """Server hook: fn(label: str) called (best-effort) when a timer fires."""
    global _notify
    if callable(fn):
        _notify = fn


def _fire(tid):
    with _lock:
        info = _timers.get(tid)
        if not info:
            return
        info["fired"] = True
        label = info["label"]
    # Never let a notify hook crash the timer thread.
    try:
        if _notify:
            _notify(label)
    except Exception:
        pass


def run_start(args):
    try:
        seconds = float(args.get("seconds", 0))
    except (TypeError, ValueError):
        return "I need a number of seconds."
    if seconds <= 0 or seconds > 24 * 3600:
        return "Timers run between 1 second and 24 hours."
    label = str(args.get("label", "")).strip() or "Timer"
    tid = uuid.uuid4().hex[:8]
    t = threading.Timer(seconds, _fire, args=(tid,))
    t.daemon = True
    with _lock:
        _timers[tid] = {"label": label, "ends_at": time.time() + seconds,
                        "timer": t, "fired": False}
    t.start()
    return f"Timer '{label}' set for {seconds:g} seconds."


def run_list(args):
    with _lock:
        items = [(tid, dict(info)) for tid, info in _timers.items()]
    if not items:
        return "No timers running."
    lines = []
    for tid, info in items:
        if info["fired"]:
            lines.append(f"- '{info['label']}' — FIRED")
        else:
            left = max(0, info["ends_at"] - time.time())
            lines.append(f"- '{info['label']}' — {left:.0f}s left "
                         f"(id {tid})")
    return "Timers:\n" + "\n".join(lines)


def run_cancel(args):
    label = str(args.get("label", "")).strip().lower()
    tid = str(args.get("id", "")).strip()
    with _lock:
        if tid and tid in _timers:
            _timers[tid]["timer"].cancel()
            gone = _timers.pop(tid)["label"]
            return f"Cancelled timer '{gone}'."
        for k, info in list(_timers.items()):
            if not info["fired"] and info["label"].lower() == label and label:
                info["timer"].cancel()
                _timers.pop(k)
                return f"Cancelled timer '{info['label']}'."
    return "No matching running timer found."


def run_sw_start(args):
    global _stopwatch_start
    _stopwatch_start = time.time()
    return "Stopwatch started."


def run_sw_stop(args):
    global _stopwatch_start
    if _stopwatch_start is None:
        return "The stopwatch isn't running."
    elapsed = time.time() - _stopwatch_start
    _stopwatch_start = None
    mins, secs = divmod(int(elapsed), 60)
    return f"Stopwatch: {mins}m {secs}s ({elapsed:.1f} seconds)."


def drain_fired():
    """Labels of fired timers since the last call (server polling hook)."""
    with _lock:
        out = [info["label"] for info in _timers.values() if info["fired"]]
        for info in _timers.values():
            info["fired"] = False
    return out


TOOLS = [
    {"name": "timer_start",
     "description": "Start a countdown timer. Say 'set a 5 minute timer for pasta'.",
     "kind": "native", "access": "write",
     "parameters": {"type": "object",
                    "properties": {
                        "seconds": {"type": "number",
                                    "description": "Countdown length in seconds."},
                        "label": {"type": "string",
                                  "description": "What the timer is for."}},
                    "required": ["seconds"]},
     "run": run_start},
    {"name": "timer_list",
     "description": "List running and fired timers.",
     "kind": "native", "access": "read",
     "parameters": {"type": "object", "properties": {}},
     "run": run_list},
    {"name": "timer_cancel",
     "description": "Cancel a running timer by label or id.",
     "kind": "native", "access": "write",
     "parameters": {"type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "id": {"type": "string"}}},
     "run": run_cancel},
    {"name": "stopwatch_start",
     "description": "Start the stopwatch.",
     "kind": "native", "access": "write",
     "parameters": {"type": "object", "properties": {}},
     "run": run_sw_start},
    {"name": "stopwatch_stop",
     "description": "Stop the stopwatch and report elapsed time.",
     "kind": "native", "access": "read",
     "parameters": {"type": "object", "properties": {}},
     "run": run_sw_stop},
]
