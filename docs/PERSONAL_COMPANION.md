# SHIRAZI LV — Personal AI Companion Upgrade

Shirazi is now a genuinely personal assistant: it learns how you want to
interact, remembers it across restarts, and can restore everything after a
reinstall or a move to a new computer.

## What was built

| Area | Implementation |
|---|---|
| User profile | `core/profile.py` — versioned JSON at `~/.shirazi/profile.json`, separate from credentials and chat memory |
| Onboarding | `core/onboarding.py` + `OnboardingOverlay` — 9-question conversational flow, offline-capable, resumable, skippable |
| Instruction enforcement | `core/instructions.py` — profile block injected into every model request; one-turn overrides never rewrite the profile |
| Memory | Provenance (`source`, `created`, `origin`), duplicate detection, secret refusal, search/filter/edit in the Memory Center, `shirazi_memory_tools` plugin |
| Backup & Restore | `core/backup.py` — versioned ZIPs with manifest + SHA-256; merge/replace restore; `BackupOverlay` UI |
| Health & recovery | `core/health.py` — 8 startup checks; crash detection via lockfile; incomplete-task scan |

## The profile

Fields (stable internal identifiers): `actual_name`, `preferred_name`,
`preferred_form_of_address`, `assistant_name` (default "Shirazi"),
`conversation_language`, `written_language`, `spoken_language`,
`interface_language`, `preferred_voice`, `speech_rate`,
`communication_style[]`, `response_length_preference`,
`persistent_instructions[]`, `user_defined_boundaries[]`,
`memory_preferences{}`, `onboarding_completed`, `profile_schema_version`,
`created_at`, `updated_at`.

Privacy rules enforced in code:
- `actual_name` is never used to address you and never enters model context.
- Only `preferred_name` / `preferred_form_of_address` address you.
- Boundaries are conversational expectations — they never grant tool
  permissions (OmniControl owns authorization).

Legacy `user_name` / `assistant_name` from `config/api_keys.json` migrate
into the profile automatically on first load.

## Onboarding

Appears once: after a provider is configured and the first connection
succeeds, if no completed profile exists. Reopen anytime from the controls
drawer (👤 PROFILE ONBOARDING). Every answer saves immediately; a restart
resumes where you left off. Works with all providers offline.

## Instruction hierarchy

1. Platform safety & app security controls
2. Developer restrictions & mandatory policies
3. Your saved preferences & instructions
4. Current-session (one-turn) instructions
5. Default behavior

Saying "answer this in English just this once" affects one response only —
your saved Urdu preference stays untouched.

## Backup format

`shirazi-backup-<kind>-<timestamp>.zip`:
- `manifest.json` — schema version, timestamps, app version, per-file
  SHA-256, record counts
- `profile.json`, `memory_long_term.json`, `memory_episodic.json`,
  `omnicontrol.json` (folders/repos only), `app_config.json` (non-secret)

Never included: `api_keys.json`, credential stores, tokens, secrets.
After restoring on a new machine, re-enter provider keys in Settings.

Restore modes: **Merge** (existing records win unless the backup copy is
newer) and **Replace** (takes a safety backup first, requires explicit
human confirmation through the app's confirmation gate).

## Reinstall recovery

1. Install Shirazi LV. 2. Open 💾 BACKUP & RESTORE. 3. Inspect the backup.
4. Restore (merge or replace). 5. Re-enter API keys. 6. Done — no repeated
onboarding.

## Health checks

At startup: config, profile, memory, secret store, providers, audio,
dependencies, backups. Failures are logged; non-fatal ones never block the
UI. A leftover `running.lock` means the previous run crashed — incomplete
tasks are reported.

## Limitations (honest)

- Scheduled/automatic backups are not implemented; create them manually.
- Backup reminders are not scheduled; the overlay shows backup dates.
- Interface-language switching translates new strings only where the UI
  already supports it; full Urdu/Arabic UI localization is partial.
- Voice selection is a stored preference; available voices depend on the
  platform TTS engines.
- Crash recovery covers task checkpoints, not mid-tool-call side effects —
  destructive actions are never auto-retried.
