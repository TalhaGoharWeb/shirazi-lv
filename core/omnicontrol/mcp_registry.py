"""
OMNICONTROL MCP tool registry.

The gateway (gateway.py) IS the execution registry — every tool is registered
there with its risk tier and handler. This module adds the MCP face:

* tool_schemas() — MCP-compatible JSON Schemas for every registered tool,
  so external MCP clients can discover the surface.
* spawn_fs_server() — launch the real MCP filesystem server
  (servers/mcp_fs_server.py, official `mcp` SDK 2.x) as a stdio child
  process. The server enforces authorization independently.

No fake interfaces: if the `mcp` package is missing, spawn_fs_server()
raises a clear error instead of pretending.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from . import gateway, policy

_APP_ROOT = Path(__file__).resolve().parent.parent.parent


def tool_schemas() -> list[dict]:
    """MCP-style tool descriptors for the registered tool surface."""
    schemas = []
    for name, risk in sorted(policy.TOOL_RISK.items()):
        schemas.append({
            "name": name,
            "description": "SHIRAZI OMNICONTROL tool '%s' (risk: %s). "
                           "All calls are authorized by the gateway; "
                           "HIGH/CRITICAL need dashboard approval." % (name, risk),
            "risk": risk,
            "inputSchema": {"type": "object",
                           "properties": {
                               "resource": {"type": "string"},
                               "op": {"type": "string"},
                               "params": {"type": "object"},
                               "approval_token": {"type": "string"}},
                           "required": ["resource", "op"]},
        })
    return schemas


_children: list = []  # P2.7: tracked for graceful shutdown

# Next steps: per-server health + reconnect state.
_servers: dict[str, dict] = {}  # name -> {proc, last_ok, failures, scopes}


def server_health(name: str) -> dict:
    """Health snapshot for a managed MCP server. Never raises."""
    s = _servers.get(name, {})
    proc = s.get("proc")
    alive = bool(proc is not None and proc.poll() is None)
    return {
        "name": name,
        "alive": alive,
        "last_ok": s.get("last_ok", 0.0),
        "failures": s.get("failures", 0),
        "scopes": sorted(s.get("scopes", set())),
        "pid": proc.pid if alive else None,
    }


def all_server_health() -> list[dict]:
    return [server_health(n) for n in sorted(_servers)]


def _note_success(name: str) -> None:
    import time as _t
    s = _servers.setdefault(name, {})
    s["last_ok"] = _t.time()
    s["failures"] = 0


def _note_failure(name: str) -> None:
    s = _servers.setdefault(name, {})
    s["failures"] = s.get("failures", 0) + 1


def spawn_managed(name: str, script: str, scopes: set | None = None,
                  max_restarts: int = 3) -> "subprocess.Popen":
    """Spawn an MCP server with health tracking and bounded restarts.

    The executable is ALWAYS the current Python; the script must live under
    the app's servers/ dir (no arbitrary paths). Restarts are bounded —
    after max_restarts failures the server stays down until manually
    re-enabled.
    """
    script_p = (_APP_ROOT / "servers" / Path(script).name).resolve()
    allowed_dir = (_APP_ROOT / "servers").resolve()
    if allowed_dir not in script_p.parents and script_p != allowed_dir:
        raise ValueError("MCP server script must live under servers/")
    if not script_p.exists():
        raise RuntimeError("MCP server script missing: %s" % script_p)
    try:
        import mcp  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("the 'mcp' package is not installed "
                           "(pip install 'mcp>=2.0,<3')") from exc
    st = _servers.setdefault(name, {})
    if st.get("failures", 0) >= max_restarts:
        raise RuntimeError(f"MCP server '{name}' exceeded {max_restarts} "
                           "restarts; re-enable it manually")
    proc = subprocess.Popen(
        [sys.executable, str(script_p)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=str(_APP_ROOT))
    _children.append(proc)
    st["proc"] = proc
    st["scopes"] = set(scopes or set())
    _note_success(name)
    return proc


def terminate_all() -> None:
    """P2.7: terminate all spawned MCP child processes (graceful shutdown)."""
    for proc in list(_children):
        try:
            proc.terminate()
        except Exception:
            pass
    for proc in list(_children):
        try:
            proc.wait(timeout=5.0)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    _children.clear()


def spawn_fs_server() -> subprocess.Popen:
    """Spawn the real MCP filesystem server (stdio). Raises if mcp missing."""
    try:
        import mcp  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("the 'mcp' package is not installed "
                           "(pip install 'mcp>=2.0,<3')") from exc
    script = _APP_ROOT / "servers" / "mcp_fs_server.py"
    if not script.exists():
        raise RuntimeError("MCP server script missing: %s" % script)
    proc = subprocess.Popen(
        [sys.executable, str(script)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=str(_APP_ROOT))
    _children.append(proc)
    return proc
