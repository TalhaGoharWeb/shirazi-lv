"""
Bachon ki Dunya (kids plugins) acceptance tests.

  1. All three kids plugins discover + validate through the real loader.
  2. Story tool returns a complete story with sabaq, personalised by name.
  3. Every theme maps to a real story; every lesson topic renders.
  4. Quiz ask/check round-trip works with kid-friendly matching.
  5. Schemas have no empty enums (the Gemini 1007 rejection class).
"""
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent.parent  # shirazi-lv/
sys.path.insert(0, str(_HERE / "plugins"))


class Discovery(unittest.TestCase):
    def test_kids_plugins_discovered_and_valid(self):
        from core.plugin_loader import discover_plugins
        reg = discover_plugins(_HERE / "plugins", set(), logger=lambda m: None)
        for name in ("shirazi_kids_story", "shirazi_kids_lesson", "shirazi_kids_quiz"):
            self.assertIn(name, reg._plugins, f"{name} not discovered")
            rec = reg._plugins[name]
            self.assertTrue(rec.valid, f"{name} invalid: {rec.error}")

    def test_no_empty_enums(self):
        from core.plugin_loader import discover_plugins
        reg = discover_plugins(_HERE / "plugins", set(), logger=lambda m: None)
        for name in ("shirazi_kids_story", "shirazi_kids_lesson", "shirazi_kids_quiz"):
            params = reg._plugins[name].parameters
            for pname, pspec in params.get("properties", {}).items():
                for v in pspec.get("enum", []):
                    self.assertTrue(v, f"empty enum in {name}.{pname}")


class StoryTool(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import shirazi_kids_story as m
        cls.mod = m

    def test_personalised_story(self):
        out = self.mod.run({"theme": "sabr", "child_name": "Ahmed"})
        self.assertIn("Ahmed", out)
        self.assertIn("sabaq", out)
        self.assertGreater(len(out), 300)

    def test_every_theme_has_story(self):
        from _kids_content import THEMES
        for theme in THEMES:
            if theme == "koi bhi":
                continue
            out = self.mod.run({"theme": theme})
            self.assertGreater(len(out), 300, theme)

    def test_unknown_theme_falls_back(self):
        out = self.mod.run({"theme": "not-a-theme"})
        self.assertGreater(len(out), 300)

    def test_never_raises(self):
        out = self.mod.run(None)
        self.assertIsInstance(out, str)


class LessonTool(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import shirazi_kids_lesson as m
        cls.mod = m

    def test_every_topic_renders(self):
        from _kids_content import LESSON_TOPICS
        for topic in LESSON_TOPICS:
            out = self.mod.run({"topic": topic, "child_name": "Fatima"})
            self.assertIn("Fatima", out)
            self.assertGreater(len(out), 200, topic)

    def test_dua_lesson_content(self):
        out = self.mod.run({"topic": "dua"})
        self.assertIn("Bismillah", out)
        self.assertIn("Alhamdulillah", out)


class QuizTool(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import shirazi_kids_quiz as m
        cls.mod = m

    def test_ask_returns_question(self):
        out = self.mod.run({"operation": "ask"})
        self.assertIn("sawal", out)

    def test_check_right_answer_praises(self):
        out = self.mod.run({
            "operation": "check",
            "question": "Ahmed ne kya kiya?",
            "expected": "Usne pyase kutte ko paani pilaya.",
            "child_answer": "kutte ko paani pilaya",
        })
        self.assertTrue(any(w in out for w in ("Shabash", "Wah", "khoob", "MashaAllah")))

    def test_check_wrong_answer_gentle(self):
        out = self.mod.run({
            "operation": "check",
            "question": "Ahmed ne kya kiya?",
            "expected": "Usne pyase kutte ko paani pilaya.",
            "child_answer": "pata nahi kuch",
        })
        self.assertIn("Usne pyase kutte ko paani pilaya", out)  # teaches the answer


if __name__ == "__main__":
    unittest.main()
