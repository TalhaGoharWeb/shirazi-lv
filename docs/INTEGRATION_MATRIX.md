# SHIRAZI LVI — Feature Integration Matrix

What was taken from each codebase, what was merged, and what was deliberately
left out (with reasons). "Shirazi" = TalhaGoharWeb/shirazi-personal-assistant
(original code); "Mark-LV" = FatihMakes/Mark-LV (CC BY-NC 4.0).

## Kept from Mark-LV (foundation, untouched or rebranded only)

| Feature | Status |
|---|---|
| PyQt6 holographic HUD + animated avatar | Kept as-is (rebranded SHIRAZI) |
| Gemini Live real-time voice loop | Kept as-is |
| 21 action modules (browser/computer/file/media/…) | Kept as-is |
| Plugin architecture (PLUGIN dict + run contract) | Kept; extended with 56 Shirazi tools |
| Confirm gate + undo stack | Kept as-is |
| Memory profile KV (JSON) + config manager | Kept; extended |
| Wake-word engine (openwakeword) | Kept; "Hey Shirazi" branding + custom-model support |
| Dashboard (phone pairing) | Kept as-is |
| Proactive engine | Kept as-is |

## Integrated from Shirazi (new capabilities)

| Shirazi capability | How integrated | Tests |
|---|---|---|
| Provider ladder (Groq/OpenRouter failover) | `core/shirazi_ladder.py`; `gemini.text()` falls back before giving up | 15 ✅ |
| 18 plugins → 55 tools (timer, notes, excel, quiz, mcq, urdu_drafter, etsy, web_research, file_organizer, clipboard, problem_solver, build_doctor, pc_health, kb_repair, task_recovery, trainer, doc_review, web_bookmark) | `plugins/shirazi_*.py` via `tools/port_shirazi_plugins.py` | 4 ✅ |
| Episodic memory (SQLite+FTS5/BM25, sessions, auto-summary) | `memory/shirazi_backend.py`; turn hooks in `main.py`; merged `search_memory` | 4 ✅ |
| Response-language pinning (Urdu / Roman Urdu / English) | `core/shirazi_language.py`; prompt directive + EdgeTTS `ur-PK` voice | 3 ✅ |
| 7-step problem-diagnosis methodology | `plugins/shirazi_problem_diagnose.py` | 3 ✅ |
| Model rung IDs (Oct 2026 snapshot) | Used for fallback rung defaults | — |

## Deliberately NOT ported (duplicates or out of scope)

| Shirazi capability | Reason |
|---|---|
| `core/voice.py` (Gemini Live sessions) | Duplicate — Mark-LV's Live loop is the voice path |
| `core/computer.py` (computer-use agent) | Duplicate — Mark-LV has computer_control actions; Shirazi's Windows backend is a `NotImplementedError` stub |
| `core/proactive.py` | Duplicate — Mark-LV has its own proactive engine |
| `core/dashboard.py` | Duplicate — Mark-LV has `dashboard/` |
| `core/selfknow.py` | Duplicate — Mark-LV's `system_status` tool covers it |
| `core/qr.py` | Duplicate — `qrcode` package already a dependency |
| Electron/React shell, HTTP sidecar | Not applicable — pure-Python app has no sidecar |
| RAG / embeddings / Shamela | Do not exist in shirazi-assistant (separate SHIRAZI project) |
| Ollama / local inference | Does not exist in shirazi-assistant |
| Full Urdu UI translation (323 Electron strings) | Out of scope — Electron strings don't apply to PyQt6; prompt-level Urdu shipped instead |

## Test report (2026-10-17)

- **29 passed, 0 failed.** Suites: `test_shirazi_ladder.py` (15), `test_shirazi_plugins.py` (4),
  `test_memory_unified.py` (4), `test_stage4.py` (6).
- Run with: `.venv/bin/python -m pytest test/ -q` (Linux) or `python -m pytest test/ -q` (Windows).
- **Not covered by automated tests (honest):** the PyQt6 HUD rendering (needs a
  display), the Gemini Live voice session (needs API key + mic/speaker),
  Windows-only code paths (Win32 APIs, Playwright browsers), the wake-word
  model download. These are verified on the user's Windows PC per
  `docs/WINDOWS_SETUP.md`.
