"""
OS-backed secret store — Stage F.

API keys and integration credentials move from plaintext
config/api_keys.json into the OS credential store:

  Windows  : Windows Credential Manager (via `keyring` if available,
             else ctypes CredWriteW/CredReadW — no new dependency)
  other OS : keyring if available, else a 0600-permission file fallback
             under ~/.shirazi/secrets/ (NOT the old api_keys.json path)

Migration:
  migrate_from_legacy() copies every key from config/api_keys.json into
  the OS store, verifies each one reads back, and ONLY then renames the
  legacy file to api_keys.json.migrated-<timestamp>. The old file is
  never deleted until migration is verified. Recovery = rename it back.

Rules:
- get_secret() / set_secret() / delete_secret() never log values.
- list_secret_names() returns names only, never values.
- Secrets are never exposed to plugins except through an explicit
  allow-listed accessor the integration declares.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

_SERVICE = "SHIRAZI-LV"

_HOME = Path.home()
_FALLBACK_DIR = _HOME / ".shirazi" / "secrets"

# Names we manage. Anything else in the legacy file is left alone.
MANAGED_KEYS = ("gemini_api_key", "groq_api_key", "openrouter_api_key",
                "github_token")


def _is_windows() -> bool:
    return sys.platform == "win32"


# ── backends ─────────────────────────────────────────────────────────────
class _KeyringBackend:
    """Uses the `keyring` package when installed (any OS)."""

    def __init__(self):
        import keyring
        self._kr = keyring

    def get(self, name: str) -> str | None:
        try:
            return self._kr.get_password(_SERVICE, name)
        except Exception:
            return None

    def set(self, name: str, value: str) -> bool:
        try:
            self._kr.set_password(_SERVICE, name, value)
            return True
        except Exception:
            return False

    def delete(self, name: str) -> bool:
        try:
            self._kr.delete_password(_SERVICE, name)
            return True
        except Exception:
            return False


class _WinCredBackend:
    """Windows Credential Manager via ctypes — no new dependency."""

    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self._ct = ctypes
        self._wt = wintypes

    def _advapi(self):
        return self._ct.windll.advapi32

    def get(self, name: str) -> str | None:
        try:
            ct, wt = self._ct, self._wt
            target = f"{_SERVICE}/{name}"

            class CREDENTIAL(ct.Structure):
                _fields_ = [("Flags", wt.DWORD), ("Type", wt.DWORD),
                            ("TargetName", wt.LPWSTR), ("Comment", wt.LPWSTR),
                            ("LastWritten", wt.FILETIME),
                            ("CredentialBlobSize", wt.DWORD),
                            ("CredentialBlob", wt.LPBYTE),
                            ("Persist", wt.DWORD),
                            ("AttributeCount", wt.DWORD),
                            ("Attributes", wt.LPVOID),
                            ("TargetAlias", wt.LPWSTR),
                            ("UserName", wt.LPWSTR)]

            CREDENTIAL._fields_ = CREDENTIAL._fields_  # noqa
            pcred = wt.LPVOID()
            ok = self._advapi().CredReadW(target, 1, 0, ct.byref(pcred))
            if not ok:
                return None
            cred = ct.cast(pcred, ct.POINTER(CREDENTIAL)).contents
            n = cred.CredentialBlobSize
            raw = ct.string_at(cred.CredentialBlob, n)
            self._advapi().CredFree(pcred)
            return raw.decode("utf-16-le")
        except Exception:
            return None

    def set(self, name: str, value: str) -> bool:
        try:
            ct, wt = self._ct, self._wt
            target = f"{_SERVICE}/{name}"
            blob = value.encode("utf-16-le")

            class CREDENTIAL(ct.Structure):
                _fields_ = [("Flags", wt.DWORD), ("Type", wt.DWORD),
                            ("TargetName", wt.LPWSTR), ("Comment", wt.LPWSTR),
                            ("LastWritten", wt.FILETIME),
                            ("CredentialBlobSize", wt.DWORD),
                            ("CredentialBlob", wt.LPBYTE),
                            ("Persist", wt.DWORD),
                            ("AttributeCount", wt.DWORD),
                            ("Attributes", wt.LPVOID),
                            ("TargetAlias", wt.LPWSTR),
                            ("UserName", wt.LPWSTR)]

            cred = CREDENTIAL()
            cred.Flags = 0
            cred.Type = 1  # CRED_TYPE_GENERIC
            cred.TargetName = target
            cred.CredentialBlobSize = len(blob)
            buf = ct.create_string_buffer(blob)
            cred.CredentialBlob = ct.cast(buf, wt.LPBYTE)
            cred.Persist = 2  # CRED_PERSIST_LOCAL_MACHINE
            ok = self._advapi().CredWriteW(ct.byref(cred), 0)
            return bool(ok)
        except Exception:
            return False

    def delete(self, name: str) -> bool:
        try:
            target = f"{_SERVICE}/{name}"
            ok = self._advapi().CredDeleteW(target, 1, 0)
            return bool(ok)
        except Exception:
            return False


class _FileBackend:
    """0600 file fallback (non-Windows without keyring). One file per key,
    never the legacy api_keys.json path."""

    def _path(self, name: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in name)
        return _FALLBACK_DIR / f"{safe}.secret"

    def get(self, name: str) -> str | None:
        try:
            p = self._path(name)
            if not p.exists():
                return None
            return p.read_text(encoding="utf-8").strip()
        except Exception:
            return None

    def set(self, name: str, value: str) -> bool:
        try:
            _FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
            p = self._path(name)
            p.write_text(value, encoding="utf-8")
            try:
                os.chmod(p, 0o600)
            except Exception:
                pass
            return True
        except Exception:
            return False

    def delete(self, name: str) -> bool:
        try:
            self._path(name).unlink(missing_ok=True)
            return True
        except Exception:
            return False


def _pick_backend():
    """Windows: Credential Manager (ctypes, no dependency). Else keyring,
    else 0600 files."""
    if _is_windows():
        try:
            return _WinCredBackend(), "windows-credential-manager"
        except Exception:
            pass
    try:
        return _KeyringBackend(), "keyring"
    except Exception:
        pass
    return _FileBackend(), "file-0600"


_backend, _backend_name = _pick_backend()


def backend_name() -> str:
    return _backend_name


class _MemoryBackend:
    """In-memory backend for tests. No disk, no OS store."""
    def __init__(self):
        self._d: dict[str, str] = {}
    def get(self, name: str) -> str | None:
        return self._d.get(name)
    def set(self, name: str, value: str) -> bool:
        self._d[name] = value
        return True
    def delete(self, name: str) -> bool:
        self._d.pop(name, None)
        return True


def use_memory_backend() -> None:
    """Swap to the in-memory backend (tests only)."""
    global _backend, _backend_name
    _backend, _backend_name = _MemoryBackend(), "memory-test"


# ── public API ───────────────────────────────────────────────────────────
def get_secret(name: str) -> str | None:
    """Read a secret. Returns None when absent. Never logs the value."""
    if not name or not isinstance(name, str):
        return None
    return _backend.get(name)


def set_secret(name: str, value: str) -> bool:
    """Store a secret. Returns True on success. Never logs the value."""
    if not name or not isinstance(name, str) or not value:
        return False
    return _backend.set(name, str(value))


def delete_secret(name: str) -> bool:
    if not name or not isinstance(name, str):
        return False
    return _backend.delete(name)


def list_secret_names() -> list[str]:
    """Names present (values never listed)."""
    return [k for k in MANAGED_KEYS if get_secret(k)]


# ── migration ────────────────────────────────────────────────────────────
def legacy_path() -> Path:
    return Path(__file__).resolve().parent.parent / "config" / "api_keys.json"


def migrate_from_legacy() -> dict:
    """Copy legacy api_keys.json secrets into the OS store.

    Returns {'migrated': [...], 'failed': [...], 'backup': path|None}.
    The legacy file is renamed (not deleted) ONLY after every key verifies.
    Recovery: rename the .migrated-* file back to api_keys.json.
    """
    result = {"migrated": [], "failed": [], "backup": None}
    lp = legacy_path()
    if not lp.exists():
        return result
    try:
        data = json.loads(lp.read_text(encoding="utf-8"))
    except Exception as e:
        result["failed"].append(f"legacy file unreadable: {e}")
        return result

    pending = [(k, str(data[k])) for k in MANAGED_KEYS
               if data.get(k) and str(data[k]).strip()]
    if not pending:
        return result

    ok_all = True
    for key, value in pending:
        if _backend.set(key, value) and _backend.get(key) == value:
            result["migrated"].append(key)
        else:
            result["failed"].append(key)
            ok_all = False

    if ok_all and result["migrated"]:
        backup = lp.with_name(
            f"api_keys.json.migrated-{int(time.time())}")
        try:
            lp.rename(backup)
            result["backup"] = str(backup)
        except Exception as e:
            result["failed"].append(f"rename failed: {e}")
    return result


def needs_migration() -> bool:
    """True when the legacy file exists with managed keys not yet in the
    OS store."""
    lp = legacy_path()
    if not lp.exists():
        return False
    try:
        data = json.loads(lp.read_text(encoding="utf-8"))
    except Exception:
        return False
    for k in MANAGED_KEYS:
        if data.get(k) and not get_secret(k):
            return True
    return False
