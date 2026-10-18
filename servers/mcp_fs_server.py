"""
OMNICONTROL MCP filesystem server — a REAL MCP server (official `mcp` SDK 2.x).

Runs as a child process over stdio, spawned by the gateway. It enforces
authorization INDEPENDENTLY (per spec §9): it reads the same
~/.shirazi/omnicontrol.db policy, checks the emergency-stop flag, and applies
the filesystem boundary itself — it never trusts the calling agent.

Exposed tools: fs_list, fs_read, fs_search, fs_stat, fs_write, fs_mkdir.
(HIGH-risk fs_move / fs_delete stay behind the in-process gateway's dashboard
approval and are NOT exposed over MCP in the MVP.)

Usage:
    python servers/mcp_fs_server.py            # stdio transport
    SHIRAZI_DATA_DIR=/custom/path python servers/mcp_fs_server.py
"""
from __future__ import annotations

import os
import sys

# Make `core` importable when launched as a subprocess from the app root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if os.environ.get("SHIRAZI_DATA_DIR"):
    # Allow tests / portable installs to relocate ~/.shirazi
    import pathlib
    os.environ["HOME"] = os.environ["SHIRAZI_DATA_DIR"]

from mcp.server.mcpserver import MCPServer  # noqa: E402

from core.omnicontrol import audit, db, estop, fs_tools, policy  # noqa: E402

server = MCPServer("shirazi-fs")


def _guard(tool: str, path: str, op: str) -> None:
    """Independent authorization inside the server process. Raises on denial."""
    if estop.is_tripped():
        raise PermissionError("emergency stop is active")
    ok, reason = policy.check_path(path, op)
    if not ok:
        audit.log("mcp-fs", "deny", tool=tool, resource=path,
                  decision="deny", reason=reason)
        raise PermissionError("denied: " + reason)


@server.tool()
def fs_list(path: str) -> list:
    """List directory entries (allow-listed folders only)."""
    _guard("fs_list", path, "read")
    return fs_tools._list(path, "read", {})


@server.tool()
def fs_read(path: str) -> dict:
    """Read a text file (size-capped, allow-listed folders only)."""
    _guard("fs_read", path, "read")
    return fs_tools._read(path, "read", {})


@server.tool()
def fs_stat(path: str) -> dict:
    """File metadata (allow-listed folders only)."""
    _guard("fs_stat", path, "read")
    return fs_tools._stat(path, "read", {})


@server.tool()
def fs_search(path: str, query: str) -> list:
    """Search file names under a folder (allow-listed folders only)."""
    _guard("fs_search", path, "read")
    return fs_tools._search(path, "read", {"query": query})


@server.tool()
def fs_write(path: str, content: str) -> dict:
    """Create/overwrite a text file (needs write on an allow-listed folder)."""
    _guard("fs_write", path, "write")
    result = fs_tools._write(path, "write", {"content": content})
    audit.log("mcp-fs", "execute", tool="fs_write", resource=path,
              decision="allow", reason="write within allow-list")
    return result


@server.tool()
def fs_mkdir(path: str) -> dict:
    """Create a directory (needs write on an allow-listed folder)."""
    _guard("fs_mkdir", path, "write")
    return fs_tools._mkdir(path, "write", {})


if __name__ == "__main__":
    db.connect()  # ensure schema exists
    server.run(transport="stdio")
