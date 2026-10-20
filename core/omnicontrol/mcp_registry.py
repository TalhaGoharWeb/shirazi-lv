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
