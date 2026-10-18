"""
Example plugin — the reference implementation for the Plugin SDK.

Copy this file to start a new plugin:
  1. Copy to plugins/shirazi_my_tool.py
  2. Rename the PLUGIN dict 'name' (must be unique, lowercase + underscores)
  3. Write your run() — it receives (parameters, player, session_memory)
  4. Optionally add a plugin.json manifest next to it (see shirazi_example_hello.json)
  5. Validate with: python tools/validate_plugin.py plugins/shirazi_my_tool.py

Rules (enforced by the loader + gateway, not by convention):
- run() must never raise for bad input — return an error string instead.
- No network, no filesystem writes, no subprocesses unless your risk tier
  justifies it AND the gateway approves it at runtime.
- Never read api_keys.json, secrets, or credentials.
- The PLUGIN description is display text only — it never grants permissions.
"""
from __future__ import annotations

PLUGIN = {
    "name": "shirazi_example_hello",
    "description": (
        "Greets the user by name. A zero-side-effect example plugin "
        "(LOW risk). Copy this file to start your own plugin."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "name": {
                "type": "STRING",
                "description": "Who to greet (default: friend).",
            },
        },
        "required": [],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    name = ""
    try:
        name = str((parameters or {}).get("name", "")).strip()
    except Exception:
        name = ""
    who = name[:40] if name else "friend"
    # No side effects: pure string building. LOW risk is honest here.
    return f"Hello, {who}! This is the example plugin — it does nothing but greet."
