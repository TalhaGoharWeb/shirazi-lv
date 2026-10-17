"""
Phase 3.7 — Provider & diagnostics center.

One place to answer: which providers are configured, which actually work,
what models are in use, and what broke recently. All checks are read-only
and never raise.
"""
from __future__ import annotations

import time

_providers = ("gemini", "groq", "openrouter")


def provider_status() -> list[dict]:
    """Per-provider: configured (key present), consent, last error."""
    from memory import config_manager as cm
    out = []
    for p in _providers:
        if p == "gemini":
            key = cm.get_gemini_key() or ""
        elif p == "groq":
            key = cm.get_groq_key() or ""
        else:
            key = cm.get_openrouter_key() or ""
        out.append({
            "provider": p,
            "configured": bool(key),
            "key_hint": (key[:4] + "…" + key[-2:]) if key else "",
            "fallback_consent": cm.get_fallback_consent(p, default=True),
        })
    return out


def model_ids() -> dict:
    """Model IDs currently pinned in code (not live-verified)."""
    try:
        from core import gemini as _g
        live = list(getattr(_g, "LIVE_MODELS", []))
    except Exception:
        live = []
    try:
        from core.shirazi_ladder import _FALLBACK_RUNGS
        ladder = {k: [f"{p}/{m}" for p, m in v]
                  for k, v in _FALLBACK_RUNGS.items()}
    except Exception:
        ladder = {}
    return {"live_voice": live, "text_ladder": ladder}


def audio_devices() -> dict:
    """Audio device summary (best effort, never raises)."""
    try:
        from core import audio_devices as _ad
        return {"available": True,
                "info": str(_ad.get_device_info() if hasattr(_ad, "get_device_info") else "")[:500]}
    except Exception as e:
        return {"available": False, "error": str(e)[:200]}


def system_summary() -> dict:
    """OS, Python, key package versions (best effort)."""
    import platform
    import sys
    out = {"os": platform.system(), "os_release": platform.release(),
           "python": sys.version.split()[0], "timestamp": time.time()}
    for pkg in ("PyQt6", "google-genai", "fastapi", "mcp"):
        try:
            m = __import__(pkg.replace("-", "_"))
            out[pkg] = getattr(m, "__version__", "?")
        except Exception:
            out[pkg] = "not installed"
    return out


def full_report() -> dict:
    """Everything the diagnostics center shows."""
    return {
        "providers": provider_status(),
        "models": model_ids(),
        "audio": audio_devices(),
        "system": system_summary(),
    }
