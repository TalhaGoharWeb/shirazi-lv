"""
Phase 3.1 — Degraded-mode text chat.

When the Gemini Live voice link is down, SHIRAZI stays useful through a
text-only conversation powered by the provider ladder (Groq -> OpenRouter).
This module owns the degraded conversation: multi-turn history, a system
prompt that states the honest limits, and provider provenance per answer.

Honest limits (surfaced to the user, not hidden):
  - No voice in or out.
  - No tools: the model cannot read files, run code, or control the PC.
  - No vision: it cannot see the screen or camera.
  - Answers come from a fallback provider, labelled per response.
"""
from __future__ import annotations

import threading

SYSTEM_PROMPT = (
    "You are SHIRAZI, a voice-first AI assistant, currently running in "
    "TEXT-ONLY DEGRADED MODE because the live voice link is down. "
    "Rules for this mode:\n"
    "- Answer helpfully in the user's language (English, Urdu, or Roman Urdu).\n"
    "- You CANNOT use tools, read files, run code, control the PC, or see/hear anything.\n"
    "- If the user asks for something needing tools or voice, say so plainly "
    "and offer to do it once the voice link is back.\n"
    "- Be concise. Do not claim capabilities you don't have in this mode."
)

_MAX_HISTORY = 20  # exchanges (user+assistant pairs); older ones are dropped.


class DegradedChat:
    """Multi-turn text conversation over the fallback ladder."""

    def __init__(self):
        self._lock = threading.Lock()
        self._history: list[dict] = []
        self._active = False

    @property
    def active(self) -> bool:
        with self._lock:
            return self._active

    def activate(self) -> None:
        with self._lock:
            self._active = True

    def deactivate(self) -> None:
        with self._lock:
            self._active = False

    def clear(self) -> None:
        with self._lock:
            self._history.clear()

    def history(self) -> list[dict]:
        with self._lock:
            return [dict(m) for m in self._history]

    def is_available(self) -> bool:
        """True if at least one fallback provider has a key + consent."""
        try:
            from .shirazi_ladder import _key_for
            return bool(_key_for("groq") or _key_for("openrouter"))
        except Exception:
            return False

    def _build_prompt(self, text: str) -> str:
        with self._lock:
            hist = list(self._history)
        parts = [SYSTEM_PROMPT, ""]
        for m in hist[-(2 * _MAX_HISTORY):]:
            role = "User" if m["role"] == "user" else "Shirazi"
            parts.append(f"{role}: {m['content']}")
        parts.append(f"User: {text}")
        parts.append("Shirazi:")
        return "\n".join(parts)

    def ask(self, text: str) -> tuple[str, str]:
        """Ask in degraded mode. Returns (answer, provider_label)."""
        from .shirazi_ladder import oai_fallback_text, last_provenance
        prompt = self._build_prompt(text)
        answer = oai_fallback_text(
            prompt, tier="SMART",
            default="All text providers are unreachable right now. "
                    "I'll be back once the connection recovers.")
        prov = last_provenance()
        label = (f"{prov['provider']}/{prov['model']}" if prov
                 else "unavailable")
        with self._lock:
            self._history.append({"role": "user", "content": text})
            self._history.append({"role": "assistant", "content": answer})
            # Trim to the last _MAX_HISTORY exchanges.
            self._history = self._history[-(2 * _MAX_HISTORY):]
            self._active = True
        return answer, label


# Process-wide singleton: one degraded conversation at a time.
degraded_chat = DegradedChat()
