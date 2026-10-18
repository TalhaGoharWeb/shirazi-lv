"""Build Failure Doctor — turn a failed build log into a diagnosis.

WHO REASONS: you do. The model pastes the build log (and what changed);
this plugin does the deterministic part: it extracts error lines,
file/line references and stack frames, then matches ranked root-cause
hypotheses against evidence it can quote. It never invents a cause the
log does not support — unmatched logs get an honest "no hypothesis
matched, here are the raw error lines".

Methodology enforced in the contract: reproduce first, confirm the root
cause, make the MINIMAL change, re-run tests, show the real build result.
A fix is done when the failure is reproduced-then-gone, not when it
"looks right".

Permissions used: none (pure text processing, stdlib only).
"""

from __future__ import annotations

import re

_MAX_LOG_CHARS = 200_000
_MAX_LINES = 5000

_ERROR_RES = [
    re.compile(r"\berror\b", re.I),
    re.compile(r"\bfailed\b", re.I),
    re.compile(r"\bexception\b", re.I),
    re.compile(r"traceback", re.I),
    re.compile(r"^\s*e:", re.I),
    re.compile(r"FAILURE:", re.I),
    re.compile(r"\bfatal\b", re.I),
]

# file.py:12 / File "x.py", line 12 / at Foo.java:45 / path/f.dart:12:5
_FILE_REF_RES = [
    re.compile(r'File "([^"]+\.(?:py|java|kt|dart|js|ts|gradle|xml|cs|cpp|c|h|swift|rb|go|rs))", line (\d+)'),
    re.compile(r"\bat\s+[\w.$]+\(([\w./\\-]+\.(?:java|kt|dart|js|ts|cs|cpp|c|h)),?\s*:?\s*(\d+)\)"),
    re.compile(r"([\w./\\-]+\.(?:py|java|kt|dart|js|ts|gradle|xml|cs|cpp|c|h|swift|rb|go|rs)):(\d+)(?::(\d+))?"),
]

# (pattern, hypothesis, why-it-matters)
_HYPOTHESES = [
    (re.compile(r"ModuleNotFoundError|No module named|ImportError|cannot import|"
                r"Could not resolve|package .* not found|Cannot resolve symbol", re.I),
     "Missing dependency",
     "the log names something that is not installed / not on the path"),
    (re.compile(r"version .* conflict|incompatible|requires .* but .* installed|"
                r"Dependency .* requires|Could not find .* which is required", re.I),
     "Dependency version conflict",
     "two packages (or package vs SDK) demand incompatible versions"),
    (re.compile(r"ANDROID_HOME|SDK .* not found|platform-tools|license .* not accepted|"
                r"flutter.*NoSuchMethod.*sdk|cmdline-tools", re.I),
     "Environment / SDK misconfiguration",
     "the toolchain itself (SDK paths, licences, tools) is missing"),
    (re.compile(r"keystore|signing.*failed|signature|jarsigner|apksigner", re.I),
     "Signing / packaging configuration",
     "release packaging needs keys or signing config"),
    (re.compile(r"OutOfMemory|GC overhead|heap space|Kotlin.*OutOfMemory|"
                r"daemon.*memory|Metaspace", re.I),
     "Resource exhaustion (memory)",
     "the build ran out of heap / daemon memory"),
    (re.compile(r"Permission denied|EACCES|access is denied|EPERM", re.I),
     "File permission problem",
     "the build cannot read/write something it needs"),
    (re.compile(r"Could not .* https?://|UnknownHost|Name or service not known|"
                r"Connection timed out|proxy|SSL.*handshake", re.I),
     "Network failure while fetching",
     "dependency download failed — network, proxy or mirror issue"),
    (re.compile(r"SyntaxError|expected .* but found|';' expected|"
                r"illegal start|mismatched input", re.I),
     "Code syntax error",
     "a source file does not parse"),
]

_VERIFY_COMMANDS = {
    "flutter": ["flutter analyze", "flutter test",
                "flutter build apk --debug"],
    "gradle": ["./gradlew assembleDebug --stacktrace"],
    "python": ["python -m pytest -x -q", "pip check"],
    "npm": ["npm run build"],
    "node": ["npm run build"],
    "maven": ["mvn -q -DskipTests package"],
}


def _cap_log(log: str):
    text = str(log or "")
    clipped = False
    if len(text) > _MAX_LOG_CHARS:
        text, clipped = text[:_MAX_LOG_CHARS], True
    lines = text.splitlines()
    if len(lines) > _MAX_LINES:
        lines, clipped = lines[:_MAX_LINES], True
    return lines, clipped


def _error_lines(lines):
    out, seen = [], set()
    for ln in lines:
        s = ln.strip()
        if not s or len(s) > 500:
            continue
        if any(r.search(s) for r in _ERROR_RES):
            key = s[:160].lower()
            if key not in seen:
                seen.add(key)
                out.append(s[:300])
        if len(out) >= 15:
            break
    return out


def _file_refs(lines):
    out, seen = [], set()
    for ln in lines:
        for rx in _FILE_REF_RES:
            for m in rx.finditer(ln):
                ref = f"{m.group(1)}:{m.group(2)}"
                if ref not in seen:
                    seen.add(ref)
                    out.append(ref)
        if len(out) >= 15:
            return out
    return out


def _hypotheses(text):
    found = []
    for rx, name, why in _HYPOTHESES:
        m = rx.search(text)
        if m:
            snippet = m.group(0)[:120]
            found.append((name, why, snippet))
    return found


def run_diagnose(args):
    log = args.get("log")
    if not str(log or "").strip():
        return ("Paste the build log — the last 100-200 lines are usually "
                "enough. Add `what_changed` (what you edited before it "
                "broke) if you know it; that halves diagnosis time.")
    build_system = str(args.get("build_system") or "").strip().lower()
    what_changed = str(args.get("what_changed") or "").strip()
    lines, clipped = _cap_log(log)
    text = "\n".join(lines)
    errs = _error_lines(lines)
    refs = _file_refs(lines)
    hyps = _hypotheses(text)

    out = ["Build diagnosis", ""]
    out.append(f"Scanned {len(lines)} log lines"
               + (" (clipped to the first chunk)" if clipped else "")
               + ".")
    if what_changed:
        out.append(f"What changed before it broke: {what_changed[:300]}")
    out.append("")
    out.append(f"Error lines found: {len(errs)}")
    for e in errs[:10]:
        out.append(f"  ! {e}")
    out.append("")
    out.append(f"File/line references: {len(refs)}")
    for r in refs[:10]:
        out.append(f"  @ {r}")
    out.append("")
    if hyps:
        out.append("Root-cause hypotheses (ranked, evidence-quoted):")
        for i, (name, why, snippet) in enumerate(hyps, 1):
            out.append(f"  {i}. {name} — {why}.")
            out.append(f'     evidence: "{snippet}"')
    else:
        out.append("No hypothesis matched this log honestly. Do NOT guess: "
                   "use the error lines and file references above, reproduce "
                   "the failure, and narrow it down manually.")
    out += ["",
            "Methodology — reproduce first:",
            "1. Reproduce: run the same build command clean and confirm "
            "the same failure.",
            "2. Confirm: the hypothesis must explain ALL the error lines, "
            "not just one.",
            "3. Minimal change: fix one thing (one dependency, one config).",
            "4. Re-run: tests first, then the build.",
            "5. Report the REAL result — never call a failed build fixed.",
            "",
            "Next: call build_fix_checklist with the confirmed root cause "
            "to get the fix-and-verify checklist."]
    return "\n".join(out)


def run_fix_checklist(args):
    root_cause = str(args.get("root_cause") or "").strip()
    if not root_cause:
        return ("Pass the CONFIRMED root cause (from build_diagnose, after "
                "reproducing) — this builds the fix checklist around it.")
    build_system = str(args.get("build_system") or "").strip().lower()
    evidence = str(args.get("evidence") or "").strip()
    cmds = _VERIFY_COMMANDS.get(build_system)
    out = ["Fix checklist", f"Root cause: {root_cause[:400]}", ""]
    if evidence:
        out.append(f"Supporting evidence: {evidence[:300]}")
        out.append("")
    out += ["1. REPRODUCE — run the failing build once more, clean, and "
            "confirm the identical failure.",
            "2. MINIMAL CHANGE — change exactly one thing:",
            "   - missing dependency  -> install/pin the named package, "
            "nothing else",
            "   - version conflict     -> pin the narrowest compatible "
            "range; do not upgrade the world",
            "   - SDK/environment     -> fix the path/licence; do not "
            "reinstall the toolchain first",
            "   - signing/packaging    -> fix the keystore/config entry",
            "   - memory               -> raise the heap/daemon memory, "
            "then re-run",
            "3. RE-RUN TESTS, then the build:"]
    if cmds:
        for c in cmds:
            out.append(f"   $ {c}")
    else:
        out.append("   $ <the project's test command, then the build "
                   "command>")
    out += ["4. VERIFY — the original error lines are gone AND the build "
            "artifact exists (apk/exe/package). Never call a failed "
            "build fixed — the artifact must exist.",
            "5. LEARN — record problem + root cause + fix in the "
            "troubleshooting memory so the next identical failure is "
            "recognised instantly.",
            "",
            "If step 4 fails, do NOT stack another fix on top — revert, "
            "re-diagnose, and treat it as a new hypothesis."]
    return "\n".join(out)


TOOLS = [
    {"name": "build_diagnose",
     "description": (
         "Diagnose a failed build from its log. YOU paste the build log "
         "(last 100-200 lines suffice) plus optionally build_system "
         "(flutter/gradle/python/npm/maven) and what_changed. Returns: "
         "error-line extraction, file:line references, ranked root-cause "
         "hypotheses each quoted against log evidence, and the "
         "reproduce-first methodology. It will NOT invent a cause the log "
         "does not support. Call this for 'build nahi ho raha / APK "
         "build failed / compile error' — then build_fix_checklist."),
     "kind": "native", "access": "read",
     "parameters": {
         "type": "object",
         "properties": {
             "log": {"type": "string",
                     "description": "The build log text (pasted)."},
             "build_system": {"type": "string",
                              "description": "flutter, gradle, python, npm, "
                                             "node, maven, or empty."},
             "what_changed": {"type": "string",
                              "description": "What was edited before it "
                                             "broke, if known."}},
         "required": ["log"]},
     "run": run_diagnose},
    {"name": "build_fix_checklist",
     "description": (
         "Build the fix-and-verify checklist around a CONFIRMED root "
         "cause: reproduce, minimal single change, re-run tests then the "
         "build (with the right verify commands for the build system), "
         "verify the artifact exists, and record the fix. Pass root_cause "
         "only after build_diagnose + reproduction."),
     "kind": "native", "access": "read",
     "parameters": {
         "type": "object",
         "properties": {
             "root_cause": {"type": "string"},
             "build_system": {"type": "string"},
             "evidence": {"type": "string",
                          "description": "Log snippet supporting the cause."}},
         "required": ["root_cause"]},
     "run": run_fix_checklist},
]
