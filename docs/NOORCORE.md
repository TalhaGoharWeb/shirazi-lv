# SHIRAZI NOORCORE — MVP Guide

The Living Intelligence Core: Shirazi's signature animated centrepiece,
replacing the old fallback reactor core as the default HUD visual.

## Visual modes (Settings → HUD style)

- **Core** (default) — NoorCore abstract intelligence sphere.
- **Face** — the holographic head (unchanged).
- **3D** — reserved for the 3D avatar track; currently unavailable. The HUD
  falls back to Core and says so — it never fakes 3D.

Switching modes never interrupts a conversation or task: all modes share the
same assistant state, voice events, task status, and permission system.

## Themes (Settings → Theme, persisted)

- **NoorCore Dark** (default): obsidian `#080D14`, electric cyan `#38BDF8`,
  emerald `#20D6B0`, restrained gold `#E9BD68`.
- **Classic Shirazi**: the previous palette, preserved.

Theme changes never affect functionality or security behavior.

## The 8 states (all driven by real events)

| State | Source |
|---|---|
| IDLE | nothing happening — slow breathing, no fake activity |
| LISTENING | mic open; audio ring follows real mic amplitude |
| THINKING | model request in flight; faster orbitals |
| SPEAKING | TTS playing; ring follows real playback amplitude |
| EXECUTING | an OMNICONTROL orchestrator task is RUNNING; ring shows real progress when measurable, honest sweep otherwise |
| AWAITING_APPROVAL | gateway has pending approval requests (steady amber) + approval card |
| ERROR | provider/operation failure (set via `set_state("ERROR")`) |
| OFFLINE | connection lost (set via `set_state("OFFLINE")`) |

## Approval card

When a HIGH-risk tool needs approval, a card appears on the HUD with
**Allow Once / Allow Always / Deny**. The decision goes straight to
`gateway.resolve_pending()` — the model cannot approve itself. The dashboard
Permissions view remains the canonical surface.

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
