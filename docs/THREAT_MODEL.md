# SHIRAZI LV — Threat Model

What we defend, what we assume, and where the sharp edges are.

## Assets

| Asset | Location | Protection |
|---|---|---|
| API keys (Gemini, Groq, OpenRouter) | OS credential store (Windows Credential Manager); legacy `config/api_keys.json` during migration | OS ACLs; redacted in logs |
| Permission grants | `~/.shirazi/omnicontrol.db` (SQLite) | Revocation checked per call; expiring |
| Approval tokens | In-memory, single-use, 120s TTL | Never leave the process |
| Episodic memory | `~/.shirazi/*.db` | Local only; user-deletable |
| Dashboard sessions | In-memory device tokens | One-time pairing keys; revocation API |

## Trust boundaries

1. **The model is untrusted for authorization.** It proposes; deterministic
   code disposes. No model output — tool description, reasoning text, or
   generated code — can grant permissions or lower risk tiers.
2. **Tool/plugin/MCP output is untrusted.** It cannot mint approvals, alter
   the folder allow-list, or change policy. Verified by
   `test/test_prompt_injection.py`.
3. **Web content is untrusted.** Page text, emails, and downloaded files are
   data. They never override user instructions or OmniControl policy.
4. **Voice is not identity.** Voice can propose; sensitive approvals need a
   dashboard/HUD tap.

## Attack scenarios & mitigations

| Attack | Mitigation | Test |
|---|---|---|
| Malicious tool description claims LOW risk | Policy risk always wins (`capabilities.py`) | `test_capabilities.py::RiskIntegrity` |
| Tool output fakes an approval | Approvals only via `user_approve()` (dashboard tap) | `test_prompt_injection.py` |
| Path traversal (`../`, absolute) | `check_path()` canonicalizes; allow-list enforced | `test_adversarial.py::FilesystemTraversal` |
| Symlink/junction escape | Resolved before allow-list check | `test_adversarial.py` |
| Revoked grant reused | `live_grant()` revalidates every call | `test_adversarial.py::RevocationEnforcement` |
| One-shot token replayed | `_consume_approval()` pops on use | `test_adversarial.py` |
| Secret in logs/diagnostics | `redact()` patterns (incl. `sk-or-v1-`) | `test_adversarial.py::SecretRedaction` |
| Plugin crash takes down app | Per-call try/except; auto-disable after 5 | `test_nextsteps.py` |
| LLM-generated code escape | No `getattr`/`hasattr`/`ctypes`; `_CheckedPath` allow-list; 60s timeout | `test_nextsteps.py::DesktopSandbox` |
| Emergency while provider down | estop is local, model-independent | `test_adversarial.py` |

## Known residual risks

- **F-012**: `actions/desktop.py` still executes LLM-generated Python. It is
  HIGH-risk (dashboard approval required), sandbox-hardened, and
  allow-list-checked — but code execution is inherently high-risk. Do not
  approve desktop actions you don't understand.
- **Windows-only verification**: UI Automation providers, Playwright flows,
  and Credential Manager behavior are implemented but need testing on a
  real Windows PC before being called production-ready.
- **Supply chain**: dependencies are pinned with upper bounds; no lockfile
  audit has been run. Run `pip audit` before release.
