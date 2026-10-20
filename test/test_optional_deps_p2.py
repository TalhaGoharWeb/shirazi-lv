"""P2.9 / F-010 regression tests: PyQt6-WebEngine is an optional dependency.

  1. requirements-base.txt exists, parses, and is exactly requirements.txt
     minus the PyQt6-WebEngine line (the base/full split is real, not a
     comment-only promise).
  2. setup.py --base wiring references requirements-base.txt.

(Item 1 of the original suite — core.avatar3d degrading gracefully without
WebEngine — was retired with the Iron Man 3D avatar itself, removed
2026-10-20 when the HUD was replaced wholesale with Mark LVI's.)
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
