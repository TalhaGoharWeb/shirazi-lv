"""Shirazi-origin tool: structured problem diagnosis (7-step methodology).

Wraps shirazi-core/core/problem_diagnosis.py: case records, evidence log,
step tracking, an append-only fix journal, and signature-keyed troubleshooting
memory (exact + fuzzy recall of past fixes).

Operations (via the `operation` parameter):
- recall: search past fixes for a problem (check this FIRST for known issues)
- start: open a new diagnosis case
- evidence: attach evidence (kind: symptom|log|test|doc) to a case
- step: mark a methodology step (detect|diagnose|gather|plan|execute|verify|learn)
- journal: read the recent fix journal
- show: render a case

Upstream: https://github.com/TalhaGoharWeb/shirazi-personal-assistant
Shirazi-origin; integrated into Shirazi LV under the project's attribution terms.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_PLUGIN_FILE = (Path(__file__).resolve().parent.parent / "vendor" / "shirazi"
                / "core" / "problem_diagnosis.py")


def _load():
    key = "_shirazi_problem_diagnosis"
    mod = sys.modules.get(key)
    if mod is None:
        spec = importlib.util.spec_from_file_location(key, _PLUGIN_FILE)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[key] = mod
        spec.loader.exec_module(mod)
    return mod


_pd = _load()
_cases: dict[str, dict] = {}
_case_seq = 0


def _new_id() -> str:
    global _case_seq
    _case_seq += 1
    return f"case-{_case_seq:03d}"

PLUGIN = {
    "name": "shirazi_problem_diagnose",
    "description": (
        "Structured troubleshooting for real problems: check past fixes first, "
        "open a diagnosis case, log evidence, track the 7-step methodology "
        "(detect, diagnose, gather, plan, execute, verify, learn), and keep an "
        "append-only fix journal. Use for build errors, PC issues, and any "
        "problem that needs methodical diagnosis instead of guessing."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "operation": {
                "type": "STRING",
                "description": "recall | start | evidence | step | journal | show",
            },
            "problem": {"type": "STRING", "description": "Problem description."},
            "case_id": {"type": "STRING", "description": "Case id from start."},
            "kind": {"type": "STRING",
                     "description": "Evidence kind: symptom|log|test|doc."},
            "text": {"type": "STRING", "description": "Evidence text or note."},
            "step": {"type": "STRING",
                     "description": "Methodology step key to mark."},
            "status": {"type": "STRING",
                       "description": "Step status: open|done|blocked."},
        },
        "required": ["operation"],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Mark-LV plugin contract: never raise; return a spoken string."""
    try:
        return _run(parameters or {})
    except Exception as e:
        return f"Problem diagnosis failed: {e}"


def _run(p: dict) -> str:
    op = str(p.get("operation", "")).lower()
    if op == "recall":
        problem = str(p.get("problem", "")).strip()
        if not problem:
            return "Give me the problem description to search past fixes."
        exact = _pd.recall_fix(problem)
        similar = _pd.recall_similar(problem, top=3)
        lines = []
        if exact:
            lines.append(f"Known fix: {exact}")
        for s in similar or []:
            lines.append(f"Similar past case: {s}")
        if not lines:
            return ("No past fixes match. Open a case with operation 'start' "
                    "and work the methodology steps.")
        return "\n".join(lines)
    if op == "start":
        problem = str(p.get("problem", "")).strip()
        if not problem:
            return "Give me the problem description to open a case."
        case = _pd.new_case(problem)
        cid = _new_id()
        _cases[cid] = case
        return (f"Case {cid} opened for: {problem}\n"
                "Next: gather evidence (operation 'evidence'), then work the "
                "steps: detect, diagnose, gather, plan, execute, verify, learn.")
    if op == "journal":
        entries = _pd.read_fix_journal(limit=10)
        if not entries:
            return "The fix journal is empty."
        return "\n".join(str(e)[:200] for e in entries)
    case = _cases.get(str(p.get("case_id", "")))
    if case is None:
        return "Unknown case_id — start a case first (operation 'start')."
    if op == "evidence":
        text = str(p.get("text", "")).strip()
        if not text:
            return "Give me the evidence text."
        _pd.add_evidence(case, str(p.get("kind", "symptom")), text)
        return f"Evidence logged on case {p.get('case_id')}."
    if op == "step":
        step = str(p.get("step", "")).strip()
        if not step:
            return "Which step? detect|diagnose|gather|plan|execute|verify|learn"
        _pd.mark_step(case, step, str(p.get("status", "done")),
                      str(p.get("text", "")))
        return f"Case {p.get('case_id')}: step '{step}' marked {p.get('status', 'done')}."
    if op == "show":
        return _pd.render_case(case)
    return ("Unknown operation. Use: recall | start | evidence | step | "
            "journal | show.")
