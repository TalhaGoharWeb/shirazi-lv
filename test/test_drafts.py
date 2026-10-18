"""Phase 3.6 regression tests: draft-first workflows."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import drafts


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("SHIRAZI_DATA_DIR", str(tmp_path))
    yield


class TestDraftLifecycle:
    def test_create_and_get(self):
        d = drafts.create("note", "T", "hello")
        assert d["status"] == "draft"
        assert d["id"].startswith("draft-")
        g = drafts.get(d["id"])
        assert g["content"] == "hello"

    def test_list_drafts(self):
        drafts.create("note", "A", "1")
        drafts.create("note", "B", "2")
        ds = drafts.list_drafts()
        assert len(ds) == 2
        assert ds[0]["title"] == "B"  # newest first

    def test_approve(self):
        d = drafts.create("note", "T", "x")
        assert drafts.set_status(d["id"], "approved") is True
        assert drafts.get(d["id"])["status"] == "approved"

    def test_discard(self):
        d = drafts.create("note", "T", "x")
        assert drafts.discard(d["id"]) is True
        assert drafts.get(d["id"])["status"] == "discarded"

    def test_invalid_status_rejected(self):
        d = drafts.create("note", "T", "x")
        assert drafts.set_status(d["id"], "bogus") is False

    def test_get_missing_is_none(self):
        assert drafts.get("draft-nonexistent") is None

    def test_path_traversal_safe(self):
        # Malicious ID must not escape the drafts dir.
        d = drafts.get("../../../etc/passwd")
        assert d is None


class TestDraftPlugin:
    def test_plugin_create(self):
        import plugins.shirazi_draft as p
        out = p.run({"action": "create", "kind": "note",
                     "title": "T", "content": "hello world"})
        assert "Draft tayyar hai" in out
        assert "kuch bheja" in out  # draft-first promise

    def test_plugin_empty_content(self):
        import plugins.shirazi_draft as p
        out = p.run({"action": "create", "content": ""})
        assert "khaali" in out

    def test_plugin_never_raises(self):
        import plugins.shirazi_draft as p
        assert isinstance(p.run(None), str)
