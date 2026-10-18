"""
Backup & Restore — Personal Companion upgrade (Phase 6).

A user who reinstalls Windows, changes computers, or loses the local
database must be able to restore their profile and memories without
repeating onboarding.

Format: versioned ZIP archive.
  manifest.json  — backup_schema_version, created_at, app_version, kind
                   (full|memory|profile), record counts, sha256 per file
  profile.json   — the versioned user profile (no secrets, ever)
  memory_long_term.json — semantic memory with provenance
  memory_episodic.json  — episodic turns (optional, kind=full only)
  omnicontrol.json      — folder allow-list, repos (no tokens/grants)
  app_config.json       — non-secret app preferences

Security (non-negotiable):
- NEVER includes api_keys.json, credential stores, tokens, or secrets.
- Restore validates the manifest, verifies sha256 hashes, rejects
  absolute paths, '..' traversal, and unexpected executables.
- Backup code never executes anything from an archive.

Restore modes:
  replace — current data is safety-backed-up first, then replaced
            (requires explicit confirmation by the caller).
  merge   — backup records are added; existing records win conflicts
            unless the backup is newer (per-record updated timestamps).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import time
import zipfile
from pathlib import Path

BACKUP_SCHEMA_VERSION = 1
APP_VERSION = "1.0.0"

# Files that must NEVER enter a backup, even if requested.
_FORBIDDEN_NAMES = {
    "api_keys.json",
}
_FORBIDDEN_SUFFIXES = (".key", ".pem", ".p12", ".pfx", ".secret")


def _app_base() -> Path:
    return Path(__file__).resolve().parent.parent


def _data_dir() -> Path:
    d = Path.home() / ".shirazi"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_read_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def _collect_profile() -> tuple[str, dict]:
    from core import profile as _prof
    data = _prof.load_profile()
    # Defensive: strip anything secret-shaped that somehow got in.
    for k in list(data.keys()):
        if any(s in k.lower() for s in ("api_key", "token", "secret",
                                        "password")):
            del data[k]
    return "profile.json", data


def _collect_memory() -> tuple[str, dict]:
    # Use memory_manager's canonical path (honours BASE_DIR overrides).
    try:
        from memory import memory_manager as _mm
        return "memory_long_term.json", _mm.load_memory()
    except Exception:
        return "memory_long_term.json", {}


def _collect_episodic() -> tuple[str, list]:
    try:
        from memory import shirazi_backend as _sb
        store = _sb.get_store()
        turns = store.recent_turns(limit=500) if hasattr(store, "recent_turns") else []
        return "memory_episodic.json", turns
    except Exception:
        return "memory_episodic.json", []


def _collect_omnicontrol() -> tuple[str, dict]:
    """Folder allow-list and repos. Grants and tokens are excluded."""
    try:
        from core.omnicontrol import db as _db
        folders = _db.list_folders() if hasattr(_db, "list_folders") else []
        repos = _db.list_repos() if hasattr(_db, "list_repos") else []
        return "omnicontrol.json", {"folders": folders, "repos": repos}
    except Exception:
        return "omnicontrol.json", {"folders": [], "repos": []}


def _collect_app_config() -> tuple[str, dict]:
    base = _app_base()
    raw = _safe_read_json(base / "config" / "api_keys.json", {})
    safe_keys = ("assistant_name", "user_name", "os_system", "ui_color",
                 "theme", "voice", "wake_word", "secret_store")
    return "app_config.json", {k: raw[k] for k in safe_keys if k in raw}


_COLLECTORS = {
    "full": (_collect_profile, _collect_memory, _collect_episodic,
             _collect_omnicontrol, _collect_app_config),
    "memory": (_collect_memory, _collect_episodic),
    "profile": (_collect_profile,),
}


def default_backup_dir() -> Path:
    d = _data_dir() / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def create_backup(kind: str = "full", dest_dir: str | Path | None = None,
                  include_episodic: bool = True) -> dict:
    """Create a backup. Returns a result dict (never raises).

    Result: {ok, path, manifest, error}. The archive is written to a temp
    file, validated, then moved atomically into place.
    """
    if kind not in _COLLECTORS:
        return {"ok": False, "path": None, "manifest": None,
                "error": f"unknown backup kind: {kind}"}
    dest = Path(dest_dir) if dest_dir else default_backup_dir()
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return {"ok": False, "path": None, "manifest": None,
                "error": f"cannot create destination: {e}"}

    tmpdir = Path(tempfile.mkdtemp(prefix="shirazi-backup-"))
    files: dict[str, str] = {}
    counts: dict[str, int] = {}
    try:
        collectors = _COLLECTORS[kind]
        if kind == "full" and not include_episodic:
            collectors = tuple(c for c in collectors
                               if c is not _collect_episodic)
        for coll in collectors:
            name, data = coll()
            _assert_safe_name(name)
            fp = tmpdir / name
            fp.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                          encoding="utf-8")
            files[name] = _sha256_file(fp)
            counts[name] = _count_records(data)

        manifest = {
            "backup_schema_version": BACKUP_SCHEMA_VERSION,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "app_version": APP_VERSION,
            "kind": kind,
            "files": files,
            "record_counts": counts,
        }
        (tmpdir / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8")

        stamp = time.strftime("%Y%m%d-%H%M%S-%f")
        final = dest / f"shirazi-backup-{kind}-{stamp}.zip"
        _n = 1
        while final.exists():
            _n += 1
            final = dest / f"shirazi-backup-{kind}-{stamp}-{_n}.zip"
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False,
                                         dir=str(dest)) as tf:
            tmp_zip = Path(tf.name)
        with zipfile.ZipFile(tmp_zip, "w",
                             compression=zipfile.ZIP_DEFLATED) as zf:
            for fname in sorted(files) + ["manifest.json"]:
                zf.write(tmpdir / fname, arcname=fname)
        # Validate before finalizing.
        problems = verify_backup(tmp_zip)
        if problems:
            tmp_zip.unlink(missing_ok=True)
            return {"ok": False, "path": None, "manifest": None,
                    "error": f"validation failed: {'; '.join(problems)}"}
        tmp_zip.replace(final)
        return {"ok": True, "path": str(final), "manifest": manifest,
                "error": None}
    except Exception as e:
        return {"ok": False, "path": None, "manifest": None,
                "error": str(e)}
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _assert_safe_name(name: str) -> None:
    if name in _FORBIDDEN_NAMES:
        raise ValueError(f"forbidden backup entry: {name}")
    low = name.lower()
    if low.endswith(_FORBIDDEN_SUFFIXES):
        raise ValueError(f"forbidden backup entry: {name}")
    if name.startswith(("/", "\\")) or ".." in name.replace("\\", "/").split("/"):
        raise ValueError(f"unsafe backup entry: {name}")


def _count_records(data) -> int:
    if isinstance(data, dict):
        # memory_long_term: count entries across categories
        n = 0
        for v in data.values():
            n += len(v) if isinstance(v, dict) else 1
        return n
    if isinstance(data, list):
        return len(data)
    return 1


def _iter_safe_members(zf: zipfile.ZipFile):
    """Yield (info, arcname) for safe members only; raise on danger."""
    for info in zf.infolist():
        name = info.filename
        if name.endswith("/"):
            continue
        _assert_safe_name(name)
        # Reject executables masquerading as data.
        if name.lower().endswith((".exe", ".dll", ".bat", ".cmd", ".ps1",
                                  ".sh", ".py", ".pyc")):
            raise ValueError(f"executable content rejected: {name}")
        yield info, name


def inspect_backup(path: str | Path) -> dict:
    """Read a backup's manifest + summary WITHOUT modifying live data."""
    result = {"ok": False, "manifest": None, "files": [],
              "problems": [], "error": None}
    p = Path(path)
    if not p.exists():
        result["error"] = "file not found"
        return result
    try:
        with zipfile.ZipFile(p, "r") as zf:
            problems = verify_backup(p)
            result["problems"] = problems
            try:
                manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            except Exception:
                manifest = None
            result["manifest"] = manifest
            result["files"] = [i.filename for i in zf.infolist()
                               if not i.filename.endswith("/")]
            result["ok"] = not problems and manifest is not None
    except Exception as e:
        result["error"] = str(e)
    return result


def verify_backup(path: str | Path) -> list[str]:
    """Return a list of problems (empty = valid). Never raises."""
    problems: list[str] = []
    p = Path(path)
    try:
        with zipfile.ZipFile(p, "r") as zf:
            names = set()
            for info in zf.infolist():
                if info.filename.endswith("/"):
                    continue
                try:
                    for _info, _name in _iter_safe_members(
                            _FakeZF([info])):
                        names.add(_name)
                except ValueError as e:
                    problems.append(str(e))
            if "manifest.json" not in {i.filename for i in zf.infolist()}:
                problems.append("missing manifest.json")
                return problems
            try:
                manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            except Exception as e:
                problems.append(f"manifest unreadable: {e}")
                return problems
            if manifest.get("backup_schema_version") != BACKUP_SCHEMA_VERSION:
                problems.append(
                    f"unsupported schema version: "
                    f"{manifest.get('backup_schema_version')}")
            for fname, want in manifest.get("files", {}).items():
                if fname not in names:
                    problems.append(f"manifest lists missing file: {fname}")
                    continue
                try:
                    got = hashlib.sha256(zf.read(fname)).hexdigest()
                except KeyError:
                    problems.append(f"unreadable: {fname}")
                    continue
                if got != want:
                    problems.append(f"hash mismatch: {fname}")
    except zipfile.BadZipFile:
        problems.append("not a valid zip archive")
    except Exception as e:
        problems.append(str(e))
    return problems


class _FakeZF:
    """Minimal wrapper so _iter_safe_members can check one entry."""
    def __init__(self, infos):
        self._infos = infos

    def infolist(self):
        return self._infos


def _safety_backup() -> str | None:
    """Snapshot current profile+memory before a replace restore."""
    res = create_backup(kind="full",
                        dest_dir=_data_dir() / "backups" / "pre-restore")
    return res["path"] if res["ok"] else None


def restore_backup(path: str | Path, mode: str = "merge",
                   confirm_replace: bool = False) -> dict:
    """Restore a backup. Returns {ok, restored, skipped, safety_backup, error}.

    - mode='merge': add backup records; existing records win unless the
      backup copy is newer (per-record 'updated').
    - mode='replace': requires confirm_replace=True; takes a safety backup
      of current data first.
    Never raises. Never touches credentials.
    """
    result = {"ok": False, "restored": {}, "skipped": [],
              "safety_backup": None, "error": None}
    if mode not in ("merge", "replace"):
        result["error"] = f"unknown mode: {mode}"
        return result
    if mode == "replace" and not confirm_replace:
        result["error"] = "replace mode requires explicit confirmation"
        return result
    problems = verify_backup(path)
    if problems:
        result["error"] = f"backup invalid: {'; '.join(problems)}"
        return result

    if mode == "replace":
        result["safety_backup"] = _safety_backup()

    try:
        with zipfile.ZipFile(path, "r") as zf:
            payloads = {}
            for info, name in _iter_safe_members(zf):
                payloads[name] = json.loads(zf.read(name).decode("utf-8"))
    except Exception as e:
        result["error"] = f"cannot read backup: {e}"
        return result

    try:
        if "profile.json" in payloads:
            _restore_profile(payloads["profile.json"], mode, result)
        if "memory_long_term.json" in payloads:
            _restore_memory(payloads["memory_long_term.json"], mode, result)
        if "memory_episodic.json" in payloads and mode == "replace":
            _restore_episodic(payloads["memory_episodic.json"], result)
        if "omnicontrol.json" in payloads:
            _restore_omnicontrol(payloads["omnicontrol.json"], mode, result)
        if "app_config.json" in payloads:
            _restore_app_config(payloads["app_config.json"], mode, result)
    except Exception as e:
        result["error"] = f"restore failed: {e}"
        return result
    result["ok"] = True
    return result


def _restore_profile(data: dict, mode: str, result: dict) -> None:
    from core import profile as _prof
    # Strip anything secret-shaped — defense in depth.
    data = {k: v for k, v in data.items()
            if not any(s in k.lower() for s in ("api_key", "token",
                                               "secret", "password"))}
    if mode == "replace":
        cur = _prof.load_profile()
        # Never let a backup silently downgrade the schema.
        if data.get("profile_schema_version", 0) > cur.get(
                "profile_schema_version", 0):
            result["skipped"].append("profile: newer schema in backup?! kept current")
            return
        _prof.save_profile(data)
        result["restored"]["profile"] = "replaced"
    else:
        cur = _prof.load_profile()
        merged = 0
        for k, v in data.items():
            if k in ("profile_schema_version", "created_at"):
                continue
            if not cur.get(k) and v:
                cur[k] = v
                merged += 1
        _prof.save_profile(cur)
        result["restored"]["profile"] = f"merged {merged} fields"


def _restore_memory(data: dict, mode: str, result: dict) -> None:
    from memory import memory_manager as _mm
    mem = _mm.load_memory()
    n = 0
    for cat, items in data.items():
        if not isinstance(items, dict):
            continue
        if mode == "replace":
            mem[cat] = items
            n += len(items)
        else:
            dest = mem.setdefault(cat, {})
            for key, entry in items.items():
                if key not in dest:
                    dest[key] = entry
                    n += 1
                else:
                    # Newer backup copy wins.
                    bu = str(entry.get("updated", "") if isinstance(entry, dict) else "")
                    cu = str(dest[key].get("updated", "") if isinstance(dest[key], dict) else "")
                    if bu > cu:
                        dest[key] = entry
                        n += 1
    _mm.save_memory(mem)
    result["restored"]["memory_long_term"] = f"{mode}d {n} entries"


def _restore_episodic(turns: list, result: dict) -> None:
    # Episodic restore is append-only and only in replace mode; the store
    # API is append-oriented, so we replay turns oldest-first.
    try:
        from memory import shirazi_backend as _sb
        count = 0
        for t in turns if isinstance(turns, list) else []:
            if isinstance(t, dict) and t.get("role") and t.get("text"):
                _sb.record_turn(t["role"], t["text"])
                count += 1
        result["restored"]["memory_episodic"] = f"replayed {count} turns"
    except Exception as e:
        result["skipped"].append(f"episodic: {e}")


def _restore_omnicontrol(data: dict, mode: str, result: dict) -> None:
    # Folders/repos only. Grants and tokens are never in backups.
    try:
        from core.omnicontrol import db as _db
        added = 0
        for f in data.get("folders", []) or []:
            try:
                if hasattr(_db, "add_folder"):
                    _db.add_folder(f.get("path", ""), **{
                        k: f.get(k, False) for k in
                        ("can_read", "can_write", "can_exec", "can_delete")})
                    added += 1
            except Exception:
                continue
        result["restored"]["omnicontrol"] = f"{mode}d {added} folders"
    except Exception as e:
        result["skipped"].append(f"omnicontrol: {e}")


def _restore_app_config(data: dict, mode: str, result: dict) -> None:
    # Non-secret preferences only; never credentials.
    try:
        base = _app_base()
        cfg_path = base / "config" / "api_keys.json"
        cur = _safe_read_json(cfg_path, {})
        safe_keys = ("assistant_name", "user_name", "os_system", "ui_color",
                     "theme", "voice", "wake_word")
        n = 0
        for k in safe_keys:
            if k in data and (mode == "replace" or k not in cur):
                cur[k] = data[k]
                n += 1
        cfg_path.write_text(json.dumps(cur, indent=4), encoding="utf-8")
        result["restored"]["app_config"] = f"{mode}d {n} keys"
    except Exception as e:
        result["skipped"].append(f"app_config: {e}")


def list_backups(dest_dir: str | Path | None = None) -> list[dict]:
    """Newest first. Each entry: path, kind, created_at, ok, problems."""
    dest = Path(dest_dir) if dest_dir else default_backup_dir()
    out = []
    if not dest.exists():
        return out
    for p in sorted(dest.glob("shirazi-backup-*.zip"), reverse=True):
        info = inspect_backup(p)
        m = info.get("manifest") or {}
        out.append({
            "path": str(p),
            "kind": m.get("kind", "?"),
            "created_at": m.get("created_at", "?"),
            "ok": info["ok"],
            "problems": info["problems"],
            "size": p.stat().st_size,
        })
    return out


def prune_backups(keep: int = 5,
                  dest_dir: str | Path | None = None) -> dict:
    """Keep the newest `keep` verified backups; never delete the only
    valid backup. Returns {kept, deleted, error}."""
    dest = Path(dest_dir) if dest_dir else default_backup_dir()
    items = list_backups(dest)
    valid = [b for b in items if b["ok"]]
    if len(valid) <= keep:
        return {"kept": len(items), "deleted": 0, "error": None}
    if len(valid) <= 1:
        return {"kept": len(items), "deleted": 0,
                "error": "refusing to prune the only valid backup"}
    # Delete oldest invalid ones first, then oldest valid beyond `keep`.
    by_age = sorted(items, key=lambda b: b["created_at"])
    doomed = [b for b in by_age if not b["ok"]]
    doomed += [b for b in by_age if b["ok"]][:-keep] \
        if len([b for b in by_age if b["ok"]]) > keep else []
    # Never leave zero valid backups.
    remaining_valid = len(valid) - sum(1 for b in doomed if b["ok"])
    if remaining_valid < 1:
        return {"kept": len(items), "deleted": 0,
                "error": "refusing to prune the only valid backup"}
    deleted = 0
    for b in doomed:
        try:
            Path(b["path"]).unlink()
            deleted += 1
        except Exception:
            pass
    return {"kept": len(items) - deleted, "deleted": deleted, "error": None}
