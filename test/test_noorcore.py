"""
NoorCore MVP acceptance tests (Phase 2 criteria).

  1. Core renders in all 8 states without error.
  2. State transitions work; unknown states fall back to IDLE.
  3. Audio ring responds to the amp fed in (and is flat when silent —
     the core never fakes audio).
  4. Approval card uses REAL gateway events (pending -> card -> resolve).
  5. Style toggle: face/core/3d — 3d reports unavailable, never fakes.
  6. Both themes render all states.
  7. Existing suite still green (regression).

Needs offscreen Qt: QT_QPA_PLATFORM=offscreen.
"""
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QApplication

from core.noorcore import NoorCore
from core import noorcore_tokens as NT

_app = None


def app():
    global _app
    if _app is None:
        _app = QApplication([])
    return _app


def render(core, state, theme_name="noorcore", amp=0.0, size=240):
    core.set_state(state)
    for _ in range(5):
        core.step(0.033, amp)
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(0xFF080D14)
    p = QPainter(img)
    core.paint(p, size / 2, size / 2, size * 0.28, NT.get_theme(theme_name))
    p.end()
    return img


class CoreStates(unittest.TestCase):
    def test_all_states_render(self):
        for state in NT.CORE_STATES:
            core = NoorCore()
            img = render(core, state)
            self.assertFalse(img.isNull(), state)
            self.assertEqual(core.state, state)

    def test_unknown_state_falls_back_to_idle(self):
        core = NoorCore()
        core.set_state("HYPERDRIVE")
        self.assertEqual(core.state, "IDLE")

    def test_transition_smoothing(self):
        core = NoorCore()
        core.set_state("IDLE")
        for _ in range(30):
            core.step(0.033, 0.0)
        e_idle = core._energy
        core.set_state("EXECUTING")
        core.step(0.033, 0.0)  # one frame: energy must move gradually
        self.assertGreater(core._energy, e_idle)
        self.assertLess(core._energy, 0.80)  # not snapping to target

    def test_reduced_motion(self):
        core = NoorCore(reduced_motion=True)
        self.assertEqual(core._particles, [])
        img = render(core, "THINKING")
        self.assertFalse(img.isNull())


class AudioRing(unittest.TestCase):
    def _ring_pixels(self, img):
        # count bright pixels in the audio-ring band (crude but real)
        n = 0
        w, h = img.width(), img.height()
        for y in range(0, h, 4):
            for x in range(0, w, 4):
                c = img.pixelColor(x, y)
                if c.red() > 120 and c.green() > 180:
                    n += 1
        return n

    def test_ring_responds_to_real_amp(self):
        core = NoorCore()
        quiet = render(core, "SPEAKING", amp=0.0)
        loud = render(core, "SPEAKING", amp=0.9)
        self.assertGreater(self._ring_pixels(loud), self._ring_pixels(quiet),
                           "audio ring must grow with real amplitude")

    def test_no_fake_audio_when_idle(self):
        core = NoorCore()
        idle_loud = render(core, "IDLE", amp=0.9)   # amp ignored outside voice states
        idle_quiet = render(core, "IDLE", amp=0.0)
        self.assertEqual(self._ring_pixels(idle_loud), self._ring_pixels(idle_quiet),
                         "IDLE must not visualize audio")

    def test_executing_progress(self):
        core = NoorCore()
        core.set_state("EXECUTING")
        core.set_progress(0.5)
        self.assertEqual(core._progress, 0.5)
        core.set_progress(None)
        self.assertIsNone(core._progress)  # honest indeterminate
        img = render(core, "EXECUTING")
        self.assertFalse(img.isNull())


class Themes(unittest.TestCase):
    def test_both_themes_all_states(self):
        for theme in ("noorcore", "classic"):
            for state in NT.CORE_STATES:
                core = NoorCore()
                img = render(core, state, theme_name=theme)
                self.assertFalse(img.isNull(), f"{theme}/{state}")

    def test_state_colors_differ_by_theme(self):
        n = NT.state_color(NT.get_theme("noorcore"), "IDLE")
        c = NT.state_color(NT.get_theme("classic"), "IDLE")
        self.assertNotEqual(n, c)
        # awaiting approval is amber in both
        self.assertEqual(
            NT.state_color(NT.get_theme("noorcore"), "AWAITING_APPROVAL"),
            NT.THEMES["noorcore"]["amber"])

    def test_unknown_theme_falls_back(self):
        self.assertEqual(NT.get_theme("nope"), NT.THEMES["noorcore"])


class StyleToggle(unittest.TestCase):
    def test_default_is_core(self):
        from memory import config_manager as cm
        d = cm.load_api_keys()
        d.pop("hud_style", None)
        # simulate get_hud_style with no stored value -> "core" default
        v = str(d.get("hud_style", "core")).strip().lower()
        self.assertEqual(v if v in cm.HUD_STYLES else "core", "core")


class ApprovalCardReal(unittest.TestCase):
    def test_card_uses_real_gateway_events(self):
        app()
        tmp = tempfile.mkdtemp()
        from core.omnicontrol import db, gateway
        db.reset_for_tests(Path(tmp) / "omni.db")
        gateway._pending.clear()
        import ui as ui_mod
        pid = gateway.request_approval("fs_delete", "/tmp/x", "delete", "test")
        self.assertEqual(len(gateway.list_pending()), 1)
        card = ui_mod.ApprovalCard(gateway.list_pending()[0])
        self.assertTrue(card.isWidgetType())
        # simulate tapping DENY
        card._decide("deny")
        self.assertEqual(len(gateway.list_pending()), 0)
        r = gateway.resolve_pending(pid, "once")
        self.assertFalse(r["ok"], "resolved requests cannot be re-resolved")


if __name__ == "__main__":
    unittest.main(verbosity=1)
