"""Tests for the Personal Companion memory upgrades (provenance, dedup,
search, edit, categories)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import memory.memory_manager as mm


class MemoryUpgradeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.p = Path(self.tmp) / "long_term.json"
        self.patcher = mock.patch.object(mm, "MEMORY_PATH", self.p)
        self.patcher.start()
        # Keep BASE_DIR-dependent helpers from touching the real tree.
        self.patcher2 = mock.patch.object(mm, "BASE_DIR", Path(self.tmp))
        self.patcher2.start()

    def tearDown(self):
        self.patcher.stop()
        self.patcher2.stop()

    def test_remember_explicit_provenance(self):
        r = mm.remember_explicit("pet", "My dog is called Rex", "notes",
                                 origin="user said so")
        self.assertIn("Remembered", r)
        mem = mm.load_memory()
        e = mem["notes"]["pet"]
        self.assertEqual(e["source"], "user_explicit")
        self.assertEqual(e["origin"], "user said so")
        self.assertIn("created", e)

    def test_secret_refused(self):
        r = mm.remember_explicit("api", "sk-or-v1-abcdefghijklmnopqrstuv", "notes")
        self.assertIn("Not stored", r)
        r = mm.remember_explicit("gh_token", "my github token is abc", "notes")
        self.assertIn("Not stored", r)

    def test_duplicate_detected(self):
        mm.remember_explicit("pet1", "My dog is called Rex", "notes")
        r = mm.remember_explicit("pet2", "My dog is named Rex", "notes")
        self.assertIn("Already remembered", r)
        # Only one entry stored.
        self.assertNotIn("pet2", mm.load_memory()["notes"])

    def test_provenance_preserved_on_update(self):
        mm.remember_explicit("pet", "My dog is called Rex", "notes")
        mm.update_memory({"notes": {"pet": {"value": "My dog is called Rex!"}}})
        e = mm.load_memory()["notes"]["pet"]
        self.assertEqual(e["source"], "user_explicit")

    def test_edit_entry(self):
        mm.remember_explicit("pet", "My dog is called Rex", "notes")
        r = mm.edit_entry("pet", "My dog is called Max", "notes")
        self.assertIn("Updated", r)
        e = mm.load_memory()["notes"]["pet"]
        self.assertEqual(e["value"], "My dog is called Max")
        self.assertIn("corrected", e.get("origin", ""))
        self.assertEqual(mm.edit_entry("nope", "x", "notes")[:9], "Not found")

    def test_search_entries(self):
        mm.remember_explicit("pet", "My dog is called Rex", "notes")
        mm.remember_explicit("food", "I love biryani", "preferences")
        rows = mm.search_entries("dog")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["key"], "pet")
        rows = mm.search_entries("love", category="preferences")
        self.assertEqual(len(rows), 1)
        rows = mm.search_entries("dog", category="preferences")
        self.assertEqual(len(rows), 0)

    def test_entries_by_category(self):
        mm.remember_explicit("a", "one", "notes")
        mm.remember_explicit("b", "two", "projects")
        grouped = mm.entries_by_category()
        self.assertIn("notes", grouped)
        self.assertIn("projects", grouped)
        self.assertEqual(grouped["notes"][0]["source"], "user_explicit")

    def test_delete_category(self):
        mm.remember_explicit("a", "one", "notes")
        mm.remember_explicit("b", "two", "notes")
        n = mm.delete_category("notes")
        self.assertEqual(n, 2)
        self.assertEqual(mm.load_memory()["notes"], {})

    def test_legacy_entries_get_provenance(self):
        # Simulate a pre-upgrade entry with no provenance.
        mem = mm.load_memory()
        mem["notes"]["old"] = {"value": "ancient", "updated": "2024-01-01"}
        mm.save_memory(mem)
        rows = mm.search_entries("ancient")
        self.assertEqual(rows[0]["source"], "legacy")

    def test_change_history(self):
        mm.remember_explicit("a", "one", "notes")
        hist = mm.memory_change_history(limit=5)
        self.assertTrue(any(r["key"] == "a" for r in hist))


if __name__ == "__main__":
    unittest.main()
