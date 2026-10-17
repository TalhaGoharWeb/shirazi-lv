"""Web research plugin — a cited research tracker.

AN HONEST DIVISION OF LABOUR: this plugin does not browse. YOU gather —
search the web, open pages, read them — and this keeps the evidence honest:
every source logged with its URL, title, your notes and a reliability flag;
every claim that does NOT have a source yet sits in an UNVERIFIED section
that cannot be silently dropped. The compiled report shows both, so a
research draft never presents an unsourced claim as a sourced one.

Reliability flags (your judgement, recorded):
  high   — primary source, official docs, printed edition, direct measurement
  medium — reputable secondary: established press, known references
  low    — forums, unverified blogs, single anonymous claims; usable as leads

A source added with an empty url is a CLAIM, not a source: something you
noted down (or the user said) that has no citation yet. The report lists
these under UNVERIFIED until a real source is attached.

Permissions used: files:write (the research JSON store).
"""

import json
import os
import time
import uuid
from pathlib import Path

RELIABILITY = ("high", "medium", "low")
_FLAG = {"high": "[HIGH]", "medium": "[MED]", "low": "[LOW]"}


def _store_path():
    base = Path(os.environ.get("SHIRAZI_DATA_DIR",
                               str(Path.home() / ".shirazi")))
    d = base / "plugins_data"
    d.mkdir(parents=True, exist_ok=True)
    return d / "web_research.json"


def _load():
    p = _store_path()
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return {}


def _save(db):
    _store_path().write_text(json.dumps(db, ensure_ascii=False, indent=2),
                             encoding="utf-8")


def _get(db, rid):
    rid = str(rid or "").strip()
    r = db.get(rid)
    return rid, r


def run_start(args):
    topic = str(args.get("topic") or "").strip()
    if not topic:
        return "What are we researching? Give me the topic."
    db = _load()
    rid = uuid.uuid4().hex[:8]
    db[rid] = {"topic": topic[:200], "created": time.time(), "sources": []}
    _save(db)
    return (f"Research started [{rid}]: {topic}. As you gather, log each "
            f"source with research_add_source — url, title, your notes, and "
            f"a reliability flag. Claims without a source yet: add them with "
            f"an empty url; they land in UNVERIFIED, not in the source list.")


def run_add_source(args):
    db = _load()
    rid, r = _get(db, args.get("research_id"))
    if r is None:
        return f"No research [{rid}]. Start one with research_start."
    url = str(args.get("url") or "").strip()
    title = str(args.get("title") or "").strip()
    notes = str(args.get("notes") or "").strip()
    rel = str(args.get("reliability") or "medium").strip().lower()
    if rel not in RELIABILITY:
        return f"reliability must be one of: {', '.join(RELIABILITY)}."
    if not url and not notes:
        return ("An unsourced claim still needs its text — put it in "
                "`notes` with an empty url.")
    if url and not title:
        title = url
    r["sources"].append({"url": url[:500], "title": title[:200],
                         "notes": notes[:2000], "reliability": rel,
                         "added": time.time()})
    _save(db)
    kind = "claim (UNVERIFIED until sourced)" if not url else "source"
    return (f"Logged {kind} #{len(r['sources'])} on [{rid}] "
            f"{_FLAG[rel]} — {title[:80]}")


def run_report(args):
    db = _load()
    rid, r = _get(db, args.get("research_id"))
    if r is None:
        return f"No research [{rid}]. Start one with research_start."
    sources = [s for s in r["sources"] if s.get("url")]
    claims = [s for s in r["sources"] if not s.get("url")]
    lines = [f"# Research: {r['topic']}", ""]
    if not r["sources"]:
        lines.append("No sources logged yet.")
        return "\n".join(lines)
    lines.append(f"## Sources ({len(sources)})")
    lines.append("")
    for i, s in enumerate(sources, 1):
        lines.append(f"{i}. {_FLAG[s['reliability']]} {s['title']}")
        lines.append(f"   {s['url']}")
        if s.get("notes"):
            lines.append(f"   Notes: {s['notes']}")
        lines.append("")
    if claims:
        lines.append(f"## UNVERIFIED ({len(claims)}) — claims without a "
                     f"source; do NOT cite these as fact")
        lines.append("")
        for i, s in enumerate(claims, 1):
            lines.append(f"{i}. {_FLAG[s['reliability']]} {s['notes']}")
        lines.append("")
    lines.append("---")
    lines.append("Write the draft FROM the sources above. Anything under "
                 "UNVERIFIED stays out of the cited draft until sourced.")
    return "\n".join(lines).strip()


TOOLS = [
    {"name": "research_start",
     "description": (
         "Starts a tracked research task on a topic. Returns a research id. "
         "Use when the user asks for research, comparison, or a cited "
         "report — then gather from the web yourself and log everything "
         "with research_add_source."),
     "kind": "native", "access": "write",
     "parameters": {
         "type": "object",
         "properties": {
             "topic": {"type": "string",
                       "description": "What is being researched."}},
         "required": ["topic"]},
     "run": run_start},
    {"name": "research_add_source",
     "description": (
         "Logs one source (or unsourced claim) to a research task. YOU do "
         "the gathering — search, open, read — then record: url, title, "
         "your notes (what this source actually says, in your words), and "
         "reliability: high (primary/official), medium (reputable "
         "secondary), low (forums/unverified). Leave url EMPTY for a claim "
         "with no source yet — it goes to UNVERIFIED, never silently into "
         "the source list."),
     "kind": "native", "access": "write",
     "parameters": {
         "type": "object",
         "properties": {
             "research_id": {"type": "string"},
             "url": {"type": "string",
                     "description": "Source URL; empty = unsourced claim."},
             "title": {"type": "string"},
             "notes": {"type": "string",
                       "description": "What the source says / the claim."},
             "reliability": {"type": "string",
                             "enum": ["high", "medium", "low"]}},
         "required": ["research_id", "notes"]},
     "run": run_add_source},
    {"name": "research_report",
     "description": (
         "Compiles the research into markdown: numbered sources with "
         "reliability flags and notes, plus an UNVERIFIED section for "
         "claims without sources. Present it, then write the draft FROM "
         "the sourced section only."),
     "kind": "native", "access": "read",
     "parameters": {
         "type": "object",
         "properties": {"research_id": {"type": "string"}},
         "required": ["research_id"]},
     "run": run_report},
]
