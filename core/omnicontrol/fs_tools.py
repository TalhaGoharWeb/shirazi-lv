"""
OMNICONTROL filesystem tools — granular, allow-list-bound file operations.

Each tool is registered with the gateway; the gateway enforces the filesystem
boundary (policy.check_path) BEFORE the handler runs, so a handler can never
see a path outside the allow-list. Tools:

  fs_list    list directory entries            (read)
  fs_stat    file metadata                     (read)
  fs_read    read file text (size-capped)       (read)
  fs_search  search file names under a folder  (read)
  fs_write   create/overwrite file             (write)
  fs_mkdir   create directory                  (write)
  fs_move    rename/move                       (write; HIGH risk)
  fs_delete  delete file/dir                   (delete; HIGH risk)
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from . import gateway, policy

_MAX_READ = 200_000  # chars


def _list(resource, op, params):
    p = Path(resource)
    if not p.is_dir():
        raise ValueError("not a directory: %s" % resource)
    return [{"name": e.name, "is_dir": e.is_dir(),
             "size": e.stat().st_size if e.is_file() else 0}
            for e in sorted(p.iterdir(), key=lambda e: e.name)][:500]


def _stat(resource, op, params):
    p = Path(resource)
    st = p.stat()
    return {"name": p.name, "is_dir": p.is_dir(), "size": st.st_size,
            "mtime": st.st_mtime}


def _read(resource, op, params):
    p = Path(resource)
    if not p.is_file():
        raise ValueError("not a file: %s" % resource)
    if p.stat().st_size > _MAX_READ * 4:
        raise ValueError("file too large to read (%d bytes)" % p.stat().st_size)
    text = p.read_text(encoding="utf-8", errors="replace")
    return {"path": resource, "truncated": len(text) > _MAX_READ,
            "content": text[:_MAX_READ]}


def _search(resource, op, params):
    q = (params.get("query") or "").lower()
    if not q:
        raise ValueError("query is required")
    p = Path(resource)
    hits = []
    for root, _dirs, files in os.walk(p):
        # never descend into sensitive children even under allowed parents
        _dirs[:] = [d for d in _dirs
                    if not policy.is_sensitive_path(os.path.join(root, d))]
        for f in files:
            if q in f.lower():
                hits.append(os.path.join(root, f))
                if len(hits) >= 200:
                    return hits
    return hits


def _write(resource, op, params):
    content = params.get("content", "")
    p = Path(resource)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return {"path": resource, "bytes": len(content.encode("utf-8"))}


def _mkdir(resource, op, params):
    Path(resource).mkdir(parents=True, exist_ok=True)
    return {"path": resource}


def _move(resource, op, params):
    dest = params.get("dest")
    if not dest:
        raise ValueError("dest is required")
    # dest must ALSO pass the boundary check
    ok, reason = policy.check_path(dest, "write")
    if not ok:
        raise PermissionError("destination blocked: " + reason)
    shutil.move(resource, dest)
    return {"src": resource, "dest": dest}


def _delete(resource, op, params):
    p = Path(resource)
    if p.is_dir():
        shutil.rmtree(p)
    else:
        p.unlink()
    return {"deleted": resource}


def register() -> None:
    gateway.register_tool("fs_list", _list)
    gateway.register_tool("fs_stat", _stat)
    gateway.register_tool("fs_read", _read)
    gateway.register_tool("fs_search", _search)
    gateway.register_tool("fs_write", _write)
    gateway.register_tool("fs_mkdir", _mkdir)
    gateway.register_tool("fs_move", _move)
    gateway.register_tool("fs_delete", _delete)
