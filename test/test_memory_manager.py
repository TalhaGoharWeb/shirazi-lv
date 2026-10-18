"""Phase 3.5 regression tests: memory manager (episodic stats/clear)."""
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memory import shirazi_backend as eb


class TestEpisodicStats:
    def test_unavailable_when_no_store(self):
        with mock.patch.object(eb, "get_store", return_value=None):
            assert eb.episodic_stats() == {"available": False}

    def test_never_raises(self):
        with mock.patch.object(eb, "get_store",
                               side_effect=RuntimeError("boom")):
            assert eb.episodic_stats() == {"available": False}


class TestClearEpisodic:
    def test_unavailable_when_no_store(self):
        with mock.patch.object(eb, "get_store", return_value=None):
            assert eb.clear_episodic() is False

    def test_never_raises(self):
        with mock.patch.object(eb, "get_store",
                               side_effect=RuntimeError("boom")):
            assert eb.clear_episodic() is False

    def test_clears_tables(self, tmp_path):
        import sqlite3
        dbf = tmp_path / "memory.db"
        conn = sqlite3.connect(str(dbf))
        conn.execute("CREATE TABLE turns (id INTEGER PRIMARY KEY, x TEXT)")
        conn.execute("INSERT INTO turns (x) VALUES ('a')")
        conn.commit()
        conn.close()
        fake_store = mock.Mock()
        with mock.patch.object(eb, "get_store", return_value=fake_store), \
             mock.patch.object(eb, "_data_dir", return_value=tmp_path):
            assert eb.clear_episodic() is True
        conn = sqlite3.connect(str(dbf))
        n = conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
        conn.close()
        assert n == 0
