"""
Unified Capability Registry — Stage B.

One authoritative registry for every tool SHIRAZI can invoke: built-in
product tools, Shirazi plugins, actions, and MCP-server tools. Each
capability carries:

  id            stable namespaced identifier: plugin.<name>, action.<name>,
                builtin.<name>, mcp.<server>.<tool>
  description   human-readable, from the source (never trusted for auth)
  version       source version string
  source        'plugin' | 'action' | 'builtin' | 'mcp'
  source_ref    plugin file / action module / MCP server name
  input_schema  JSON Schema for arguments (validated before execution)
  risk          LOW | MODERATE | HIGH | CRITICAL (from policy, never the tool)
  scopes        permission scopes required, e.g. {'fs:read', 'net:out'}
  timeout_s     default execution timeout
  cancellable   whether mid-execution cancellation is supported
  idempotent    True | False | 'unknown'
  reversible    True | False | 'unknown'
  health        'ok' | 'degraded' | 'failed' | 'unknown'
  last_error    last structured error (for diagnostics, secrets redacted)

Security rules:
- Risk comes from policy.TOOL_RISK / gateway.TOOL_RISK_MAP, NEVER from the
  tool's own description or annotations.
- Input validation happens here, before the gateway authorizes execution.
- Third-party descriptions are display text only.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

try:
    from core.omnicontrol import policy as _policy
    from core.omnicontrol import gateway as _gateway
except Exception:
    _policy = None
    _gateway = None

# ── identifier rules ─────────────────────────────────────────────────────
_ID_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")


def _namespaced(source: str, name: str) -> str:
    """Deterministic namespaced id. Conflicts resolve by source prefix —
    plugin.foo and action.foo are different capabilities."""
    base = re.sub(r"[^a-z0-9_]", "_", str(name).lower()).strip("_")
    return f"{source}.{base or 'unnamed'}"


@dataclass
class Capability:
    id: str
    description: str = ""
    version: str = "1.0.0"
    source: str = "plugin"          # plugin | action | builtin | mcp
    source_ref: str = ""
    input_schema: dict = field(default_factory=dict)
    risk: str = "MODERATE"
    scopes: set = field(default_factory=set)
    timeout_s: float = 120.0
    cancellable: bool = True
    idempotent: str = "unknown"     # True | False | 'unknown'
    reversible: str = "unknown"
    health: str = "unknown"         # ok | degraded | failed | unknown
    last_error: str = ""
    registered_at: float = field(default_factory=time.time)
    invoke_count: int = 0
    error_count: int = 0


class CapabilityRegistry:
    """The single registry. Populated from plugins, actions, builtins and
    MCP servers; queried by the planner, dashboard and diagnostics."""

    def __init__(self):
        self._caps: dict[str, Capability] = {}

    # ── registration ──────────────────────────────────────────────────
    def register(self, cap: Capability) -> str:
        if not _ID_RE.match(cap.id):
            raise ValueError(f"invalid capability id: {cap.id!r}")
        # Risk is authoritative from policy — a capability may not declare
        # itself safer than policy says. Check both policy.TOOL_RISK and
        # gateway.TOOL_RISK_MAP (builtins live in the latter).
        short = cap.id.split(".", 1)[1] if "." in cap.id else cap.id
        policy_risk = None
        if _policy is not None:
            policy_risk = _policy.TOOL_RISK.get(short)
        if not policy_risk and _gateway is not None:
            try:
                policy_risk = _gateway.TOOL_RISK_MAP.get(short)
            except Exception:
                pass
        if policy_risk:
            cap.risk = policy_risk
        self._caps[cap.id] = cap
        return cap.id

    def get(self, cid: str) -> Capability | None:
        return self._caps.get(cid)

    def by_tool_name(self, tool_name: str) -> Capability | None:
        """Find by bare tool name across namespaces (deterministic order)."""
        for prefix in ("builtin", "plugin", "action", "mcp"):
            cap = self._caps.get(f"{prefix}.{tool_name}")
            if cap is not None:
                return cap
        # mcp.<server>.<tool> — match suffix
        for cid, cap in self._caps.items():
            if cid.startswith("mcp.") and cid.endswith(f".{tool_name}"):
                return cap
        return None

    def list(self, source: str | None = None,
             risk: str | None = None) -> list[Capability]:
        caps = list(self._caps.values())
        if source:
            caps = [c for c in caps if c.source == source]
        if risk:
            caps = [c for c in caps if c.risk == risk]
        return sorted(caps, key=lambda c: c.id)

    def count(self) -> int:
        return len(self._caps)

    # ── health ────────────────────────────────────────────────────────
    def report_success(self, cid: str) -> None:
        cap = self._caps.get(cid)
        if cap:
            cap.invoke_count += 1
            cap.health = "ok"
            cap.last_error = ""

    def report_error(self, cid: str, error: str) -> None:
        cap = self._caps.get(cid)
        if cap:
            cap.invoke_count += 1
            cap.error_count += 1
            cap.last_error = str(error)[:500]
            # 3 consecutive errors -> degraded; never auto-recovers to ok
            # without a success.
            if cap.error_count >= 3 and cap.health != "failed":
                cap.health = "degraded"

    def mark_failed(self, cid: str, error: str = "") -> None:
        cap = self._caps.get(cid)
        if cap:
            cap.health = "failed"
            if error:
                cap.last_error = str(error)[:500]

    # ── input validation ──────────────────────────────────────────────
    def validate_args(self, cid: str, args: dict) -> tuple[bool, str]:
        """Validate arguments against the capability's input schema.
        Returns (ok, error). Never raises."""
        cap = self._caps.get(cid)
        if cap is None:
            return False, f"unknown capability: {cid}"
        schema = cap.input_schema or {}
        return _validate_schema(args, schema)

    # ── discovery ─────────────────────────────────────────────────────
    def populate_from_plugins(self, plugin_registry) -> int:
        """Register every tool the plugin loader discovered."""
        n = 0
        try:
            tools = plugin_registry.list_tools()
        except Exception:
            return 0
        for t in tools:
            name = t.get("name", "")
            params = t.get("parameters") or {}
            cap = Capability(
                id=_namespaced("plugin", name),
                description=str(t.get("description", ""))[:500],
                source="plugin",
                source_ref=str(t.get("source_ref", "")),
                input_schema=_normalize_schema(params),
                scopes=_scopes_from_text(str(t.get("description", ""))),
            )
            self.register(cap)
            n += 1
        return n

    def populate_from_actions(self, action_registry) -> int:
        n = 0
        try:
            actions = action_registry.list_actions()
        except Exception:
            return 0
        for a in actions:
            name = a.get("name", "")
            cap = Capability(
                id=_namespaced("action", name),
                description=str(a.get("description", ""))[:500],
                source="action",
                source_ref=str(a.get("module", "")),
                scopes={"app:control", "fs:read"},
            )
            self.register(cap)
            n += 1
        return n

    def populate_from_gateway(self) -> int:
        """Register gateway builtins (covers tools with no plugin/action)."""
        if _gateway is None:
            return 0
        n = 0
        try:
            risk_map = dict(_gateway.TOOL_RISK_MAP)
        except Exception:
            return 0
        for name, risk in risk_map.items():
            cid = _namespaced("builtin", name)
            if cid in self._caps:
                continue
            cap = Capability(
                id=cid,
                description=f"Built-in tool '{name}' (risk: {risk})",
                source="builtin",
                risk=risk,
                scopes=_scopes_for_risk(risk),
            )
            # register() re-applies policy risk; pass through directly
            self._caps[cid] = cap
            n += 1
        return n


# ── schema helpers ───────────────────────────────────────────────────────
def _normalize_schema(params: dict) -> dict:
    """Convert the plugin PARAMS dict (Gemini types) to JSON Schema."""
    if not isinstance(params, dict):
        return {"type": "object"}
    out = {"type": "object", "properties": {}, "required": []}
    props = params.get("properties", {})
    for k, v in props.items():
        if isinstance(v, dict):
            t = str(v.get("type", "string")).lower()
            out["properties"][k] = {
                "type": {"object": "object", "string": "string",
                         "number": "number", "integer": "integer",
                         "boolean": "boolean", "array": "array"}.get(t, "string"),
                "description": str(v.get("description", ""))[:200],
            }
            if t == "array":
                out["properties"][k]["items"] = {"type": "string"}
        else:
            out["properties"][k] = {"type": "string"}
    req = params.get("required", [])
    if isinstance(req, list):
        out["required"] = [str(r) for r in req if isinstance(r, str)]
    return out


def _validate_schema(args: dict, schema: dict) -> tuple[bool, str]:
    """Minimal JSON-Schema validation: types + required. Never raises."""
    try:
        if not isinstance(args, dict):
            return False, "arguments must be an object"
        required = schema.get("required", [])
        for r in required:
            if r not in args:
                return False, f"missing required argument: {r}"
        props = schema.get("properties", {})
        type_map = {"string": str, "integer": int, "number": (int, float),
                    "boolean": bool, "array": list, "object": dict}
        for k, v in args.items():
            spec = props.get(k)
            if not spec:
                continue  # unknown args allowed (forward-compatible)
            want = type_map.get(spec.get("type"))
            if want and not isinstance(v, want):
                return False, (
                    f"argument '{k}' must be {spec.get('type')}, "
                    f"got {type(v).__name__}")
        return True, ""
    except Exception as e:
        return False, f"validation error: {e}"


def _scopes_from_text(description: str) -> set:
    """Heuristic scope extraction from '[shirazi permissions: ...]' tags."""
    scopes = set()
    m = re.search(r"\[shirazi permissions:\s*([^\]]+)\]", description)
    if m:
        for part in m.group(1).split(","):
            scopes.add(part.strip())
    return scopes or {"general"}


def _scopes_for_risk(risk: str) -> set:
    return {
        "LOW": {"read"},
        "MODERATE": {"read", "write"},
        "HIGH": {"read", "write", "execute"},
        "CRITICAL": {"all"},
    }.get(risk, {"read"})


# ── singleton ────────────────────────────────────────────────────────────
_registry: CapabilityRegistry | None = None


def get_registry() -> CapabilityRegistry:
    global _registry
    if _registry is None:
        _registry = CapabilityRegistry()
    return _registry


def reset_registry() -> None:
    global _registry
    _registry = None
