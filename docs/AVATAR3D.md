# SHIRAZI 3D Avatar — Iron Man Mark III

The third HUD centrepiece: the user's Iron Man Mark III **helmet** (GLB)
rendered live with Three.js inside the app.

## How it works

- **Model:** `assets/avatar/ironman.glb` (12.2 MB) — the Mark III helmet,
  static (no rig, no animations), 8 PBR textures. Ships inside the app;
  no download needed.
- **Renderer:** `ui/avatar3d.html` — local Three.js r160 (MIT, vendored in
  `ui/three/`), heroic 3-point lighting (warm key, cool rim, eye-glow fill),
  transparent background so it sits on the HUD.
- **Bridge:** `core/avatar3d.py` — QWebEngineView wrapper exposing
  `set_state()` / `set_amp()`; the same assistant state every other visual
  mode uses.

## Behavior (all from real events)

| Assistant state | Helmet does |
|---|---|
| IDLE | gentle heroic sway |
| LISTENING | sway + slight lean-in energy |
| SPEAKING | amp-driven nod/bob; eye/arc glow pulses with the **real** playback amplitude |
| THINKING | emerald rim light |
| AWAITING_APPROVAL | amber rim light |
| ERROR | red rim light |

No fake motion: every movement follows the real audio amplitude — never invented.

## Selecting it

Settings → HUD button cycles **Animated Face → NoorCore → 3D Iron Man**.
Switching never interrupts a conversation or task; all modes share one
state/voice/task/permission pipeline.

If WebEngine or the model file is missing, "3d" is reported unavailable and
the HUD falls back to NoorCore — never a placeholder.

## Requirements

`PyQt6-WebEngine` (in requirements.txt; `pip install -r requirements.txt`).
First load compiles shaders — a brief pause is normal.

## Swapping the model

Drop any GLB/GLTF over `assets/avatar/ironman.glb` (keep the name) and
restart. Rigged models with animations get the animation-driven treatment
automatically; static models get the amp-driven sway + glow treatment.
