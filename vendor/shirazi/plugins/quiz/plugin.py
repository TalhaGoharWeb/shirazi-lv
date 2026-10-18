"""Quiz plugin — test the user on anything, in any language.

WHO WRITES THE QUESTIONS: you do, in the same breath you call quiz_start.
The questions arrive as arguments, already written by the model that is
mid-conversation with the user. This plugin never calls an API of its own.

That is deliberate, not a shortcut. A separate generation call would spend a
request against a daily quota, add seconds of latency, and throw away
everything already known — the user's level, their language, the file just
discussed, what they got wrong last week. Passing questions through as
arguments costs nothing extra and keeps all of it.

IT KEEPS NO STORE OF ITS OWN: no quiz_history.json, no private database. What
is worth carrying between sessions goes to long-term memory through the
normal memory tools, and only when there is real continuity (working through
a language, repeatedly missing the same tense). A score from one Tuesday is
not that.

Grading is language-agnostic: answers are compared after Unicode
normalisation rather than per-language tables, and anything the comparison
cannot decide is handed back to you to mark rather than marked wrong.

Permissions used: none (stdlib only).
"""

from __future__ import annotations

import unicodedata

_MAX_QUESTIONS = 20
_MAX_TEXT = 600
_MAX_OPTION = 200
_TYPES = ("multiple_choice", "true_false", "fill_blank", "open")


# ── answer comparison ────────────────────────────────────────────────────────
# Normalise, do not pattern-match. Stripping accents and case makes "café",
# "CAFE" and "cafe" agree without a rule per language, so the same code path
# serves Urdu, Turkish, Greek and Vietnamese alike. Whatever this cannot
# decide is handed back for human/model marking instead of being called wrong.

def _norm(s) -> str:
    s = unicodedata.normalize("NFD", str(s or "").strip().casefold())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = "".join(c if (c.isalnum() or c.isspace()) else " " for c in s)
    return " ".join(s.split())


def _truthy(s):
    """A true/false answer, whatever it was displayed as."""
    t = _norm(s)
    if t in ("true", "t", "1", "yes", "haan", "jee", "sahi", "durust"):
        return True
    if t in ("false", "f", "0", "no", "na", "nahi", "ghalat"):
        return False
    return None


def grade(question: dict, given: str):
    """True = right, False = wrong, None = mark it yourself (the model)."""
    qtype = str(question.get("type") or "").strip()
    correct = str(question.get("answer") or "")
    opts = question.get("options") or []
    if not str(given or "").strip():
        return False
    if qtype == "open":
        return None
    # An answer key matching none of the buttons cannot mark anything — the
    # model sometimes replies with a letter. clean_questions resolves most;
    # whatever survives is deferred rather than marked wrong.
    if opts and not any(_norm(correct) == _norm(o) for o in opts):
        return None
    if _norm(given) == _norm(correct):
        return True
    if qtype == "true_false":
        a, b = _truthy(given), _truthy(correct)
        if a is not None and b is not None:
            return a == b
        return False
    if qtype == "multiple_choice":
        return False
    # fill_blank: near misses are common and often still right — defer.
    return None


# ── validation ───────────────────────────────────────────────────────────────
# Questions come from a language model: treat as untrusted input, drop the
# unusable rather than presenting a broken question.

def _resolve_answer(answer: str, opts: list) -> str:
    """Point the answer key at one of the buttons (letter/number → option)."""
    if not opts:
        return answer
    for o in opts:
        if _norm(answer) == _norm(o):
            return o
    token = _norm(answer)
    if len(token) == 1 and "a" <= token <= "z":
        i = ord(token) - ord("a")
        if i < len(opts):
            return opts[i]
    if token.isdigit():
        i = int(token) - 1
        if 0 <= i < len(opts):
            return opts[i]
    return answer


def clean_questions(raw) -> list:
    out = []
    for q in (raw or [])[:_MAX_QUESTIONS]:
        if not isinstance(q, dict):
            continue
        text = str(q.get("question") or "").strip()[:_MAX_TEXT]
        answer = str(q.get("answer") or "").strip()[:_MAX_TEXT]
        if not text or not answer:
            continue
        qtype = str(q.get("type") or "").strip()
        if qtype not in _TYPES:
            qtype = "multiple_choice" if q.get("options") else "open"
        opts, seen = [], set()
        for o in (q.get("options") or []):
            o = str(o).strip()[:_MAX_OPTION]
            if o and _norm(o) not in seen:
                seen.add(_norm(o))
                opts.append(o)
        if qtype == "multiple_choice" and len(opts) < 2:
            qtype = "open"
        if qtype == "true_false" and len(opts) != 2:
            opts = ["True", "False"]
        shown = opts if qtype in ("multiple_choice", "true_false") else []
        out.append({
            "type": qtype,
            "question": text,
            "options": shown,
            "answer": _resolve_answer(answer, shown),
            "note": str(q.get("note") or "").strip()[:_MAX_TEXT],
        })
    return out


# ── tools ────────────────────────────────────────────────────────────────────

def run_start(args):
    questions = clean_questions(args.get("questions"))
    if not questions:
        return ("I need the questions themselves — write them and call "
                "quiz_start again with them.")
    topic = str(args.get("topic") or "").strip()
    lines = []
    if topic:
        lines.append(f"Quiz: {topic}")
        lines.append("")
    for i, q in enumerate(questions, 1):
        lines.append(f"{i}. {q['question']}")
        for j, o in enumerate(q["options"]):
            lines.append(f"   {chr(65 + j)}) {o}")
        if q["type"] == "fill_blank":
            lines.append("   (fill in the blank)")
        lines.append("")
    lines.append("Present these to the user one at a time in conversation. "
                 "When they answer, call quiz_grade with the question and "
                 "their answer — or mark 'open' questions yourself.")
    return "\n".join(lines).strip()


def run_grade(args):
    question = args.get("question")
    given = str(args.get("given") or "")
    if not isinstance(question, dict) or not question.get("question"):
        return "Pass the question (as you received it from quiz_start) and the user's answer."
    result = grade(question, given)
    note = str(question.get("note") or "").strip()
    if result is True:
        out = "Correct."
    elif result is False:
        out = (f"Not quite — the answer is: {question.get('answer')}.")
    else:
        out = ("I can't mark this one mechanically — judge it yourself "
               "against the model answer.")
        if question.get("answer"):
            out += f" Model answer: {question['answer']}"
    if note:
        out += f" Note for the user: {note}"
    return out


def run_stop(args):
    return ("Quiz cleared. If anything from it is worth remembering long-term "
            "(e.g. a topic they keep missing), store it with the memory tools.")


TOOLS = [
    {"name": "quiz_start",
     "description": (
         "Starts a quiz on screen/in chat. Use when the user wants to be "
         "tested, drilled or revised on ANY topic — 'test me', 'quiz me', "
         "'mujhe test karo'. YOU WRITE THE QUESTIONS and pass them in "
         "`questions`, in the user's own language, pitched at their level, "
         "mixing types (not a page of identical multiple-choice). Say one "
         "short sentence naming the topic FIRST ('French subjunctive par "
         "test karta hoon...'), then call. If they uploaded a file, read it "
         "first and base questions on it. This returns immediately with the "
         "validated questions — present them one at a time; grade each "
         "answer with quiz_grade."),
     "kind": "native", "access": "read",
     "parameters": {
         "type": "object",
         "properties": {
             "topic": {"type": "string",
                       "description": "Short name of what's tested, in the "
                                      "user's language."},
             "questions": {
                 "type": "array",
                 "description": "1-20 questions, in order.",
                 "items": {
                     "type": "object",
                     "properties": {
                         "type": {"type": "string",
                                  "enum": ["multiple_choice", "true_false",
                                           "fill_blank", "open"]},
                         "question": {"type": "string"},
                         "options": {"type": "array",
                                     "items": {"type": "string"},
                                     "description": "3-5 choices for "
                                                    "multiple_choice; exactly "
                                                    "2 (true/false words in "
                                                    "the user's language) for "
                                                    "true_false."},
                         "answer": {"type": "string",
                                    "description": "Correct answer, written "
                                                   "exactly as in options "
                                                   "when there are options."},
                         "note": {"type": "string",
                                  "description": "One-line explanation shown "
                                                 "after they answer."},
                     },
                     "required": ["type", "question", "answer"]}}},
         "required": ["questions"]},
     "run": run_start},
    {"name": "quiz_grade",
     "description": (
         "Grades one quiz answer. Pass the question exactly as quiz_start "
         "returned it, plus the user's answer text. Returns Correct / the "
         "right answer / a deferral for you to mark yourself (open "
         "questions, near-misses). Handles 'haan'/'na' and yes/no in any "
         "language for true/false."),
     "kind": "native", "access": "read",
     "parameters": {
         "type": "object",
         "properties": {
             "question": {"type": "object",
                          "description": "The question dict from quiz_start."},
             "given": {"type": "string",
                       "description": "What the user answered."}},
         "required": ["question", "given"]},
     "run": run_grade},
    {"name": "quiz_stop",
     "description": "Clears a quiz the user wants to abandon.",
     "kind": "native", "access": "read",
     "parameters": {"type": "object", "properties": {}},
     "run": run_stop},
]
