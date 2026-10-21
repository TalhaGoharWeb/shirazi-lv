# SHIRAZI LV — Personal Companion Upgrade: Phase 1 Audit

Date: 2026-10-18. Audited against local repo HEAD (`integration`).

## What exists today

| System | Location | State |
|---|---|---|
| Startup / first-run | `main.py` → `ShiraziUI` → `MainWindow`; `SetupOverlay` for API keys | Works. No user-profile onboarding. |
| Settings storage | `config/api_keys.json` (mixed secrets + `assistant_name`, `user_name`, `os_system`) | Works, but secrets and profile are mingled. |
| Profile | `assistant_name`, `user_name` in api_keys.json via `config_manager` | Minimal. No actual/preferred name split, no languages, style, rules. |
| Memory (semantic) | `memory/memory_manager.py` — JSON dict, categories, keyword search, trim | Works. No provenance, no per-category retention. |
| Memory (episodic) | `memory/shirazi_backend.py` — SQLite + FTS5/BM25, per-turn | Works. `record_turn`/`recall_episodic`. |
| Memory viewer | `MemoryOverlay` (ui.py:2705) — lists entries, delete | Basic. No search/filter/edit, no categories view. |
| System prompt | `main.py::_build_config` — time + identity + memory + prompt.txt + language directive | Good injection point. Identity uses `user_name` directly as the address form. |
| Voice | wake word, STT/TTS, language pinning (`core/shirazi_language.py`) | Works. No per-language voice prefs. |
| Backup / restore | — | **Missing.** |
| Health checks | ad-hoc log lines | **Missing as a system.** |
| Crash recovery | task checkpoints exist (`shirazi_task_checkpoint`) | Partial; no restart detection. |
| Provider resilience | `core/shirazi_ladder.py` failover, reconnect loop | Works. |

## Gaps this upgrade fills

1. No structured, versioned user profile (actual vs preferred name, 4 language prefs, style, length, rules).
2. No onboarding; new users start from a blank slate.
3. Preferences live in prompts only — no enforcement layer, no temp-override handling.
4. Memory has no provenance, no Memory Center management, no retention policies.
5. No backup/restore at all — reinstall = total loss.
6. No startup health checks or database recovery.

## Data-flow (after upgrade)

```
Onboarding overlay → core/profile.py (~/.shirazi/profile.json, v1)
                          ↓
core/instructions.py → profile directive block → main.py::_build_config
                          ↓ (also: temp-override detection per turn)
memory (categories+provenance) → Memory Center UI
                          ↓
core/backup.py → versioned ZIP (manifest, hashes, no secrets) → restore/merge
core/health.py → startup checks → log + UI
```

## Migration safety

- Existing `user_name` → `preferred_name`; `assistant_name` → profile (default Shirazi).
- Existing memories preserved; provenance backfilled as `legacy`.
- Profile file is separate from `api_keys.json`; secrets never enter the profile.
