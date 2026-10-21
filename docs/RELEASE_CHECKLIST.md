# SHIRAZI LV — Release Checklist

Run this before every release. Every item must be checked with evidence,
not assumed.

## Pre-release

- [ ] `python -m pytest test/ -q` — all green, no skips without a recorded reason
- [ ] `pip audit` — no high/critical vulnerabilities in dependencies
- [ ] `config/api_keys.json` not tracked by git (`git ls-files | grep api_keys.json` → only `api_keys.example.json`)
- [ ] No secrets in the diff (`git diff` reviewed; no `AIza`, `gsk_`, `sk-or-`)
- [ ] README test count matches (`pytest --collect-only -q | tail -1`)
- [ ] Threat model reviewed for new tools/capabilities

## Windows verification (on a real PC)

- [ ] Clean install: unzip → `python setup.py` → `python main.py` works
- [ ] Gemini Live connects (or degraded mode engages honestly)
- [ ] "Hey Shirazi" wake word (or push-to-talk fallback)
- [ ] Credential migration prompt appears; keys land in Credential Manager
- [ ] Dashboard pairs via QR; phone shows capabilities/plugins/tasks
- [ ] HIGH-risk tool triggers approval card; Allow Once works; Deny blocks
- [ ] Emergency stop cancels a running task
- [ ] Companion appears when minimized; approval badge shows on pending

## Post-release

- [ ] GitHub release created with the source zip
- [ ] Release notes list: new features, fixes, known limitations
- [ ] Previous release's download link retired

## Rollback

Each release is a single commit on `main` (via the API push). To roll back:
`git revert <commit>` locally, then push. The local `integration` branch
keeps full history for bisection.
