"""Phase 3.8 regression tests: accessible interaction."""
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import accessibility as a11y


class TestTextScale:
    def test_default(self):
        with mock.patch("memory.config_manager.load_api_keys",
                         return_value={}):
            assert a11y.get_text_scale() == 1.0

    def test_clamped(self):
        with mock.patch("memory.config_manager.load_api_keys",
                         return_value={"a11y_text_scale": 5.0}):
            assert a11y.get_text_scale() == 2.0
        with mock.patch("memory.config_manager.load_api_keys",
                         return_value={"a11y_text_scale": 0.1}):
            assert a11y.get_text_scale() == 0.8

    def test_scaled_font_size(self):
        with mock.patch.object(a11y, "get_text_scale", return_value=1.5):
            assert a11y.scaled_font_size(10) == 15
        with mock.patch.object(a11y, "get_text_scale",
                               side_effect=RuntimeError):
            assert a11y.scaled_font_size(10) == 10  # never raises


class TestReducedMotion:
    def test_default_off(self):
        with mock.patch("memory.config_manager.load_api_keys",
                         return_value={}):
            assert a11y.get_reduced_motion() is False

    def test_collapses_duration(self):
        with mock.patch.object(a11y, "get_reduced_motion", return_value=True):
            assert a11y.motion_duration(450) == 0
        with mock.patch.object(a11y, "get_reduced_motion", return_value=False):
            assert a11y.motion_duration(450) == 450


class TestHighContrast:
    def test_theme_override(self):
        from core import noorcore_tokens as tok
        with mock.patch.object(a11y, "get_high_contrast", return_value=True):
            # Patch the import inside get_theme
            import core.accessibility
            with mock.patch.object(core.accessibility, "get_high_contrast",
                                   return_value=True):
                t = tok.get_theme("noorcore")
        assert t["name"] == "High Contrast"
        assert t["bg"] == "#000000"

    def test_no_override_by_default(self):
        from core import noorcore_tokens as tok
        with mock.patch("memory.config_manager.load_api_keys",
                         return_value={}):
            t = tok.get_theme("noorcore")
        assert t["name"] == "NoorCore Dark"
