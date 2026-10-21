"""Tests for plugins/shirazi_my_settings.py."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import core.profile as prof
from plugins.shirazi_my_settings import run


class MySettingsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        (Path(self.tmp) / ".shirazi").mkdir(parents=True, exist_ok=True)
        self.p = mock.patch.object(prof, "_data_dir",
                                   return_value=Path(self.tmp) / ".shirazi")
        self.p.start()

    def tearDown(self):
        self.p.stop()

    def test_no_profile_yet(self):
        out = run({}, None, None)
        self.assertIn("hasn't finished onboarding", out)

    def test_returns_settings(self):
        prof.update_profile({
            "preferred_name": "Talha",
            "conversation_language": "urdu",
            "communication_style": ["friendly", "technical"],
            "response_length_preference": "short",
            "persistent_instructions": ["Always be concise."],
            "onboarding_completed": True,
        })
        out = run({}, None, None)
        self.assertIn("Talha", out)
        self.assertIn("Urdu", out)
        self.assertIn("technical", out)
        self.assertIn("Always be concise.", out)

    def test_actual_name_never_leaked(self):
        prof.update_profile({
            "actual_name": "Muhammad Talha Gohar",
            "preferred_name": "Talha",
            "onboarding_completed": True,
        })
        out = run({}, None, None)
        self.assertNotIn("Muhammad Talha Gohar", out)
        self.assertIn("Talha", out)


if __name__ == "__main__":
    unittest.main()
