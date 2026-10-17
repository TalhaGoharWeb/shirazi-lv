"""Phase 3.3 regression tests: permission center (grant list/revoke)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.omnicontrol import db, policy


@pytest.fixture(autouse=True)
def _clean():
    conn = db.connect()
    conn.execute("DELETE FROM grants")
    conn.commit()
    yield
    conn.execute("DELETE FROM grants")
    conn.commit()


def _add_grant(tool="desktop", ops="execute", persistent=True):
    conn = db.connect()
    cur = conn.execute(
        "INSERT INTO grants(principal, resource_kind, resource, ops,"
        " created_at, persistent, created_by)"
        " VALUES ('user','tool',?,?,?,1,'dashboard')",
        (tool, ops, db.now()))
    conn.commit()
    return cur.lastrowid


class TestGrantList:
    def test_lists_active_grants(self):
        gid = _add_grant()
        grants = policy.list_grants()
        assert any(g["id"] == gid for g in grants)

    def test_empty_when_none(self):
        assert policy.list_grants() == []


class TestGrantRevoke:
    def test_revoke_marks_revoked(self):
        gid = _add_grant()
        assert policy.revoke_grant(gid) is True
        assert policy.list_grants() == []  # no longer active
        # still in DB as revoked
        conn = db.connect()
        row = conn.execute("SELECT revoked FROM grants WHERE id=?",
                           (gid,)).fetchone()
        assert row["revoked"] == 1

    def test_revoke_nonexistent_is_false(self):
        assert policy.revoke_grant(999999) is False

    def test_revoke_twice_is_false(self):
        gid = _add_grant()
        assert policy.revoke_grant(gid) is True
        assert policy.revoke_grant(gid) is False

    def test_revoked_grant_no_longer_authorizes(self):
        from core.omnicontrol import gateway
        gid = _add_grant(tool="slowtool")
        gateway._handlers.clear()
        policy.TOOL_RISK.clear()
        try:
            gateway.register_tool("slowtool", lambda r, o, p: "x",
                                  risk=policy.LOW)
            # live grant exists -> authorized
            d = gateway.authorize("slowtool", "slowtool", "execute")
            assert d.allowed
            # revoke -> denied
            policy.revoke_grant(gid)
            d2 = gateway.authorize("slowtool", "slowtool", "execute")
            assert not d2.allowed
        finally:
            gateway._handlers.clear()
            policy.TOOL_RISK.clear()
