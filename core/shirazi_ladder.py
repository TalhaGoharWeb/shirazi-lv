"""Shirazi-origin provider failover for one-shot text tiers.

Mark-LV's live voice conversation stays on the Gemini Live API by design —
real-time voice models are not interchangeable. This module adds Shirazi's
multi-provider ladder as a fallback for the ONE-SHOT text tiers
(FAST/SMART/SEARCH in core/gemini.py): when every Gemini rung is exhausted,
or no Gemini key is configured, Groq and OpenRouter are tried before giving up.

Ported from shirazi-core/core/llm.py (Shirazi-origin, original code):
- OpenAI-compatible /chat/completions over stdlib http.client (no new deps).
- HTTP 401 -> AuthError (honest, never retried); 429 / 5xx / network errors
  -> ProviderError (fail over to the next rung).
- A rung without a configured key is skipped silently.
"""
from __future__ import annotations

import http.client
import json
import socket
import urllib.parse

# P2.6: sanitize provider error bodies so secrets never reach logs/UI.
# Safe: core.omnicontrol.audit imports only db + stdlib (no cycle).
from core.omnicontrol.audit import redact

# Shirazi-origin: provider bases (from shirazi-core/core/llm.py).
_OAI_BASES = {
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}


class ProviderError(Exception):
    """A rung failed in a way that allows failing over (429/5xx/network)."""

    def __init__(self, provider: str, status: int, message: str):
        super().__init__(message)
        self.provider = provider
        self.status = status


class AuthError(ProviderError):
    """The provider rejected the key (401) — honest, never retried."""


def _check_status(provider: str, resp) -> None:
    status = resp.status
    if status == 200:
        return
    body = resp.read(2048).decode("utf-8", "replace")
    if status == 401:
        raise AuthError(provider, 401, f"API key rejected by {provider}.")
    if status == 429 or status >= 500:
        raise ProviderError(provider, status,
                            f"{provider} returned HTTP {status}: {redact(body[:200])}")
    raise ProviderError(provider, status,
                        f"{provider} returned HTTP {status}: {redact(body[:200])}")


def _oai_text(provider: str, model: str, prompt: str, key: str,
              timeout_s: int = 60) -> str:
    """One non-streaming chat completion via an OpenAI-compatible API."""
    base = _OAI_BASES[provider]
    body = {"model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7}
    parsed = urllib.parse.urlparse(base)
    conn = http.client.HTTPSConnection(parsed.netloc, timeout=timeout_s)
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://shirazi.local"
        headers["X-Title"] = "Shirazi"
    try:
        conn.request("POST", parsed.path.rstrip("/") + "/chat/completions",
                     body=json.dumps(body), headers=headers)
        resp = conn.getresponse()
        _check_status(provider, resp)
        data = json.loads(resp.read().decode("utf-8", "replace"))
        choices = data.get("choices") or []
        if not choices:
            raise ProviderError(provider, 200, f"{provider}: empty choices")
        return ((choices[0].get("message") or {}).get("content") or "").strip()
    except (socket.timeout, TimeoutError, socket.error,
            http.client.HTTPException) as e:
        raise ProviderError(provider, 0, f"{provider} network error: {e}")
    finally:
        conn.close()


# Shirazi-origin rung order (from shirazi-core/ladder.yaml, Oct 2026 snapshot).
# Kept to text-tier models; the live voice path is intentionally untouched.
_FALLBACK_RUNGS = {
    "FAST": [("groq", "openai/gpt-oss-20b"),
             ("openrouter", "google/gemma-4-31b-it:free")],
    "SMART": [("groq", "openai/gpt-oss-120b"),
              ("openrouter", "qwen/qwen3.8-27b:free")],
    "SEARCH": [("groq", "openai/gpt-oss-120b"),
               ("openrouter", "qwen/qwen3.8-27b:free")],
}


def _key_for(provider: str) -> str:
    from memory import config_manager as _cm
    # P2.10: provider consent — a rung is only used if the user supplied a
    # key (implicit consent via Settings > API KEYS) AND hasn't disabled it.
    if not _cm.get_fallback_consent(provider, default=True):
        return ""
    if provider == "groq":
        return _cm.get_groq_key() or ""
    if provider == "openrouter":
        return _cm.get_openrouter_key() or ""
    return ""


# P2.10: last-answer provenance — which provider/model actually answered.
# Callers (UI, logs) read this to show "answered via groq/openai/gpt-oss-20b".
_last_provenance: dict = {}


def last_provenance() -> dict:
    """{'provider': ..., 'model': ..., 'tier': ...} of the last ladder answer."""
    return dict(_last_provenance)


def contents_to_text(contents) -> str:
    """Reduce Gemini-style `contents` (str | list) to plain text for OAI APIs."""
    if isinstance(contents, str):
        return contents
    parts: list[str] = []
    for c in contents or []:
        if isinstance(c, str):
            parts.append(c)
        elif isinstance(c, dict):
            t = c.get("text")
            if isinstance(t, str):
                parts.append(t)
            for p in c.get("parts") or []:
                if isinstance(p, dict) and isinstance(p.get("text"), str):
                    parts.append(p["text"])
        else:
            tx = getattr(c, "text", None)
            if isinstance(tx, str):
                parts.append(tx)
    return "\n".join(p for p in parts if p).strip()


def oai_fallback_text(prompt: str, tier: str = "FAST", default: str = "") -> str:
    """Groq -> OpenRouter rungs only (no Gemini attempt). Never raises."""
    if not prompt:
        return default
    rungs = _FALLBACK_RUNGS.get(str(tier).upper(), _FALLBACK_RUNGS["FAST"])
    for provider, model in rungs:
        key = _key_for(provider)
        if not key:
            continue
        try:
            out = _oai_text(provider, model, prompt, key)
        except AuthError as e:
            print(f"[Ladder] {e}")
            continue  # wrong key for this provider — try the next rung
        except ProviderError as e:
            print(f"[Ladder] {e}")
            continue
        except Exception as e:  # never let a fallback rung crash the caller
            print(f"[Ladder] {provider}/{model}: {type(e).__name__}: {e}")
            continue
        if out:
            print(f"[Ladder] answered via {provider}/{model}")
            _last_provenance.update(provider=provider, model=model,
                                    tier=str(tier).upper())
            return out
    _last_provenance.clear()
    return default


def text_with_fallback(contents, tier: str = "FAST", default: str = "") -> str:
    """Gemini text tiers with Shirazi provider failover.

    Tries Mark-LV's Gemini ladder first (existing behaviour preserved);
    on total Gemini failure, walks the Groq -> OpenRouter rungs for the tier.
    Never raises — returns `default` when nothing answered.
    """
    from core import gemini as _gemini
    try:
        out = _gemini.text(contents, tier=tier, default="")
    except Exception:
        out = ""
    if out:
        return out
    return oai_fallback_text(contents_to_text(contents), tier, default)
