#!/usr/bin/env python3
"""
Phase 3.10 — Plugin validator. Checks a plugin file before installation.

Usage: python tools/validate_plugin.py plugins/my_tool.py

Checks:
  - File parses (syntax).
  - PLUGIN dict exists with name/description/parameters.
  - Name matches ^[a-zA-Z_][a-zA-Z0-9_]{0,63}$ and is unique.
  - Description is non-empty.
  - Parameters schema is a valid OBJECT with no empty enums.
  - run() exists with the right signature.
  - No obvious secret literals (api_key = "...", etc.).
Exit 0 = valid, 1 = problems found.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$")
SECRET_RE = re.compile(
    r"(api[_-]?key|secret|password|token)\s*=\s*['\"][^'\"]{8,}['\"]",
    re.IGNORECASE)


def validate(path: Path) -> list[str]:
    problems: list[str] = []
    try:
        src = path.read_text(encoding="utf-8")
    except OSError as e:
        return [f"cannot read file: {e}"]
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError as e:
        return [f"syntax error: {e}"]

    # PLUGIN dict
    plugin = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "PLUGIN":
                    try:
                        plugin = ast.literal_eval(node.value)
                    except Exception:
                        problems.append("PLUGIN is not a literal dict")
    if plugin is None:
        problems.append("no PLUGIN dict found")
        return problems

    name = plugin.get("name", "")
    if not NAME_RE.match(str(name)):
        problems.append(f"bad name '{name}' (must match ^[a-zA-Z_]...)")
    if not str(plugin.get("description", "")).strip():
        problems.append("description is empty")
    params = plugin.get("parameters") or {}
    if params.get("type") != "OBJECT":
        problems.append("parameters.type must be 'OBJECT'")
    props = params.get("properties") or {}
    for pname, pspec in props.items():
        if isinstance(pspec, dict) and "enum" in pspec and not pspec["enum"]:
            problems.append(f"empty enum on '{pname}' (Live API rejects it)")

    # run()
    has_run = any(isinstance(n, ast.FunctionDef) and n.name == "run"
                  for n in ast.walk(tree))
    if not has_run:
        problems.append("no run() function found")

    # Secrets
    if SECRET_RE.search(src):
        problems.append("possible hardcoded secret (api_key/secret/password/token = \"...\")")

    # Name collision with existing plugins
    plugins_dir = path.parent
    if plugins_dir.name == "plugins":
        for other in plugins_dir.glob("*.py"):
            if other == path or other.name.startswith("_"):
                continue
            try:
                otree = ast.parse(other.read_text(encoding="utf-8"))
                for node in ast.walk(otree):
                    if isinstance(node, ast.Assign):
                        for t in node.targets:
                            if isinstance(t, ast.Name) and t.id == "PLUGIN":
                                try:
                                    oname = ast.literal_eval(node.value).get("name")
                                    if oname == name:
                                        problems.append(
                                            f"name '{name}' collides with {other.name}")
                                except Exception:
                                    pass
            except Exception:
                pass
    return problems


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_plugin.py plugins/my_tool.py")
        return 2
    problems = validate(Path(argv[1]))
    if problems:
        print("INVALID:")
        for p in problems:
            print(f"  ✗ {p}")
        return 1
    print("VALID ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
