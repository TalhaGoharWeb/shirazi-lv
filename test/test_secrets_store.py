"""
Secret store tests — Stage F.

  1. set/get/delete round-trip (never logs values — verified by inspection).
  2. list_secret_names never returns values.
  3. Invalid inputs rejected without raising.
  4. Migration: legacy file -> OS store, verified, then renamed (not deleted).
  5. needs_migration detection.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


# Isolate secrets: in-memory backend so tests never touch the
# real OS store or disk.
try:
    from core import secrets_store as _ss
    _ss.use_memory_backend()
except Exception:
    pass


class SecretsStore(unittest.TestCase):
    def test_roundtrip(self):
        from core import secrets_store as ss
        self.assertTrue(ss.set_secret("ut_key", "ut-value-123"))
        self.assertEqual(ss.get_secret("ut_key"), "ut-value-123")
        self.assertTrue(ss.delete_secret("ut_key"))
        self.assertIsNone(ss.get_secret("ut_key"))

    def test_list_names_only(self):
        from core import secrets_store as ss
        ss.set_secret("gemini_api_key", "AIza" + "x" * 35)
        try:
            names = ss.list_secret_names()
            self.assertIn("gemini_api_key", names)
            for n in names:
                self.assertNotIn("AIza", n, "values must never leak via listing")
        finally:
            ss.delete_secret("gemini_api_key")

    def test_invalid_inputs(self):
        from core import secrets_store as ss
        self.assertIsNone(ss.get_secret(""))
        self.assertIsNone(ss.get_secret(None))
        self.assertFalse(ss.set_secret("", "x"))
        self.assertFalse(ss.set_secret("k", ""))


class Migration(unittest.TestCase):
    def test_migrate_and_rename(self):
        from core import secrets_store as ss
        with tempfile.TemporaryDirectory() as tmp:
            legacy = Path(tmp) / "api_keys.json"
            legacy.write_text(json.dumps({
                "gemini_api_key": "AIza" + "y" * 35,
                "groq_api_key": "gsk_" + "z" * 24,
            }))
            with mock.patch.object(ss, "legacy_path", return_value=legacy):
                # Ensure clean slate in the backend.
                ss.delete_secret("gemini_api_key")
                ss.delete_secret("groq_api_key")
                result = ss.migrate_from_legacy()
                self.assertEqual(set(result["migrated"]),
                                 {"gemini_api_key", "groq_api_key"})
                self.assertEqual(result["failed"], [])
                self.assertIsNotNone(result["backup"])
                # Values verify in the OS store.
                self.assertEqual(ss.get_secret("gemini_api_key"),
                                 "AIza" + "y" * 35)
                # Legacy file renamed, NOT deleted.
                self.assertFalse(legacy.exists())
                self.assertTrue(Path(result["backup"]).exists())
                ss.delete_secret("gemini_api_key")
                ss.delete_secret("groq_api_key")

    def test_needs_migration(self):
        from core import secrets_store as ss
        with tempfile.TemporaryDirectory() as tmp:
            legacy = Path(tmp) / "api_keys.json"
            legacy.write_text(json.dumps({"gemini_api_key": "AIza" + "q" * 35}))
            with mock.patch.object(ss, "legacy_path", return_value=legacy):
                ss.delete_secret("gemini_api_key")
                self.assertTrue(ss.needs_migration())
                ss.set_secret("gemini_api_key", "AIza" + "q" * 35)
                self.assertFalse(ss.needs_migration())
                ss.delete_secret("gemini_api_key")


if __name__ == "__main__":
    unittest.main()
