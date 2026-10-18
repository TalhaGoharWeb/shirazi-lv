"""Tests for core/profile.py — versioned user profile."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import core.profile as prof


class ProfileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.patcher = mock.patch.object(prof, "_data_dir", return_value=Path(self.tmp))
        self.patcher.start()
        # Keep legacy migration from reading the real repo config.
        self.patcher2 = mock.patch.object(prof, "_migrate_legacy", side_effect=lambda d: d)
        self.patcher2.start()

    def tearDown(self):
        self.patcher.stop()
        self.patcher2.stop()

    def test_default_profile_shape(self):
        d = prof.default_profile()
        for k in ("actual_name", "preferred_name", "preferred_form_of_address",
                  "assistant_name", "conversation_language", "written_language",
                  "spoken_language", "interface_language", "communication_style",
                  "response_length_preference", "persistent_instructions",
                  "user_defined_boundaries", "memory_preferences",
                  "onboarding_completed", "profile_schema_version"):
            self.assertIn(k, d)

    def test_round_trip(self):
        self.assertTrue(prof.set_field("preferred_name", "Talha"))
        self.assertEqual(prof.get_field("preferred_name"), "Talha")
        # Survives a fresh load.
        self.assertEqual(prof.load_profile()["preferred_name"], "Talha")

    def test_actual_name_never_used_as_address(self):
        prof.set_field("actual_name", "Muhammad Talha Gohar")
        prof.set_field("preferred_name", "Talha")
        self.assertEqual(prof.address_form(), "Talha")
        # With no preferred name, address form is empty — never actual_name.
        prof.set_field("preferred_name", "")
        prof.set_field("preferred_form_of_address", "")
        self.assertEqual(prof.address_form(), "")

    def test_form_of_address_priority(self):
        prof.set_field("preferred_name", "Talha")
        prof.set_field("preferred_form_of_address", "Brother Talha")
        self.assertEqual(prof.address_form(), "Brother Talha")

    def test_language_validation(self):
        self.assertTrue(prof.set_field("conversation_language", "urdu"))
        self.assertFalse(prof.set_field("conversation_language", "klingon"))
        self.assertEqual(prof.get_field("conversation_language"), "urdu")

    def test_style_validation(self):
        self.assertTrue(prof.set_field("communication_style", ["friendly", "technical", "bogus"]))
        self.assertEqual(prof.get_field("communication_style"), ["friendly", "technical"])

    def test_length_validation(self):
        self.assertFalse(prof.set_field("response_length_preference", "novel"))
        self.assertTrue(prof.set_field("response_length_preference", "detailed"))

    def test_speech_rate_clamped(self):
        prof.set_field("speech_rate", 5.0)
        self.assertEqual(prof.get_field("speech_rate"), 2.0)
        prof.set_field("speech_rate", 0.1)
        self.assertEqual(prof.get_field("speech_rate"), 0.5)

    def test_instructions_capped(self):
        prof.set_field("persistent_instructions", [f"rule {i}" for i in range(100)])
        self.assertEqual(len(prof.get_field("persistent_instructions")), 50)

    def test_update_profile_reports_rejected(self):
        ok, rejected = prof.update_profile({
            "preferred_name": "Talha",
            "conversation_language": "elvish",
        })
        self.assertTrue(ok)
        self.assertEqual(rejected, ["conversation_language"])
        self.assertEqual(prof.get_field("preferred_name"), "Talha")

    def test_atomic_write_no_partial(self):
        prof.set_field("preferred_name", "Talha")
        p = Path(self.tmp) / "profile.json"
        self.assertTrue(p.exists())
        self.assertFalse((Path(self.tmp) / "profile.tmp").exists())
        json.loads(p.read_text(encoding="utf-8"))  # valid JSON

    def test_delete_profile(self):
        prof.set_field("preferred_name", "Talha")
        self.assertTrue(prof.delete_profile())
        self.assertFalse((Path(self.tmp) / "profile.json").exists())
        # A fresh default is created on next load.
        self.assertEqual(prof.get_field("preferred_name"), "")


if __name__ == "__main__":
    unittest.main()
