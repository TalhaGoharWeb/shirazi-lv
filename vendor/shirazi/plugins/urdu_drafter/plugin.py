"""Urdu drafter plugin — a style contract plus a living glossary.

WHAT THIS PLUGIN DOES NOT DO: it does not write the Urdu. The model writes
it, in the same breath it calls urdu_draft — because good Urdu rendering is
judgement work (tone, register, which Arabic term to keep), and a lookup
table cannot do judgement.

WHAT IT DOES:
1. Hands you the STYLE CONTRACT every time, so the quality bar is identical
   across a hundred articles: simple scholarly daily-spoken Urdu, fresh
   wording (never literal translation), no AI-dash markers, consistent
   transliteration of Arabic terms.
2. Keeps YOUR glossary (urdu_terms.json): English term -> approved Urdu
   rendering. When a glossary term's English side appears in the text being
   drafted, it is surfaced so the same term never gets three different Urdu
   spellings across the database.

Permissions used: files:write (the glossary JSON).
"""

import json
import os
import time
from pathlib import Path

STYLE_CONTRACT = """URDU STYLE CONTRACT — follow every line:
1. SIMPLE SCHOLARLY DAILY-SPOKEN URDU. Write the way a learned person speaks
   in everyday life — clear, dignified, unpretentious. Not high literary
   Urdu, not street slang.
2. FRESH WORDING, NEVER LITERAL TRANSLATION. Read the English, understand
   the ruling/meaning, then say it anew in Urdu. A translation that mirrors
   English sentence structure is a failed draft.
3. NO AI-DASH MARKERS. Never use the em-dash (—) as a stylistic crutch, and
   avoid the other tells: no "moreover/furthermore" stacks, no bullet-point
   everything, no hollow intensifiers ("very crucial", "extremely vital").
4. ARABIC TERMS STAY ARABIC. Wudu, salah, zakah, sawm, tayammum, najasah —
   keep them in Urdu script as established terms; do not "translate" them
   into awkward Urdu equivalents. Use the GLOSSARY rendering when one exists.
5. CONSISTENCY. The same English term gets the same Urdu rendering every
   time — that is what the glossary is for.
6. COMPLETE AND SELF-CONTAINED. The Urdu must stand alone: a reader who
   never sees the English gets the full meaning."""


def _store_path():
    base = Path(os.environ.get("SHIRAZI_DATA_DIR",
                               str(Path.home() / ".shirazi")))
    d = base / "plugins_data"
    d.mkdir(parents=True, exist_ok=True)
    return d / "urdu_terms.json"


def _load():
    p = _store_path()
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return []


def _save(terms):
    _store_path().write_text(json.dumps(terms, ensure_ascii=False, indent=2),
                             encoding="utf-8")


def _next_id(terms):
    return max([t["id"] for t in terms], default=0) + 1


_last_forgotten = None


def _restore_last_forget():
    global _last_forgotten
    if _last_forgotten is None:
        return
    terms = _load()
    if all(t["id"] != _last_forgotten["id"] for t in terms):
        terms.append(_last_forgotten)
        _save(sorted(terms, key=lambda t: t["id"]))
    _last_forgotten = None


def _matches(text: str, term_en: str) -> bool:
    """Does this glossary term appear in the text? Case-insensitive, whole
    words where the term is a single word; substring for phrases."""
    t = str(text or "").casefold()
    e = str(term_en or "").casefold().strip()
    if not e:
        return False
    if " " not in e:
        import re
        return re.search(r"\b" + re.escape(e) + r"\b", t) is not None
    return e in t


def run_draft(args):
    text = str(args.get("english_text") or "").strip()
    if not text:
        return ("Give me the English text to draft from in `english_text` — "
                "then write the Urdu yourself, following the contract below.")
    topic = str(args.get("topic") or "").strip()
    matched = [t for t in _load() if _matches(text, t.get("term_en", ""))]
    out = [STYLE_CONTRACT, ""]
    if matched:
        out.append("GLOSSARY TERMS FOUND IN THIS TEXT — use these renderings:")
        for t in matched:
            note = f" ({t['note']})" if t.get("note") else ""
            out.append(f"  {t['term_en']} -> {t['term_ur']}{note}")
        out.append("")
    else:
        out.append("No glossary terms matched this text. If you settle a new "
                   "term's Urdu rendering while drafting, add it with "
                   "term_add so the next article stays consistent.")
        out.append("")
    if topic:
        out.append(f"Topic: {topic}")
        out.append("")
    out.append("Now write the Urdu draft in your reply, following the "
               "contract above.")
    return "\n".join(out)


def run_term_add(args):
    en = str(args.get("term_en") or "").strip()
    ur = str(args.get("term_ur") or "").strip()
    if not en or not ur:
        return "I need both the English term and its Urdu rendering."
    terms = _load()
    for t in terms:
        if t.get("term_en", "").casefold() == en.casefold():
            return (f"'{en}' is already in the glossary [{t['id']}] as "
                    f"'{t['term_ur']}'. Forget it first to replace it.")
    term = {"id": _next_id(terms), "term_en": en[:120], "term_ur": ur[:120],
            "note": str(args.get("note") or "").strip()[:300],
            "created": time.time()}
    terms.append(term)
    _save(terms)
    return f"Glossary [{term['id']}]: {en} -> {ur}"


def run_term_list(args):
    terms = _load()
    if not terms:
        return "Glossary is empty. Add terms with term_add as you draft."
    lines = [f"Glossary — {len(terms)} terms:"]
    for t in sorted(terms, key=lambda t: t["id"]):
        note = f" ({t['note']})" if t.get("note") else ""
        lines.append(f"  [{t['id']}] {t['term_en']} -> {t['term_ur']}{note}")
    return "\n".join(lines)


def run_term_forget(args):
    global _last_forgotten
    try:
        tid = int(args.get("id", 0))
    except (TypeError, ValueError):
        return "Give me the [id] from term_list to forget."
    terms = _load()
    doomed = [t for t in terms if t["id"] == tid]
    if not doomed:
        return f"No glossary term with id [{tid}]."
    _last_forgotten = doomed[0]
    _save([t for t in terms if t["id"] != tid])
    return f"Forgot [{tid}]: {doomed[0]['term_en']} -> {doomed[0]['term_ur']}"


TOOLS = [
    {"name": "urdu_draft",
     "description": (
         "Drafting aid for English->Urdu rendering. Pass the English text; "
         "returns the URDU STYLE CONTRACT (simple scholarly daily-spoken "
         "Urdu, fresh wording never literal, no AI-dash markers, Arabic "
         "terms kept, consistency) plus any glossary terms found in the "
         "text. YOU then write the Urdu draft in your reply, following the "
         "contract. Use for articles, quiz explanations, any EN->UR work."),
     "kind": "native", "access": "read",
     "parameters": {
         "type": "object",
         "properties": {
             "english_text": {"type": "string",
                              "description": "The English text to render "
                                             "into Urdu."},
             "topic": {"type": "string",
                       "description": "Optional topic tag."}},
         "required": ["english_text"]},
     "run": run_draft},
    {"name": "term_add",
     "description": (
         "Add a term to the Urdu glossary: the English term and its approved "
         "Urdu rendering. Future urdu_draft calls surface it whenever the "
         "English appears, keeping renderings consistent across articles."),
     "kind": "native", "access": "write",
     "parameters": {
         "type": "object",
         "properties": {
             "term_en": {"type": "string"},
             "term_ur": {"type": "string",
                         "description": "Urdu rendering, in Urdu script."},
             "note": {"type": "string",
                      "description": "Optional usage note."}},
         "required": ["term_en", "term_ur"]},
     "run": run_term_add},
    {"name": "term_list",
     "description": "List the Urdu glossary with ids.",
     "kind": "native", "access": "read",
     "parameters": {"type": "object", "properties": {}},
     "run": run_term_list},
    {"name": "term_forget",
     "description": "Forget one glossary term by [id]. Asks for confirmation "
                    "first (destructive).",
     "kind": "native", "access": "destructive",
     "parameters": {"type": "object",
                    "properties": {"id": {"type": "integer"}}},
     "run": run_term_forget,
     "restore": _restore_last_forget},
]
