"""
OMNICONTROL policy engine: risk tiers, grant matching, filesystem boundaries.

Risk model (user's scoping decision):
  LOW      read/search approved files, inspect structure, analyze code.
  MODERATE create/edit files, install deps, run project commands, change config.
  HIGH     delete files, privileged commands, security changes, secret
           exposure, publishing. Needs explicit confirmation.
  CRITICAL destructive system-wide ops, security bypasses, irreversible
           actions. Blocked unless a secure authorization procedure allows.

Filesystem rules:
  * Paths canonicalized with realpath (symlinks/junctions resolved).
  * Access must sit inside an allow-listed folder with the matching per-op flag.
  * Sensitive children NEVER inherit parent approval (_SENSITIVE_PATTERNS).
  * Deny-by-default: no live grant covering (resource, op) => denial.
"""
from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass
from pathlib import Path

from . import db

LOW, MODERATE, HIGH, CRITICAL = "low", "moderate", "high", "critical"

# Tool -> risk tier. Unregistered tools are treated as CRITICAL (deny).
TOOL_RISK: dict[str, str] = {
    "fs_list": LOW, "fs_read": LOW, "fs_search": LOW, "fs_stat": LOW,
    "fs_write": MODERATE, "fs_mkdir": MODERATE,
    "fs_move": HIGH, "fs_delete": HIGH,
    "gh_repo_info": LOW, "gh_list_files": LOW, "gh_read_file": LOW,
    "gh_list_issues": LOW, "gh_list_prs": LOW, "gh_list_commits": LOW,
    "perm_grant": HIGH, "perm_revoke": MODERATE, "perm_status": LOW,
    "task_start": MODERATE, "task_cancel": LOW, "task_status": LOW,
}

_SENSITIVE_PATTERNS = (
    "*/.ssh/*", "*/.gnupg/*", "*/.aws/*", "*/.azure/*",
    "*/*.pem", "*/*.key", "*/id_rsa*", "*/id_ed25519*",
    "*/*credential*", "*/*secret*", "*/*token*", "*/.env", "*/.env.*",
    "*password*", "*passwd*",
    "*/AppData/Local/Google/Chrome/*", "*/AppData/Roaming/Mozilla/*",
    "*/.config/google-chrome/*", "*/.mozilla/*",
    "*/Windows/System32/*", "*/Windows/SysWOW64/*", "*/Program Files/*",
)


def _norm(p: str) -> str:
    """Canonical absolute path: realpath + normcase (case-insensitive compare)."""
    return os.path.normcase(os.path.realpath(os.path.abspath(os.path.expanduser(p))))


def is_sensitive_path(path: str) -> bool:
    canon = _norm(path).replace(os.sep, "/")
    return any(fnmatch.fnmatch(canon, pat) for pat in _SENSITIVE_PATTERNS)


@dataclass
class FolderRule:
    path: str
    can_read: bool
    can_write: bool
    can_exec: bool
    can_delete: bool


_OP_TO_FLAG = {"read": "can_read", "write": "can_write",
               "exec": "can_exec", "delete": "can_delete"}


def folder_allows(path: str, op: str) -> FolderRule | None:
    """Return the deepest allow-listed folder containing path with op permitted."""
    canon = _norm(path)
    conn = db.connect()
    rows = conn.execute("SELECT path, can_read, can_write, can_exec, can_delete "
                        "FROM folders").fetchall()
    best = None
    for r in rows:
        fp = _norm(r["path"])
        if canon == fp or canon.startswith(fp + os.sep):
            if best is None or len(fp) > len(_norm(best["path"])):
                best = r
    if best is None:
        return None
    rule = FolderRule(best["path"], bool(best["can_read"]), bool(best["can_write"]),
                      bool(best["can_exec"]), bool(best["can_delete"]))
    flag = _OP_TO_FLAG.get(op)
    return rule if flag and getattr(rule, flag) else None


def check_path(path: str, op: str) -> tuple[bool, str]:
    """(allowed, reason) for a filesystem operation."""
    if is_sensitive_path(path):
        return False, "path is sensitive: parent folder approval does not cover it"
    rule = folder_allows(path, op)
    if rule is None:
        return False, "no allow-listed folder covers this path with '%s'" % op
    return True, "covered by allow-list %s" % rule.path


def list_grants(active_only: bool = True) -> list[dict]:
    """Phase 3.3: all grants for the Permission Center UI."""
    from . import db as _db
    conn = _db.connect()
    q = "SELECT * FROM grants"
    if active_only:
        q += " WHERE revoked=0 AND (expires_at IS NULL OR expires_at > %f)" % _db.now()
    q += " ORDER BY created_at DESC"
    return [dict(r) for r in conn.execute(q).fetchall()]


def revoke_grant(grant_id: int, by: str = "dashboard") -> bool:
    """Phase 3.3: revoke a grant. Returns True if a live grant was revoked."""
    from . import audit as _audit, db as _db
    conn = _db.connect()
    cur = conn.execute(
        "UPDATE grants SET revoked=1, revoked_at=? WHERE id=? AND revoked=0",
        (_db.now(), grant_id))
    conn.commit()
    if cur.rowcount:
        _audit.log(by, "grant-revoke", resource=str(grant_id),
                   decision="revoked", reason="permission center")
        return True
    return False


def live_grant(resource_kind: str, resource: str, op: str) -> dict | None:
    """Newest non-expired, non-revoked grant covering (kind, resource, op)."""
    conn = db.connect()
    rows = conn.execute(
        "SELECT * FROM grants WHERE resource_kind=? AND revoked=0 "
        "ORDER BY id DESC", (resource_kind,)).fetchall()
    t = db.now()
    for r in rows:
        if r["expires_at"] is not None and r["expires_at"] <= t:
            continue
        ops = [o.strip() for o in (r["ops"] or "").split(",")]
        if op not in ops and "*" not in ops:
            continue
        res = r["resource"]
        if res not in ("*", resource) and not resource.startswith(res.rstrip("*")):
            continue
        return dict(r)
    return None


def risk_of(tool: str) -> str:
    return TOOL_RISK.get(tool, CRITICAL)
