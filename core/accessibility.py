"""
Phase 3.8 — Accessible interaction.

Settings (persisted in api_keys.json alongside other prefs):
  text_scale     0.8–2.0 (default 1.0) — scales UI fonts.
  reduced_motion bool (default False) — collapses animations to 0ms.
  high_contrast  bool (default False) — high-contrast theme variant.

Helpers are pure and never raise; the UI reads them at build time and
when the user changes them in Settings.
"""
from __future__ import annotations

from memory import config_manager as _cm

_DEFAULTS = {
    "a11y_text_scale": 1.0,
    "a11y_reduced_motion": False,
    "a11y_high_contrast": False,
}


def _get(key: str):
    try:
        return _cm.load_api_keys().get(key, _DEFAULTS[key])
    except Exception:
        return _DEFAULTS[key]


def _set(key: str, value) -> None:
    import json
    _cm.ensure_config_dir()
    data: dict = {}
    p = _cm.CONFIG_FILE
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data[key] = value
    p.write_text(json.dumps(data, indent=4), encoding="utf-8")


def get_text_scale() -> float:
    try:
        v = float(_get("a11y_text_scale"))
        return min(2.0, max(0.8, v))
    except Exception:
        return 1.0


def set_text_scale(v: float) -> None:
    _set("a11y_text_scale", min(2.0, max(0.8, float(v))))


def get_reduced_motion() -> bool:
    return bool(_get("a11y_reduced_motion"))


def set_reduced_motion(v: bool) -> None:
    _set("a11y_reduced_motion", bool(v))


def get_high_contrast() -> bool:
    return bool(_get("a11y_high_contrast"))


def set_high_contrast(v: bool) -> None:
    _set("a11y_high_contrast", bool(v))


def motion_duration(base_ms: int) -> int:
    """Animation duration honoring reduced-motion. Never raises."""
    try:
        return 0 if get_reduced_motion() else int(base_ms)
    except Exception:
        return int(base_ms)


def scaled_font_size(base_pt: int) -> int:
    """Font size honoring text scale. Never raises."""
    try:
        return max(6, round(base_pt * get_text_scale()))
    except Exception:
        return base_pt
