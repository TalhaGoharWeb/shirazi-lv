"""Tests for core/onboarding.py."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import onboarding as ob
from core import profile as prof


class OnboardingTest(unittest.TestCase):
    def test_no_question_3(self):
        ids = [s["id"] for s in ob.build_steps()]
        # Q3 (assistant name) removed per user directive.
        self.assertNotIn("assistant_name", ids)
        self.assertNotIn("assistant_name_choice", ids)

    def test_step_order(self):
        ids = [s["id"] for s in ob.build_steps()]
        self.assertEqual(ids[0], "welcome")
        self.assertLess(ids.index("actual_name"), ids.index("preferred_name"))
        self.assertLess(ids.index("preferred_name"), ids.index("conversation_language"))
        self.assertEqual(ids[-1], "summary")

    def test_language_branch_hidden_by_default(self):
        ids = [s["id"] for s in ob.visible_steps({})]
        self.assertNotIn("written_language", ids)

    def test_language_branch_shown_when_separate(self):
        ids = [s["id"] for s in ob.visible_steps({"language_scope": "separate"})]
        self.assertIn("written_language", ids)
        self.assertIn("spoken_language", ids)
        self.assertIn("interface_language", ids)

    def test_language_scope_same_copies(self):
        p = prof.default_profile()
        p["conversation_language"] = "urdu"
        u = ob.apply_answer("language_scope", "same", p)
        self.assertEqual(u["written_language"], "urdu")
        self.assertEqual(u["spoken_language"], "urdu")
        self.assertEqual(u["interface_language"], "urdu")

    def test_text_answer(self):
        u = ob.apply_answer("actual_name", "  Muhammad Talha  ", {})
        self.assertEqual(u["actual_name"], "Muhammad Talha")

    def test_text_skipped(self):
        u = ob.apply_answer("actual_name", "", {})
        self.assertEqual(u["actual_name"], "")

    def test_invalid_choice_rejected(self):
        u = ob.apply_answer("conversation_language", "klingon", {})
        self.assertEqual(u, {})

    def test_multichoice_filters_invalid(self):
        u = ob.apply_answer("communication_style",
                            ["friendly", "bogus", "technical"], {})
        self.assertEqual(u["communication_style"], ["friendly", "technical"])

    def test_slider_clamped(self):
        u = ob.apply_answer("speech_rate", 9.0, {})
        self.assertEqual(u["speech_rate"], 2.0)

    def test_toggles_update_prefs(self):
        p = prof.default_profile()
        u = ob.apply_answer("memory_categories",
                            {"projects": False, "bogus": True}, p)
        self.assertFalse(u["memory_preferences"]["projects"])
        self.assertTrue(u["memory_preferences"]["personal_preferences"])
        self.assertNotIn("bogus", u["memory_preferences"])

    def test_rules_include_security_boundaries(self):
        u = ob.apply_answer("rules", {"preset": [ob.RULE_PRESETS[0]],
                                      "custom": "Always greet me warmly."}, {})
        self.assertIn(ob.RULE_PRESETS[0], u["persistent_instructions"])
        self.assertIn("Always greet me warmly.", u["persistent_instructions"])
        self.assertTrue(any("delete files" in b for b in u["user_defined_boundaries"]))

    def test_unknown_step_no_crash(self):
        self.assertEqual(ob.apply_answer("nope", "x", {}), {})

    def test_progress(self):
        self.assertEqual(ob.progress(0, 10), (1, 10))
        self.assertEqual(ob.progress(9, 10), (10, 10))


if __name__ == "__main__":
    unittest.main()
