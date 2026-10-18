"""MCQ maker plugin — bilingual MCQs for the fiqh content pipeline.

WHO WRITES THE MCQs: you do, in the same breath you call mcq_generate. The
questions arrive as the `mcqs` argument, already written by the model that has
the article in context. This plugin never calls an API of its own.

That is deliberate, not a shortcut. A separate generation call would spend a
request against a daily quota, add latency, and throw away everything already
known — the article text, the target level, the bilingual style contract.
Passing MCQs through as arguments costs nothing extra and keeps all of it.

WHAT THIS PLUGIN DOES: validates every MCQ against the app's database
schema, fixes what is deterministically fixable (whitespace, numeric-string
answer indices), and DROPS what is broken — reporting exactly which items
were dropped and why. A malformed MCQ in the database is worse than a
missing one: it ships to the app.

The schema (matches the quiz database files):
  id, topic, question_en, question_ur, options_en[4], options_ur[4],
  answer_index (0-3), explanation_en, explanation_ur

Quality rules enforced:
- every field present and non-empty
- exactly 4 options in EACH language, aligned in count
- answer_index an integer 0-3
- question self-explanatory: >= 20 characters in each language
  (a question that needs the article open to understand is not app-ready)

Permissions used: none (pure validation, stdlib only).
"""

from __future__ import annotations

import json
import unicodedata

REQUIRED = ("question_en", "question_ur", "options_en", "options_ur",
            "answer_index", "explanation_en", "explanation_ur")
_MIN_QUESTION = 20


def _norm(s) -> str:
    """Compare answers/options without tripping on case, accents or spacing."""
    s = unicodedata.normalize("NFD", str(s or "").strip().casefold())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join("".join(c if (c.isalnum() or c.isspace()) else " "
                            for c in s).split())


def _clean_str(v) -> str:
    return " ".join(str(v or "").split())


def validate_one(raw, idx: int):
    """Return (clean_mcq_or_None, [fix notes], [drop reasons])."""
    fixes, drops = [], []
    if not isinstance(raw, dict):
        return None, fixes, [f"item {idx}: not an object"]

    mcq = {}
    for field in ("question_en", "question_ur",
                  "explanation_en", "explanation_ur"):
        v = _clean_str(raw.get(field))
        if not v:
            drops.append(f"item {idx}: missing/empty '{field}'")
        mcq[field] = v
    if drops:
        return None, fixes, drops

    for field in ("options_en", "options_ur"):
        opts = raw.get(field)
        if not isinstance(opts, list):
            drops.append(f"item {idx}: '{field}' is not a list")
            continue
        cleaned = [_clean_str(o) for o in opts]
        if any(not o for o in cleaned):
            drops.append(f"item {idx}: '{field}' has an empty option")
            continue
        if len(cleaned) != 4:
            drops.append(f"item {idx}: '{field}' has {len(cleaned)} options, "
                         f"need exactly 4")
            continue
        # duplicate options (after normalisation) = a broken question
        if len({_norm(o) for o in cleaned}) != 4:
            drops.append(f"item {idx}: '{field}' has duplicate options")
            continue
        mcq[field] = cleaned
    if drops:
        return None, fixes, drops

    # answer_index: accept int or a numeric string ("2") — fix deterministically
    ai = raw.get("answer_index")
    if isinstance(ai, str) and ai.strip().isdigit():
        ai = int(ai.strip())
        fixes.append(f"item {idx}: answer_index coerced from string")
    if not isinstance(ai, int) or isinstance(ai, bool) or not 0 <= ai <= 3:
        drops.append(f"item {idx}: answer_index must be 0-3, "
                     f"got {raw.get('answer_index')!r}")
        return None, fixes, drops
    mcq["answer_index"] = ai

    # self-explanatory: a question that needs the article open is not app-ready
    for field in ("question_en", "question_ur"):
        if len(mcq[field]) < _MIN_QUESTION:
            drops.append(f"item {idx}: '{field}' too short "
                         f"({len(mcq[field])} chars) to be self-explanatory")
    if drops:
        return None, fixes, drops

    mcq["topic"] = _clean_str(raw.get("topic"))
    return mcq, fixes, drops


def _process(mcqs, id_prefix: str, topic: str):
    """Validate a raw list; return (batch, report_lines)."""
    batch, report = [], []
    kept, dropped, fixed = 0, 0, 0
    for i, raw in enumerate(mcqs or []):
        mcq, fixes, drops = validate_one(raw, i + 1)
        if drops:
            dropped += 1
            report.extend("DROPPED: " + d for d in drops)
            continue
        kept += 1
        fixed += len(fixes)
        report.extend("FIXED: " + f for f in fixes)
        mcq["id"] = f"{id_prefix}{kept}"
        if topic and not mcq["topic"]:
            mcq["topic"] = topic
        batch.append(mcq)
    head = (f"MCQ batch: {kept} kept, {dropped} dropped, {fixed} auto-fixed "
            f"out of {len(mcqs or [])} submitted.")
    return batch, [head] + report


def run_generate(args):
    count = args.get("count", 5)
    try:
        count = max(1, min(int(count), 30))
    except (TypeError, ValueError):
        count = 5
    mcqs = args.get("mcqs")
    if not mcqs:
        return ("I need the MCQs themselves — read the article, write "
                f"{count} bilingual MCQs, and call mcq_generate again with "
                "them in `mcqs`. Each needs: question_en, question_ur "
                "(self-explanatory, 20+ chars each), options_en[4], "
                "options_ur[4], answer_index 0-3, explanation_en, "
                "explanation_ur.")
    batch, report = _process(mcqs, str(args.get("id_prefix") or "q"),
                             _clean_str(args.get("topic")))
    out = ["\n".join(report), "",
           "BATCH JSON (app-ready, save as-is):",
           json.dumps(batch, ensure_ascii=False, indent=2)]
    return "\n".join(out)


def run_validate(args):
    batch_in = args.get("batch")
    if not batch_in:
        return "Pass an existing MCQ batch (list of objects) in `batch`."
    clean, report = [], []
    kept = dropped = fixed = 0
    for i, raw in enumerate(batch_in):
        mcq, fixes, drops = validate_one(raw, i + 1)
        if drops:
            dropped += 1
            report.extend("DROPPED: " + d for d in drops)
            continue
        kept += 1
        fixed += len(fixes)
        report.extend("FIXED: " + f for f in fixes)
        mcq["id"] = _clean_str(raw.get("id")) or f"q{kept}"
        clean.append(mcq)
    head = (f"Validation: {kept} valid, {dropped} dropped, {fixed} auto-fixed "
            f"out of {len(batch_in)}.")
    return "\n".join([head] + report + ["",
                      json.dumps(clean, ensure_ascii=False, indent=2)])


TOOLS = [
    {"name": "mcq_generate",
     "description": (
         "Generates a validated batch of bilingual MCQs from an article. YOU "
         "write the MCQs — read the article first, then write `count` of "
         "them in the user's quality bar: every question FULLY "
         "self-explanatory (complete context inside the question itself, "
         "20+ characters per language), 4 options per language, one correct "
         "answer, bilingual explanation. Write fresh, scholarly wording — "
         "never copy the article verbatim. Pass them in `mcqs`; the plugin "
         "validates the schema, fixes the fixable, drops the broken, and "
         "returns the app-ready JSON batch plus a validation report. Say "
         "one short sentence first so the user doesn't hear silence while "
         "you compose."),
     "kind": "native", "access": "read",
     "parameters": {
         "type": "object",
         "properties": {
             "article_text": {"type": "string",
                              "description": "The article to base MCQs on "
                                             "(for your reference while "
                                             "writing)."},
             "count": {"type": "integer",
                       "description": "How many MCQs to write (1-30)."},
             "topic": {"type": "string",
                       "description": "Topic tag, e.g. 'wudu', 'salah'."},
             "id_prefix": {"type": "string",
                           "description": "ID prefix, e.g. 'mfb-ch2-s1-q'."},
             "mcqs": {"type": "array",
                      "description": "The MCQs you wrote, in schema order.",
                      "items": {
                          "type": "object",
                          "properties": {
                              "question_en": {"type": "string"},
                              "question_ur": {"type": "string"},
                              "options_en": {"type": "array",
                                             "items": {"type": "string"}},
                              "options_ur": {"type": "array",
                                             "items": {"type": "string"}},
                              "answer_index": {"type": "integer",
                                               "description": "0-3"},
                              "explanation_en": {"type": "string"},
                              "explanation_ur": {"type": "string"}},
                          "required": ["question_en", "question_ur",
                                       "options_en", "options_ur",
                                       "answer_index", "explanation_en",
                                       "explanation_ur"]}}},
         "required": ["mcqs"]},
     "run": run_generate},
    {"name": "mcq_validate",
     "description": (
         "Validates an EXISTING MCQ batch (from a file, an earlier draft, "
         "or another session) against the app schema. Same rules as "
         "mcq_generate: schema complete, 4 aligned options per language, "
         "answer_index 0-3, self-explanatory questions. Returns the clean "
         "batch JSON plus a report of dropped/fixed items."),
     "kind": "native", "access": "read",
     "parameters": {
         "type": "object",
         "properties": {
             "batch": {"type": "array",
                       "description": "Existing MCQ objects to validate.",
                       "items": {"type": "object"}}},
         "required": ["batch"]},
     "run": run_validate},
]
