"""Tests for core/health.py."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import core.health as hl


class HealthTest(unittest.TestCase):
    def test_all_checks_return_shape(self):
        for fn in hl.CHECKS:
            try:
                r = fn()
            except Exception as e:
                self.fail(f"{fn.__name__} raised: {e}")
            for k in ("name", "status", "detail", "fatal"):
                self.assertIn(k, r, fn.__name__)
            self.assertIn(r["status"], ("ok", "warn", "fail"), fn.__name__)

    def test_run_health_checks_shape(self):
        res = hl.run_health_checks()
        self.assertIn("checks", res)
        self.assertIn("fatal", res)
        self.assertIn("summary", res)
        self.assertEqual(len(res["checks"]), len(hl.CHECKS))

    def test_report_text(self):
        text = hl.health_report_text()
        self.assertIn("Health:", text)
        self.assertIn("config", text)

    def test_lockfile_cycle(self):
        with mock.patch.object(hl, "_data_dir",
                               return_value=Path(tempfile.mkdtemp())):
            hl.mark_running()
            self.assertFalse(hl.was_clean_shutdown())
            hl.mark_clean_shutdown()
            self.assertTrue(hl.was_clean_shutdown())

    def test_incomplete_tasks_empty(self):
        with mock.patch.object(hl, "_data_dir",
                               return_value=Path(tempfile.mkdtemp())):
            self.assertEqual(hl.check_incomplete_tasks(), [])

    def test_incomplete_tasks_found(self):
        tmp = Path(tempfile.mkdtemp())
        d = tmp / "plugins_data"
        d.mkdir()
        (d / "shirazi_task_checkpoint.json").write_text(json.dumps({
            "tasks": [
                {"id": "t1", "title": "Write report", "state": "in_progress"},
                {"id": "t2", "title": "Done thing", "state": "done"},
                {"id": "t3", "title": "Old thing", "state": "cancelled"},
            ]
        }))
        with mock.patch.object(hl, "_data_dir", return_value=tmp):
            tasks = hl.check_incomplete_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["id"], "t1")


if __name__ == "__main__":
    unittest.main()
