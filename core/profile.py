"""
Structured, versioned user profile — Personal Companion upgrade (Phase 3).

The profile is the application's long-term memory of WHO the user is and
HOW they want to be treated. It is:

- versioned (`profile_schema_version`) so future app versions can migrate it,
- stored at ~/.shirazi/profile.json, separate from API credentials
  (config/api_keys.json) and from conversation memory,
- never transmitted wholesale to any provider — only the fields relevant
  to a request are included in model context (see core/instructions.py).

Fields (stable internal identifiers — never translated UI labels):
  actual_name, preferred_name, preferred_form_of_address, assistant_name,
  conversation_language, written_language, spoken_language, interface_language,
  preferred_voice, speech_rate, communication_style[], response_length_preference,
  persistent_instructions[], user_defined_boundaries[], memory_preferences{},
  onboarding_completed, onboarding_step, profile_schema_version,
  created_at, updated_at.

Privacy rules (enforced here, not by convention):
- actual_name is NEVER used as the address form; only preferred_name /
  preferred_form_of_address address the user.
- actual_name is never placed in model context unless the user explicitly
  asks for it (consent-gated).
"""
from __future__ import annotations

import copy
import json
import time
from pathlib import Path

SCHEMA_VERSION = 1

_LANGUAGES = ("english", "urdu", "roman_urdu", "arabic")
_STYLES = ("friendly", "professional", "detailed", "scholarly", "technical", "custom")
_LENGTHS = ("short", "balanced", "detailed", "adaptive")


def _data_dir() -> Path:
    d = Path.home() / ".shirazi"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _profile_path() -> Path:
    return _data_dir() / "profile.json"


def default_profile() -> dict:
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    return {
        "actual_name": "",
        "preferred_name": "",
        "preferred_form_of_address": "",
        "assistant_name": "Shirazi",
        "conversation_language": "english",
        "written_language": "english",
        "spoken_language": "english",
        "interface_language": "english",
        "preferred_voice": "",
        "speech_rate": 1.0,
        "communication_style": ["friendly"],
        "response_length_preference": "balanced",
        "persistent_instructions": [],
        "user_defined_boundaries": [],
        "memory_preferences": {
            "personal_preferences": True,
            "projects": True,
            "work_tasks": True,
            "frequent_instructions": True,
            "technical_environment": True,
            "long_term_goals": True,
            "auto_create": True,
        },
        "onboarding_completed": False,
        "onboarding_step": 0,
        "profile_schema_version": SCHEMA_VERSION,
        "created_at": now,
        "updated_at": now,
    }


def _migrate_legacy(data: dict) -> dict:
    """Pull the pre-profile fields out of config/api_keys.json.

    Old keys: user_name -> preferred_name, assistant_name -> assistant_name.
    Never invents actual_name; never touches secrets.
    """
    try:
        from pathlib import Path as _P
        import sys as _s
        legacy = _P(__file__).resolve().parent.parent / "config" / "api_keys.json"
        if not legacy.exists():
            return data
        old = json.loads(legacy.read_text(encoding="utf-8"))
    except Exception:
        return data
    changed = False
    if not data.get("preferred_name") and old.get("user_name"):
        data["preferred_name"] = str(old["user_name"]).strip()[:80]
        changed = True
    if old.get("assistant_name") and data.get("assistant_name") == "Shirazi":
        data["assistant_name"] = str(old["assistant_name"]).strip()[:40] or "Shirazi"
        changed = True
    if changed:
        data["_migrated_from_legacy"] = True
    return data


def load_profile() -> dict:
    """Load the profile, migrating legacy fields on first read. Never raises."""
    p = _profile_path()
    data = None
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            data = None
    if not isinstance(data, dict):
        data = default_profile()
        data = _migrate_legacy(data)
        save_profile(data)
        return data
    # Fill in any fields a newer schema expects; never drop unknown ones.
    base = default_profile()
    for k, v in base.items():
        if k not in data:
            data[k] = v
    if data.get("profile_schema_version") != SCHEMA_VERSION:
        data = _migrate_schema(data)
    return data


def _migrate_schema(data: dict) -> dict:
    data["profile_schema_version"] = SCHEMA_VERSION
    data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    return data


def save_profile(data: dict) -> bool:
    """Atomic write (temp file + rename). Returns True on success."""
    try:
        data = copy.deepcopy(data)
        data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        data["profile_schema_version"] = SCHEMA_VERSION
        p = _profile_path()
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                       encoding="utf-8")
        tmp.replace(p)
        return True
    except Exception:
        return False


def get_field(name: str, default=None):
    return load_profile().get(name, default)


def set_field(name: str, value) -> bool:
    """Set one field with validation. Returns True on success."""
    data = load_profile()
    value = _validate_field(name, value)
    if value is _INVALID:
        return False
    data[name] = value
    return save_profile(data)


_INVALID = object()


def _validate_field(name: str, value):
    if name in ("actual_name", "preferred_name", "preferred_form_of_address"):
        v = str(value or "").strip()
        return v[:80]
    if name == "assistant_name":
        v = str(value or "").strip()
        return v[:40] or "Shirazi"
    if name in ("conversation_language", "written_language",
                "spoken_language", "interface_language"):
        v = str(value or "").lower().strip()
        return v if v in _LANGUAGES else _INVALID
    if name == "preferred_voice":
        return str(value or "").strip()[:80]
    if name == "speech_rate":
        try:
            f = float(value)
            return min(2.0, max(0.5, f))
        except (TypeError, ValueError):
            return _INVALID
    if name == "communication_style":
        items = [str(x).lower().strip() for x in (value or []) if str(x).strip()]
        items = [x for x in items if x in _STYLES]
        return items or ["friendly"]
    if name == "response_length_preference":
        v = str(value or "").lower().strip()
        return v if v in _LENGTHS else _INVALID
    if name in ("persistent_instructions", "user_defined_boundaries"):
        items = [str(x).strip() for x in (value or []) if str(x).strip()]
        return items[:50]
    if name == "memory_preferences":
        base = default_profile()["memory_preferences"]
        if isinstance(value, dict):
            for k in base:
                if k in value:
                    base[k] = bool(value[k])
        return base
    if name in ("onboarding_completed",):
        return bool(value)
    if name == "onboarding_step":
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return _INVALID
    # Unknown fields are stored as-is (forward compatibility).
    return value


def update_profile(updates: dict) -> tuple[bool, list[str]]:
    """Set several fields at once. Returns (ok, [rejected field names])."""
    data = load_profile()
    rejected = []
    for k, v in updates.items():
        vv = _validate_field(k, v)
        if vv is _INVALID:
            rejected.append(k)
        else:
            data[k] = vv
    ok = save_profile(data)
    return ok, rejected


def address_form() -> str:
    """How Shirazi should address the user. Never the actual_name."""
    data = load_profile()
    if data.get("preferred_form_of_address"):
        return data["preferred_form_of_address"]
    if data.get("preferred_name"):
        return data["preferred_name"]
    return ""


def profile_summary() -> dict:
    """Non-sensitive summary for UI display (actual_name included — it is
    the user's own screen)."""
    data = load_profile()
    return {
        "preferred_name": data.get("preferred_name", ""),
        "assistant_name": data.get("assistant_name", "Shirazi"),
        "languages": {
            "conversation": data.get("conversation_language"),
            "written": data.get("written_language"),
            "spoken": data.get("spoken_language"),
            "interface": data.get("interface_language"),
        },
        "style": data.get("communication_style"),
        "length": data.get("response_length_preference"),
        "rules": len(data.get("persistent_instructions", [])),
        "boundaries": len(data.get("user_defined_boundaries", [])),
        "onboarding_completed": data.get("onboarding_completed", False),
    }


def delete_profile() -> bool:
    """Delete the profile file entirely (user-requested)."""
    try:
        _profile_path().unlink(missing_ok=True)
        return True
    except Exception:
        return False
