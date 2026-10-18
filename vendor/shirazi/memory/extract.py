"""Rule-based fact extraction for the memory write path (no model calls).

Covers English, Urdu (Arabic script), and Roman Urdu. Patterns are kept
tight on purpose — extraction must not produce junk facts. At most
MAX_FACTS facts are returned per turn.
"""

import re

MAX_FACTS = 3


def _clean(span, limit=80):
    s = span.strip()
    # keep the first sentence only
    s = re.split(r"[.!?؟\n]", s, maxsplit=1)[0].strip()
    s = s.strip(" \t\"'“”‘’-,;:")
    if len(s) > limit:
        s = s[:limit].rstrip()
    return s


_NAME_CUT = re.compile(
    r"\s+(?:and|but|who|which|that|because|i)\b|,", re.IGNORECASE)


def _name(span, limit=40):
    """Trim a captured name at connector words ("Ali and I ..." -> "Ali")."""
    s = _NAME_CUT.split(span.strip(), maxsplit=1)[0]
    return _clean(s, limit)


_PATTERNS = [
    # English
    (re.compile(r"(?i)\bmy name is\s+([A-Za-z][\w .'\-]{0,40})"),
     lambda m: ("User's name is %s." % _name(m.group(1)), "fact")),
    (re.compile(r"(?i)\bmy project is\s+([A-Za-z0-9][\w .'\-]{0,60})"),
     lambda m: ("User's project is %s." % _clean(m.group(1), 60), "fact")),
    (re.compile(r"(?i)\bi (?:like|love)\s+([\w][\w .'\-]{0,60})"),
     lambda m: ("User likes %s." % _clean(m.group(1), 60), "preference")),
    (re.compile(r"(?i)\bremember(?:\s+that)?\s+(.{3,140})"),
     lambda m: ("%s." % _clean(m.group(1), 140).rstrip("."), "note")),
    # Urdu (Arabic script)
    (re.compile(r"میرا نام\s+([\u0600-\u06FF][\u0600-\u06FF .]{0,40}?)\s+ہے"),
     lambda m: ("User's name is %s." % _name(m.group(1)), "fact")),
    (re.compile(r"یاد رکھو(?: کہ)?\s+(.{3,140})"),
     lambda m: ("%s." % _clean(m.group(1), 140).rstrip("."), "note")),
    # Roman Urdu
    (re.compile(r"(?i)\bmera naam\s+([A-Za-z][\w .'\-]{0,40}?)\s+hai\b"),
     lambda m: ("User's name is %s." % _name(m.group(1)), "fact")),
    (re.compile(r"(?i)\byaad rakho(?: keh?)?\s+(.{3,140})"),
     lambda m: ("%s." % _clean(m.group(1), 140).rstrip("."), "note")),
]


def extract_facts(text):
    """Return up to MAX_FACTS (content, kind) tuples from a user message."""
    s = text if isinstance(text, str) else str(text)
    facts = []
    seen = set()
    for rx, build in _PATTERNS:
        if len(facts) >= MAX_FACTS:
            break
        m = rx.search(s)
        if not m:
            continue
        content, kind = build(m)
        # drop junky extractions (too short or no content words)
        core = content.strip().rstrip(".")
        if len(core) < 6 or core.lower() in seen:
            continue
        seen.add(core.lower())
        facts.append((content, kind))
    return facts
