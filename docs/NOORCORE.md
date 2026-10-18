# SHIRAZI NOORCORE — MVP Guide

The Living Intelligence Core: Shirazi's signature animated centrepiece,
replacing the old fallback reactor core as the default HUD visual.

## Visual modes (Settings → HUD style)

- **Core** (default) — NoorCore abstract intelligence sphere.
- **Face** — the holographic head (unchanged).

Switching modes never interrupts a conversation or task: all modes share the
same assistant state, voice events, task status, and permission system.

## Themes (Settings → ◉ NOORCORE, persisted)

- **NoorCore Dark** (default): obsidian `#080D14`, electric cyan `#38BDF8`,
  emerald `#20D6B0`, restrained gold `#E9BD68`.
- **Classic Shirazi**: the previous palette, preserved.
- **High Contrast**: accessibility theme (also auto-applied by the
  high-contrast accessibility setting).

Theme changes never affect functionality or security behavior. The ◉ NOORCORE
settings panel shows a live mini-core preview that re-renders instantly when
you pick a theme, plus reduced-motion and text-size controls.

## The 9 states (all driven by real events)

| State | Source |
|---|---|
| IDLE | nothing happening — slow breathing, no fake activity |
| LISTENING | mic open; audio ring follows real mic amplitude |
| THINKING | model request in flight; faster orbitals (`set_thinking_depth(1/2)` for visibly deeper work) |
| SPEAKING | TTS playing; ring follows real playback amplitude |
| EXECUTING | an OMNICONTROL orchestrator task is RUNNING; ring shows REAL step progress (from the task's step counts), honest sweep otherwise |
| AWAITING_APPROVAL | gateway has pending approval requests + approval card; the amber pulse quickens gently the longer it waits (real elapsed time) |
| ERROR | provider/operation failure |
| OFFLINE | connection lost |
| DEGRADED | Live voice is down — text-only fallback is serving (desaturated dashed ring; never pretends voice works) |

Every state change fires a brief transition pulse (expanding ring, ~0.6s) so
the eye catches the change. The status line under the core names the state in
plain words ("Listening…", "Needs your approval", "Working… 42%").

## Approval card

When a tool needs approval, a card appears on the HUD with
**Allow Once / Allow Always / Deny**. The card is color-coded by risk tier
(LOW cyan / MODERATE gold / HIGH amber / CRITICAL red) and shows a live
"waiting mm:ss" timer. The decision goes straight to
`gateway.resolve_pending()` — the model cannot approve itself. The dashboard
Permissions view remains the canonical surface. The floating companion shows
an amber badge with the pending count, so approvals aren't missed while the
main window is minimized.

## For developers

- `core/noorcore.py` — renderer (`step(dt, amp)` + `paint(p, cx, cy, r, theme)`).
- `core/noorcore_tokens.py` — themes, state accents, motion durations.
- New themes: add one dict to `THEMES` in tokens — no component changes.
- Tests: `pytest test/test_noorcore.py` (13 tests: states, transitions,
  audio-ring honesty, approval card on real gateway events, toggle, themes).

## Honest limitations (MVP)

- Floating companion is Phase 4 (opt-in setting lands with it).
- Contextual themes (coding/research/…) are Phase 5.
- 60 FPS is a target, not a claim — frame cost follows the existing
  paint-throttle pattern; measure on your own hardware.
- Multi-monitor/DPI behavior of future floating windows needs testing on a
  real Windows PC.
