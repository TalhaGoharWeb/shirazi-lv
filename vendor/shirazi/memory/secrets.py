"""Redact-before-write: strip secrets from memory text BEFORE it is stored.

Pure function ``redact(text) -> (redacted_text, kinds_found)``.

What gets redacted:
    card      card numbers — digit runs (13-19 digits, spaces/dashes allowed)
              that PASS the Luhn check (avoids false positives like
              "order 12345").              -> [redacted card]
    otp       4-8 digit runs NEAR otp/code/verification words only, so
              "call me at 5551234" is left alone.   -> [redacted otp]
    password  password is|:|= <secret>     -> [redacted password]
    api-key   sk-..., AIza..., ghp_..., xox..., or
              api[_-]?key|secret [:|=] <token>      -> [redacted api-key]

Emails and personal names are NOT secrets and are never redacted.
"""

import re

CARD_RE = re.compile(r"\b\d(?:[ \d-]{11,21}\d)\b")
PASSWORD_RE = re.compile(
    r"(?i)\bpassword\b\s*(?:is|:|=)\s*(\S+)")
API_PREFIX_RE = re.compile(
    r"\b(?:sk-[A-Za-z0-9]{4,}|AIza[0-9A-Za-z\-_]{10,}"
    r"|ghp_[A-Za-z0-9]{10,}|gho_[A-Za-z0-9]{10,}"
    r"|xox[bpasr]-[A-Za-z0-9\-]{6,})\b")
API_KV_RE = re.compile(
    r"(?i)\b(?:api[_-]?key|secret)\b\s*[:=]\s*(\S+)")
OTP_DIGITS_RE = re.compile(r"\b\d{4,8}\b")
OTP_WORD_RE = re.compile(
    r"(?i)\b(?:otp|one[\s-]?time|verification|verify|passcode|2fa|"
    r"two[\s-]?factor|auth(?:entication)?[\s-]?code|security[\s-]?code|"
    r"code|pin)\b")

_OTP_WINDOW = 40  # chars around an OTP keyword


def _luhn_ok(digits):
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = ord(ch) - 48
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _redact_cards(text):
    found = False

    def repl(m):
        nonlocal found
        digits = re.sub(r"[^\d]", "", m.group(0))
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            found = True
            return "[redacted card]"
        return m.group(0)

    return CARD_RE.sub(repl, text), found


def _redact_otp(text):
    word_spans = [m.span() for m in OTP_WORD_RE.finditer(text)]
    if not word_spans:
        return text, False
    found = False

    def repl(m):
        nonlocal found
        s, e = m.span()
        for ws, we in word_spans:
            if ws - _OTP_WINDOW <= e and s <= we + _OTP_WINDOW:
                found = True
                return "[redacted otp]"
        return m.group(0)

    return OTP_DIGITS_RE.sub(repl, text), found


def _redact_password(text):
    found = False

    def repl(m):
        nonlocal found
        found = True
        return m.group(0).replace(m.group(1), "[redacted password]", 1)

    return PASSWORD_RE.sub(repl, text), found


def _redact_api_keys(text):
    found = False

    def repl_prefix(m):
        nonlocal found
        found = True
        return "[redacted api-key]"

    text = API_PREFIX_RE.sub(repl_prefix, text)

    def repl_kv(m):
        nonlocal found
        found = True
        return m.group(0).replace(m.group(1), "[redacted api-key]", 1)

    text = API_KV_RE.sub(repl_kv, text)
    return text, found


def redact(text):
    """Return (redacted_text, kinds_found).

    kinds_found is a list drawn from {"card","otp","password","api-key"},
    in detection order, with no duplicates.
    """
    s = text if isinstance(text, str) else str(text)
    kinds = []
    s, hit = _redact_cards(s)
    if hit:
        kinds.append("card")
    s, hit = _redact_api_keys(s)
    if hit:
        kinds.append("api-key")
    s, hit = _redact_password(s)
    if hit:
        kinds.append("password")
    s, hit = _redact_otp(s)
    if hit:
        kinds.append("otp")
    return s, kinds
