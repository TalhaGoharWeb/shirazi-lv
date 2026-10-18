"""
OMNICONTROL GitHub adapter — READ-ONLY in the MVP.

Per the user's scoping decision: start with read-only access to explicitly
selected repositories (beginning with the Shirazi Personal Assistant repo).
Write operations (branches, commits, pushes, PRs, settings) stay disabled
until separately authorized.

Token handling:
  * The token is read from the OS keyring or the SHIRAZI_GITHUB_TOKEN
    environment variable — NEVER from source files, prompts, or logs.
  * Without a token the tools report 'not configured' (an honest disabled
    state, not a fake integration).
  * Repository must be in the approved `repos` table with can_read=1.

Uses the public GitHub REST API via urllib (no new dependency).
"""
from __future__ import annotations

import json
import os
import urllib.request

from . import audit, db, gateway

_API = "https://api.github.com"


def _token() -> str | None:
    tok = os.environ.get("SHIRAZI_GITHUB_TOKEN")
    if tok:
        return tok
    try:
        import keyring
        return keyring.get_password("shirazi", "github_token")
    except Exception:
        return None


def _repo_allowed(full_name: str) -> bool:
    conn = db.connect()
    r = conn.execute("SELECT can_read FROM repos WHERE full_name=?",
                     (full_name,)).fetchone()
    return bool(r and r["can_read"])


def _get(path: str) -> dict | list:
    token = _token()
    if not token:
        raise RuntimeError("GitHub not configured: set SHIRAZI_GITHUB_TOKEN "
                           "or store a token in the OS keyring, then approve "
                           "repositories in the dashboard.")
    req = urllib.request.Request(
        _API + path,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "shirazi-omnicontrol"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def _guard_repo(full_name: str, tool: str) -> None:
    if not _repo_allowed(full_name):
        audit.log("github", "deny", tool=tool, resource=full_name,
                  decision="deny", reason="repository not approved")
        raise PermissionError("repository '%s' is not approved" % full_name)


def _repo_info(resource, op, params):
    _guard_repo(resource, "gh_repo_info")
    d = _get("/repos/" + resource)
    return {"name": d["full_name"], "description": d.get("description"),
            "stars": d.get("stargazers_count"), "default_branch": d.get("default_branch"),
            "updated": d.get("updated_at")}


def _list_files(resource, op, params):
    _guard_repo(resource, "gh_list_files")
    path = params.get("path", "")
    ref = params.get("ref", "")
    q = "/repos/%s/contents/%s" % (resource, path) + ("?ref=" + ref if ref else "")
    items = _get(q)
    if isinstance(items, dict):  # single file
        items = [items]
    return [{"name": i["name"], "type": i["type"], "size": i.get("size")}
            for i in items]


def _read_file(resource, op, params):
    _guard_repo(resource, "gh_read_file")
    path = params.get("path", "")
    if not path:
        raise ValueError("path is required")
    import base64
    d = _get("/repos/%s/contents/%s" % (resource, path))
    if d.get("encoding") != "base64":
        raise ValueError("not a file")
    text = base64.b64decode(d["content"]).decode("utf-8", errors="replace")
    return {"path": path, "truncated": len(text) > 200_000,
            "content": text[:200_000]}


def _list_issues(resource, op, params):
    _guard_repo(resource, "gh_list_issues")
    items = _get("/repos/%s/issues?state=open&per_page=20" % resource)
    return [{"number": i["number"], "title": i["title"],
             "labels": [l["name"] for l in i.get("labels", [])]} for i in items]


def _list_prs(resource, op, params):
    _guard_repo(resource, "gh_list_prs")
    items = _get("/repos/%s/pulls?state=open&per_page=20" % resource)
    return [{"number": i["number"], "title": i["title"],
             "head": i["head"]["ref"]} for i in items]


def _list_commits(resource, op, params):
    _guard_repo(resource, "gh_list_commits")
    items = _get("/repos/%s/commits?per_page=20" % resource)
    return [{"sha": i["sha"][:8], "message": i["commit"]["message"].splitlines()[0][:120],
             "author": (i["commit"]["author"] or {}).get("name")} for i in items]


def register() -> None:
    gateway.register_tool("gh_repo_info", _repo_info)
    gateway.register_tool("gh_list_files", _list_files)
    gateway.register_tool("gh_read_file", _read_file)
    gateway.register_tool("gh_list_issues", _list_issues)
    gateway.register_tool("gh_list_prs", _list_prs)
    gateway.register_tool("gh_list_commits", _list_commits)


def approve_repo(full_name: str, by: str = "dashboard") -> None:
    conn = db.connect()
    conn.execute(
        "INSERT INTO repos(full_name, can_read, can_write, added_at, added_by)"
        " VALUES (?,?,0,?,?) ON CONFLICT(full_name) DO UPDATE SET can_read=1",
        (full_name.strip(), db.now(), by))
    conn.commit()
    audit.log("user", "repo-approve", resource=full_name, decision="read-only",
              reason="approved via " + by)


def revoke_repo(full_name: str) -> None:
    conn = db.connect()
    conn.execute("DELETE FROM repos WHERE full_name=?", (full_name,))
    conn.execute("UPDATE grants SET revoked=1, revoked_at=? WHERE resource_kind='repo'"
                 " AND resource=? AND revoked=0", (db.now(), full_name))
    conn.commit()
    audit.log("user", "repo-revoke", resource=full_name, decision="revoked")
