"""Tests for core/instructions.py."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import instructions as ins
from core import profile as prof


class InstructionsTest(unittest.TestCase):
    def test_block_contains_address_not_actual_name(self):
        d = prof.default_profile()
        d["actual_name"] = "Muhammad Talha Gohar"
        d["preferred_name"] = "Talha"
        block = ins.build_profile_block(d)
        self.assertIn("Talha", block)
        self.assertNotIn("Muhammad Talha Gohar", block)

    def test_no_name_generic_address(self):
        d = prof.default_profile()
        block = ins.build_profile_block(d)
        self.assertIn("no name", block.lower())

    def test_form_of_address_used(self):
        d = prof.default_profile()
        d["preferred_name"] = "Talha"
        d["preferred_form_of_address"] = "Brother Talha"
        block = ins.build_profile_block(d)
        self.assertIn("Brother Talha", block)

    def test_language_lines(self):
        d = prof.default_profile()
        d["conversation_language"] = "urdu"
        d["written_language"] = "urdu"
        block = ins.build_profile_block(d)
        self.assertIn("Urdu", block)
        self.assertIn("right-to-left", block)

    def test_temp_override_detected(self):
        o = ins.detect_temp_override("answer this question in English just this once")
        self.assertEqual(o.get("written_language"), "english")
        self.assertEqual(o.get("scope"), "once")

    def test_temp_override_not_triggered(self):
        self.assertEqual(ins.detect_temp_override("what is the weather"), {})
        self.assertEqual(ins.detect_temp_override(""), {})

    def test_temp_override_in_block_not_saved(self):
        d = prof.default_profile()
        d["written_language"] = "urdu"
        block = ins.build_profile_block(d, {"written_language": "english"})
        self.assertIn("English", block)
        self.assertIn("THIS response only", block)
        # Profile itself untouched.
        self.assertEqual(d["written_language"], "urdu")

    def test_style_and_length(self):
        d = prof.default_profile()
        d["communication_style"] = ["professional", "technical"]
        d["response_length_preference"] = "short"
        block = ins.build_profile_block(d)
        self.assertIn("professional and concise", block)
        self.assertIn("short and direct", block)

    def test_boundaries_marked_non_authoritative(self):
        d = prof.default_profile()
        d["user_defined_boundaries"] = ["Do not delete files without approval."]
        block = ins.build_profile_block(d)
        self.assertIn("do NOT", block)
        self.assertIn("authorization system", block)

    def test_speech_rate_line(self):
        d = prof.default_profile()
        d["speech_rate"] = 1.5
        self.assertIn("1.5x", ins.build_profile_block(d))
        d["speech_rate"] = 1.0
        self.assertNotIn("speech rate", ins.build_profile_block(d).lower().replace("preferred speech rate", ""))

    def test_profile_block_for_request(self):
        block = ins.profile_block_for_request("tell me in urdu for this answer just this once")
        self.assertIn("Urdu", block)


if __name__ == "__main__":
    unittest.main()
