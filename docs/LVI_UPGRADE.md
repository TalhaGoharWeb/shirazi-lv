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

## HUD wave (same day, at the user's direction)

- **Mark LVI's HUD panel is in.** `ProvidersOverlay` + `_ScrollSafeCombo`
  were ported into `ui.py` (byte-identical class; Shirazi's palette and
  `_HudOverlay` base already matched), together with the providers block
  of LVI's `memory/config_manager.py` (mode / pipeline / per-provider
  creds / sidecar, incl. the one-write `save_providers`). The SETUP
  drawer gained the **🔌 ENGINE & PROVIDERS** button; applying rebuilds
  the session through the same callback as an audio-device change.
  Shirazi's own HUD was NOT replaced wholesale — LVI's canvas is the
  same HUD family minus Shirazi's NoorCore / 3D avatar / OmniControl
  cards, so the panel was transplanted, not the window.
- **MYRA's edge glow is in** as `core/edge_glow.py`: four click-through
  strips + a badge, conical-gradient colours travelling the screen edge,
  `WDA_EXCLUDEFROMCAPTURE` so it never pollutes vision frames. Keyed to
  the 8 NoorCore states via the same `_noor_state()` the HUD uses;
  badge shows for AWAITING_APPROVAL ("Approval needed") and ERROR.
  Toggle in the CONTROLS drawer (🌈 EDGE GLOW), persisted, opt-in.
  MYRA's floating orb was NOT ported: Shirazi's floating NoorCore
  companion already fills that role.

## HUD replacement (later the same day, at the user's explicit direction)

The transplant above was not what the user wanted — they directed the
whole window replaced. Done:

- **`ui.py` is now Mark LVI's `ui.py`**, wholesale. Shirazi-side changes
  are limited to: SHIRAZI branding on user-visible defaults/labels, a
  `set_degraded_mode` compat method (logs; LVI has no degraded banner),
  the `on_close_request` ordered-shutdown hook in MainWindow.closeEvent
  (main.py sets it), the MYRA edge-glow wiring, and a `ShiraziUI =
  JarvisUI` alias. main.py's full 31-name UI contract was verified
  against the new window before and after.
- **The Iron Man 3D avatar is removed completely**: `core/avatar3d.py`,
  `ui/avatar3d.html`, `ui/three/`, the config `"3d"` HUD style,
  `is_3d_available()`, and its tests are all deleted.
- Retired with the old HUD: the NoorCore canvas and the floating
  companion's window wiring (`core/noorcore.py` / `core/companion.py`
  remain on disk, unwired, with their module tests). Shirazi-only HUD
  entry points (kids-mode and dashboard buttons) went with the old
  drawers; the underlying tools/plugins are unchanged.
- The edge glow survived the swap: its toggle lives in LVI's CONTROLS
  drawer, fed by the LVI canvas state (+ gateway approval check).

## Friendly conversation pack (2026-10-21)

Goal: conversation that feels like a friend, ChatGPT-voice style.

- **core/prompt.txt** — a new [CONVERSATION] section (small talk is part of
  the job; greet return visits with a remembered thread; notice the person;
  genuine follow-ups allowed, reflex closers banned; listening sounds;
  speak like a person, not a document — headline first, detail on offer).
  [VOICE] gained the warmth-in-specifics rule. [LANGUAGE]'s hard
  "never mix languages" rules were replaced with **mirror the user's own
  mix**. [JUDGEMENT] gained the repair carve-out: glide over garbled words,
  but never guess a garbled name/number that changes the outcome — ask one
  short question instead.
- **TOOL_STARTING watchdog** (`core/conversation.py` + main.py) — the
  prompt always documented this tag but nothing sent it. Now any tool
  still running after 2.5 s triggers one short spoken sentence in the
  user's language, so a slow tool no longer leaves dead air.
- **Voice barge-in, opt-in** — EchoGuard classification + BargeInVoter
  (consecutive-block voting) in the mic path, behind the
  `barge_in_enabled` config flag (default off; room-dependent, to be
  tried on real hardware). Server-side `interrupted` turns now drain
  queued audio and clear buffers immediately.

## Follow-ups worth doing

1. ~~Settings panel for providers~~ — **done** (HUD wave above). Next:
   wire `engine_pipeline` into the degraded-chat path so a configured
   pipeline actually takes conversations.
2. **`core/appidentity.py`** — LVI's fuzzy app index + "raise, don't
   duplicate" window focusing for `open_app`.
3. Remaining plain-string returns in `computer_settings.py` (type_text,
   press_key, scroll) can adopt `outcome` the same way.

## History reconciliation (2026-10-21)

The user's PC line (their snapshot commit "Fix onboarding UI: ghost widgets
+ clipped chips (280 green)", tree-identical reconstruction merged here as
second parent) and the LVI line were merged into one history:

- **Taken wholesale from the PC line** (LVI line had not touched them):
  secrets-store integration (`core/secrets_store.py`; config keys resolve
  OS credential store first, api_keys.json fallback), `core/profile.py` +
  `core/instructions.py` (versioned user profile, one-turn overrides),
  `core/onboarding.py`, `core/capabilities.py`, `core/health.py`,
  `core/backup.py`, the memory-tools / my-settings / example plugins,
  their dashboard + omnicontrol + memory-manager updates, and 13 new test
  files (283 tests pass in the sandbox run; 2 `test_nextsteps` cases need
  a real DISPLAY for pyautogui, and the Qt-collection files run on
  Windows as before).
- **Hand-merged**: main.py (their profile/instructions/health wiring +
  the friendly pack), memory/config_manager.py (three-way clean after
  line-ending normalization), README / WINDOWS_SETUP (LVI facts kept).
- **Kept from the LVI line**: ui.py — the PC line's ui.py work (onboarding
  overlays, +1,000 lines) targeted the retired Shirazi HUD that the user
  replaced with Mark LVI's window. The onboarding *logic* module is in;
  an onboarding panel for the LVI window is a separate build when wanted.
- requirements.txt / setup.py kept the base/full split (the PC line's
  single-file simplification dropped `setup.py --base`); stale "3D avatar"
  comments refreshed — WebEngine is optional legacy now.
- test_noorcore_v2 reuses an existing QApplication instance when another
  test module created one first (single-app-per-process rule).
