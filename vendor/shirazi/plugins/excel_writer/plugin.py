"""Excel writer plugin — build a real .xlsx from a structured description.

How it works: YOU (the model, already talking to the user) turn their spoken
request into the structured arguments below — title, headers, rows, totals,
chart — and this builds a genuine .xlsx on the Desktop with openpyxl: bold
headers, typed cells, an optional SUM total row, an optional chart.

This differs deliberately from the Mark-LV original this was adapted from:
that version made its own extra Gemini call with a hardcoded model ID to turn
the request into a spec. That costs a second request, needs the API key inside
the plugin, and breaks whenever the model ID is retired (it was). Here the
conversation's own model fills the spec directly — no key, no extra call, no
stale model ID. Same pattern as the quiz plugin.

Permissions used: files:write (creating the .xlsx). Needs openpyxl —
`pip install openpyxl` (also listed in requirements-plugins.txt).
"""

import os
import re
from datetime import datetime
from pathlib import Path

_MAX_ROWS = 200
_MAX_COLS = 26
_MAX_CELL = 500


def _output_dir() -> Path:
    # SHIRAZI_EXCEL_DIR is set by the Shirazi LV wrapper from the plugin's
    # "save_folder" setting (empty = default Desktop behavior).
    custom = os.environ.get("SHIRAZI_EXCEL_DIR", "").strip()
    if custom:
        d = Path(custom).expanduser()
        if d.is_dir():
            return d
    desktop = Path.home() / "Desktop"
    return desktop if desktop.is_dir() else Path.home()


def _safe_name(name) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "", str(name or "").strip()) or "spreadsheet"
    return name[:60]


def _clean_rows(headers, rows):
    """Trim/pad rows to the header width; cap sizes; clip wild cells."""
    ncols = max(1, min(len(headers), _MAX_COLS))
    headers = [str(h)[:_MAX_CELL] for h in headers[:ncols]]
    clean = []
    for row in (rows or [])[:_MAX_ROWS]:
        if not isinstance(row, list):
            row = [row]
        cells = []
        for c in range(ncols):
            v = row[c] if c < len(row) else None
            if isinstance(v, bool):
                pass  # keep booleans as-is (not 1/0)
            elif isinstance(v, (int, float)):
                pass  # numbers stay numbers — Excel can sum them
            elif v is None:
                pass
            else:
                v = str(v)[:_MAX_CELL]
            cells.append(v)
        clean.append(cells)
    return headers, clean


def _build_xlsx(spec: dict, path: Path) -> dict:
    """Writes the workbook. Returns a small summary dict. Raises on hard errors."""
    from openpyxl import Workbook
    from openpyxl.chart import BarChart, LineChart, PieChart, Reference
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    headers, rows = _clean_rows(spec.get("headers") or [],
                                spec.get("rows") or [])
    if not headers and rows:
        headers = [f"Column {i + 1}" for i in range(len(rows[0]))]
        headers, rows = _clean_rows(headers, rows)
    ncols = len(headers)

    wb = Workbook()
    ws = wb.active
    ws.title = str(spec.get("title") or "Sheet1")[:31]

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="1F4E78")
    for c, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    r = 2
    for row in rows:
        for c in range(ncols):
            ws.cell(row=r, column=c + 1, value=row[c])
        r += 1
    last_data_row = r - 1

    total_cols = [i for i in (spec.get("total_columns") or [])
                  if isinstance(i, int) and 0 <= i < ncols]
    # Only total columns that actually hold numbers — SUM over text is noise.
    if total_cols and last_data_row >= 2:
        numeric = [i for i in total_cols
                   if any(isinstance(row[i], (int, float))
                           and not isinstance(row[i], bool)
                           for row in rows)]
        if numeric:
            ws.cell(row=r, column=1, value="TOTAL").font = Font(bold=True)
            for i in numeric:
                col = get_column_letter(i + 1)
                cell = ws.cell(row=r, column=i + 1,
                               value=f"=SUM({col}2:{col}{last_data_row})")
                cell.font = Font(bold=True)
            total_done = True
            r += 1
        else:
            total_done = False
    else:
        total_done = False

    for c in range(1, ncols + 1):
        col = get_column_letter(c)
        width = max([len(str(ws.cell(row=rr, column=c).value or ""))
                     for rr in range(1, last_data_row + 1)] + [8]) + 2
        ws.column_dimensions[col].width = min(40, width)

    chart_added = False
    chart = spec.get("chart")
    if isinstance(chart, dict) and last_data_row >= 2:
        try:
            ctype = str(chart.get("type", "bar")).lower()
            cat_col = int(chart.get("category_col", 0))
            val_col = int(chart.get("value_col", 1))
            if 0 <= cat_col < ncols and 0 <= val_col < ncols \
                    and cat_col != val_col:
                ch = {"line": LineChart, "pie": PieChart}.get(ctype,
                                                             BarChart)()
                ch.title = str(chart.get("title") or ws.title)[:100]
                data_ref = Reference(ws, min_col=val_col + 1, min_row=1,
                                     max_row=last_data_row)
                cats_ref = Reference(ws, min_col=cat_col + 1, min_row=2,
                                     max_row=last_data_row)
                ch.add_data(data_ref, titles_from_data=True)
                ch.set_categories(cats_ref)
                ws.add_chart(ch, f"{get_column_letter(ncols + 2)}2")
                chart_added = True
        except Exception:
            chart_added = False

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return {"rows": last_data_row - 1, "cols": ncols,
            "total": total_done, "chart": chart_added}


def run_create(args):
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        return ("I need the openpyxl library to build Excel files — "
                "pip install openpyxl (it's in shirazi-core/"
                "requirements-plugins.txt).")

    headers = args.get("headers") or []
    rows = args.get("rows") or []
    if not headers and not rows:
        return ("I need the table itself — pass headers and rows. Turn the "
                "user's request into columns and data first.")

    fname = _safe_name(args.get("filename") or args.get("title"))
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = _output_dir() / f"{fname}_{stamp}.xlsx"

    try:
        info = _build_xlsx(
            {"title": args.get("title"),
             "headers": headers,
             "rows": rows,
             "total_columns": args.get("total_columns") or [],
             "chart": args.get("chart")},
            path)
    except Exception as e:
        return f"I couldn't write the spreadsheet file: {e}"

    bits = [f"{info['rows']} rows × {info['cols']} columns"]
    if info["total"]:
        bits.append("a SUM total row")
    if info["chart"]:
        bits.append("a chart")
    return (f"Created {path.name} ({', '.join(bits)}) — saved to {path}. "
            f"Tell the user the file name and where it is.")


TOOLS = [
    {"name": "excel_create",
     "description": (
         "Builds a REAL Excel .xlsx file from a spoken description and saves "
         "it to the Desktop. Use when the user wants an actual spreadsheet "
         "FILE — 'make me a table of my expenses', 'excel bana do', 'sales "
         "table with a chart' — never for just answering a question about "
         "numbers. YOU turn their request into the structured arguments: "
         "invent reasonable example data when they didn't give values, keep "
         "it under 200 rows. Say one short sentence first ('Banata hoon...') "
         "so they don't hear silence while you compose the table."),
     "kind": "native", "access": "write",
     "parameters": {
         "type": "object",
         "properties": {
             "title": {"type": "string",
                       "description": "Short sheet title, in the user's language."},
             "headers": {"type": "array", "items": {"type": "string"},
                         "description": "Column headers, in order."},
             "rows": {"type": "array",
                      "items": {"type": "array"},
                      "description": "Data rows; each an array of cell values "
                                     "(numbers as numbers, text as strings), "
                                     "matching the headers length."},
             "total_columns": {"type": "array", "items": {"type": "integer"},
                               "description": "0-based indices of numeric "
                                              "columns that get a SUM total "
                                              "row. [] or omit for none."},
             "chart": {"type": "object",
                       "description": "Optional: {\"type\": \"bar\"|\"line\"|"
                                      "\"pie\", \"category_col\": int, "
                                      "\"value_col\": int, \"title\": str}. "
                                      "Omit for no chart."},
             "filename": {"type": "string",
                          "description": "Optional file name without extension."},
         },
         "required": ["headers", "rows"]},
     "run": run_create},
]
