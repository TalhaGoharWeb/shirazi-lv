"""
NoorCore Living Intelligence Core — the signature animated centrepiece.

Software-rendered (QPainter), like HoloAvatar: no OpenGL context, no shader
compile, no GPU driver to disagree with us. Looks the same on a gaming rig
and a 2013 laptop.

Explicit state model — every visual is driven by a REAL event, never invented:
  IDLE              slow breathing, low intensity, no fake activity
  LISTENING         audio ring follows the real mic amplitude
  THINKING          faster orbitals while a model request is in flight;
                    set_thinking_depth(1/2) for visibly deeper work
  SPEAKING          audio ring follows real TTS playback amplitude
  EXECUTING         segmented ring; real progress when measurable, honest
                    indeterminate sweep otherwise (never fabricated %)
  AWAITING_APPROVAL steady amber ring + approval card (UI layer); urgency
                    rises gently the longer the request waits (real elapsed)
  ERROR             restrained red pulse; the message lives in the UI
  OFFLINE           dim, almost still; never implies work is happening
  DEGRADED          text-only fallback (Live voice down): desaturated, slow
                    dashed ring — honest about reduced capability

Every state change fires a brief transition pulse (an expanding ring that
fades in ~0.6s) so the eye catches the change without a jarring cut.

Interface mirrors HoloAvatar for drop-in use in HudCanvas:
    core = NoorCore()
    core.set_state("LISTENING")
    core.step(dt, amp)            # amp: 0..1 smoothed audio level
    core.paint(painter, cx, cy, r, theme_dict)
"""
from __future__ import annotations

import math
import random

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen, QRadialGradient

from .noorcore_tokens import CORE_STATES, DUR_NORMAL, state_color

_TAU = math.tau


class NoorCore:
    # state -> (energy 0..1, orbital speed x, breathing on)
    _PARAMS = {
        "IDLE":              (0.15, 1.0, True),
        "LISTENING":         (0.50, 1.2, True),
        "THINKING":          (0.70, 2.6, False),
        "SPEAKING":          (0.60, 1.4, False),
        "EXECUTING":         (0.80, 2.0, False),
        "AWAITING_APPROVAL": (0.25, 0.6, True),
        "ERROR":             (0.30, 0.8, False),
        "OFFLINE":           (0.05, 0.3, False),
        "DEGRADED":          (0.20, 0.5, True),
    }

    def __init__(self, reduced_motion: bool = False, seed: int = 7):
        self.state = "IDLE"
        self._energy = 0.15
        self._tgt_energy = 0.15
        self._orb_speed = 1.0
        self._tgt_orb_speed = 1.0
        self._breathing = True
        self._t = 0.0
        self._amp = 0.0          # smoothed audio level 0..1
        self._amp_tgt = 0.0
        self._progress: float | None = None  # EXECUTING real progress
        self._pulse_t = -10.0    # transition pulse: seconds since state change
        self._approval_since: float | None = None  # AWAITING_APPROVAL start (perf_counter)
        self._think_depth = 0    # 0 normal, 1 deep, 2 very deep
        self._reduced = reduced_motion
        rng = random.Random(seed)
        # particle field: (angle, radius_frac, speed, size)
        self._particles = [
            (rng.uniform(0, _TAU), rng.uniform(0.55, 1.35),
             rng.uniform(-0.25, 0.25), rng.uniform(1.0, 2.2))
            for _ in range(0 if reduced_motion else 44)
        ]
        # orbital elements: (tilt, phase, speed, dot_count)
        self._orbits = [
            (0.12, 0.0, 0.55, 2),
            (-0.35, 2.1, 0.38, 3),
            (0.55, 4.2, 0.72, 2),
        ]

    # ── state ─────────────────────────────────────────────────────────────
    def set_state(self, state: str) -> None:
        s = str(state or "IDLE").upper()
        if s not in CORE_STATES:
            s = "IDLE"
        if s == self.state:
            return
        self.state = s
        e, o, b = self._PARAMS[s]
        self._tgt_energy, self._tgt_orb_speed, self._breathing = e, o, b
        self._pulse_t = 0.0  # transition pulse starts now
        if s == "AWAITING_APPROVAL":
            import time as _t
            self._approval_since = _t.perf_counter()
        else:
            self._approval_since = None
        if s != "EXECUTING":
            self._progress = None

    def set_progress(self, frac: float | None) -> None:
        """Real task progress 0..1, or None for honest indeterminate."""
        if frac is None:
            self._progress = None
        else:
            self._progress = max(0.0, min(1.0, float(frac)))

    def set_reduced_motion(self, on: bool) -> None:
        self._reduced = on
        if on:
            self._particles = []

    def set_thinking_depth(self, depth: int) -> None:
        """0 = normal, 1 = deep, 2 = very deep. Only affects THINKING visuals;
        the orbital speed multiplier makes multi-stage model work visible."""
        self._think_depth = max(0, min(2, int(depth)))

    def approval_wait_s(self) -> float:
        """Seconds the current approval request has been waiting (0 if none)."""
        if self._approval_since is None:
            return 0.0
        import time as _t
        return max(0.0, _t.perf_counter() - self._approval_since)

    # ── per-frame ─────────────────────────────────────────────────────────
    def step(self, dt: float, amp: float = 0.0) -> None:
        # time-constant smoothing (frame-rate independent, like the avatar)
        k = 1.0 - math.exp(-dt / 0.08)
        self._amp_tgt = max(0.0, min(1.0, amp))
        self._amp += (self._amp_tgt - self._amp) * k
        ke = 1.0 - math.exp(-dt / (DUR_NORMAL / 1000.0))
        self._energy += (self._tgt_energy - self._energy) * ke
        self._orb_speed += (self._tgt_orb_speed - self._orb_speed) * ke
        self._t += dt * (0.35 + self._energy)
        self._pulse_t += dt

    # ── paint ─────────────────────────────────────────────────────────────
    def paint(self, p: QPainter, cx: float, cy: float, r: float,
              theme: dict) -> None:
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        accent = QColor(state_color(theme, self.state))
        cyan = QColor(theme["cyan"])
        dim = QColor(theme["text_dim"])

        audio_states = self.state in ("LISTENING", "SPEAKING")
        a = self._amp if audio_states else 0.0  # never fake audio

        # 1. halo — soft atmospheric glow, breathes + reacts to real audio
        breathe = (0.5 + 0.5 * math.sin(self._t * 1.4)) if self._breathing else 0.5
        halo_r = r * (1.55 + 0.10 * breathe + 0.35 * a)
        halo = QRadialGradient(QPointF(cx, cy), halo_r)
        hc = QColor(accent)
        hc.setAlphaF(0.10 + 0.10 * self._energy + 0.15 * a)
        halo.setColorAt(0.0, hc)
        hc2 = QColor(accent)
        hc2.setAlphaF(0.0)
        halo.setColorAt(1.0, hc2)
        p.setBrush(QBrush(halo))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), halo_r, halo_r)

        # 2. particle field — slow drift, subtle swirl when thinking
        if self._particles:
            swirl = 0.6 if self.state == "THINKING" else 0.15
            p.setPen(Qt.PenStyle.NoPen)
            for ang, rf, spd, sz in self._particles:
                aa = ang + self._t * spd * (1 + swirl)
                px = cx + math.cos(aa) * r * rf
                py = cy + math.sin(aa) * r * rf * 0.9
                pc = QColor(cyan)
                pc.setAlphaF(0.10 + 0.12 * self._energy)
                p.setBrush(QBrush(pc))
                p.drawEllipse(QPointF(px, py), sz, sz)

        # 3. orbital paths — fine ellipses with moving elements
        # Thinking depth multiplies orbital speed: deeper work is visible.
        think_mult = 1.0
        if self.state == "THINKING":
            think_mult = (1.0, 1.8, 2.8)[self._think_depth]
        p.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        for tilt, phase, spd, dots in self._orbits:
            op = QPen(QColor(cyan))
            op.setWidthF(max(1.0, r * 0.004))
            opc = QColor(cyan)
            opc.setAlphaF(0.16 + 0.20 * self._energy)
            op.setColor(opc)
            p.setPen(op)
            # tilted ellipse via scaled rect
            w, h = r * 1.9, r * 1.9 * (0.55 + 0.2 * math.sin(tilt))
            p.save()
            p.translate(cx, cy)
            p.rotate(math.degrees(tilt))
            p.drawEllipse(QRectF(-w / 2, -h / 2, w, h))
            # moving elements on the path
            for d in range(dots):
                ta = (phase + self._t * spd * self._orb_speed * think_mult
                      * _TAU * 0.14 + d * _TAU / dots)
                dx, dy = math.cos(ta) * w / 2, math.sin(ta) * h / 2
                dc = QColor(accent)
                dc.setAlphaF(0.55 + 0.30 * self._energy)
                p.setBrush(QBrush(dc))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(dx, dy), r * 0.022, r * 0.022)
            p.restore()

        # 4. shell — two translucent rings
        for i, frac in enumerate((1.18, 1.02)):
            sp = QPen(QColor(cyan))
            sp.setWidthF(max(1.0, r * 0.006))
            sc = QColor(cyan)
            sc.setAlphaF(0.22 - i * 0.08 + 0.10 * a)
            sp.setColor(sc)
            p.setPen(sp)
            rr = r * frac * (1 + 0.02 * math.sin(self._t * 2 + i))
            p.drawEllipse(QPointF(cx, cy), rr, rr)

        # 5. audio ring — ONLY from real audio; flat when silent
        if audio_states:
            ar = r * (0.86 + 0.22 * a)
            ap = QPen(QColor(accent))
            ap.setWidthF(max(1.5, r * 0.012))
            ac = QColor(accent)
            ac.setAlphaF(0.25 + 0.55 * a)
            ap.setColor(ac)
            p.setPen(ap)
            p.drawEllipse(QPointF(cx, cy), ar, ar)

        # 6. nucleus — luminous centre
        nuc_r = r * (0.34 + 0.03 * breathe + 0.06 * a)
        nuc = QRadialGradient(QPointF(cx, cy), nuc_r)
        white = QColor("#ffffff")
        nuc.setColorAt(0.0, white)
        ac2 = QColor(accent)
        nuc.setColorAt(0.45, ac2)
        ac3 = QColor(accent)
        ac3.setAlphaF(0.25)
        nuc.setColorAt(1.0, ac3)
        p.setBrush(QBrush(nuc))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), nuc_r, nuc_r)

        # 6b. transition pulse — an expanding ring that fades in ~0.6s after
        # every state change, so the eye catches the transition. Skipped under
        # reduced motion.
        if not self._reduced and 0.0 <= self._pulse_t < 0.6:
            pf = self._pulse_t / 0.6  # 0 → 1
            pr = r * (1.38 + 0.55 * pf)
            pp = QPen(QColor(accent))
            pp.setWidthF(max(1.0, r * 0.010 * (1 - pf)))
            pc = QColor(accent)
            pc.setAlphaF(0.55 * (1 - pf))
            pp.setColor(pc)
            p.setPen(pp)
            p.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            p.drawEllipse(QPointF(cx, cy), pr, pr)

        # 7. state ring — outer indicator; EXECUTING shows real or honest sweep
        rp = QPen(QColor(accent))
        rp.setWidthF(max(2.0, r * 0.014))
        rc = QColor(accent)
        if self.state == "ERROR":
            rc.setAlphaF(0.55 + 0.35 * math.sin(self._t * 6))
        elif self.state == "OFFLINE":
            rc.setAlphaF(0.25)
        elif self.state == "AWAITING_APPROVAL":
            # Calm authority that quickens gently: the pulse period shrinks
            # from ~3s to ~1.2s over the first minute of waiting. Never a
            # frantic blink — the request is waiting, not the user.
            wait = self.approval_wait_s()
            urgency = min(1.0, wait / 60.0)
            period = 3.0 - 1.8 * urgency
            pulse = 0.5 + 0.5 * math.sin(self._t * _TAU / max(0.8, period))
            rc.setAlphaF(0.70 + 0.25 * pulse)
        else:
            rc.setAlphaF(0.50 + 0.25 * self._energy)
        rp.setColor(rc)
        p.setPen(rp)
        rr = r * 1.38
        if self.state == "DEGRADED":
            # Honest reduced capability: slow dashed ring, desaturated.
            # Text-only mode — the core never pretends voice is working.
            rp.setStyle(Qt.PenStyle.DashLine)
            dash_phase = (self._t * 12) % 40
            rp.setDashOffset(dash_phase)
            p.setPen(rp)
            p.drawEllipse(QPointF(cx, cy), rr, rr)
        elif self.state == "EXECUTING":
            if self._progress is None:
                # honest indeterminate: a sweeping arc, never a fake %
                start = int(math.degrees(self._t * 2.2) % 360)
                p.drawArc(QRectF(cx - rr, cy - rr, rr * 2, rr * 2),
                          start * 16, 100 * 16)
            else:
                p.drawArc(QRectF(cx - rr, cy - rr, rr * 2, rr * 2),
                          90 * 16, -int(self._progress * 360) * 16)
        else:
            p.drawEllipse(QPointF(cx, cy), rr, rr)

        p.restore()
