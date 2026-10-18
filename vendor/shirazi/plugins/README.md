# Shirazi Plugins

Drop-in extensions for Shirazi. A plugin is **one folder** with two files:

```
plugins/my_plugin/
  plugin.yaml   # manifest: name, version, description, permissions, actions
  plugin.py     # TOOLS list — same schema as core actions
```

## The format

**plugin.yaml**
```yaml
name: my_plugin
version: 0.1.0
description: What it does, in one line.
permissions:
  - files:write        # what it may touch (see below)
actions:
  - my_action_name     # must match a TOOL name in plugin.py
```

**plugin.py**
```python
TOOLS = [{
    "name": "my_action_name",
    "description": "What the assistant can do with this.",
    "kind": "native",          # "native" | "agent"
    "access": "write",         # "read" | "write" | "destructive"
    "parameters": {            # JSON Schema for the arguments
        "type": "object",
        "properties": {"text": {"type": "string"}},
    },
    "run": lambda args: "did: " + args.get("text", ""),
    # optional: "restore": callable  (undo support for write actions)
}]
```

See `_template/` for a fully commented starter.

## Permissions (declared in the manifest, enforced at load)

| Permission     | Plain words                              |
|----------------|------------------------------------------|
| `network`      | Talk to the internet                     |
| `files:read`   | Read files on this computer                |
| `files:write`  | Create and change files (implies read)     |
| `clipboard`    | Read and write the clipboard               |
| `exec`         | Run system commands                        |

**Enforcement is real, not just config.** Before a plugin is imported,
Shirazi scans its source (AST) for anything needing a permission it did
not declare — `import socket` without `network`, `open()` for writing
without `files:write`, and so on. A plugin that over-reaches is
**blocked**: it never loads, never appears as enabled, and its actions
never reach the assistant. Destructive plugin actions additionally go
through the same confirm gate as core actions.

## Lifecycle

- **Disabled by default.** Drop the folder in, restart Shirazi, then
  enable it in the Plugins tab (or `POST /plugins/<name>/enable`).
- Enable/disable takes effect immediately — disabling mid-session
  removes the plugin's actions from the assistant's action list.
- Blocked plugins show their block reason in the Plugins tab.

## The three first-party plugins

- **notes** (`files:write`) — save, list, search, delete local notes.
- **timer** (`—`) — countdowns and a stopwatch; when a timer fires while
  Shirazi runs, a proactive card appears.
- **web_bookmark** (`—`) — save and list bookmarks (URL validation only;
  no network access needed).

## Security notes

- Plugins run in-process with the sidecar. Only install plugins from
  sources you trust — a permission is a *declared* boundary, and the
  AST scan is a guardrail, not a sandbox.
- The phone dashboard (`/dashboard/*`) is LAN-only in v1: no cloud
  relay, no TLS. Pairing tokens expire in 60s and are single-use;
  device tokens are hashed at rest and can be revoked instantly.
