"""
OMNICONTROL voice hooks — the 3-line integration for main.py.

main.py's voice-session handler calls maybe_handle(transcript) BEFORE sending
the text to Gemini. If it returns a string, that string is spoken/printed as
the response and the turn ends there. Otherwise returns None and the normal
pipeline continues.

Handled locally (no model call):
  * the emergency-stop phrase -> estop.trip()  (model-independent, per spec)
  * permission commands ("allow read access to ...", "revoke ...",
    "show permissions", "stop everything") -> permissions pipeline.
    Voice confirmations apply ONLY to 'voice-ok' proposals (LOW-risk reads
    in approved folders); anything else produces a dashboard confirmation
    card and a spoken prompt to tap it.

Integration (main.py, in the transcript handler):

    from core.omnicontrol import voice_hooks
    handled = voice_hooks.maybe_handle(transcript_text, origin="user")
    if handled:
        speak(handled); continue
"""
from __future__ import annotations

from . import estop, permissions


def maybe_handle(text: str, origin: str = "user") -> str | None:
    """Return a response string if the utterance was handled, else None."""
    t = (text or "").strip()
    if not t:
        return None
    low = t.lower()

    # 1. Emergency phrase — pure string match, no model, no network.
    if low == estop.emergency_phrase():
        result = estop.trip(source="voice")
        n = len(result["tasks_cancelled"])
        return ("Emergency stop engaged. New tool calls are blocked%s. "
                "Tap Resume on the dashboard Permissions view to clear it."
                % ((" and %d task(s) cancelled" % n) if n else ""))

    # 2. Permission commands.
    proposal = permissions.parse_shape(t)
    if proposal is None:
        return None
    checked = permissions.propose(proposal, origin=origin)
    if not checked.get("ok"):
        return "Permission request unclear: %s" % checked.get("error")
    if checked["confirm_level"] == "question":
        return checked["summary"]  # ask for clarification, never guess
    if checked["confirm_level"] == "voice-ok":
        result = permissions.confirm(proposal, via="voice", origin=origin)
        if result.get("ok"):
            return "Done. %s" % result.get("summary", "")
        return "I couldn't apply that: %s" % result.get("error")
    # tap-required: create the pending request so the dashboard shows a card.
    from . import gateway
    action = proposal["action"]
    if action == "grant":
        pid = gateway.request_approval(
            "perm_grant", proposal.get("resource", ""), proposal.get("ops", "read"),
            checked["summary"])
        return ("That needs your approval. I've put a confirmation card on the "
                "dashboard Permissions view — tap Allow Once, Allow Always, or Deny.")
    if action == "revoke":
        pid = gateway.request_approval(
            "perm_revoke", proposal.get("resource", ""), "revoke", checked["summary"])
        return ("Revoking needs your confirmation — tap it on the dashboard "
                "Permissions view.")
    if action == "resume":
        return ("For safety, clearing the emergency stop needs your tap — "
                "press Resume on the dashboard Permissions view.")
    return None
