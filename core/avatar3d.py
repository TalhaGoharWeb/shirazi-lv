"""
3D avatar — Iron Man Mark III helmet rendered in a QWebEngineView.

Loads the user's Iron Man Mark III helmet GLB into a local Three.js scene and
drives it from the same assistant state every other visual mode uses.

The helmet is a STATIC model (no rig, no animations) — motion comes from
amp-driven sway/nod and emissive eye-glow pulsing, all following the REAL
audio amplitude. Rim light shifts hue by state (amber = approval, red =
error, emerald = thinking, cyan = otherwise).

Files are loaded over plain file:// with LocalContentCanAccessFileUrls enabled.
"""
from __future__ import annotations

from pathlib import Path

_QW = None
_QW_IMPORT_ERROR = ""
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView as _QW
except Exception as e:
    _QW_IMPORT_ERROR = f"{type(e).__name__}: {e}"

_HERE = Path(__file__).resolve().parent
_HTML = _HERE.parent / "ui" / "avatar3d.html"
_MODEL = _HERE.parent / "assets" / "avatar" / "ironman.glb"


def availability_reason() -> str:
    """Human-readable reason 3D is on/off — shown in the HUD tooltip/log."""
    if _QW is None:
        return ("PyQt6-WebEngine is not installed "
                f"({_QW_IMPORT_ERROR or 'import failed'}). "
                "Run: pip install PyQt6-WebEngine")
    if not _HTML.is_file():
        return f"avatar page missing: {_HTML}"
    if not _MODEL.is_file():
        return f"robot model missing: {_MODEL}"
    return "ready"


def is_3d_available() -> bool:
    """True only when WebEngine exists AND the model file ships."""
    return availability_reason() == "ready"




class Avatar3D:
    """Thin wrapper: owns the QWebEngineView, exposes set_state/set_amp."""

    def __init__(self, parent=None, log=None):
        self._view = None
        self._state = "IDLE"
        self._amp = 0.0
        self._log = log  # callable(str) or None
        self._ready = False
        self._tried_file_fallback = False
        if _QW is None:
            self._say(f"[3D] unavailable: {availability_reason()}")
            return
        try:
            from PyQt6.QtCore import QUrl, Qt
            from PyQt6.QtGui import QColor
            from PyQt6.QtWebEngineCore import QWebEngineSettings
            v = _QW(parent)
            v.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            # The page has its OWN default background (white) — without this
            # the white page background paints over the transparent canvas.
            v.page().setBackgroundColor(QColor(0, 0, 0, 0))
            st = v.page().settings()
            st.setAttribute(
                QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
            st.setAttribute(
                QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            # Forward JS console -> Python log so failures are never silent.
            def _console(level, msg, line, src):
                self._say(f"[3D][js] {src}:{line}: {msg}")
            try:
                v.page().javaScriptConsoleMessage = _console
            except Exception:
                pass
            # Plain file:// with LocalContentCanAccessFileUrls — the page, ES
            # modules and the GLB all resolve via relative URLs.
            url = QUrl.fromLocalFile(str(_HTML))

            def _loaded(ok: bool):
                self._say(f"[3D] page loaded: {ok}")
                if ok:
                    v.page().runJavaScript(
                        "({api: typeof window.shiraziAvatar, "
                        "err: window.__avatar_error || null})",
                        lambda r: self._say(f"[3D] js state: {r}"))
                    # Deep diagnostics: what actually rendered inside the page.
                    # Delayed slightly so the async GLB fetch has time to finish.
                    def _diag_later():
                        try:
                            v.page().runJavaScript(
                                "window.shiraziAvatar ? window.shiraziAvatar.diag() : 'no-api'",
                                lambda r: self._say(f"[3D] diag: {r}"))
                        except Exception as e:
                            self._say(f"[3D] diag failed: {e}")
                    try:
                        from PyQt6.QtCore import QTimer
                        QTimer.singleShot(4000, _diag_later)
                    except Exception:
                        _diag_later()
            v.loadFinished.connect(_loaded)
            v.load(url)
            v.setStyleSheet("background: transparent;")
            self._view = v
            self._say(f"[3D] initialised ({availability_reason()})")
        except Exception as e:
            self._say(f"[3D] init failed: {type(e).__name__}: {e}")
            self._view = None

    def _say(self, msg: str) -> None:
        try:
            if self._log is not None:
                self._log(msg)
            else:
                print(msg, flush=True)
        except Exception:
            pass

    @property
    def widget(self):
        return self._view

    @property
    def ready(self) -> bool:
        return self._ready

    def available(self) -> bool:
        return self._view is not None

    def _js(self, expr: str) -> None:
        try:
            if self._view is not None:
                self._view.page().runJavaScript(expr)
        except Exception:
            pass

    def set_state(self, state: str) -> None:
        self._state = (state or "IDLE").upper()
        self._js(f"window.shiraziAvatar && window.shiraziAvatar.setState({self._state!r})")

    def set_amp(self, amp: float) -> None:
        try:
            self._amp = max(0.0, min(1.0, float(amp)))
        except Exception:
            self._amp = 0.0
        self._js(f"window.shiraziAvatar && window.shiraziAvatar.setAmp({self._amp})")

    def hide(self) -> None:
        try:
            if self._view is not None:
                self._view.hide()
        except Exception:
            pass

    def show(self) -> None:
        try:
            if self._view is not None:
                self._view.show()
        except Exception:
            pass
