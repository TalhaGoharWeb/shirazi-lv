"""Document review plugin — explain what a document actually says.

A lease, an insurance policy, a phone contract, a loan agreement, terms of
service, a job offer, a consent form, a government letter. You read it first
(uploaded file, screen, photo, pasted text — all reach you through existing
machinery), then call this with what YOU found. This lays the findings out,
ordered by how much they matter.

WHY THIS PLUGIN CONTAINS NO LEGAL KNOWLEDGE: any it contained would be wrong
somewhere. A "red flag" checklist works in the country it was written for and
quietly misleads everywhere else. The reading is done by the model already in
the conversation, in the document's own language; this receives findings and
never decides what a finding is. That is what lets the same code serve an
Urdu rental agreement and an English job offer without knowing either exists.

Permissions used: none (stdlib only). No keys, no network calls.
"""

from __future__ import annotations

# Severity is an ordinal, not a category — the only thing claimed about a
# finding is how far up the page it belongs. Three levels is what a person
# can act on: changes their decision, should be aware, context.
_LEVELS = ("serious", "caution", "note")
_RANK = {name: i for i, name in enumerate(_LEVELS)}

_MAX_FINDINGS = 30
_MAX_QUOTE = 400
_MAX_TEXT = 1200


def _clip(s, limit: int) -> str:
    s = str(s or "").strip()
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"


def clean_findings(raw) -> list:
    """Findings come from a language model: treat as untrusted, drop what
    cannot be rendered, sort by severity so the clause that could cost money
    is never below a note about office hours."""
    out = []
    for f in (raw or []):
        if not isinstance(f, dict):
            continue
        heading = _clip(f.get("heading"), 120)
        detail = _clip(f.get("detail"), _MAX_TEXT)
        if not heading and not detail:
            continue
        sev = str(f.get("severity") or "").strip().lower()
        if sev not in _RANK:
            sev = "note"
        out.append({
            "heading": heading or detail[:60],
            "detail": detail,
            "severity": sev,
            "quote": _clip(f.get("quote"), _MAX_QUOTE),
            "suggestion": _clip(f.get("suggestion"), 300),
        })
    out.sort(key=lambda f: _RANK[f["severity"]])
    return out[:_MAX_FINDINGS]


def tally(findings: list) -> dict:
    return {lvl: sum(1 for f in findings if f["severity"] == lvl)
            for lvl in _LEVELS}


def run_review(args):
    title = _clip(args.get("title"), 120)
    summary = _clip(args.get("summary"), _MAX_TEXT)
    findings = clean_findings(args.get("findings"))
    unclear = [_clip(u, 300) for u in (args.get("unclear") or [])
               if str(u or "").strip()][:10]

    if not findings and not summary:
        return ("Read the document first — the uploaded file, the screen, "
                "or the photo — then call document_review with what you "
                "found.")

    lines = []
    if title:
        lines += [title.upper(), ""]
    if summary:
        lines += [summary, ""]
    for f in findings:
        lines.append(f"[{f['severity'].upper()}] {f['heading']}")
        lines.append(f"    {f['detail']}")
        if f["quote"]:
            lines.append(f"    \"{f['quote']}\"")
        if f["suggestion"]:
            lines.append(f"    → {f['suggestion']}")
        lines.append("")
    if unclear:
        lines.append("Not settled by the document:")
        lines += [f"  · {u}" for u in unclear]
        lines.append("")

    counts = tally(findings)
    bits = [f"{counts[l]} {l}" for l in _LEVELS if counts[l]]
    spoken = (f"{len(findings)} points from {title or 'the document'}"
              + (f" — {', '.join(bits)}" if bits else "") + ".")
    if counts["serious"]:
        spoken += " Say the serious ones first, briefly, in their language."
    if unclear:
        spoken += f" {len(unclear)} things the document doesn't settle."
    lines.append(f"(Say aloud: {spoken})")
    return "\n".join(lines).strip()


TOOLS = [
    {"name": "document_review",
     "description": (
         "Lays out a document's contents: what it is, what agreeing commits "
         "the user to, and each point worth knowing before they sign — "
         "ordered by severity. Use for contracts, policies, loan/subscription "
         "agreements, terms of service, offer letters, official forms. "
         "'Explain this contract', 'what am I signing', 'is mein koi masla "
         "to nahi'. FIRST read the text yourself (uploaded file, screen, "
         "photo they showed), THEN call with your findings — this holds no "
         "legal knowledge and applies no checklist, because what counts as a "
         "warning depends on the document, the country and the person. Write "
         "every field in the user's own language, quote the document's real "
         "wording, mark severity by what would actually change their "
         "decision, and say plainly in `unclear` what the document doesn't "
         "settle. You are not a lawyer: explain the text, suggest "
         "professional help when the stakes justify it."),
     "kind": "native", "access": "read",
     "parameters": {
         "type": "object",
         "properties": {
             "title": {"type": "string",
                       "description": "What the document is, in the user's "
                                      "language."},
             "summary": {"type": "string",
                         "description": "One or two sentences: what it's for "
                                        "and what accepting commits them to."},
             "findings": {
                 "type": "array",
                 "description": "Points worth knowing, most important first. "
                                "Leave out the routine.",
                 "items": {
                     "type": "object",
                     "properties": {
                         "heading": {"type": "string"},
                         "detail": {"type": "string",
                                    "description": "What it means for them, "
                                                   "plainly, with the numbers "
                                                   "and deadlines."},
                         "severity": {"type": "string",
                                      "enum": ["serious", "caution", "note"],
                                      "description": "'serious' sparingly — "
                                                     "if everything is "
                                                     "serious, nothing is."},
                         "quote": {"type": "string",
                                   "description": "The document's own wording, "
                                                  "copied exactly."},
                         "suggestion": {"type": "string",
                                        "description": "What they could do: a "
                                                       "question to ask, a "
                                                       "term to negotiate."}},
                     "required": ["heading", "detail", "severity"]}},
             "unclear": {"type": "array", "items": {"type": "string"},
                         "description": "What the document leaves "
                                        "unanswered — say so, don't guess."}},
         "required": ["title", "findings"]},
     "run": run_review},
]
