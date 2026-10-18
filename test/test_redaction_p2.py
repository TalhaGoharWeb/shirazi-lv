"""P2.6 regression tests: sanitize provider errors + redact Gemini/Groq keys.

- F-006: core/shirazi_ladder._check_status must not leak secrets from the
  provider response body into exception messages (which reach logs/UI).
- F-007: core.omnicontrol.audit.redact must catch Gemini (AIza...) and
  Groq (gsk_...) key formats, not just sk-/GitHub/PEM forms.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import shirazi_ladder as lad
from core.omnicontrol.audit import redact

# --- redact(): provider-specific key formats --------------------------------

GEMINI_SAMPLE = "AIza" + "A" * 35          # AIza + 35 chars
GROQ_SAMPLE = "gsk_" + "b" * 24            # gsk_ + 24 chars


def test_redact_gemini_key():
    out = redact(f"auth failed for key {GEMINI_SAMPLE} please retry")
    assert GEMINI_SAMPLE not in out
    assert "[REDACTED-API-KEY]" in out


def test_redact_groq_key():
    out = redact(f"using groq key {GROQ_SAMPLE} here")
    assert GROQ_SAMPLE not in out
    assert "[REDACTED-API-KEY]" in out


def test_redact_leaves_innocent_text_alone():
    assert redact("all systems nominal, HTTP 200") == "all systems nominal, HTTP 200"
    assert redact(None) == ""
    assert redact("") == ""


# --- _check_status(): no secret leaks ----------------------------------------

class _Resp:
    def __init__(self, status, body=b""):
        self.status = status
        self._body = body

    def read(self, n=-1):
        return self._body


def test_check_status_500_redacts_assignment_secret():
    with pytest.raises(lad.ProviderError) as ei:
        lad._check_status("groq", _Resp(500, b'{"error": "bad", "detail": "api_key=SECRET123"}'))
    msg = str(ei.value)
    assert "SECRET123" not in msg
    assert "groq" in msg and "500" in msg


def test_check_status_429_redacts_gemini_key_in_body():
    body = f'{{"message": "quota hit for {GEMINI_SAMPLE}"}}'.encode()
    with pytest.raises(lad.ProviderError) as ei:
        lad._check_status("openrouter", _Resp(429, body))
    msg = str(ei.value)
    assert GEMINI_SAMPLE not in msg
    assert "[REDACTED-API-KEY]" in msg


def test_check_status_401_unaffected():
    with pytest.raises(lad.AuthError):
        lad._check_status("groq", _Resp(401, b"bad key"))
