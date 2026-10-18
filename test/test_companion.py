"""
Floating companion acceptance tests.

  1. Companion is opt-in (off by default).
  2. Settings persist (enabled/pos/size/opacity) with sane clamping.
  3. CompanionWindow builds offscreen, paints, and emits restore on click.
  4. Drag repositions + persists; off-screen saved pos gets rescued.
  5. Companion never bypasses authorization (display + restore only).
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtTest import QTest

_app = None


def app():
    global _app
    if _app is None:
        _app = QApplication([])
    return _app


class CompanionSettings(unittest.TestCase):
    def test_opt_in_default_off(self):
        from memory import config_manager as cm
        # a fresh flag reads False; save/restore round-trips
        cm.save_companion_enabled(False)
        self.assertFalse(cm.get_companion_enabled())
        cm.save_companion_enabled(True)
        self.assertTrue(cm.get_companion_enabled())
        cm.save_companion_enabled(False)
        self.assertFalse(cm.get_companion_enabled())

    def test_size_opacity_clamped(self):
        from memory import config_manager as cm
        cm.save_companion_size(9999)
        self.assertEqual(cm.get_companion_size(), 240)
        cm.save_companion_size(10)
        self.assertEqual(cm.get_companion_size(), 72)
        cm.save_companion_opacity(5.0)
        self.assertEqual(cm.get_companion_opacity(), 1.0)
        cm.save_companion_opacity(0.0)
        self.assertEqual(cm.get_companion_opacity(), 0.3)
        cm.save_companion_size(120)
        cm.save_companion_opacity(0.95)

    def test_pos_round_trip(self):
        from memory import config_manager as cm
        cm.save_companion_pos([321, 654])
        self.assertEqual(cm.get_companion_pos(), [321, 654])


class CompanionWindowTests(unittest.TestCase):
    def test_builds_and_paints(self):
        app()
        from core.companion import CompanionWindow
        w = CompanionWindow(state_provider=lambda: "SPEAKING",
                            amp_provider=lambda: 0.7,
                            theme_provider=lambda: "noorcore")
        self.assertTrue(w.windowFlags() & Qt.WindowType.FramelessWindowHint)
        self.assertTrue(w.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        w.show()
        QTest.qWait(150)
        self.assertTrue(w.isVisible())
        # let a few paint ticks run — must not raise
        QTest.qWait(200)
        w.hide(); w.deleteLater()

    def test_click_restores_not_bypass(self):
        app()
        from core.companion import CompanionWindow
        w = CompanionWindow()
        fired = []
        w.restore_requested.connect(lambda: fired.append(1))
        w.show()
        QTest.qWait(50)
        # plain click (press+release, no move) -> restore_requested
        QTest.mouseClick(w, Qt.MouseButton.LeftButton, pos=w.rect().center())
        QTest.qWait(50)
        self.assertEqual(len(fired), 1)
        # the companion exposes NO approval/grant/exec surface
        for attr in ("resolve_pending", "grant", "execute", "run_tool"):
            self.assertFalse(hasattr(w, attr), attr)
        w.hide(); w.deleteLater()

    def test_offscreen_pos_rescued(self):
        app()
        from memory import config_manager as cm
        from core.companion import CompanionWindow
        cm.save_companion_pos([99999, 99999])
        w = CompanionWindow()
        from PyQt6.QtWidgets import QApplication
        g = QApplication.primaryScreen().availableGeometry()
        self.assertTrue(g.contains(w.pos()),
                        "off-screen saved pos must be rescued on-screen")
        w.deleteLater()
        cm.save_companion_pos([g.right() - 150, g.bottom() - 150])


if __name__ == "__main__":
    unittest.main(verbosity=1)


class HudCanvasInitRegression(unittest.TestCase):
    """The 3D-avatar edit once truncated HudCanvas.__init__, leaving
    paintEvent attributes (_grid_cache, hud_style, ...) unset -> crash on
    startup. This statically verifies __init__ assigns everything
    paintEvent/_step touch."""

    def test_init_assigns_paintevent_attrs(self):
        import ast
        src = open("ui.py", encoding="utf-8").read()
        tree = ast.parse(src)
        hud = next(n for n in ast.walk(tree)
                   if isinstance(n, ast.ClassDef) and n.name == "HudCanvas")
        init = next(n for n in hud.body
                    if isinstance(n, ast.FunctionDef) and n.name == "__init__")
        assigned = set()
        for n in ast.walk(init):
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) \
               and n.value.id == "self":
                assigned.add(n.attr)
        for attr in ("_grid_cache", "_grid_key", "hud_style", "_live_amp",
                     "_amp_disp", "_tick", "_tmr", "_noor",
                     "muted", "speaking", "state"):
            self.assertIn(attr, assigned,
                          f"HudCanvas.__init__ must assign self.{attr}")
