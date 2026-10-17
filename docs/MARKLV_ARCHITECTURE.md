# Mark-LV Architecture Report

Read-only analysis of `~/workspace/mark-lv/` (upstream: https://github.com/FatihMakes/Mark-LV).
License: **CC BY-NC 4.0** (`LICENSE`) — attribution required, commercial use not permitted.
Stack: Python + PyQt6 (`ui.py`, 5848 lines) + Gemini Live API (`google.genai`). No Electron, no packaging layer.

---

## 1. Main loop (`main.py`, 2321 lines)

**Entry.** `main()` (`main.py:2307`) → inner `runner()` (`main.py:2310`) constructs `JarvisUI` and `JarvisLive(ui)`, then runs `JarvisLive.run()` on an asyncio loop. Console is forced to UTF-8 at import (`main.py:27-34`); on Windows every `subprocess.Popen` is patched with `CREATE_NO_WINDOW` (`main.py:7-17`).

**Session class.** `class JarvisLive` (`main.py:538`); `__init__` (`main.py:539`) builds the two registries (see §2–3) and wires UI callbacks.

**Run loop.** `async def run(self)` (`main.py:2058`) is an infinite reconnect loop:
1. Binds safety/UI services: `confirm_gate.bind(show=ui.show_confirm, hide=ui.hide_confirm, log=ui.write_log)` and `set_trim_notifier` (`main.py:2066-2072`).
2. Picks the live model: `LIVE_MODEL = _gemini.live_model()` (`main.py:2102`).
3. Builds `config = self._build_config()` (`main.py:2105`) — a `types.LiveConnectConfig`.
4. Opens the session: `client.aio.live.connect(model=live_model, config=config)` with a fresh `genai.Client(api_key=...)` per reconnect (`main.py:2112-2120`).
5. Spawns an `asyncio.TaskGroup` of streaming tasks: `_send_realtime` (mic PCM → session, `main.py:1294`), `_listen_audio` (mic capture, `main.py:1309`), `_receive_audio` (server → speaker/UI, `main.py:1472`), `_play_audio` (speaker, `main.py:1601`), plus `_watch_reconnect` (`main.py:812`), `_run_system_monitor` (`main.py:1904`), `_run_background_monitor` (`main.py:1926`), `_run_proactive_mode` (`main.py:1959`), and dashboard command relay (`main.py:2025`; dashboard itself is optional, `main.py:2084-2091`).

**Input flow.**
- Voice: mic → `_listen_audio` → `audio_in_queue` → `_send_realtime` sends `audio` chunks on the live session.
- Text: `JarvisUI` emits → `_on_text_command(text)` (`main.py:839`) → `session.send_client_content(turns={"role":"user","parts":[{"text": text}]}, turn_complete=True)` on the event loop. Gated by wake-word sleep state (`main.py:843-846`).
- Interrupt: `interrupt()` (`main.py:922`).

**Model call path.** Everything conversational goes through the Gemini **Live** API session. One-shot side calls (classification, extraction) go through `core/gemini.py`'s `call()`/`text()`/`as_json()` (`core/gemini.py:467/524/534`), which open short throwaway Live sessions keyed by tier (`FAST`/`SMART`/`SEARCH`, `core/gemini.py:82-84`).

**Tool-call dispatch.** `_receive_audio` reads server messages; on `response.tool_call` it iterates `function_calls`, awaits `self._execute_tool(fc)` for each, then `session.send_tool_response(function_responses=...)` (`main.py:1586-1593`). `async def _execute_tool(self, fc)` (`main.py:1126`):
- Inline tools handled by hardcoded branches (`save_memory`, `recall_memory`, `undo`, `screen_process`, `close_camera`, `system_status`, `manage_monitor`, `shutdown_jarvis`).
- Discovered actions: `self._action_registry.run(name, args, ctx)` (falls through at `main.py:1260`).
- Plugins: `self._plugin_registry.run(name, args, player=self.ui, session_memory=None)` via `run_in_executor` (`main.py:1261-1265`).
- Unknown → `"Unknown tool: {name}"` (`main.py:1267`).
- Result wrapped in `types.FunctionResponse(id, name, response={"result": result})` plus optional `scheduling` hint (`main.py:1284-1289`).

**Tool declarations.** `_build_config()` (`main.py:960`) merges three declaration lists (`main.py:1010`):
`TOOL_DECLARATIONS` (8 inline tools, `main.py:331`: `system_status, screen_process, close_camera, manage_monitor, shutdown_jarvis, save_memory, recall_memory, undo`)
`+ self._action_registry.get_tool_declarations()`
`+ self._plugin_registry.get_tool_declarations()`.
System prompt = `core/prompt.txt` rendered with identity/time/memory/tool context (`_render_prompt`, `main.py:280`; `_load_system_prompt`, `main.py:298`).

---

## 2. Tool/action contract (`core/action_loader.py` + `actions/`)

Each `actions/<name>.py` exposes a module-level `TOOL` dict. Required keys (`core/action_loader.py:31-45`, validated in `_validate`, `core/action_loader.py:147-180`):

| Key | Requirement |
|---|---|
| `name` | unique, regex `^[a-zA-Z_][a-zA-Z0-9_]{0,63}$` |
| `description` | non-empty string (what the model reads to route) |
| `parameters` | dict with `"type": "OBJECT"` (Gemini function-declaration schema) |
| `handler` | callable |
| `behavior` | optional: `BLOCKING` / `NON_BLOCKING` (goes to the API with the declaration) |
| `scheduling` | optional: `WHEN_IDLE` / `SILENT` / `INTERRUPT` (when the result may re-enter speech) |

Real example — `actions/open_app.py:277-293`:
```python
TOOL = {
    "name": "open_app",
    "description": "Opens any application on the computer. Use this whenever the user asks to open, launch, or start any app, website, or program. Always call this tool — never just say you opened it.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "app_name": {
                "type": "STRING",
                "description": "Exact name of the application (e.g. 'WhatsApp', 'Chrome', 'Spotify')"
            }
        },
        "required": ["app_name"]
    },
    "handler": open_app,
}
```

**Invocation.** `_call_handler` (`core/action_loader.py:133-144`) inspects the handler signature and passes `parameters=` plus whichever of `player` / `speak` / `response` / `session_memory` the handler declares (`_CTX_KEYS`, `core/action_loader.py:49`).

**Discovery.** `discover_actions(actions_dir, reserved_names, logger)` (`core/action_loader.py:183`) scans `actions/*.py` (skips `_`-prefixed files), imports each, validates, rejects name collisions; import/validation errors are logged and **never raise**. Returns `ActionRegistry` with `get_tool_declarations()`, `run(name, parameters, ctx)`, `has()`, `names()`, `scheduling()`. Called once in `JarvisLive.__init__` (`main.py:618-624`); inline-tool names are reserved (`main.py:614`).

---

## 3. Plugin contract (`core/plugin_loader.py` + `plugins/_template.py`)

Drop-in plugins are single files in `plugins/` exposing a module-level `PLUGIN` dict and a `run()` function (`plugins/_template.py`, 45 lines):

```python
PLUGIN = {
    "name": "my_plugin",          # snake_case, unique, same identifier regex
    "description": "...",         # routing text for the model
    "parameters": {"type": "OBJECT", "properties": {...}, "required": [...]},
}
def run(parameters: dict, player=None, session_memory=None) -> str: ...
```

**Validation** (`_validate`, `core/plugin_loader.py:178-210`) requires: `PLUGIN` dict, valid `name`, non-empty `description`, `parameters` dict with `"type": "OBJECT"`, callable `run`. Optional: `PLUGIN_SETTINGS` (dict with a `fields` list — rendered as a config form in the settings UI via `settings_schemas()`, `core/plugin_loader.py:127`); `behavior` / `scheduling` inside the `PLUGIN` dict (same enums as actions).

**Invocation.** `_call_run` (`core/plugin_loader.py:160-169`) passes `parameters` plus only the kwargs among `player` / `session_memory` that `run()` declares (or all, with `**kwargs`). `PluginRegistry.run(name, parameters, player, session_memory)` (`core/plugin_loader.py:105`) refuses disabled plugins, catches exceptions, returns a spoken error string. Contract: *"Return a short natural-language string — this is spoken back to the user. Never raise."* (`plugins/_template.py:31-37`).

**Discovery.** `discover_plugins(plugins_dir, core_tool_names, logger, notify)` (`core/plugin_loader.py:240`) — same skip-`_`-files / never-raise discipline as actions; rejects names colliding with inline tools or actions. Runs once (`main.py:627-635`); the registry is cached for the process lifetime.

**Enable/disable.** `get_plugin_enabled(name)` (`memory/config_manager.py:326`) is re-read from config on **every** `get_tool_declarations()` / `run()` / `list_for_ui()` call, so toggling needs no restart (`core/plugin_loader.py:1-8`). Per-plugin config values: `get_plugin_config(namespace)` (`memory/config_manager.py:337`), `get_plugin_setting(namespace, key, default)` (`:344`), `save_plugin_config(namespace, values)` (`:349`). UI surfaces: `list_for_ui()` (`core/plugin_loader.py:142`) for the Plugin Manager overlay, `settings_schemas()` for the settings tab.

---

## 4. Memory API

**Store.** `memory/memory_manager.py`. File: `memory/long_term.json` (`MEMORY_PATH`, `memory/memory_manager.py:16`); all access behind a module lock. Shape: `{category: {key: {"value": ...}}}`; `remember()` accepts categories `identity | preferences | projects | relationships | wishes | notes` (`memory/memory_manager.py:404`).

| Function | Signature (`memory/memory_manager.py:line`) | Notes |
|---|---|---|
| `load_memory` | `() -> dict` (`:57`) | missing/corrupt file → empty skeleton |
| `save_memory` | `(memory: dict) -> None` (`:118`) | |
| `update_memory` | `(memory_update: dict) -> dict` (`:159`) | recursive merge via `_recursive_update` (`:136`), then save |
| `format_memory_for_prompt` | `(memory: dict \| None) -> str` (`:194`) | injected into system prompt by `_build_config` |
| `search_memory` | `(query: str, limit: int = 8) -> str` (`:350`) | keyword scoring (`_score`, `:329`); backs the `recall_memory` tool |
| `remember` | `(key: str, value: str, category: str = "notes") -> str` (`:404`) | |
| `forget` | `(key: str, category: str = "notes") -> str` (`:412`) | |
| `save_session_summary` | `(summary: str, language: str = "") -> None` (`:431`) | called on shutdown (`main.py:1874`) |
| `pop_last_session` | `() -> dict \| None` (`:457`) | |
| `all_entries_for_ui` | `() -> list[dict]` (`:383`) | settings UI |
| `set_trim_notifier` | `(fn) -> None` (`:90`) | bound to `ui.write_log` at startup |

**Config.** `memory/config_manager.py`. Single JSON file `config/api_keys.json` (`CONFIG_FILE`, `memory/config_manager.py:12`); read-modify-write via `_patch_config` (`:291`). Get/save pairs (all `get_*` / `save_*`): `get_gemini_key` (`:46`) / `save_api_keys` (`:20`); `get_assistant_name` (`:54`), `get_user_name` (`:59`) / `save_assistant_config` (`:64`); `get_voice` (`:85`) / `save_voice` (`:92`); `get_wake_word_enabled` (`:107`) / `save_wake_word_enabled` (`:112`); `get_push_to_talk_enabled` (`:124`); `get_hud_style` (`:136`); `get_thinking_enabled` (`:158`); `get_turn_tuning` (`:172`) / `save_turn_tuning` (`:206`); `get_proactive_audio_enabled` (`:221`); `get_media_resolution` (`:241`); `get_brief_enabled` (`:268`); `get_input_device` (`:308`) / `save_input_device` (`:313`); `get_output_device` (`:317`) / `save_output_device` (`:322`); plugin flags above. No secrets are logged; key read is `api_key()` in `core/gemini.py:298`.

---

## 5. Safety gates (`core/confirm.py`, `core/undo.py`)

**Confirmation — `core/confirm.py` (161 lines).** Design principle stated in the module docstring: the confirmation token is issued by the *interface*, never the model — the old `confirmed=yes` tool-parameter pattern was forgeable, so it was removed.
- `bind(show, hide, log)` (`core/confirm.py:73`) — wired once in `JarvisLive.run()` (`main.py:2066-2070`); callbacks are marshalled onto the Qt thread by the UI.
- `request(key, title, detail, run)` (`core/confirm.py:79`) — action passes a zero-arg callable; module shows a CONFIRM/CANCEL banner and returns **immediately** with a sentence the model speaks. Nothing blocks.
- `resolve(accepted)` (`core/confirm.py:115`) — called by the UI; runs the callable on a worker thread. Refuses if unbound, expired (`TIMEOUT_SECONDS = 90.0`, `core/confirm.py:45`), or cancelled.
- `pending_title()` (`core/confirm.py:150`) — lets actions avoid stacking banners.
- Policy: only genuinely irreversible things go here; everything reversible uses undo instead.

**Undo — `core/undo.py` (121 lines).** One shared stack, `MAX_DEPTH = 10`.
- `push_undo(label, undo_fn)` (`core/undo.py:70`) — action captures "before" state, pushes zero-arg reversal; never raises.
- `undo_last()` (`core/undo.py:99`) — pops *before* running (a failed undo can't be retried forever); `can_undo()`, `peek()`, `history()` (most-recent-first, for UI), `clear()` on shutdown.
- Exposed to the model as the `undo` inline tool (`main.py:1155-1162`, list mode via `history()`).

---

## 6. What Mark-LV does NOT have (integration gaps for a Shirazi-style brain)

1. **No multi-provider LLM fallback.** The live conversation path is Gemini-only. `core/gemini.py` defines `LIVE_MODELS` as exactly **two** Gemini live models (`core/gemini.py:163-166`), with an explicit design comment that the ladder is *deliberately* short (`core/gemini.py:148-162`): Live models aren't interchangeable like text models. `live_model()` (`core/gemini.py:259`) returns the first non-cooling rung; `note_live_failure()` (`core/gemini.py:269`) advances only on quota/unavailability errors — a bad key or dead network is not retried down the ladder. The `FAST`/`SMART`/`SEARCH` tier tuples (`core/gemini.py:82-84`, `131-146`) are all Gemini models. `core/llm_client.py` (Ollama + OpenAI-compatible backends) exists but is **imported nowhere** in the repo (verified by repo-wide grep) — dead code, docstring says "Local LLM client for MARK XL". A Shirazi-style provider ladder (Gemini → Groq → OpenRouter with quota-aware failover) would be new.
2. **No Urdu / no i18n.** Case-insensitive repo-wide grep for `urdu`, `i18n`, `gettext` across `*.py` returns **zero** hits (the only near-miss is the substring `locale` inside `localentry` in `core/tts.py:280` / `core/stt.py:32` and a code comment in `memory/config_manager.py:80`). Address form is handled as a language-agnostic principle, not a lookup (`main.py:989-997`: '"sir" in English, its everyday equivalent in any other language'). TTS/STT (`core/tts.py`, `core/stt.py`, 442/93 lines) and the system prompt are English-first. A Shirazi-style Urdu-first layer (RTL UI, Urdu TTS voice, Urdu system-prompt variant) would be new.
3. **No structured plugin permissions.** Plugins declare `name`/`description`/`parameters`/`behavior`/`scheduling` and optional `PLUGIN_SETTINGS` — there is **no** permission/capability/scope declaration, no sandboxing, and no per-call authorization. The only access control is the boolean enable flag (`get_plugin_enabled`, `memory/config_manager.py:326`). Dangerous operations rely on each action *opting in* to `confirm.request()` (`core/confirm.py:79`) or `push_undo()` (`core/undo.py:70`) individually. A Shirazi-style permission manifest (e.g. `files:read`, `network`, `shell`) with install-time grants would be new.
4. **Related gaps worth knowing:** memory is a flat JSON key/value store with keyword search (`search_memory`, `memory/memory_manager.py:350`) — no embeddings/vector recall; plugin `run()` is synchronous inside `run_in_executor` with a spoken-string return contract, so long-running structured workflows (checkpoints, cancellation, resume) have no first-class support; config mixes secrets and UI flags in one `config/api_keys.json`.

---

*Report prepared 2026-10-17 from a read-only pass. Every file:line reference was taken from the cloned tree at `~/workspace/mark-lv/`; no code was modified.*
