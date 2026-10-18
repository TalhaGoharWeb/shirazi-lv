# SHIRAZI OMNICONTROL — MVP Guide

Dynamic access control, MCP-based tool orchestration, and autonomous task
execution for SHIRAZI LV. This is the **MVP** (stages 1–4 of the 9-stage plan
in `~/workspace/omnicontrol/OMNICONTROL_ARCHITECTURE.md`).

## What the MVP includes

- **Authorization gateway** (`core/omnicontrol/gateway.py`) — every tool call
  passes through it. Deny-by-default: no grant = no access.
- **Risk tiers** — LOW (reads in approved folders, voice-OK), MODERATE
  (writes, needs a scoped grant), HIGH (deletes, privileged ops — dashboard
  approval), CRITICAL (blocked by policy).
- **Filesystem tools** (`fs_list/read/search/stat/write/mkdir/move/delete`)
  bound to a folder allow-list. Symlink/junction/traversal escapes blocked;
  sensitive children (`.ssh`, `*.pem`, browser profiles, `*credential*`, …)
  never inherit a parent's approval.
- **Real MCP server** (`servers/mcp_fs_server.py`, official `mcp` SDK 2.x,
  stdio) exposing the fs tools with **independent server-side authorization**.
- **Task orchestrator** — states, cancellation, checkpoints, honest failure.
- **Permission commands** — voice or text ("allow read access to …", "revoke
  …", "show permissions", "stop everything"). Voice alone only confirms
  LOW-risk reads; everything else needs your tap.
- **Permission dashboard** — tap the 🛡 button: pending approvals
  (Allow Once / Allow Always / Deny), folder allow-list, GitHub repos,
  tasks, audit log, and the emergency stop.
- **Emergency stop** — voice phrase ("stop everything"), dashboard button,
  HUD hotkey hook. Implemented in the local layer — works with no AI model.
- **GitHub** — read-only, per-repo approval, token from `SHIRAZI_GITHUB_TOKEN`
  env var or OS keyring. Never logged.

## Setup (Windows PC)

1. Install the new dependency:
   `C:\Python314\python.exe -m pip install "mcp>=2.0,<3"`
2. Run SHIRAZI as usual. The policy DB is created at
   `%USERPROFILE%\.shirazi\omnicontrol.db` on first run.
3. Open the dashboard → 🛡 → **Folder Allow-List** → add your project folders
   (e.g. your Shirazi workspace, dev folders, an import folder).
4. Optional: set `SHIRAZI_GITHUB_TOKEN`, then approve repos in the dashboard.

## Voice commands

- "Shirazi, allow read access to my Madrassa 360 project."
- "Give Shirazi write access to this folder for two hours."
- "Revoke access to my Downloads folder."
- "Show permissions."
- "Stop everything." (emergency stop — also works mid-task)

## For developers

- New privileged tool? Register it in `core/omnicontrol/policy.py`
  (`TOOL_RISK`) + `gateway.register_tool(name, handler)`, then call it only
  via `gateway.execute(...)`.
- Tests: `python -m pytest test/test_omnicontrol.py` — 20 acceptance tests
  (deny-by-default, per-call enforcement, revocation, path escapes, estop
  without a model, audit secret-redaction).
- Voice integration in `main.py` (3 lines, see `voice_hooks.py` docstring).
