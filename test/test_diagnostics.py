"""Phase 3.7 regression tests: diagnostics center."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import diagnostics as dg


class TestDiagnostics:
    def test_provider_status_shape(self):
        ps = dg.provider_status()
        assert {p["provider"] for p in ps} == {"gemini", "groq", "openrouter"}
        for p in ps:
            assert isinstance(p["configured"], bool)
            # Never leak full keys
            assert len(p["key_hint"]) <= 8

    def test_model_ids(self):
        m = dg.model_ids()
        assert "live_voice" in m and "text_ladder" in m

    def test_audio_never_raises(self):
        a = dg.audio_devices()
        assert "available" in a

    def test_system_summary(self):
        s = dg.system_summary()
        assert s["os"] and s["python"]

    def test_full_report(self):
        r = dg.full_report()
        assert set(r) == {"providers", "models", "audio", "system"}
