"""Kharcha — a spoken expense tracker (Shirazi LV plugin).

From MYRA ULTRA's quick-features layer: the highest daily-usefulness-per-line
feature in that app is a dead-simple expense log. Shirazi had notes and
tasks but no money log. Entries live in the app's own data dir
(~/.shirazi/shirazi_lv_memory/expenses.json, SHIRAZI_DATA_DIR honoured —
the same place the episodic memory backend stores its files).
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

PLUGIN = {
    "name": "shirazi_expense",
    "description": (
        "Tracks daily expenses (kharcha). action='add' with item and amount records an "
        "expense ('500 ka petrol', '1200 ki sabzi'). action='summary' reports this "
        "month's total and the top categories. action='today' reports today's total. "
        "action='recent' lists the last few entries. Amounts are rupees. Use whenever "
        "the user mentions spending money or asks 'is month kitna kharcha hua'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["add", "summary", "today", "recent"],
                "description": "add = record an expense; summary = this month; today = today's total; recent = last entries.",
            },
            "item": {"type": "STRING", "description": "What the money was spent on (action='add')."},
            "amount": {"type": "NUMBER", "description": "Amount in rupees (action='add')."},
            "category": {
                "type": "STRING",
                "description": "Optional category: khana, safar, bill, kharidari, sehat, taleem, other. "
                               "Guess from the item when not given.",
            },
        },
        "required": ["action"],
    },
}

PLUGIN_SETTINGS = None

_CATEGORIES = ("khana", "safar", "bill", "kharidari", "sehat", "taleem", "other")


def _log(player, msg: str) -> None:
    if player:
        try:
            player.write_log(f"SHIRAZI: {msg}")
        except Exception:
            pass


def _store_path() -> Path:
    base = Path(os.environ.get("SHIRAZI_DATA_DIR", str(Path.home() / ".shirazi")))
    d = base / "shirazi_lv_memory"
    d.mkdir(parents=True, exist_ok=True)
    return d / "expenses.json"


def _load() -> list:
    try:
        p = _store_path()
        if p.is_file():
            data = json.loads(p.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
    except Exception:
        pass
    return []


def _save(entries: list) -> None:
    p = _store_path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(entries, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    tmp.replace(p)


def _fmt(n: float) -> str:
    return f"Rs {n:,.0f}" if float(n).is_integer() else f"Rs {n:,.2f}"


def _add(params: dict, player) -> str:
    item = str(params.get("item") or "").strip()
    try:
        amount = float(params.get("amount") or 0)
    except Exception:
        amount = 0.0
    if not item:
        return "Kharcha note karne ke liye cheez ka naam chahiye — kya kharida?"
    if amount <= 0:
        return f"'{item}' ki raqam kitni thi? Amount bata dein, note kar dunga."
    cat = str(params.get("category") or "other").strip().lower()
    if cat not in _CATEGORIES:
        cat = "other"
    entries = _load()
    entries.append({
        "ts": datetime.now().isoformat(timespec="seconds"),
        "item": item, "amount": amount, "category": cat,
    })
    _save(entries)
    month = datetime.now().strftime("%Y-%m")
    month_total = sum(e["amount"] for e in entries
                      if str(e.get("ts", "")).startswith(month))
    _log(player, f"Expense added: {item} {_fmt(amount)} ({cat})")
    return (f"Note kar liya: {item}, {_fmt(amount)}. "
            f"Is month ka total ab {_fmt(month_total)} hai.")


def _summary() -> str:
    entries = _load()
    if not entries:
        return "Abhi tak koi kharcha note nahi hua. Pehla kharcha bata dein, main likh dunga."
    month = datetime.now().strftime("%Y-%m")
    rows = [e for e in entries if str(e.get("ts", "")).startswith(month)]
    if not rows:
        return "Is month abhi koi kharcha note nahi hua."
    total = sum(e["amount"] for e in rows)
    by_cat: dict[str, float] = {}
    for e in rows:
        by_cat[e.get("category", "other")] = \
            by_cat.get(e.get("category", "other"), 0.0) + e["amount"]
    top = sorted(by_cat.items(), key=lambda kv: -kv[1])[:3]
    parts = ", ".join(f"{c}: {_fmt(v)}" for c, v in top)
    return (f"Is month kul {len(rows)} entries mein {_fmt(total)} kharcha hua. "
            f"Sab se zyada: {parts}.")


def _today() -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    rows = [e for e in _load() if str(e.get("ts", "")).startswith(today)]
    if not rows:
        return "Aaj abhi koi kharcha note nahi hua."
    total = sum(e["amount"] for e in rows)
    items = ", ".join(f"{e['item']} {_fmt(e['amount'])}" for e in rows[-4:])
    return f"Aaj ka kharcha {_fmt(total)} — {items}."


def _recent() -> str:
    entries = _load()
    if not entries:
        return "Abhi tak koi kharcha note nahi hua."
    last = entries[-5:][::-1]
    parts = []
    for e in last:
        day = str(e.get("ts", ""))[:10]
        parts.append(f"{day}: {e.get('item', '?')} {_fmt(e.get('amount', 0))}")
    return "Recent kharchay: " + "; ".join(parts) + "."


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Mark-LV plugin contract: never raise; return a spoken string."""
    try:
        params = dict(parameters or {})
        action = str(params.get("action") or "").strip().lower()
        if action == "add":
            return _add(params, player)
        if action == "summary":
            return _summary()
        if action == "today":
            return _today()
        if action == "recent":
            return _recent()
        return _summary()
    except Exception as e:
        return f"Kharcha tracker failed: {e}"
