# SHIRAZI CORE — Capability Inventory

**Source:** `~/workspace/shirazi-assistant/shirazi-core/` (original Python brain; the Electron/React shell is out of scope).
**Method:** every module read in full; every claim has a file:line reference. Verdicts are honest, not aspirational.
**Verdict key:** REAL = implemented, tested, and wired into `core/server.py`. PARTIAL = works but has a documented gap. STUB = interface exists, production path unimplemented.

---

## 1. Core modules

### core/llm.py — multi-provider LLM client with failover (REAL)
Streaming chat + agentic tool loop across **gemini / groq / openrouter**, stdlib `http.client` only (no SDK deps). `stream_chat()` core/llm.py:267 yields `("text", delta)` / `("tool_call", {...})`; `chat_with_tools()` core/llm.py:293 fails over the ladder on 429/5xx/404/timeout (`ProviderError.retryable` core/llm.py:44), raises honest `AuthError` on 401 (no silent retry). Mock mode (`keys["mock"]=="shirazi-test"`) returns canned deltas. **Deps:** stdlib only. **Tests:** exercised via server/chat paths; mock path used in CI. REAL.

### core/router.py — fast-lane intent router (REAL)
`route()` core/router.py:44 returns `("fastlane", text)` for help/time-date/calculator/open-app (regex, zero model calls) else `("llm", tier)` with tier tiny/mid/strong from length + keywords. **Deps:** stdlib. **Tests:** covered in test suite (fastlane patterns). REAL.

### core/actions.py — native action discovery (REAL)
`discover_actions()` core/actions.py:118 imports every `actions/*.py` (except dunders), validates the `TOOL` dict (`_validate_tool` core/actions.py:34: requires name/description/kind/access/parameters/callable run), broken files are logged + skipped, never crash boot. `ActionRegistry` core/actions.py:65 with `get/list/all/is_builtin`; builtin `undo_last` core/actions.py:92. **Deps:** stdlib + `core/policy.py`. REAL, wired into server at startup.

### core/plugins.py — permission-enforced plugin system (REAL)
`PluginManager` core/plugins.py:333 discovers `plugins/<name>/` folders: requires `plugin.yaml` (parsed by a minimal hand-rolled YAML-subset parser `parse_manifest` core/plugins.py:275) + `plugin.py` defining non-empty `TOOLS = [...]` (same TOOL schema as actions). **Load-time AST permission scan** `scan_permissions` core/plugins.py:160 maps imports/calls to `network | files:read | files:write | clipboard | exec`; undeclared use → plugin BLOCKED (never imported). Plugins are **disabled by default**; state persisted to `<data_dir>/plugins.json`; enable/disable takes effect immediately. **Deps:** stdlib only. **Tests:** test_plugins.py (9 tests). REAL.

### core/policy.py — trust-boundary policy gate (REAL)
`check(name, args, registry)` core/policy.py:51 → `allow` (read) / `allow+undo` (write) / `confirm` (destructive) / `deny` (unknown). Verdicts derive ONLY from the declared `access` class — tool output is untrusted by design. `UndoStack` core/policy.py:22 (in-memory LIFO, maxlen 50). **Deps:** stdlib. REAL — enforced in server `_make_execute` and voice/computer tool bridges.

### core/problem_diagnosis.py — 7-step methodology bookkeeping (REAL)
Deterministic helpers for the Detect→Diagnose→Gather→Plan→Execute→Verify→Learn loop: `new_case` core/problem_diagnosis.py:72, `add_evidence` :84, `mark_step` :98, `render_case` :109; append-only fix journal (`append_fix_journal` :158 / `read_fix_journal` :182) and signature-keyed troubleshooting memory (`remember_fix` :211, `recall_fix` :235, `recall_similar` fuzzy Jaccard). Storage: `<SHIRAZI_DATA_DIR>/plugins_data/problem_diagnosis/*.json`. **Deps:** stdlib. **Tests:** test_problem_solver.py (44 tests incl. real-DB audit). REAL.

### core/voice.py — Gemini Live voice sessions (REAL, key-gated)
`VoiceManager` core/voice.py:574: per-session thread + own asyncio loop; mic PCM 16kHz in (RAM-only, never touches disk), model audio 24kHz out, barge-in/interruption, transcripts, tool calls bridged through the policy gate (`_execute_tool` core/voice.py:177; destructive → voice-spoken confirm via `confirm()`), 3 personas (Shirazi/Roshan/Tez, core/voice.py:86), stop-words incl. Urdu/Roman Urdu (`STOP_WORDS_RE`), 14-min session cap. Backends: `GeminiLiveBackend` core/voice.py:270 + `MockBackend` core/voice.py:214 (`SHIRAZI_VOICE_MOCK=1`). **Deps:** `google-genai` (optional; missing → HTTP 501 with install note). **Tests:** test_voice.py (7), test_voice_workflow.py (11), voice_501_check. REAL — requires Gemini key + `pip install -r requirements-voice.txt`.

### core/wakeword.py — on-device wake-word (REAL, dep-gated)
`WakeWordEngine` core/wakeword.py:100 scores 80ms 16kHz PCM frames via OpenWakeWord (Apache-2.0); `VoiceFirstController` core/wakeword.py:178 state machine off→listening→suppressed→(resume)→listening. Privacy by construction: rolling RAM buffer only, no disk writes, no network; `MAX_BUFFER_FRAMES=8`. Default model: built-in `hey_jarvis` (custom "hey shirazi" needs user voice samples — deferred). **Deps:** `openwakeword` + `onnxruntime` (optional; missing → 501). **Tests:** test_wakeword.py (16, incl. no-disk assertion). REAL.

### core/computer.py — computer-use agent (REAL, heavy deps)
`ComputerTask` core/computer.py:469: screenshot→plan→ground→act→verify loop, max 200 steps, stop-event checked before every blocking call (~1s abort), Esc kill (pynput on Linux; Windows needs WH_KEYBOARD_LL hook — **STUB, UNTESTABLE-HERE**), user-mouse-move auto-pause (60px), destructive steps (file_delete/run_shell) require explicit 120s-TTL confirm, file ops undoable (trash-dir for deletes). Grounding: a11y-first — `AtspiBackend` core/computer.py:119 (Linux, real), `WindowsUIABackend` core/computer.py:176 (**STUB: raises NotImplementedError** — the one Windows-critical piece not yet coded), `BridgeBackend` (HTTP helper, used by test harness), `VLMGrounding` (strong-tier model, needs live keys). `Actuator` (pyautogui, lazy; Unicode typing via clipboard). `ComputerManager` core/computer.py:838: one active task, confirms, SSE events. **Deps:** `mss`, `Pillow`, `pyautogui` (all lazy; `requirements-computer.txt`). **Tests:** test_computer.py (pure-logic, stdlib-only). REAL except the Windows UIA backend.

### core/selfknow.py — live self-knowledge (REAL)
`assemble(registry, extra)` core/selfknow.py:36 reads OS/CPU/disk/Python from stdlib + live action list from the registry; honest "unknown — no probe deps" for screens/mic/camera. Feeds the model a capability block. **Deps:** stdlib. REAL.

### core/proactive.py — proactive engine (REAL, gated-off by default)
`ProactiveEngine` core/proactive.py:69: 2s tick loop; monitors: reminders (ON), battery, disk, clipboard (OFF by default); tiered cards (trivial→auto-surfaced, else pending queue persisted JSON); quiet hours (23:00–07:00 default); `decide(card_id, approve|dismiss|never)` with learned deny-patterns; anticipation synthesis (model chief-of-staff tick, 5-min, default OFF, keys RAM-only). Timer plugin fires → proactive card via `_set_notify` hook (wired in server.py:946). **Deps:** stdlib (+ memory store). REAL.

### core/dashboard.py — QR-paired phone dashboard (REAL)
Second HTTP server on `0.0.0.0` (LAN) serving a self-contained mobile web UI (chat SSE + push-to-talk). `DashboardManager` core/dashboard.py:74: one-time pairing tokens (10-min TTL, single-use), device tokens sha256-hashed at rest, revoke → immediate 401. `lan_ip()` core/dashboard.py:42 via UDP-socket trick (no deps). Phone voice → Gemini transcription `_transcribe` (needs desktop keys, RAM-only via POST /dashboard/keys). **Deps:** stdlib only (+ core/qr.py). **Tests:** test_dashboard.py (9). REAL. Note: LAN HTTP, no TLS (documented).

### core/qr.py — clean-room QR generator (REAL)
`qr_data_uri()` core/qr.py:423 → PNG data URI; byte-mode, ECC-M, versions 1–7 (≤122 bytes), Reed-Solomon + masking + penalty scoring all hand-rolled, PNG via zlib+struct (no Pillow). **Deps:** stdlib. **Tests:** test_qr.py (9). REAL.

### core/voice_workflow.py — voice-only command layer (REAL)
Deterministic intent layer between transcripts and actions: spoken yes/no (Urdu/EN/Roman Urdu), instant acks, dictation intents (note/memory/reminder), voice corrections, voice settings, HUD commands, progress narration. `confirm_prompt()` core/voice_workflow.py:163. Never touches audio bytes (caller's `speak()` callback). **Deps:** stdlib (+ core/voice regexes). **Tests:** test_voice_workflow.py (11, incl. no-disk-writes rule). REAL.

### memory/store.py — SQLite+FTS5 memory (REAL)
`MemoryStore` memory/store.py:33: `remember` (secret-redact → normalize → dedupe → insert, WAL mode, thread-safe) :83; `recall` (stopword-stripped FTS5 AND-query across `memories_fts` + `memories_fts_en` trigram tables, BM25 merge) :117; `forget`/`forget_query` hard deletes :153; `export`/`backup` (keeps 10) ; entities+aliases; sessions with deterministic auto-summary (`end_session` :247); reminders (`create_reminder` :292, `due_reminders` :301). Trilingual stopwords (EN/Urdu-script/Roman Urdu). **Deps:** stdlib sqlite3. **Tests:** test_memory.py (37). REAL.

### memory/extract.py — rule-based fact extraction (REAL, narrow)
`extract_facts()` memory/extract.py:56: regex patterns for EN/Urdu-script/Roman Urdu ("my name is…", "yaad rakho…"), max 3 facts/turn, junk-filtered. Deliberately narrow — no model calls. REAL.

### ladder.yaml — model ladder config (REAL)
User-editable tiers tiny/mid/strong × providers gemini→groq→openrouter. **No Ollama, no local-inference provider exists** (only the three cloud providers in core/llm.py `_OAI_BASES` + gemini). REAL.

---

## 2. Native actions/ (always-on, no enable needed)

| file | action | what | access |
|---|---|---|---|
| calculator.py | `calculator` | safe arithmetic eval | read |
| clipboard_read.py | `clipboard_read` | read clipboard (used by proactive clipboard monitor) | read |
| date_time.py | `date_time` | current time/date | read |
| open_app.py | `open_app` | launch app by name (fast-lane `open X`) | write |
| system_info.py | `system_info` | OS/CPU/RAM/disk snapshot | read |
| web_search.py | `web_search` | **real** DuckDuckGo scrape (lite.duckduckgo.com + html fallback, stdlib urllib, HTMLParser result pairing) | read |

---

## 3. Plugin contract (how core/plugins.py discovers a plugin)

`plugins/<name>/` must contain:
1. **`plugin.yaml`** — minimal hand-rolled YAML subset (flat `key: value` + top-level `- item` lists only). Required: `name` (must equal folder name, `[a-z0-9_]+`), `version`, `description`. Optional lists: `permissions` (subset of `network`, `files:read`, `files:write` [implies read], `clipboard`, `exec`), `actions` (names, informational).
2. **`plugin.py`** — must define non-empty `TOOLS = [TOOL, ...]` where each TOOL = `{"name", "description", "kind": "native"|"agent", "access": "read"|"write"|"destructive", "parameters": <jsonschema>, "run": callable, ["restore": callable]}`.
3. **Permission enforcement:** `scan_permissions()` AST-scans `plugin.py` (imports, `open()` modes, `os.*`/`pathlib` calls, `eval/exec/__import__`, `subprocess/ctypes/multiprocessing`, `pyperclip`, `shutil`, network libs). Any need not declared → plugin **blocked** (listed with reason, never imported). This is a guardrail, not a sandbox — stated honestly in the module docstring.
4. **Lifecycle:** disabled-by-default; `PluginManager.enable/disable()` persists to `<data_dir>/plugins.json`; enabled tools merge into the model-visible tool list in `server.py:780-788`; mid-session disable removes tools immediately.

---

## 4. Plugins (18) — purpose, I/O, permissions, deps

| plugin | purpose | actions (tools) | permissions | external deps |
|---|---|---|---|---|
| excel_writer | builds a real .xlsx (bold headers, typed cells, SUM row, bar/line/pie chart) on the Desktop from a structured spec the model fills | excel_create | files:write | **openpyxl** (lazy; honest error if missing) |
| quiz | validates/grades/formats model-written quizzes (schema-checked, no API, no storage) | quiz_start, quiz_grade, quiz_stop | — | stdlib |
| document_review | structures the model's document findings by severity (model reads doc first, plugin formats) | document_review | — | stdlib |
| trainer | curated teachable KB: facts, preferences, corrections, custom commands; list/test/forget | train_fact, train_preference, train_correction, train_command, training_list, training_forget, train_test | files:write | stdlib |
| mcq_maker | bilingual MCQ schema validation for the fiqh pipeline (fixes the fixable, reports drops) | mcq_generate, mcq_validate | — | stdlib |
| urdu_drafter | returns the scholarly-Urdu style contract + glossary; term add/list/forget | urdu_draft, term_add, term_list, term_forget | files:write | stdlib |
| etsy_listing | validates Etsy listing constraints + deterministic Pakistan fee math (13% + $0.50) | listing_create, listing_check, price_suggest | — | stdlib |
| web_research | cited-research session tracker: sources, reliability flags, UNVERIFIED section, compiled report | research_start, research_add_source, research_report | files:write | stdlib |
| file_organizer | tidy-a-folder with **preview-token → apply** two-step; no-overwrite, dotfiles skipped, stays in folder | organize_preview, organize_apply | files:write | stdlib |
| clipboard_plus | clipboard get/set + 20-entry history (JSON in data dir) | clipboard_get, clipboard_set, clipboard_history | clipboard, files:write | pyperclip (lazy, graceful) |
| problem_solver | Universal Problem Solver router: classify/plan/route via the 7-step methodology (pure reasoning, no own storage) | problem_classify, problem_plan, problem_route | — | stdlib |
| build_doctor | paste a failed build log → error lines, file:line refs, ranked root-cause hypotheses, reproduce-first checklist; honest no-match | build_diagnose, build_fix_checklist | — | stdlib |
| pc_health | CPU/RAM/disk/process snapshot + threshold red flags; read-only, interprets nothing itself | health_snapshot, health_report | — | psutil (lazy, graceful) |
| kb_repair | audit a JSON knowledge base (dup ids, missing fields, bad metadata, empty chunks); fix **preview only**, never writes | kb_audit, kb_fix_preview | files:read | stdlib |
| task_recovery | checkpoint task state to plain JSON, resume verbatim, list checkpoints | task_checkpoint, task_resume, task_list | files:write | stdlib |
| notes | local notes save/list/search/delete (JSON in data dir) | note_save, note_list, note_search, note_delete | files:write | stdlib |
| timer | countdown timers + stopwatch; firing surfaces via proactive card (server.py:947 `_set_notify` hook) | timer_start, timer_list, timer_cancel, stopwatch_start, stopwatch_stop | — | stdlib |
| web_bookmark | save/search bookmarks (title+URL, JSON in data dir) | bookmark_save, bookmark_list, bookmark_search, bookmark_delete | files:write | stdlib |

**Test coverage:** test_plugins.py (9), test_new_plugins.py (21), test_more_plugins.py (32), test_problem_solver.py (44) — all passing per last run. excel_writer's openpyxl path degrades with an honest message when uninstalled.

---

## 5. HTTP API surface (core/server.py)

Single `ThreadingHTTPServer` on 127.0.0.1, per-launch token (`--token`, `X-Shirazi-Token` header or `?token=`). Prints `SHIRAZI_PORT=<port>` (+ `SHIRAZI_STARTING=1` heartbeat) on stdout.

**GET:** `/health` · `/actions` · `/selfknow` · `/memory/recall?q&k` · `/memory/export` · `/memory/sessions` · `/reminders` · `/proactive/triggers` · `/proactive/cards` · `/plugins` · `/computer/status?task_id` · `/computer/events?task_id&since` (SSE) · `/voice/personas` · `/voice/state?session_id` · `/voice/wake_state` · `/voice/events?session_id` (SSE) · `/dashboard/pair` (mints token+QR) · `/dashboard/devices` · `/dashboard/status`

**POST:** `/chat` (SSE: provider/text/tool_call events, confirm flow) · `/voice/start|audio|interrupt|stop|confirm` · `/voice/wake_start|wake_chunk|wake_stop|wake_resume` · `/memory/store` · `/memory/forget` · `/memory/sessions/end` · `/reminders` (+ `/reminders/dismiss`) · `/proactive/*` · `/computer/start|stop|resume|confirm|undo` · `/plugins/<name>/enable|disable` · `/dashboard/revoke` · `/dashboard/keys` (keys RAM-only)

State object (`ShiraziState`, server.py:~130): registry, ladder, memory, voice (`VoiceManager`), wake (`VoiceFirstController`), computer (`ComputerManager`), proactive (`ProactiveEngine`), plugins (`PluginManager`), dashboard (`DashboardManager`).

---

## 6. Honest gaps — what does NOT exist in shirazi-core

- **No RAG engine.** No embeddings, no vector store, no document ingestion. `kb_repair` audits JSON files; `web_research` only *tracks* sources the model gathered. The two "rag" string hits are docstring mentions.
- **No Shamela / scholarly-library integration.** (That belongs to the separate SHIRAZI research project, not this repo.)
- **No Ollama / local-inference provider.** Providers are gemini, groq, openrouter only. No Arabic-script research support beyond Urdu regexes in memory/extract.py.
- **WindowsUIABackend.find() raises NotImplementedError** (core/computer.py:176) — the production Windows a11y grounding path is a documented interface, not code. Windows computer-use currently depends on VLM fallback (needs live keys).
- **Voice needs `google-genai` + a Gemini key** (501 otherwise); wake-word needs `openwakeword`+`onnxruntime` (501 otherwise); computer-use needs `mss`/`Pillow`/`pyautogui`; excel_writer needs `openpyxl`. All degrade honestly, none crash boot.
- **Dashboard is LAN HTTP without TLS** (documented; 256-bit tokens).
- API keys live in RAM only, passed per-request by the Electron shell; the core never persists them. There is no built-in key vault in the core itself.

## 7. Test inventory (stdlib `unittest`-style scripts, run via `python3 test_X.py`)

| file | tests | covers |
|---|---|---|
| test_memory.py | 37 | store recall/forget/dedupe/redact/sessions/reminders |
| test_problem_solver.py | 44 | 7-step methodology + 5 problem-solver plugins |
| test_more_plugins.py | 32 | second plugin batch |
| test_new_plugins.py | 21 | first plugin batch |
| test_wakeword.py | 16 | engine scoring, controller states, no-disk rule |
| test_voice_workflow.py | 11 | intents, confirm vocab, no-disk rule |
| test_qr.py | 9 | QR encode/decode round-trip |
| test_dashboard.py | 9 | pairing, device auth, revoke |
| test_plugins.py | 9 | discovery, manifest parse, permission scan, enable/disable |
| test_voice.py | 7 | mock backend session lifecycle |
| test_computer.py | check()-style | step kinds, grounding backends, dry-run actuator |
| test_voice_501_check.py | integration | real server boot w/o voice deps → honest 501 |
