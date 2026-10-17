"""
OMNICONTROL audit log: append-only, secret-free by construction.

Every gateway decision (allow/deny), grant change, task event and emergency
stop is recorded here. The acceptance criteria require that audit logs never
contain secrets, so ALL values pass through redact() before storage — keys,
tokens, passwords, private-key material and bearer credentials are replaced
with '[REDACTED]' even if a caller accidentally includes them.
"""
from __future__ import annotations

import json
import re

from . import db

_PATTERNS = [
    # private key blocks
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "[REDACTED-PRIVATE-KEY]"),
    # github tokens
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"), "[REDACTED-GITHUB-TOKEN]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "[REDACTED-GITHUB-TOKEN]"),
    # generic bearer/api-key assignments
    (re.compile(r"(?i)(api[_-]?key|bearer|passwd|password|secret|token)\s*[:=]\s*['\"]?([^\s'\";,}]{6,})['\"]?"), r"\1=[REDACTED]"),
    # openai-style keys
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), "[REDACTED-API-KEY]"),
    # gemini keys (AIza + 35 chars)
    (re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), "[REDACTED-API-KEY]"),
    # groq keys (gsk_ + 20+ chars)
    (re.compile(r"\bgsk_[0-9A-Za-z]{20,}\b"), "[REDACTED-API-KEY]"),
]


def redact(text: str | None) -> str:
    if not text:
        return ""
    out = str(text)
    for rx, repl in _PATTERNS:
        out = rx.sub(repl, out)
    return out


def log(actor: str, action: str, tool: str | None = None,
        resource: str | None = None, decision: str | None = None,
        reason: str | None = None, details: str | dict | None = None) -> int:
    """Append one audit record. Returns the row id."""
    if isinstance(details, dict):
        details = json.dumps(details, default=str)
    conn = db.connect()
    cur = conn.execute(
        "INSERT INTO audit_log(ts, actor, action, tool, resource, decision, reason, details)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (db.now(), redact(actor), redact(action),
         redact(tool), redact(resource), redact(decision),
         redact(reason), redact(details)),
    )
    conn.commit()
    return cur.lastrowid


def recent(limit: int = 100) -> list[dict]:
    conn = db.connect()
    rows = conn.execute(
        "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]
