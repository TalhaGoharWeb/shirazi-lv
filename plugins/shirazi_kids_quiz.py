"""Bachon ki Dunya — fun quiz for kids (Shirazi LV plugin).

Asks a playful question from one of the Bachon ki Dunya stories and can check
the child's answer with a warm, encouraging response. Keeps learning joyful —
praise for right answers, gentle hints for wrong ones.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _kids_content import quiz_question  # noqa: E402

PLUGIN = {
    "name": "shirazi_kids_quiz",
    "description": (
        "Bachon se kahaniyon par pyara sawal poocho ya unke jawab ko check karo. "
        "Pehle 'ask' se sawal poocho, phir bachay ke jawab par 'check' se batayo sahi "
        "ya ghalat — hamesha pyaar bhare andaz mein, ghalat jawab par halka hint do. "
        "Bachon ke saath khel khel mein seekhne ke liye."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "operation": {
                "type": "STRING",
                "enum": ["ask", "check"],
                "description": "'ask' = naya sawal poocho. 'check' = bachay ke jawab ko parko.",
            },
            "child_answer": {
                "type": "STRING",
                "description": "Bachay ka jawab (sirf 'check' ke saath).",
            },
            "expected": {
                "type": "STRING",
                "description": "Sahi jawab (sirf 'check' ke saath — pichle sawal ka).",
            },
            "question": {
                "type": "STRING",
                "description": "Wo sawal jo poocha gaya tha (sirf 'check' ke saath).",
            },
        },
        "required": ["operation"],
    },
}

PLUGIN_SETTINGS = None

_PRAISE = [
    "Shabash! Bilkul sahi jawab!",
    "Wah! Tum to bohat zaheen ho!",
    "Bohat khoob! Tumne kahani ghor se suni thi.",
    "MashaAllah! Sahi jawab diya tumne!",
]

_HINTS = [
    "Thoda sa ghalat hua, koi baat nahi! Kahani ko yaad karo —",
    "Qareeb qareeb! Phir se socho —",
    "Koi baat nahi, ghalti se hi seekhte hain! Hint suno —",
]


def _check(question: str, expected: str, given: str) -> str:
    import random
    g = (given or "").strip().lower()
    e = (expected or "").strip().lower()
    if not g:
        return "Koi baat nahi! Jawab do, phir main bataunga sahi hai ya nahi."
    # generous matching for kids: any meaningful word overlap counts
    stop = {"ne", "ko", "ki", "ka", "ke", "mein", "se", "aur", "hai", "tha",
            "thi", "the", "wo", "us", "usne", "ye", "yah", "to", "bhi"}
    gw = {w for w in g.split() if w not in stop and len(w) > 2}
    ew = {w for w in e.split() if w not in stop and len(w) > 2}
    if gw and ew and (gw & ew):
        return (random.choice(_PRAISE) + f" Sawal tha: {question} "
                f"Aur sahi jawab hai: {expected}")
    return (random.choice(_HINTS) + f" sahi jawab hai: {expected} "
            "Ab ye yaad rahega na?")


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Mark-LV plugin contract: never raise; return a spoken string."""
    try:
        params = dict(parameters or {})
        op = (params.get("operation") or "ask").strip().lower()
        if op == "check":
            return _check(params.get("question") or "",
                          params.get("expected") or "",
                          params.get("child_answer") or "")
        q = quiz_question()
        return (f"To dosto, ek pyara sa sawal! Kahani '{q['story_title']}' se: "
                f"{q['question']} Soch kar jawab do!")
    except Exception as e:
        return f"Quiz mein masla hua: {e}"
