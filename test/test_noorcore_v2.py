"""
NoorCore v2 improvements — acceptance tests.

  1. DEGRADED state renders without error (all themes).
  2. State transitions fire a pulse (pulse timer resets on set_state).
  3. Thinking depth: set_thinking_depth(0/1/2) clamps; affects THINKING only.
  4. Approval urgency: approval_wait_s() grows while AWAITING_APPROVAL,
     resets on leaving the state.
  5. Orchestrator progress: _set_progress/task_progress/active_task_progress
     report REAL step counts; None when no countable steps.
  6. VISUAL_MODES no longer contains "3d".
  7. Companion approval badge: pending_count() reflects the provider.
"""
import os
import tempfile
import time
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


def render(core, state, theme_name="noorcore", size=240):
    core.set_state(state)
    for _ in range(5):
        core.step(0.033, 0.3)
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(0xFF080D14)
    p = QPainter(img)
    core.paint(p, size / 2, size / 2, size * 0.28, NT.get_theme(theme_name))
    p.end()
    return img


class DegradedState(unittest.TestCase):
    def test_degraded_in_states(self):
        self.assertIn("DEGRADED", NT.CORE_STATES)

    def test_degraded_renders_all_themes(self):
        app()
        for theme in ("noorcore", "classic", "high_contrast"):
            c = NoorCore()
            img = render(c, "DEGRADED", theme)
            self.assertFalse(img.isNull(), f"DEGRADED failed on {theme}")

    def test_degraded_has_accent(self):
        th = NT.get_theme("noorcore")
        col = NT.state_color(th, "DEGRADED")
        self.assertTrue(col.startswith("#"))


class TransitionPulse(unittest.TestCase):
    def test_pulse_fires_on_change(self):
        c = NoorCore()
        c.set_state("THINKING")   # fires pulse: _pulse_t = 0
        self.assertEqual(c._pulse_t, 0.0)
        c.step(0.1, 0.0)
        c.step(0.1, 0.0)
        self.assertGreater(c._pulse_t, 0.15)  # timer advances
        c.set_state("SPEAKING")   # new transition resets it
        self.assertEqual(c._pulse_t, 0.0)

    def test_pulse_skipped_reduced_motion(self):
        app()
        c = NoorCore(reduced_motion=True)
        c.set_state("SPEAKING")
        c.step(0.05, 0.5)  # pulse active but must not draw
        img = QImage(240, 240, QImage.Format.Format_ARGB32)
        img.fill(0xFF080D14)
        p = QPainter(img)
        # must not raise under reduced motion
        c.paint(p, 120, 120, 67, NT.get_theme("noorcore"))
        p.end()
        self.assertFalse(img.isNull())


class ThinkingDepth(unittest.TestCase):
    def test_depth_clamps(self):
        c = NoorCore()
        c.set_thinking_depth(5)
        self.assertEqual(c._think_depth, 2)
        c.set_thinking_depth(-3)
        self.assertEqual(c._think_depth, 0)

    def test_depth_affects_thinking_render(self):
        app()
        for d in (0, 1, 2):
            c = NoorCore()
            c.set_thinking_depth(d)
            img = render(c, "THINKING")
            self.assertFalse(img.isNull(), f"depth {d} render failed")


class ApprovalUrgency(unittest.TestCase):
    def test_wait_grows_and_resets(self):
        c = NoorCore()
        self.assertEqual(c.approval_wait_s(), 0.0)
        c.set_state("AWAITING_APPROVAL")
        time.sleep(0.05)
        w = c.approval_wait_s()
        self.assertGreater(w, 0.0)
        self.assertLess(w, 5.0)
        c.set_state("IDLE")
        self.assertEqual(c.approval_wait_s(), 0.0)

    def test_urgency_renders(self):
        app()
        c = NoorCore()
        img = render(c, "AWAITING_APPROVAL")
        self.assertFalse(img.isNull())


class OrchestratorProgress(unittest.TestCase):
    def setUp(self):
        # Isolate the omnicontrol DB per test.
        self._tmp = tempfile.mkdtemp()
        os.environ["SHIRAZI_OMNI_DB"] = str(Path(self._tmp) / "omni.db")
        from core.omnicontrol import db as _db
        import importlib
        importlib.reload(_db)
        from core.omnicontrol import orchestrator as _orc
        importlib.reload(_orc)
        self.orc = _orc

    def test_progress_real_counts(self):
        plan = [{"tool": "t%d" % i, "resource": "r", "op": "read"}
                for i in range(4)]
        tid = self.orc.start("t", "ws", plan)
        self.assertAlmostEqual(self.orc.task_progress(tid), 0.0)  # 0/4 done
        # Simulate two steps done via the real helper.
        self.orc._set_progress(tid, 2, 4)
        self.assertAlmostEqual(self.orc.task_progress(tid), 0.5)
        self.orc._set_progress(tid, 4, 4)
        self.assertAlmostEqual(self.orc.task_progress(tid), 1.0)

    def test_progress_none_empty_plan(self):
        tid = self.orc.start("t", "ws", [])
        self.assertIsNone(self.orc.task_progress(tid))

    def test_progress_none_unknown(self):
        self.assertIsNone(self.orc.task_progress("nope"))

    def test_active_none_when_idle(self):
        self.assertIsNone(self.orc.active_task_progress())


class VisualModes(unittest.TestCase):
    def test_no_3d(self):
        self.assertNotIn("3d", NT.VISUAL_MODES)
        self.assertEqual(set(NT.VISUAL_MODES), {"core", "face"})


class CompanionBadge(unittest.TestCase):
    def test_pending_count(self):
        app()
        from core.companion import CompanionWindow
        w = CompanionWindow(pending_provider=lambda: 3)
        self.assertEqual(w.pending_count(), 3)
        w2 = CompanionWindow()
        self.assertEqual(w2.pending_count(), 0)
        w3 = CompanionWindow(pending_provider=lambda: (_ for _ in ()).throw(Exception()))
        self.assertEqual(w3.pending_count(), 0)


if __name__ == "__main__":
    unittest.main()
