"""Knowledge Base Repair — audit a JSON knowledge base, preview fixes.

WHO REASONS: you do. kb_audit deterministically checks a JSON file
(a list of records, or {"entries": [...]}) for:

  - duplicate records by id field
  - records missing required fields
  - bad metadata (empty / non-string ids)
  - empty chunks (empty text field)

kb_fix_preview proposes the deterministic fixes for what the audit
found — it NEVER applies anything. Applying stays model-side, through
the normal file tools, with user approval.

Permissions used: [files:read] — it only reads the audited file.
"""

from __future__ import annotations

import json
import os

_MAX_FILE_BYTES = 100 * 1024 * 1024
_MAX_EXAMPLES = 5

_FIX_OPS = ("drop_duplicates", "drop_empty_chunks", "drop_missing_id")


def _load_records(path):
    if not path or not os.path.isfile(path):
        return None, f"Not a file: {path}"
    try:
        size = os.path.getsize(path)
    except OSError as e:
        return None, f"Cannot stat file: {e}"
    if size > _MAX_FILE_BYTES:
        return None, (f"File is {size // (1024*1024)} MB — over the "
                      f"{_MAX_FILE_BYTES // (1024*1024)} MB audit cap. "
                      f"Split it first.")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as e:
        return None, f"Cannot read/parse JSON: {e}"
    if isinstance(data, dict):
        for key in ("entries", "items", "records", "data"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        return None, ("Top level must be a JSON list of records (or an "
                      "object holding one under entries/items/records).")
    return data, None


def _audit(records, id_field, required_fields, text_field):
    seen, duplicates = {}, []
    missing, bad_ids, empty_chunks = [], [], []
    non_records = 0
    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            non_records += 1
            continue
        rid = rec.get(id_field)
        if isinstance(rid, str) and rid.strip():
            rid = rid.strip()
            if rid in seen:
                duplicates.append(rid)
            else:
                seen[rid] = i
        else:
            bad_ids.append(i)
        absent = [f for f in required_fields if rec.get(f) in (None, "")]
        if absent:
            missing.append((i, rid if isinstance(rid, str) else f"#{i}",
                            absent))
        if text_field and not str(rec.get(text_field) or "").strip():
            empty_chunks.append(rid if isinstance(rid, str) else f"#{i}")
    return {
        "total": len(records),
        "non_records": non_records,
        "unique_ids": len(seen),
        "duplicates": sorted(set(duplicates)),
        "missing_fields": missing,
        "bad_ids": bad_ids,
        "empty_chunks": empty_chunks,
    }


def _fmt_audit(rep, id_field):
    L = [f"KB audit — {rep['total']} records checked (id field: "
         f"'{id_field}')", ""]
    L.append(f"Unique ids: {rep['unique_ids']}")
    dups = rep["duplicates"]
    L.append(f"Duplicate ids: {len(dups)}"
             + (f" — e.g. {dups[:_MAX_EXAMPLES]}" if dups else ""))
    miss = rep["missing_fields"]
    L.append(f"Records missing required fields: {len(miss)}")
    for i, rid, fields in miss[:_MAX_EXAMPLES]:
        L.append(f"  - record #{i} (id={rid}): missing {fields}")
    L.append(f"Bad ids (empty/non-string): {len(rep['bad_ids'])}"
             + (f" — record indexes {rep['bad_ids'][:_MAX_EXAMPLES]}"
                if rep["bad_ids"] else ""))
    L.append(f"Empty chunks: {len(rep['empty_chunks'])}"
             + (f" — e.g. {rep['empty_chunks'][:_MAX_EXAMPLES]}"
                if rep["empty_chunks"] else ""))
    if rep["non_records"]:
        L.append(f"Non-record entries (not objects): {rep['non_records']}")
    problems = (len(dups) + len(miss) + len(rep["bad_ids"])
                + len(rep["empty_chunks"]) + rep["non_records"])
    L += ["",
          "Verdict: " + ("CLEAN — no issues found."
                         if problems == 0
                         else f"{problems} issue(s) found. Run "
                              f"kb_fix_preview to see the deterministic "
                              f"fix plan (nothing is applied silently).")]
    return "\n".join(L)


def run_audit(args):
    path = str(args.get("path") or "").strip()
    if not path:
        return ("Pass `path` to the JSON knowledge-base file, e.g. "
                "~/workspace/your_files/MajlisAlFatih-Quiz-Database.json. "
                "Optional: id_field (default 'id'), required_fields "
                "(default ['id']), text_field (checked for emptiness).")
    id_field = str(args.get("id_field") or "id").strip() or "id"
    required = args.get("required_fields")
    if required is None:
        required = [id_field]
    required = [str(f).strip() for f in required if str(f).strip()]
    text_field = str(args.get("text_field") or "").strip()
    records, err = _load_records(path)
    if err:
        return err
    return _fmt_audit(_audit(records, id_field, required, text_field),
                      id_field)


def run_fix_preview(args):
    path = str(args.get("path") or "").strip()
    if not path:
        return "Pass `path` (same file you audited) and `fixes` to preview."
    fixes = args.get("fixes") or ["drop_duplicates"]
    fixes = [str(f).strip() for f in fixes if str(f).strip()]
    unknown = [f for f in fixes if f not in _FIX_OPS]
    if unknown:
        return (f"Unknown fix ops: {unknown}. Supported: "
                f"{', '.join(_FIX_OPS)}.")
    id_field = str(args.get("id_field") or "id").strip() or "id"
    required = args.get("required_fields")
    if required is None:
        required = [id_field]
    required = [str(f).strip() for f in required if str(f).strip()]
    text_field = str(args.get("text_field") or "").strip()
    records, err = _load_records(path)
    if err:
        return err
    rep = _audit(records, id_field, required, text_field)
    plan, n = [], 0
    if "drop_duplicates" in fixes and rep["duplicates"]:
        plan.append(f"drop_duplicates: remove {len(rep['duplicates'])} "
                    f"duplicate record(s), keep the first occurrence "
                    f"(e.g. {rep['duplicates'][:_MAX_EXAMPLES]})")
        n += len(rep["duplicates"])
    if "drop_empty_chunks" in fixes and rep["empty_chunks"] and text_field:
        plan.append(f"drop_empty_chunks: remove "
                    f"{len(rep['empty_chunks'])} record(s) with empty "
                    f"'{text_field}'")
        n += len(rep["empty_chunks"])
    if "drop_missing_id" in fixes and rep["bad_ids"]:
        plan.append(f"drop_missing_id: remove {len(rep['bad_ids'])} "
                    f"record(s) with empty/non-string id")
        n += len(rep["bad_ids"])
    L = ["KB fix preview — NOTHING HAS BEEN CHANGED.", ""]
    if plan:
        L.append(f"Proposed operations ({len(fixes)} requested):")
        for p in plan:
            L.append(f"  - {p}")
        L += ["",
              f"Total records that would be removed: {n} of "
              f"{rep['total']} ({rep['total'] - n} would remain).",
              "Duplicates keep their FIRST occurrence; order of the rest "
              "is unchanged."]
    else:
        L.append("The requested fixes match no issues in this file — "
                 "nothing to do.")
    L += ["",
          "To apply: YOU rewrite the file with the normal file tools, "
          "after user approval. This plugin never writes; it only "
          "audits and previews."]
    return "\n".join(L)


TOOLS = [
    {"name": "kb_audit",
     "description": (
         "Audit a JSON knowledge base for duplicates (by id field), "
         "records missing required fields, bad ids, and empty chunks. "
         "Pass `path` to the JSON file (list of records, or an object "
         "holding one under entries/items/records), plus optional "
         "id_field, required_fields, text_field. Read-only; capped at "
         "100 MB. Use for RAG datasets, quiz databases, any JSON "
         "record list."),
     "kind": "native", "access": "read",
     "parameters": {
         "type": "object",
         "properties": {
             "path": {"type": "string",
                      "description": "Path to the JSON file."},
             "id_field": {"type": "string", "default": "id"},
             "required_fields": {"type": "array",
                                 "items": {"type": "string"},
                                 "description": "Default: [id_field]."},
             "text_field": {"type": "string",
                            "description": "Field checked for empty "
                                           "chunks."}},
         "required": ["path"]},
     "run": run_audit},
    {"name": "kb_fix_preview",
     "description": (
         "Preview deterministic fixes for kb_audit findings WITHOUT "
         "applying them: drop_duplicates (keep first), drop_empty_chunks, "
         "drop_missing_id. Returns exactly what would change and what "
         "would remain. Applying stays with you via the file tools + user "
         "approval — this never writes."),
     "kind": "native", "access": "read",
     "parameters": {
         "type": "object",
         "properties": {
             "path": {"type": "string"},
             "fixes": {"type": "array", "items": {"type": "string"},
                       "description": "Subset of drop_duplicates, "
                                      "drop_empty_chunks, drop_missing_id."},
             "id_field": {"type": "string", "default": "id"},
             "required_fields": {"type": "array",
                                 "items": {"type": "string"}},
             "text_field": {"type": "string"}},
         "required": ["path"]},
     "run": run_fix_preview},
]
