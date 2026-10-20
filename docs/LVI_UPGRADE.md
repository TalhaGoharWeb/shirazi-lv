# Shirazi LVI — Upgrade Notes

What the LVI wave changed, where it came from, and what is deliberately
left for a follow-up. Sources: **Mark LVI** (FatihMakes, CC BY-NC 4.0) and
**MYRA ULTRA** (Vikas, MIT) — full notices in `docs/ATTRIBUTION.md`.

## From Mark LVI

- **`providers/`** — the pluggable provider engine, ported whole with its
  self-tests (`python -m providers._tests`: 85/87 pass here; the 2
  remaining checks exercise LVI's settings-panel UI and its rewritten
  `core/gemini.py` ladder internals, which were out of this port's scope).
  Bring-your-own hearing (Whisper), thinking (any OpenAI-compatible
  endpoint) and speaking (Piper / system / ElevenLabs). The package is
  lazily imported — nothing in the running app changes until a caller
  builds a pipeline, exactly as upstream designed it.
  One adaptation: `providers/schema.py` falls back to a local
  `META_KEYS`/`strip_meta` because Shirazi's `core/action_loader.py`
  predates those helpers.
- **`core/outcome.py`** — outcome honesty, wired into:
  - `actions/open_app.py` — a launch is verified against the process
    table (≤6 s poll): `done` only when the app actually appeared,
    `unverified` when it could not be confirmed, `failed` when nothing
    answered. (Synchronous, where upstream reports `started` on a
    background thread — Shirazi has no follow-up channel on this path,
    and a `started` with no follow-up would recreate the false-success
    problem this module exists to kill.)
  - `actions/computer_settings.py` — `close_app` is now an honest named
    refusal (nothing in this build closes an app by name) instead of a
    blind Alt+F4; volume/brightness are read back before claiming `done`;
    unknown actions return `outcome.ask`.
  - `actions/web_search.py` — results return wrapped in
    `outcome.untrusted("web", …)`, and `core/prompt.txt` gained the
    matching **[UNTRUSTED CONTENT]** rule: wrapped text is data, never
    instructions.

## From MYRA ULTRA (re-implemented as native Shirazi plugins)

| Plugin | What it does |
|---|---|
| `shirazi_spotify` | Spotify play/pause/next with **no API account**: `spotify:search:` URI, screen-reader-flag UIA click on the top result, window-title verification. |
| `shirazi_qr` | QR maker (text/link), Wi-Fi join QRs, and offline QR reading via OpenCV. |
| `shirazi_ppt_create` | Real `.pptx` decks from a spoken outline (Shirazi could only read them before). |
| `shirazi_website` | WebForge in miniature: description → SMART-ladder-generated single-page site → saved under Documents/Shirazi Websites and opened. Offline template fallback; **no auto-deploy** (publishing needs the user's own tokens and say-so). |
| `shirazi_expense` | Kharcha log with monthly totals by category, stored with the episodic memory data. |
| `shirazi_duplicates` | Read-only duplicate-file finder (size pre-filter + SHA-256); reports, never deletes. |

All six are registered in OmniControl's risk map (MODERATE; duplicates
LOW). `core/prompt.txt` also gained MYRA's vision anti-hallucination rule.

Deliberately **not** taken from MYRA: the Wi-Fi password reader and
confirmation-free WhatsApp sending — both clash with OmniControl.

## Follow-ups worth doing

1. **Settings panel for providers** — LVI's ⚙ → ENGINE & PROVIDERS overlay
   (`ui.py` + `memory/config_manager.py` helpers) so the engine can be
   chosen in the UI instead of by config; then wire `engine_pipeline`
   into the degraded-chat path.
2. **`core/appidentity.py`** — LVI's fuzzy app index + "raise, don't
   duplicate" window focusing for `open_app`.
3. Remaining plain-string returns in `computer_settings.py` (type_text,
   press_key, scroll) can adopt `outcome` the same way.
