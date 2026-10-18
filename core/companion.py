"""
Floating NoorCore companion — the opt-in mini core that stays visible while
the main window is minimized.

- Frameless, always-on-top, translucent; never steals focus (no taskbar entry,
  click-through is OFF so it stays clickable, but it never activates itself).
- Renders the same NoorCore (core/noorcore.py) at small size, driven by the
  same real state + audio amplitude the HUD uses.
- Draggable; position/size/opacity persisted via config_manager.
- Off-screen rescue: if the saved position is outside every current screen,
  it re-docks to the primary screen's bottom-right.
- Click restores the main window. Right-click opens a small menu:
  voice on/off, restore, hide companion.
- The companion never bypasses authorization: it is a display + restore
  affordance only. Approvals still need the dashboard/HUD card tap.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, QPoint, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QWidget, QMenu

try:
    from core.noorcore import NoorCore
except Exception:
    NoorCore = None

try:
    from core import noorcore_tokens as _NT
except Exception:
    _NT = None


class CompanionWindow(QWidget):
    restore_requested = pyqtSignal()
    voice_toggled = pyqtSignal(bool)
    hide_requested = pyqtSignal()

    def __init__(self, state_provider=None, amp_provider=None, theme_provider=None,
                 pending_provider=None):
        super().__init__(None)
        self._state_provider = state_provider or (lambda: "IDLE")
        self._amp_provider = amp_provider or (lambda: 0.0)
        self._theme_provider = theme_provider or (lambda: "noorcore")
        # pending_provider -> int count of approvals waiting. When > 0 the
        # companion paints an amber badge so a minimized user still notices.
        self._pending_provider = pending_provider or (lambda: 0)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool  # no taskbar entry, never steals focus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self._core = NoorCore() if NoorCore is not None else None
        self._drag_pos = None
        self._moved = True

        try:
            from memory import config_manager as cm
            size = int(cm.get_companion_size() or 120)
            op = float(cm.get_companion_opacity() or 0.95)
        except Exception:
            size, op = 120, 0.95
        size = max(72, min(240, size))
        self.resize(size, size)
        self.setWindowOpacity(max(0.3, min(1.0, op)))

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)  # 20 Hz — cheap at this size

        self._place()

    # ── placement ──────────────────────────────────────────────────────────
    def _place(self) -> None:
        try:
            from memory import config_manager as cm
            from PyQt6.QtWidgets import QApplication
            saved = cm.get_companion_pos()
            pt = None
            if isinstance(saved, (list, tuple)) and len(saved) == 2:
                pt = QPoint(int(saved[0]), int(saved[1]))
                # off-screen rescue: must intersect at least one screen
                ok = any(s.availableGeometry().contains(pt)
                         for s in QApplication.screens())
                if not ok:
                    pt = None
            if pt is None:
                g = QApplication.primaryScreen().availableGeometry()
                pt = QPoint(g.right() - self.width() - 24,
                            g.bottom() - self.height() - 24)
            self.move(pt)
        except Exception:
            pass

    def _save_pos(self) -> None:
        try:
            from memory import config_manager as cm
            cm.save_companion_pos([self.x(), self.y()])
        except Exception:
            pass

    # ── interaction ────────────────────────────────────────────────────────
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._moved = False
        elif e.button() == Qt.MouseButton.RightButton:
            self._menu(e.globalPosition().toPoint())
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag_pos is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)
            self._moved = True
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        moved = getattr(self, "_moved", True)
        self._drag_pos = None
        super().mouseReleaseEvent(e)
        if e.button() == Qt.MouseButton.LeftButton:
            if not moved:
                self.restore_requested.emit()  # plain click restores
            else:
                self._save_pos()               # drag only repositions

    def _menu(self, pos) -> None:
        m = QMenu(self)
        m.setStyleSheet("QMenu { background: #101824; color: #F2F7FC; "
                        "border: 1px solid #38BDF8; }"
                        "QMenu::item:selected { background: #142130; }")
        try:
            from memory import config_manager as cm
            voice_on = bool(cm.get_wake_enabled()) if hasattr(cm, "get_wake_enabled") else True
        except Exception:
            voice_on = True
        a_voice = m.addAction("🔇 Mute voice" if voice_on else "🔊 Unmute voice")
        a_restore = m.addAction("⤢ Restore SHIRAZI")
        m.addSeparator()
        a_hide = m.addAction("✕ Hide companion")
        act = m.exec(pos)
        if act == a_voice:
            self.voice_toggled.emit(not voice_on)
        elif act == a_restore:
            self.restore_requested.emit()
        elif act == a_hide:
            self.hide_requested.emit()

    # ── rendering ──────────────────────────────────────────────────────────
    def _tick(self):
        if self._core is None:
            return
        try:
            self._core.set_state(str(self._state_provider() or "IDLE"))
            self._core.step(0.05, float(self._amp_provider() or 0.0))
        except Exception:
            pass
        self.update()

    def paintEvent(self, e):
        if self._core is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        try:
            theme = _NT.get_theme(self._theme_provider()) if _NT else {}
        except Exception:
            theme = {}
        cx, cy = self.width() / 2.0, self.height() / 2.0
        self._core.paint(p, cx, cy, min(cx, cy) * 0.78, theme)
        # Approval badge: amber dot with count when approvals are waiting.
        try:
            n = int(self._pending_provider() or 0)
        except Exception:
            n = 0
        if n > 0:
            from PyQt6.QtGui import QColor, QBrush, QFont
            from PyQt6.QtCore import Qt
            bx, by, br = self.width() - 18, 18, 11
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(theme.get("amber", "#F2B84B"))))
            p.drawEllipse(QPointF(bx, by), br, br)
            p.setPen(QColor("#080D14"))
            p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            p.drawText(QRectF(bx - br, by - br, br * 2, br * 2),
                       Qt.AlignmentFlag.AlignCenter, str(min(n, 99)))
        p.end()

    def pending_count(self) -> int:
        """Approvals currently waiting (0 when the provider fails)."""
        try:
            return max(0, int(self._pending_provider() or 0))
        except Exception:
            return 0

    def set_size(self, px: int) -> None:
        px = max(72, min(240, int(px)))
        self.resize(px, px)
        try:
            from memory import config_manager as cm
            cm.save_companion_size(px)
        except Exception:
            pass

    def set_opacity_level(self, op: float) -> None:
        op = max(0.3, min(1.0, float(op)))
        self.setWindowOpacity(op)
        try:
            from memory import config_manager as cm
            cm.save_companion_opacity(op)
        except Exception:
            pass
