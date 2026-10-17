"""Shirazi problem-diagnosis helpers — the shared 7-step methodology.

Every problem-solving plugin works the same seven steps:

    1. Detect          — name the problem and its symptoms.
    2. Diagnose        — form hypotheses about the root cause and test them.
    3. Gather evidence — logs, files, errors, anything checkable.
    4. Plan            — propose the lowest-risk fix that fits the evidence.
    5. Execute         — apply it within the granted permissions.
    6. Verify          — re-test and prove the problem is actually gone.
    7. Learn           — save the confirmed root cause + fix so the next
                       occurrence is recognised, not re-diagnosed.

This module holds the deterministic parts: case records, the fix journal
(append-only history of confirmed fixes) and the troubleshooting memory
(signature -> root cause + fix). The model does the reasoning; these
functions do the bookkeeping. Stdlib only.

Storage: <SHIRAZI_DATA_DIR>/plugins_data/problem_diagnosis/
  fix_journal.json            append-only list of confirmed fixes
  troubleshooting_memory.json {signature: {root_cause, fix, domain, hits, ...}}
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

# ── the seven steps ──────────────────────────────────────────────────────────

STEPS = (
    ("detect",
     "Detect",
     "State the problem in one sentence and list the observable symptoms. "
     "No guessing yet — only what was seen."),
    ("diagnose",
     "Diagnose",
     "Write down 2-4 candidate root causes, ranked by likelihood. For each, "
     "name the single cheapest test that would confirm or rule it out."),
    ("gather",
     "Gather evidence",
     "Collect logs, error text, file paths, versions, recent changes. "
     "Attach each piece of evidence to the hypothesis it supports or kills."),
    ("plan",
     "Plan",
     "Propose the smallest change that fits the evidence. Name the risk "
     "(low/medium/high), what needs backing up first, and what approval "
     "the change requires before it runs."),
    ("execute",
     "Execute",
     "Apply the plan inside the granted permissions only. One change at a "
     "time — never bundle two fixes, or you won't know which one worked."),
    ("verify",
     "Verify",
     "Re-run the failing thing and the cheapest related checks. A fix is "
     "not done when it 'looks right' — it is done when the failure is "
     "reproduced-then-gone. Never report a failed action as success."),
    ("learn",
     "Learn",
     "Record the confirmed root cause and the fix that worked "
     "(troubleshooting memory). Future occurrences match on the signature "
     "instead of starting from zero."),
)

_EVIDENCE_KINDS = ("symptom", "log", "hypothesis", "test", "fix",
                   "result", "note")


def new_case(problem: str, domain: str = "") -> dict:
    """Start a fresh problem case record."""
    return {
        "problem": str(problem or "").strip()[:2000],
        "domain": str(domain or "").strip()[:120],
        "created_at": int(time.time()),
        "steps": {key: {"status": "pending", "notes": []}
                  for key, _, _ in STEPS},
        "evidence": [],
    }


def add_evidence(case: dict, kind: str, text: str, source: str = "") -> dict:
    """Attach one piece of evidence to a case. Returns the case."""
    kind = str(kind or "").strip().lower()
    if kind not in _EVIDENCE_KINDS:
        kind = "note"
    case.setdefault("evidence", []).append({
        "kind": kind,
        "text": str(text or "").strip()[:4000],
        "source": str(source or "").strip()[:300],
        "at": int(time.time()),
    })
    return case


def mark_step(case: dict, step_key: str, status: str, note: str = "") -> dict:
    """Mark a methodology step done/skipped/in-progress with an optional note."""
    steps = case.setdefault("steps", {})
    if step_key in steps and status in ("pending", "in_progress", "done",
                                       "skipped"):
        steps[step_key]["status"] = status
        if note:
            steps[step_key]["notes"].append(str(note)[:1000])
    return case


def render_case(case: dict) -> str:
    """Render a case as plain text for the model / user."""
    lines = [f"Problem: {case.get('problem', '')}"]
    if case.get("domain"):
        lines.append(f"Domain: {case['domain']}")
    lines.append("")
    lines.append("Steps:")
    for key, title, _ in STEPS:
        st = (case.get("steps") or {}).get(key, {})
        status = st.get("status", "pending")
        lines.append(f"  [{status}] {title}")
        for n in st.get("notes", [])[:3]:
            lines.append(f"         - {n}")
    ev = case.get("evidence") or []
    if ev:
        lines.append("")
        lines.append(f"Evidence ({len(ev)}):")
        for e in ev[:20]:
            src = f" ({e['source']})" if e.get("source") else ""
            lines.append(f"  [{e['kind']}] {e['text'][:160]}{src}")
    return "\n".join(lines).strip()


# ── storage ──────────────────────────────────────────────────────────────────

def _data_dir() -> Path:
    base = Path(os.environ.get("SHIRAZI_DATA_DIR",
                               str(Path.home() / ".shirazi")))
    d = base / "plugins_data" / "problem_diagnosis"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read_json(path: Path, default):
    try:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    return default


def _write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2),
                    encoding="utf-8")


# ── fix journal (append-only) ────────────────────────────────────────────────

def append_fix_journal(entry: dict) -> dict:
    """Record a CONFIRMED fix. Only call after Verify passed.

    entry: {problem, root_cause, fix, domain?, verified?}
    Returns the stored record (with id + timestamp).
    """
    p = _data_dir() / "fix_journal.json"
    journal = _read_json(p, [])
    if not isinstance(journal, list):
        journal = []
    rec = {
        "id": len(journal) + 1,
        "at": int(time.time()),
        "problem": str(entry.get("problem") or "")[:1000],
        "root_cause": str(entry.get("root_cause") or "")[:2000],
        "fix": str(entry.get("fix") or "")[:2000],
        "domain": str(entry.get("domain") or "")[:120],
        "verified": bool(entry.get("verified", True)),
    }
    journal.append(rec)
    _write_json(p, journal)
    return rec


def read_fix_journal(limit: int = 20, domain: str = "") -> list:
    """Newest-first confirmed fixes, optionally filtered by domain."""
    p = _data_dir() / "fix_journal.json"
    journal = _read_json(p, [])
    if not isinstance(journal, list):
        return []
    if domain:
        d = domain.strip().lower()
        journal = [r for r in journal
                   if str(r.get("domain") or "").lower() == d]
    try:
        limit = max(1, min(int(limit), 200))
    except (TypeError, ValueError):
        limit = 20
    return list(reversed(journal[-limit:]))


# ── troubleshooting memory (signature -> fix) ────────────────────────────────

def _signature(text: str) -> str:
    """Normalised signature for a problem description."""
    toks = re.findall(r"[a-z0-9]+", str(text or "").lower())
    stop = {"the", "a", "an", "is", "are", "my", "me", "i", "it", "to",
            "of", "and", "or", "on", "in", "for", "with", "not", "no",
            "hai", "hy", "ka", "ki", "ky", "ko", "mein", "nahi", "na"}
    toks = [t for t in toks if t not in stop and len(t) > 1]
    return " ".join(sorted(set(toks)))[:500]


def remember_fix(problem: str, root_cause: str, fix: str,
                 domain: str = "") -> dict:
    """Save a verified root cause + fix under the problem's signature."""
    sig = _signature(problem)
    if not sig:
        return {"saved": False, "reason": "problem text too short to sign"}
    p = _data_dir() / "troubleshooting_memory.json"
    mem = _read_json(p, {})
    if not isinstance(mem, dict):
        mem = {}
    prev = mem.get(sig, {})
    mem[sig] = {
        "signature": sig,
        "problem": str(problem)[:500],
        "root_cause": str(root_cause)[:2000],
        "fix": str(fix)[:2000],
        "domain": str(domain or "")[:120],
        "hits": int(prev.get("hits", 0)),
        "updated_at": int(time.time()),
    }
    _write_json(p, mem)
    return {"saved": True, "signature": sig}


def recall_fix(problem: str):
    """Exact-signature lookup. Returns the record (and bumps hits) or None."""
    sig = _signature(problem)
    if not sig:
        return None
    p = _data_dir() / "troubleshooting_memory.json"
    mem = _read_json(p, {})
    rec = mem.get(sig) if isinstance(mem, dict) else None
    if not rec:
        return None
    rec["hits"] = int(rec.get("hits", 0)) + 1
    _write_json(p, mem)
    return rec


def recall_similar(problem: str, top: int = 3) -> list:
    """Keyword-overlap search over saved fixes. Deterministic, stdlib."""
    sig = _signature(problem)
    if not sig:
        return []
    p = _data_dir() / "troubleshooting_memory.json"
    mem = _read_json(p, {})
    if not isinstance(mem, dict) or not mem:
        return []
    want = set(sig.split())
    scored = []
    for s, rec in mem.items():
        if s == sig:
            continue
        have = set(str(s).split())
        if not have:
            continue
        jaccard = len(want & have) / len(want | have)
        if jaccard > 0:
            scored.append((jaccard, rec))
    scored.sort(key=lambda t: t[0], reverse=True)
    try:
        top = max(1, min(int(top), 10))
    except (TypeError, ValueError):
        top = 3
    return [{"score": round(j, 3), **r} for j, r in scored[:top]]
