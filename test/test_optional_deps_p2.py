"""P2.9 / F-010 regression tests: PyQt6-WebEngine is an optional dependency.

  1. Simulates PyQt6-WebEngine being ABSENT (an import hook makes
     `import PyQt6.QtWebEngineWidgets` raise ImportError) in a fresh
     subprocess, and asserts core.avatar3d degrades gracefully:
     is_3d_available() returns False (no exception), availability_reason()
     explains the missing package, and Avatar3D() still constructs with
     available() False while set_state/set_amp/show/hide never raise.
  2. requirements-base.txt exists, parses, and is exactly requirements.txt
     minus the PyQt6-WebEngine line (the base/full split is real, not a
     comment-only promise).
  3. setup.py --base wiring references requirements-base.txt.

The base-install acceptance gate ("base install works without optional
rendering/browser features") rests on all three.
"""
import json
import subprocess
import sys
import textwrap
from pathlib import Path

_HERE = Path(__file__).resolve().parent.parent  # shirazi-lv/


def _req_names(path: Path):
    """Parse a requirements file into a set of lower-cased package names."""
    from packaging.requirements import Requirement
    names = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # strip inline comments and environment markers (everything after ';')
        line = line.split(" #", 1)[0].strip()
        names.add(Requirement(line.split(";")[0].strip()).name.lower())
    return names


_CHILD = textwrap.dedent(
    """
    import importlib.abc
    import json
    import sys

    sys.path.insert(0, {repo!r})

    class _BlockWebEngine(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path, target=None):
            if name == "PyQt6.QtWebEngineWidgets" or name.startswith(
                    "PyQt6.QtWebEngineWidgets."):
                raise ImportError(
                    "No module named 'PyQt6.QtWebEngineWidgets' "
                    "(simulated missing WebEngine)")
            return None

    sys.meta_path.insert(0, _BlockWebEngine())

    # Sanity: the blocker must actually fire.
    try:
        import PyQt6.QtWebEngineWidgets  # noqa
        print("RESULT:" + json.dumps({{"blocker_failed": True}}))
        sys.exit(2)
    except ImportError:
        pass

    import core.avatar3d as a3d

    out = {{
        "is_3d_available": a3d.is_3d_available(),
        "reason": a3d.availability_reason(),
    }}
    av = a3d.Avatar3D()  # must not raise without WebEngine
    out["widget_is_none"] = av.widget is None
    out["method_available"] = av.available()
    # No-ops must never raise.
    av.set_state("SPEAKING")
    av.set_amp(0.9)
    av.show()
    av.hide()
    out["no_raise"] = True
    print("RESULT:" + json.dumps(out))
    """
).format(repo=str(_HERE))


def _run_child():
    r = subprocess.run(
        [sys.executable, "-c", _CHILD],
        capture_output=True, text=True, timeout=120, cwd=str(_HERE),
    )
    assert r.returncode == 0, f"child failed (rc={r.returncode}): {r.stderr[-2000:]}"
    for line in r.stdout.splitlines():
        if line.startswith("RESULT:"):
            result = json.loads(line[len("RESULT:"):])
            assert not result.pop("blocker_failed", False), "import blocker did not fire"
            return result
    raise AssertionError(f"no RESULT line in child output: {r.stdout[-1000:]}\n{r.stderr[-1000:]}")


class TestWebEngineAbsent:
    def test_is_3d_available_false_no_exception(self):
        result = _run_child()
        assert result["is_3d_available"] is False

    def test_reason_mentions_webengine(self):
        result = _run_child()
        assert "WebEngine" in result["reason"], result["reason"]

    def test_avatar3d_wrapper_still_usable(self):
        result = _run_child()
        assert result["widget_is_none"] is True
        assert result["method_available"] is False
        assert result["no_raise"] is True


class TestRequirementsSplit:
    def test_base_file_exists_and_excludes_webengine(self):
        base = _HERE / "requirements-base.txt"
        full = _HERE / "requirements.txt"
        assert base.is_file(), "requirements-base.txt must ship"
        base_names = _req_names(base)
        full_names = _req_names(full)
        assert "pyqt6-webengine" not in base_names
        assert "pyqt6-webengine" in full_names
        # The base file must be exactly the full file minus WebEngine —
        # otherwise the split silently rots.
        assert full_names - base_names == {"pyqt6-webengine"}, (
            f"base/full drift: {full_names ^ base_names}"
        )

    def test_full_file_still_documents_split(self):
        header = (_HERE / "requirements.txt").read_text(encoding="utf-8")[:1500]
        assert "requirements-base.txt" in header


class TestSetupBaseFlag:
    def test_setup_py_supports_base(self):
        src = (_HERE / "setup.py").read_text(encoding="utf-8")
        assert '"--base"' in src or "'--base'" in src
        assert "requirements-base.txt" in src
