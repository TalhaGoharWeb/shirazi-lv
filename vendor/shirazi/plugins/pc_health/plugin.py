"""PC Health Doctor — snapshot system vitals, flag what is actually wrong.

WHO INTERPRETS: you do. health_snapshot collects the numbers;
health_report applies the thresholds and lists red flags; the model in
the middle decides what they mean for THIS user (a render running at
95% CPU is not a problem; 95% CPU at idle is).

psutil is OPTIONAL and lazy: imported inside the function, never at
module load. Without it the tool degrades gracefully with an install
hint instead of failing. It is read-only — it changes nothing on the PC.

Permissions used: none. There is no `system:read` in the permission
vocabulary; psutil is not mapped by the AST scan, is imported lazily,
and only reads counters. Stdlib otherwise.
"""

from __future__ import annotations

import json
import platform
import time

_THRESHOLDS = {
    "cpu_percent": {"watch": 70.0, "high": 90.0,
                    "why": "sustained high CPU = runaway process or "
                           "underpowered for the workload"},
    "mem_percent": {"watch": 75.0, "high": 90.0,
                    "why": "high RAM = swapping soon; check what grew"},
    "disk_percent": {"watch": 85.0, "high": 95.0,
                     "why": "a nearly-full disk breaks updates, builds "
                            "and databases"},
}


def _psutil():
    try:
        import psutil  # lazy, optional
        return psutil
    except Exception:
        return None


def _degraded():
    return (
        "psutil is not installed, so live system counters are unavailable.\n"
        "To enable PC health snapshots, run once in a terminal:\n"
        "  pip install psutil\n"
        "then restart Shirazi. Everything else keeps working — this tool "
        "only degrades, it never breaks.\n"
        "Fallback: ask the user what Task Manager / Settings shows for "
        "CPU, Memory and Disk, and reason from that.")


def run_snapshot(args):
    psutil = _psutil()
    if psutil is None:
        return _degraded()
    try:
        vm = psutil.virtual_memory()
        du = psutil.disk_usage("/")
        snap = {
            "at": int(time.time()),
            "os": f"{platform.system()} {platform.release()}",
            "cpu_percent": round(psutil.cpu_percent(interval=0.5), 1),
            "cpu_cores": psutil.cpu_count(logical=True),
            "mem_percent": round(vm.percent, 1),
            "mem_total_gb": round(vm.total / (1024 ** 3), 1),
            "mem_available_gb": round(vm.available / (1024 ** 3), 1),
            "disk_percent": round(du.percent, 1),
            "disk_free_gb": round(du.free / (1024 ** 3), 1),
            "process_count": len(psutil.pids()),
            "uptime_hours": round((time.time() - psutil.boot_time()) / 3600, 1),
        }
    except Exception as e:
        return (f"Could not read system counters ({e}). psutil is present "
                f"but the OS refused the read — treat as unknown, not as "
                f"healthy.")
    lines = ["PC health snapshot (raw numbers — interpret with "
             "health_report):",
             json.dumps(snap, indent=2),
             "",
             "Pass this JSON back into health_report for thresholds + red "
             "flags."]
    return "\n".join(lines)


def _flag(value, spec):
    if value is None:
        return None
    if value >= spec["high"]:
        return "HIGH"
    if value >= spec["watch"]:
        return "watch"
    return None


def run_report(args):
    metrics = args.get("metrics")
    if isinstance(metrics, str):
        try:
            metrics = json.loads(metrics)
        except ValueError:
            return ("Pass the snapshot JSON from health_snapshot (as an "
                    "object or JSON string).")
    if not isinstance(metrics, dict) or not metrics:
        return ("Pass the snapshot JSON from health_snapshot — I apply "
                "thresholds to it; I don't guess numbers.")
    flags = []
    for key in ("cpu_percent", "mem_percent", "disk_percent"):
        val = metrics.get(key)
        try:
            val = float(val) if val is not None else None
        except (TypeError, ValueError):
            val = None
        level = _flag(val, _THRESHOLDS[key]) if val is not None else None
        if level:
            flags.append((level, key, val))
    out = ["PC health report", ""]
    if not flags:
        out.append("No red flags: CPU, memory and disk are all inside "
                   "normal thresholds.")
    else:
        out.append("Red flags:")
        for level, key, val in flags:
            spec = _THRESHOLDS[key]
            out.append(f"  [{level}] {key} = {val}% — {spec['why']} "
                       f"(watch ≥ {spec['watch']}%, high ≥ {spec['high']}%)")
    out += ["",
            f"Context: {metrics.get('process_count', '?')} processes, "
            f"{metrics.get('uptime_hours', '?')}h uptime, "
            f"{metrics.get('disk_free_gb', '?')} GB disk free.",
            "",
            "Interpretation is yours: match these numbers against what the "
            "user reports (slow when idle? slow only in one app?). A "
            "single snapshot is a hint; two snapshots minutes apart are "
            "evidence. Propose the lowest-risk next step (e.g. find the "
            "top process in Task Manager) before any change."]
    return "\n".join(out)


TOOLS = [
    {"name": "health_snapshot",
     "description": (
         "Take a live snapshot of PC vitals: CPU %, RAM %, disk %, free "
         "disk, process count, uptime. Needs the optional psutil package — "
         "without it, degrades gracefully with an install hint (never "
         "fails). Read-only; changes nothing. Pass the returned JSON into "
         "health_report for thresholds and red flags."),
     "kind": "native", "access": "read",
     "parameters": {"type": "object", "properties": {}},
     "run": run_snapshot},
    {"name": "health_report",
     "description": (
         "Apply thresholds to a health_snapshot result and list red "
         "flags (HIGH/watch) with what each means. Pass `metrics` as the "
         "snapshot object (or its JSON string). Interpretation stays with "
         "you — one snapshot is a hint, two are evidence."),
     "kind": "native", "access": "read",
     "parameters": {
         "type": "object",
         "properties": {
             "metrics": {"description": "The health_snapshot JSON, as an "
                                        "object or JSON string."}},
         "required": ["metrics"]},
     "run": run_report},
]
