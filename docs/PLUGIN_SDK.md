# SHIRAZI Plugin SDK

Build tools for SHIRAZI. A plugin is one Python file in `plugins/` — no
registration, no restarts for code changes (restart the app once to discover).

## Quick start

1. Copy `plugins/_template.py` to `plugins/my_tool.py` (no leading underscore).
2. Fill in `PLUGIN` (name, description, parameters) and `run()`.
3. Validate: `python tools/validate_plugin.py plugins/my_tool.py`
4. Restart SHIRAZI. Your tool appears in Gemini's function list.

## The PLUGIN dict

```python
PLUGIN = {
    "name": "my_tool",  # snake_case, unique, ^[a-zA-Z_][a-zA-Z0-9_]{0,63}$
    "description": "What this does — Gemini reads this to decide when to call it.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "arg": {"type": "STRING", "description": "What this arg means",
                    "enum": ["a", "b"]},  # optional: restrict values
        },
        "required": ["arg"],
    },
}
```

Parameter types: `STRING`, `NUMBER`, `INTEGER`, `BOOLEAN`, `ARRAY`, `OBJECT`.
Keep enums non-empty (empty enums are rejected by the Live API).

## The run() function

```python
def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        arg = parameters.get("arg", "")
        # ... do the work ...
        return "Done — natural language result, spoken to the user."
    except Exception as e:
        return f"my_tool failed: {e}"  # NEVER raise
```

- Return a short natural-language string (it is spoken back).
- Never raise: catch errors, return a spoken error.
- `player` is the UI (may be None) — `player.write_log("...")` to log.
- Keep it fast: dispatch has a 120s timeout.

## Authorization (OMNICONTROL)

Every plugin call passes the gateway:
- **LOW** (read-only): auto-allowed, audit-logged.
- **MODERATE** (creates/edits): auto-allowed, audit-logged.
- **HIGH** (deletes, system control): needs dashboard approval per call.
- Your plugin's tier is set in `core/omnicontrol/gateway.py` `TOOL_RISK_MAP`.
  Default for unlisted plugins: LOW. If your plugin deletes or controls the
  system, add it to the HIGH list.

## Settings (optional)

```python
PLUGIN_SETTINGS = {
    "namespace": "my_tool",  # config section
    "env": {"API_KEY": "MY_TOOL_API_KEY"},  # setting key -> env var
    "schema": [  # rendered in Settings UI
        {"key": "API_KEY", "label": "API Key", "type": "password"},
    ],
}
```

## Best practices

- One tool, one job. Small plugins compose better.
- Validate input; the model can send unexpected values.
- No secrets in code — use PLUGIN_SETTINGS or env vars.
- Test with `pytest test/test_my_tool.py` before shipping.
- Document trigger phrases in the description.
