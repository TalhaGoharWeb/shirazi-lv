"""Universal Problem Solver — the router every specialist plugs into.

WHO REASONS: you do, mid-conversation. This plugin never diagnoses on its
own; it enforces the contract every problem-solving plugin follows:

    problem_classify -> problem_plan -> specialist tools -> problem_route

The model classifies the problem (type, severity, permissions, risk);
this plugin VALIDATES that classification deterministically, renders the
7-step plan (Detect -> Diagnose -> Gather evidence -> Plan -> Execute ->
Verify -> Learn), and routes to the specialist plugin whose tools fit.

It works with whatever specialists exist: the routing table below covers
the bundled ones, and anything else on the live tool list is yours to
pick — the table says so honestly instead of pretending to know them.

Permissions used: none (pure reasoning contract, stdlib only).
"""

from __future__ import annotations

try:
    from core.problem_diagnosis import (
        STEPS, recall_fix, recall_similar,
    )
    _SHARED = True
except Exception:  # standalone: keep the tools working without core/
    _SHARED = False
    STEPS = (
        ("detect", "Detect", "State the problem and its symptoms."),
        ("diagnose", "Diagnose", "Rank candidate root causes; name the "
                                 "cheapest test for each."),
        ("gather", "Gather evidence", "Collect logs, errors, versions, "
                                      "recent changes."),
        ("plan", "Plan", "Propose the smallest change fitting the "
                         "evidence; name risk and needed approvals."),
        ("execute", "Execute", "Apply inside granted permissions, one "
                               "change at a time."),
        ("verify", "Verify", "Re-run the failing thing; prove it is "
                             "gone. Never report failure as success."),
        ("learn", "Learn", "Save the confirmed root cause + fix."),
    )

    def recall_fix(problem):  # noqa: E306
        return None

    def recall_similar(problem, top=3):  # noqa: E306
        return []


_SEVERITIES = ("low", "medium", "high", "critical")
_RISKS = ("low", "medium", "high")
_KNOWN_PERMS = ("network", "files:read", "files:write", "clipboard", "exec")

# Bundled specialists. (keywords, plugin, tools, fits-when)
_SPECIALISTS = (
    (("build", "compile", "gradle", "apk", "aab", "exe", "installer",
       "traceback", "stacktrace", "compilation", "flutter build",
       "npm run build", "pip install"),
     "build_doctor", ["build_diagnose", "build_fix_checklist"],
     "build / compile / packaging failures"),
    (("slow", "freeze", "frozen", "hang", "crash", "cpu", "memory", "ram",
       "disk full", "disk", "startup", "overheat", "battery"),
     "pc_health", ["health_snapshot", "health_report"],
     "PC slowness, crashes, resource pressure"),
    (("knowledge base", "rag", "dataset", "duplicate records",
       "chunks", "indexing", "retrieval"),
     "kb_repair", ["kb_audit", "kb_fix_preview"],
     "knowledge-base / dataset quality problems"),
    (("resume", "checkpoint", "continue", "pick up", "interrupted task",
       "task state", "where was i"),
     "task_recovery", ["task_checkpoint", "task_resume", "task_list"],
     "resuming an interrupted multi-step task"),
    (("click", "window", "app open", "gui", "screen", "desktop"),
     "computer", ["computer_*"],
     "doing things in Windows apps by GUI"),
    (("messy", "clutter", "organise", "organize", "downloads folder",
       "duplicates"),
     "file_organizer", ["organize_preview", "organize_apply"],
     "tidying files and folders"),
    (("research", "sources", "investigate", "find information"),
     "web_research", ["research_start", "research_add_source",
                      "research_report"],
     "multi-source research with honest citations"),
    (("remember", "preference", "teach", "don't forget"),
     "trainer", ["train_fact", "train_preference", "train_correction",
                 "training_list"],
     "teaching Shirazi lasting facts/preferences"),
)


def _norm_list(v):
    if v is None:
        return []
    if isinstance(v, str):
        v = [v]
    return [str(x).strip() for x in v if str(x).strip()]


def run_classify(args):
    problem = str(args.get("problem") or "").strip()
    if not problem:
        return ("Describe the problem first — one or two sentences about "
                "what is wrong and what you were doing when it happened.")
    domain = str(args.get("domain") or "").strip()[:120] or "general"
    severity = str(args.get("severity") or "medium").strip().lower()
    risk = str(args.get("risk_level") or "medium").strip().lower()
    if severity not in _SEVERITIES:
        return (f"severity must be one of {', '.join(_SEVERITIES)} — "
                f"you passed '{args.get('severity')}'. Re-classify.")
    if risk not in _RISKS:
        return (f"risk_level must be one of {', '.join(_RISKS)} — "
                f"you passed '{args.get('risk_level')}'. Re-classify.")
    perms = _norm_list(args.get("permissions_needed"))
    unknown = [p for p in perms if p not in _KNOWN_PERMS]
    if unknown:
        return (f"Unknown permissions: {', '.join(unknown)}. Known: "
                f"{', '.join(_KNOWN_PERMS)}. Re-classify.")
    needs_approval = (
        risk == "high"
        or severity == "critical"
        or "exec" in perms
    )
    lines = [
        "Classification recorded:",
        f"  problem : {problem[:300]}",
        f"  domain  : {domain}",
        f"  severity: {severity} | risk: {risk}",
        f"  permissions needed: {', '.join(perms) or 'none'}",
        f"  user approval before Execute: "
        f"{'YES — confirm with the user first' if needs_approval else 'no'}",
    ]
    if _SHARED:
        seen = recall_fix(problem)
        if seen:
            lines += ["",
                      "Troubleshooting memory HIT — this was solved before:",
                      f"  root cause: {seen.get('root_cause', '')[:200]}",
                      f"  fix       : {seen.get('fix', '')[:200]}",
                      "Verify it still applies before reusing it."]
        else:
            sims = recall_similar(problem)
            if sims:
                lines += ["", "Similar past fixes (check relevance):"]
                for s in sims[:2]:
                    lines.append(
                        f"  - {s.get('problem', '')[:120]} "
                        f"(score {s.get('score')})")
    lines += ["",
              "Next: call problem_plan with this classification to lay out "
              "the 7 steps."]
    return "\n".join(lines)


def run_plan(args):
    problem = str(args.get("problem") or "").strip()
    if not problem:
        return "Pass the problem text so the plan has something to plan."
    domain = str(args.get("domain") or "").strip() or "general"
    lines = [f"7-step plan — {problem[:200]}", f"domain: {domain}", ""]
    for i, (key, title, desc) in enumerate(STEPS, 1):
        lines.append(f"{i}. {title}")
        lines.append(f"   {desc}")
    lines += ["",
              "Rules for every step:",
              "- Sensitive changes need user approval first; back up "
              "important files before touching them.",
              "- One change at a time; re-test after each.",
              "- Never present a failed action as a success.",
              "- Step 7 (Learn) is not optional — record confirmed fixes.",
              "",
              "Next: call problem_route to pick the specialist, or start "
              "step 1 directly for simple problems."]
    return "\n".join(lines)


def run_route(args):
    problem = str(args.get("problem") or "").strip()
    if not problem:
        return "Pass the problem text to route it."
    text = problem.lower()
    scored = []
    for keywords, plugin, tools, fits in _SPECIALISTS:
        hits = sum(1 for k in keywords if k in text)
        if hits:
            scored.append((hits, plugin, tools, fits))
    scored.sort(key=lambda t: t[0], reverse=True)
    lines = [f"Routing for: {problem[:200]}", ""]
    if scored:
        lines.append("Recommended specialists (best match first):")
        for hits, plugin, tools, fits in scored[:3]:
            lines.append(f"  - {plugin} [{', '.join(tools)}]")
            lines.append(f"    fits: {fits}")
    else:
        lines.append("No bundled specialist matches clearly — work it with "
                     "the 7-step plan and the general tool list.")
    lines += ["",
              "Note: this table covers the bundled specialists only. The "
              "live tool list may hold more (check it before falling back "
              "to a general plan). A specialist may use another "
              "specialist's results, but each stays inside its own "
              "permissions."]
    return "\n".join(lines)


TOOLS = [
    {"name": "problem_classify",
     "description": (
         "Classify a user's problem before solving it. YOU analyse the "
         "problem and pass YOUR classification: domain, severity "
         "(low/medium/high/critical), risk_level (low/medium/high) and "
         "permissions_needed (subset of network, files:read, files:write, "
         "clipboard, exec). This validates the values, decides whether "
         "user approval is required before Execute, and checks the "
         "troubleshooting memory for a previously confirmed fix. Call "
         "this FIRST for any 'fix my X / why is Y broken' request, then "
         "problem_plan."),
     "kind": "native", "access": "read",
     "parameters": {
         "type": "object",
         "properties": {
             "problem": {"type": "string",
                         "description": "The problem in the user's words."},
             "domain": {"type": "string",
                        "description": "e.g. build, pc, knowledge-base, "
                                       "task, general."},
             "severity": {"type": "string",
                          "enum": ["low", "medium", "high", "critical"]},
             "risk_level": {"type": "string",
                            "enum": ["low", "medium", "high"],
                            "description": "Risk of the likely fix, not of "
                                           "the problem."},
             "permissions_needed": {"type": "array", "items": {"type": "string"},
                                    "description": "Subset of: network, "
                                                   "files:read, files:write, "
                                                   "clipboard, exec."}},
         "required": ["problem"]},
     "run": run_classify},
    {"name": "problem_plan",
     "description": (
         "Render the 7-step problem-solving plan for a classified problem: "
         "Detect -> Diagnose -> Gather evidence -> Plan -> Execute -> "
         "Verify -> Learn, with per-step guidance and the standing rules "
         "(approval for sensitive changes, backups, one change at a time, "
         "never report failure as success). Call after problem_classify."),
     "kind": "native", "access": "read",
     "parameters": {
         "type": "object",
         "properties": {
             "problem": {"type": "string"},
             "domain": {"type": "string"}},
         "required": ["problem"]},
     "run": run_plan},
    {"name": "problem_route",
     "description": (
         "Recommend which specialist plugin and tools fit a problem "
         "(build_doctor, pc_health, kb_repair, task_recovery and other "
         "bundled plugins), ranked by keyword match. Covers the bundled "
         "specialists only — check the live tool list for anything newer. "
         "Call after problem_plan, before diving into specialist tools."),
     "kind": "native", "access": "read",
     "parameters": {
         "type": "object",
         "properties": {
             "problem": {"type": "string"},
             "domain": {"type": "string"}},
         "required": ["problem"]},
     "run": run_route},
]
