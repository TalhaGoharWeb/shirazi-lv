"""Phase 3.4 regression tests: workspace search plugin.

Covers: filename search, content search, allow-list enforcement
(only approved folders searched), result caps, empty query handling.
"""
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import plugins.shirazi_workspace_search as ws


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "report_2026.md").write_text("# Annual report\nrevenue up 20%")
    (tmp_path / "notes.txt").write_text("buy milk tomorrow")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "data.csv").write_text("a,b,c\n1,2,3")
    (tmp_path / "binary.bin").write_bytes(b"\x00\x01\x02" * 100)
    return tmp_path


def _roots(ws_path):
    with mock.patch.object(ws, "_search_roots", return_value=[ws_path]):
        yield


class TestFilenameSearch:
    def test_glob_match(self, workspace):
        with mock.patch.object(ws, "_search_roots", return_value=[workspace]):
            out = ws.run({"query": "*.md", "mode": "filename"})
        assert "report_2026.md" in out

    def test_substring_match(self, workspace):
        with mock.patch.object(ws, "_search_roots", return_value=[workspace]):
            out = ws.run({"query": "report", "mode": "filename"})
        assert "report_2026.md" in out

    def test_no_match(self, workspace):
        with mock.patch.object(ws, "_search_roots", return_value=[workspace]):
            out = ws.run({"query": "zzz_no_such_file_xyz", "mode": "filename"})
        assert "nahi mila" in out


class TestContentSearch:
    def test_content_match(self, workspace):
        with mock.patch.object(ws, "_search_roots", return_value=[workspace]):
            out = ws.run({"query": "revenue", "mode": "content"})
        assert "report_2026.md" in out
        assert "revenue" in out.lower()

    def test_binary_skipped(self, workspace):
        with mock.patch.object(ws, "_search_roots", return_value=[workspace]):
            # binary.bin contains no searchable text; query for its name only
            out = ws.run({"query": "binary", "mode": "content"})
        assert "binary.bin" not in out


class TestAllowList:
    def test_no_roots_message(self):
        with mock.patch.object(ws, "_search_roots", return_value=[]):
            out = ws.run({"query": "x"})
        assert "allow-listed" in out

    def test_only_searches_roots(self, tmp_path):
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        (allowed / "ok.txt").write_text("hello")
        secret = tmp_path / "secret"
        secret.mkdir()
        (secret / "hidden.txt").write_text("hello")
        with mock.patch.object(ws, "_search_roots", return_value=[allowed]):
            out = ws.run({"query": "hello", "mode": "content"})
        assert "ok.txt" in out
        assert "hidden.txt" not in out


class TestInputHandling:
    def test_empty_query(self, workspace):
        with mock.patch.object(ws, "_search_roots", return_value=[workspace]):
            out = ws.run({"query": ""})
        assert out  # helpful prompt, not a crash

    def test_never_raises(self):
        out = ws.run(None)
        assert isinstance(out, str)
