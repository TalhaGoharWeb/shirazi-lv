"""
SHIRAZI OMNICONTROL — dynamic access control, MCP tool orchestration,
autonomous PC operation.

Importing this package registers all built-in tools with the gateway:

    from core.omnicontrol import gateway, policy, audit, estop
    from core.omnicontrol import fs_tools, github_tools, orchestrator, permissions
    fs_tools.register(); github_tools.register()
"""
from . import audit, db, estop, gateway, policy  # noqa: F401
