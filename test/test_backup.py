"""Tests for core/backup.py — versioned backups, integrity, safe restore."""
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import core.backup as bk
import core.profile as prof
import memory.memory_manager as mm


class BackupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = Path(self.tmp) / "home"
        self.home.mkdir()
        # The real _data_dir() mkdirs; the mock must too or writes fail.
        (self.home / ".shirazi").mkdir(parents=True, exist_ok=True)
        self.p1 = mock.patch.object(bk, "_data_dir", return_value=self.home / ".shirazi")
        self.p2 = mock.patch.object(prof, "_data_dir", return_value=self.home / ".shirazi")
        self.p3 = mock.patch.object(mm, "BASE_DIR", Path(self.tmp))
        self.p4 = mock.patch.object(mm, "MEMORY_PATH", Path(self.tmp) / "lt.json")
        self.p1.start(); self.p2.start(); self.p3.start(); self.p4.start()
        prof.set_field("preferred_name", "Talha")
        mm.remember_explicit("pet", "Rex", "notes")

    def tearDown(self):
        self.p1.stop(); self.p2.stop(); self.p3.stop(); self.p4.stop()

    def _make(self, kind="full"):
        dest = Path(self.tmp) / "backups"
        return bk.create_backup(kind=kind, dest_dir=dest)

    def test_full_backup_round_trip(self):
        r = self._make("full")
        self.assertTrue(r["ok"], r["error"])
        self.assertTrue(Path(r["path"]).exists())
        m = r["manifest"]
        self.assertEqual(m["backup_schema_version"], 1)
        self.assertEqual(m["kind"], "full")
        self.assertIn("profile.json", m["files"])
        # No secrets anywhere in the archive.
        with zipfile.ZipFile(r["path"]) as zf:
            names = zf.namelist()
            self.assertNotIn("api_keys.json", names)
            blob = "\n".join(zf.read(n).decode("utf-8", "ignore") for n in names)
            self.assertNotIn("api_keys", blob.replace("api_keys.json", ""))

    def test_profile_only(self):
        r = self._make("profile")
        self.assertTrue(r["ok"])
        with zipfile.ZipFile(r["path"]) as zf:
            self.assertEqual(set(zf.namelist()),
                             {"profile.json", "manifest.json"})

    def test_memory_only(self):
        r = self._make("memory")
        self.assertTrue(r["ok"])
        self.assertEqual(r["manifest"]["kind"], "memory")

    def test_verify_detects_tampering(self):
        r = self._make("full")
        # Tamper: rewrite profile.json inside the zip.
        p = Path(r["path"])
        with zipfile.ZipFile(p, "a") as zf:
            zf.writestr("profile.json", '{"tampered": true}')
        problems = bk.verify_backup(p)
        self.assertTrue(any("hash mismatch" in x for x in problems),
                        problems)

    def test_malicious_archive_rejected(self):
        dest = Path(self.tmp) / "evil"
        dest.mkdir()
        evil = dest / "evil.zip"
        with zipfile.ZipFile(evil, "w") as zf:
            zf.writestr("../../evil.txt", "x")
            zf.writestr("manifest.json", json.dumps({
                "backup_schema_version": 1, "files": {}}))
        problems = bk.verify_backup(evil)
        self.assertTrue(problems)
        r = bk.restore_backup(evil, mode="merge")
        self.assertFalse(r["ok"])

    def test_executable_rejected(self):
        dest = Path(self.tmp) / "evil2"
        dest.mkdir()
        evil = dest / "evil2.zip"
        with zipfile.ZipFile(evil, "w") as zf:
            zf.writestr("run.exe", "MZ")
            zf.writestr("manifest.json", json.dumps({
                "backup_schema_version": 1, "files": {"run.exe": "abc"}}))
        problems = bk.verify_backup(evil)
        self.assertTrue(any("executable" in x for x in problems), problems)

    def test_restore_merge(self):
        r = self._make("full")
        # Wipe current profile + memory, then merge-restore.
        prof.delete_profile()
        mm.delete_category("notes")
        rr = bk.restore_backup(r["path"], mode="merge")
        self.assertTrue(rr["ok"], rr["error"])
        self.assertEqual(prof.get_field("preferred_name"), "Talha")
        mem = mm.load_memory()
        self.assertIn("pet", mem["notes"])

    def test_restore_replace_needs_confirmation(self):
        r = self._make("full")
        rr = bk.restore_backup(r["path"], mode="replace",
                               confirm_replace=False)
        self.assertFalse(rr["ok"])
        self.assertIn("confirmation", rr["error"])

    def test_restore_replace_takes_safety_backup(self):
        r = self._make("full")
        rr = bk.restore_backup(r["path"], mode="replace",
                               confirm_replace=True)
        self.assertTrue(rr["ok"], rr["error"])
        self.assertIsNotNone(rr["safety_backup"])
        self.assertTrue(Path(rr["safety_backup"]).exists())

    def test_inspect_does_not_modify(self):
        r = self._make("full")
        before = prof.get_field("preferred_name")
        info = bk.inspect_backup(r["path"])
        self.assertTrue(info["ok"])
        self.assertEqual(prof.get_field("preferred_name"), before)
        self.assertEqual(info["manifest"]["kind"], "full")

    def test_list_and_prune(self):
        for _ in range(3):
            self._make("profile")
        dest = Path(self.tmp) / "backups"
        items = bk.list_backups(dest)
        self.assertEqual(len(items), 3)
        pr = bk.prune_backups(keep=2, dest_dir=dest)
        self.assertEqual(pr["deleted"], 1)
        # Never prune the only valid backup.
        pr = bk.prune_backups(keep=0, dest_dir=dest)
        self.assertEqual(pr["deleted"], 0)

    def test_no_secrets_in_profile_backup(self):
        # Even if junk got into the profile, backups strip secret-shaped keys.
        d = prof.load_profile()
        d["my_api_key"] = "sk-123"
        prof.save_profile(d)
        r = self._make("profile")
        with zipfile.ZipFile(r["path"]) as zf:
            profdata = json.loads(zf.read("profile.json"))
        self.assertNotIn("my_api_key", profdata)


if __name__ == "__main__":
    unittest.main()
