"""
NoorCore design tokens — the single source of visual truth.

Two themes:
  "noorcore" — NoorCore Dark (default): obsidian backgrounds, electric cyan,
               emerald intelligence accents, restrained heritage gold.
  "classic"  — Classic Shirazi: the pre-NoorCore palette, preserved as a
               selectable alternative.

Every component reads colors/spacing/motion from here — no hardcoded hex in
paint code. Adding a future theme means adding one dict here, not touching
components. Theme choice never affects functionality or security behavior.
"""
from __future__ import annotations

# ── NoorCore Dark (spec §3) ──────────────────────────────────────────────────
NOORCORE_DARK = {
    "name": "NoorCore Dark",
    "bg":         "#080D14",
    "surface":    "#101824",
    "surface2":   "#142130",
    "cyan":       "#38BDF8",
    "voice_cyan": "#71D9FF",
    "emerald":    "#20D6B0",
    "gold":       "#E9BD68",
    "text_dim":   "#A6B6C8",
    "text":       "#F2F7FC",
    "amber":      "#F2B84B",
    "red":        "#FF647C",
    # derived roles
    "border":     "#1B2A3D",
    "panel":      "#101824",
    "success":    "#20D6B0",
}

# ── Classic Shirazi (pre-NoorCore palette, preserved) ─────────────────────────
CLASSIC = {
    "name": "Classic Shirazi",
    "bg":         "#00060a",
    "surface":    "#010d14",
    "surface2":   "#010f18",
    "cyan":       "#00d4ff",
    "voice_cyan": "#8ffcff",
    "emerald":    "#00ff88",
    "gold":       "#ffcc00",
    "text_dim":   "#3a8a9a",
    "text":       "#8ffcff",
    "amber":      "#ff6b00",
    "red":        "#ff3355",
    "border":     "#0d3347",
    "panel":      "#010d14",
    "success":    "#00ff88",
}

# ── High Contrast (Phase 3.8 accessibility) ────────────────────────────────
HIGH_CONTRAST = {
    "name": "High Contrast",
    "bg":         "#000000",
    "surface":    "#0A0A0A",
    "surface2":   "#1A1A1A",
    "cyan":       "#00E5FF",
    "voice_cyan": "#80F0FF",
    "emerald":    "#00FF9D",
    "gold":       "#FFD700",
    "text_dim":   "#D0D0D0",
    "text":       "#FFFFFF",
    "amber":      "#FFC400",
    "red":        "#FF1744",
    "border":     "#FFFFFF",
    "panel":      "#0A0A0A",
    "success":    "#00FF9D",
}

THEMES = {"noorcore": NOORCORE_DARK, "classic": CLASSIC,
          "high_contrast": HIGH_CONTRAST}
DEFAULT_THEME = "noorcore"

# ── State → accent roles (both themes support all states) ─────────────────────
# Maps core state -> theme key for the state ring / indicators.
STATE_ACCENT = {
    "IDLE":              "cyan",
    "LISTENING":         "voice_cyan",
    "THINKING":          "emerald",
    "SPEAKING":          "voice_cyan",
    "EXECUTING":         "cyan",
    "AWAITING_APPROVAL": "amber",
    "ERROR":             "red",
    "OFFLINE":           "text_dim",
    "DEGRADED":          "gold",   # honest reduced capability — warm, not alarming
}
CORE_STATES = tuple(STATE_ACCENT)

# ── Spacing / radii ───────────────────────────────────────────────────────────
SPACE_XS, SPACE_S, SPACE_M, SPACE_L = 4, 8, 16, 24
RADIUS_S, RADIUS_M, RADIUS_L = 6, 12, 18

# ── Motion (ms) — named durations; reduced-motion collapses these to 0 ───────
DUR_FAST, DUR_NORMAL, DUR_SLOW = 120, 220, 450

# ── Visual modes (decision 2: coexist via style toggle) ───────────────────────
VISUAL_MODES = ("core", "face")
DEFAULT_MODE = "core"


def get_theme(name: str | None = None) -> dict:
    """Theme dict for `name`; falls back to default. Never raises.
    Phase 3.8: high-contrast accessibility setting overrides the theme."""
    try:
        from core.accessibility import get_high_contrast
        if get_high_contrast():
            return THEMES["high_contrast"]
    except Exception:
        pass
    if name in THEMES:
        return THEMES[name]
    return THEMES[DEFAULT_THEME]


def state_color(theme: dict, state: str) -> str:
    """Accent hex for a core state under the given theme."""
    key = STATE_ACCENT.get(state, "cyan")
    return theme.get(key, theme["cyan"])
