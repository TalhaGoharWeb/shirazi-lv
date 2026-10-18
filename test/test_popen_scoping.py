"""
P2.5 (F-005) regression tests: the global Popen monkeypatch in main.py must
respect caller-supplied STARTUPINFO instead of silently discarding it.

The patch block only activates on Windows (`if _platform.system() == "Windows"`),
so on Linux we extract the exact block from main.py via AST and exec it under a
simulated Windows environment — the logic under test is the real code, not a copy.
"""
import ast
import types
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent.parent  # shirazi-lv/

CREATE_NO_WINDOW = 0x08000000  # same value as Windows' CREATE_NO_WINDOW


class _FakePopen:
    """Records constructor kwargs instead of spawning a process."""

    def __init__(self, args, **kw):
        self.args = args
        self.kw = kw


class _FakeStartupInfo:
    def __init__(self, dwFlags=0):
        self.dwFlags = dwFlags


def _load_patched_popen():
    """Exec main.py's Windows Popen-patch block with a fake Windows env."""
    tree = ast.parse((_HERE / "main.py").read_text(encoding="utf-8"))
    block = None
    for node in tree.body:
        if isinstance(node, ast.If):
            src = ast.dump(node)
            if "_platform" in src and "Windows" in src and "_Popen" in src:
                block = node
                break
    assert block is not None, "Popen patch block not found in main.py"

    fake_platform = types.SimpleNamespace(system=lambda: "Windows")
    fake_subprocess = types.SimpleNamespace(
        Popen=_FakePopen, CREATE_NO_WINDOW=CREATE_NO_WINDOW
    )
    ns = {"_platform": fake_platform, "_subprocess": fake_subprocess}
    exec(compile(ast.Module(body=[block], type_ignores=[]), "<popen_patch>", "exec"), ns)
    return ns["_subprocess"].Popen  # the patched _Popen class


_PatchedPopen = _load_patched_popen()


class TestPopenScoping(unittest.TestCase):
    def test_default_gets_create_no_window(self):
        p = _PatchedPopen(["dummy"])
        self.assertIn("creationflags", p.kw)
        self.assertTrue(p.kw["creationflags"] & CREATE_NO_WINDOW)
        self.assertNotIn("startupinfo", p.kw)

    def test_existing_creationflags_preserved(self):
        p = _PatchedPopen(["dummy"], creationflags=0x2)
        self.assertEqual(p.kw["creationflags"], 0x2 | CREATE_NO_WINDOW)

    def test_caller_startupinfo_preserved(self):
        si = _FakeStartupInfo(dwFlags=0x1)
        p = _PatchedPopen(["dummy"], startupinfo=si)
        # Same object passed through — not dropped, not replaced.
        self.assertIs(p.kw["startupinfo"], si)
        # The no-window flag added to dwFlags.
        self.assertEqual(si.dwFlags, 0x1 | CREATE_NO_WINDOW)
        # creationflags left alone when caller supplied their own STARTUPINFO.
        self.assertNotIn("creationflags", p.kw)

    def test_dwflags_already_set_left_unchanged(self):
        si = _FakeStartupInfo(dwFlags=CREATE_NO_WINDOW | 0x1)
        _PatchedPopen(["dummy"], startupinfo=si)
        self.assertEqual(si.dwFlags, CREATE_NO_WINDOW | 0x1)

    def test_startupinfo_without_dwflags_gets_flag(self):
        si = types.SimpleNamespace()  # no dwFlags attribute at all
        p = _PatchedPopen(["dummy"], startupinfo=si)
        self.assertIs(p.kw["startupinfo"], si)
        self.assertEqual(si.dwFlags, CREATE_NO_WINDOW)


if __name__ == "__main__":
    unittest.main()
