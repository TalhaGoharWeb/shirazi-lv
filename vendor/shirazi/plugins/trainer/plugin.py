"""Trainer plugin — teach Shirazi, properly.

An honest note on what "training" means here: this is NOT neural-network
training. No weights change. What it IS: a structured, reviewable knowledge
base where the user teaches facts, preferences, corrections and custom
commands — each listed with an id, testable with train_test, deletable with
training_forget. That beats the alternative (hoping something said in chat
three weeks ago is still remembered) because it is explicit: the user can
see exactly what was taught, test whether it stuck, and remove what didn't.

How the model should use it:
- When the user teaches in conversation ("yaad rakho", "seekho", "note kar
  lo", "ainda se ..."), call the matching train_* tool — don't just reply
  "yaad kar liya".
- Before answering questions about the user, their work, or how to behave,
  check training_list (facts + preferences + commands).
- When corrected ("ghalat jawab diya", "nahi, aisa nahi"), call
  train_correction with what was wrong and what is right.
- Durable facts (name, shop, long-term preferences) should ALSO go to the
  normal long-term memory tools — the trainer is the curated review copy.

Storage: <data_dir>/plugins_data/trainer.json (plain JSON, yours to keep).
Permissions used: files:write (the JSON store).
"""

import json
import os
import time
from pathlib import Path

KINDS = ("fact", "preference", "correction", "command")


def _store_path():
    base = Path(os.environ.get("SHIRAZI_DATA_DIR",
                               str(Path.home() / ".shirazi")))
    d = base / "plugins_data"
    d.mkdir(parents=True, exist_ok=True)
    return d / "trainer.json"


def _load():
    p = _store_path()
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return []


def _save(items):
    _store_path().write_text(json.dumps(items, ensure_ascii=False, indent=2),
                             encoding="utf-8")


def _next_id(items):
    return max([i["id"] for i in items], default=0) + 1


def _fmt(item):
    k = item["kind"]
    ts = time.strftime("%Y-%m-%d", time.localtime(item["created"]))
    if k == "fact":
        body = item["text"]
    elif k == "preference":
        body = "Preference: " + item["text"]
    elif k == "correction":
        body = (f"Correction — wrong was: {item.get('wrong', '')} | "
                f"right is: {item.get('right', '')}")
    elif k == "command":
        body = f"Command '{item.get('name', '')}': {item.get('text', '')}"
    else:
        body = item["text"]
    topic = f" [{item['topic']}]" if item.get("topic") else ""
    return f"[{item['id']}] ({k}{topic}, {ts}) {body}"


_last_forgotten = None


def _restore_last_forget():
    global _last_forgotten
    if _last_forgotten is None:
        return
    items = _load()
    if all(i["id"] != _last_forgotten["id"] for i in items):
        items.append(_last_forgotten)
        _save(sorted(items, key=lambda i: i["id"]))
    _last_forgotten = None


def _add(kind, text, topic="", extra=None):
    text = str(text or "").strip()
    if not text:
        return f"Nothing to teach — the {kind} text was empty."
    items = _load()
    item = {"id": _next_id(items), "kind": kind, "text": text[:2000],
            "topic": str(topic or "").strip()[:120], "created": time.time()}
    if extra:
        item.update(extra)
    items.append(item)
    _save(items)
    return (f"Seekh liya [{item['id']}]: {text[:120]}. "
            f"Test it anytime with train_test, remove it with training_forget.")


def run_fact(args):
    return _add("fact", args.get("text"), args.get("topic"))


def run_preference(args):
    return _add("preference", args.get("text"), args.get("topic"))


def run_correction(args):
    wrong = str(args.get("wrong") or "").strip()
    right = str(args.get("right") or "").strip()
    if not wrong or not right:
        return "I need both: what was wrong, and what is right."
    return _add("correction", right, args.get("topic"),
                {"wrong": wrong[:1000], "right": right[:2000]})


def run_command(args):
    name = str(args.get("name") or "").strip().lower()
    template = str(args.get("template") or "").strip()
    if not name or not template:
        return "Give me the command's trigger name and what it should do."
    items = _load()
    for i in items:
        if i["kind"] == "command" and i.get("name") == name:
            return (f"A command called '{name}' already exists [{i['id']}]. "
                    f"Forget it first if you want to replace it.")
    return _add("command", template, "", {"name": name[:60]})


def run_list(args):
    kind = str(args.get("kind") or "").strip().lower()
    items = _load()
    if kind:
        if kind not in KINDS:
            return f"kind must be one of: {', '.join(KINDS)}."
        items = [i for i in items if i["kind"] == kind]
    if not items:
        return "Nothing taught yet. Teach me with train_fact / train_preference / train_correction / train_command."
    counts = {k: sum(1 for i in items if i["kind"] == k) for k in KINDS}
    head = (f"Taught so far — {len(items)} items "
            f"({', '.join(f'{v} {k}' for k, v in counts.items() if v)}):")
    return head + "\n" + "\n".join(_fmt(i) for i in
                                   sorted(items, key=lambda i: i["id"]))


def run_forget(args):
    global _last_forgotten
    try:
        tid = int(args.get("id", 0))
    except (TypeError, ValueError):
        return "Give me the [id] from training_list to forget."
    items = _load()
    doomed = [i for i in items if i["id"] == tid]
    if not doomed:
        return f"No taught item with id [{tid}]."
    _last_forgotten = doomed[0]
    _save([i for i in items if i["id"] != tid])
    return f"Forgot [{tid}]: {doomed[0]['text'][:120]}"


def run_test(args):
    """Build a self-test from what was taught.

    Returns question prompts derived from facts/preferences/corrections. The
    model answers each from its own recall (checking long-term memory where
    needed), then compares against the stored answers below and reports an
    honest score. Corrections are tested as: "what should you NOT do here?"
    """
    topic = str(args.get("topic") or "").strip().lower()
    items = [i for i in _load() if i["kind"] in ("fact", "preference",
                                                "correction")]
    if topic:
        items = [i for i in items if topic in str(i.get("topic", "")).lower()
                 or topic in i["text"].lower()
                 or topic in str(i.get("right", "")).lower()]
    if not items:
        return "Nothing to test on yet — teach me something first."
    items = items[:10]
    lines = ["SELF-TEST — answer each from your own recall first (check your "
             "memory tools if unsure), THEN compare with the answers and give "
             "an honest score out of "
             f"{len(items)}.", ""]
    for n, i in enumerate(items, 1):
        if i["kind"] == "correction":
            lines.append(f"{n}. You were corrected on this before — what is "
                         f"the RIGHT thing to do/say here? "
                         f"(Context: {i.get('wrong', '')[:120]})")
        elif i["kind"] == "preference":
            lines.append(f"{n}. What is your standing preference about: "
                         f"{i.get('topic') or i['text'][:80]}?")
        else:
            lines.append(f"{n}. What were you taught"
                         f"{(' about ' + i['topic']) if i.get('topic') else ''}? "
                         f"(Hint: {i['text'][:60]}...)")
    lines += ["", "ANSWERS (compare after answering):"]
    for n, i in enumerate(items, 1):
        ans = i.get("right") if i["kind"] == "correction" else i["text"]
        lines.append(f"{n}. {ans[:200]}")
    lines.append("")
    lines.append("Score yourself honestly and tell the user what you missed — "
                 "missed items may need re-teaching or a memory save.")
    return "\n".join(lines)


TOOLS = [
    {"name": "train_fact",
     "description": (
         "Teach Shirazi a FACT — 'meri shop ka naam DottedCreatives hai', "
         "'I work in PKR'. Use when the user says 'yaad rakho', 'seekho', "
         "'note kar lo', or tells you something durable about themselves, "
         "their work, or their world. If it's truly long-term (name, shop, "
         "core work), ALSO save it with the normal memory tools."),
     "kind": "native", "access": "write",
     "parameters": {"type": "object",
                    "properties": {
                        "text": {"type": "string",
                                 "description": "The fact, as taught."},
                        "topic": {"type": "string",
                                  "description": "Short topic tag, e.g. "
                                                 "'shop', 'family'."}},
                    "required": ["text"]},
     "run": run_fact},
    {"name": "train_preference",
     "description": (
         "Teach Shirazi a PREFERENCE about how to behave — 'hamesha concise "
         "jawab do', 'Urdu mein jawab do', 'har email bhejne se pehle pucho'. "
         "Check training_list before answering behaviour questions."),
     "kind": "native", "access": "write",
     "parameters": {"type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "topic": {"type": "string"}},
                    "required": ["text"]},
     "run": run_preference},
    {"name": "train_correction",
     "description": (
         "Record a CORRECTION when you got something wrong — 'pichli baar "
         "tumne X kaha tha, sahi Y hai'. Stores both so the mistake isn't "
         "repeated. Use it yourself whenever the user corrects you; don't "
         "wait to be asked."),
     "kind": "native", "access": "write",
     "parameters": {"type": "object",
                    "properties": {
                        "wrong": {"type": "string",
                                  "description": "What was wrong."},
                        "right": {"type": "string",
                                  "description": "What is right instead."},
                        "topic": {"type": "string"}},
                    "required": ["wrong", "right"]},
     "run": run_correction},
    {"name": "train_command",
     "description": (
         "Teach a CUSTOM COMMAND: a trigger name plus what it should do — "
         "e.g. name 'month_end', template 'Summarize my Etsy sales and apply "
         "the Pakistan fee math'. When the user says the trigger, follow the "
         "template. Names must be unique."),
     "kind": "native", "access": "write",
     "parameters": {"type": "object",
                    "properties": {
                        "name": {"type": "string",
                                 "description": "Trigger phrase, e.g. "
                                                "'month_end'."},
                        "template": {"type": "string",
                                     "description": "What to do when "
                                                    "triggered."}},
                    "required": ["name", "template"]},
     "run": run_command},
    {"name": "training_list",
     "description": (
         "List everything taught so far — facts, preferences, corrections, "
         "commands — with ids. Consult this before answering questions about "
         "the user, their work, or how you should behave."),
     "kind": "native", "access": "read",
     "parameters": {"type": "object",
                    "properties": {
                        "kind": {"type": "string",
                                 "enum": ["fact", "preference", "correction",
                                          "command", ""],
                                 "description": "Filter by kind, or empty "
                                                "for all."}}},
     "run": run_list},
    {"name": "training_forget",
     "description": "Forget one taught item by its [id] from training_list. "
                    "Asks for confirmation first (destructive).",
     "kind": "native", "access": "destructive",
     "parameters": {"type": "object",
                    "properties": {"id": {"type": "integer"}}},
     "run": run_forget,
     "restore": _restore_last_forget},
    {"name": "train_test",
     "description": (
         "Self-test: builds questions from what was taught. Answer each from "
         "your own recall FIRST (use memory tools if unsure), then compare "
         "with the answers and report an honest score. Use when the user "
         "says 'test yourself', 'dekho kya yaad hai', or after a teaching "
         "session."),
     "kind": "native", "access": "read",
     "parameters": {"type": "object",
                    "properties": {
                        "topic": {"type": "string",
                                  "description": "Optional topic filter."}}},
     "run": run_test},
]
