"""Reading and writing entries as CSV (spreadsheets: Excel, Google Sheets, Numbers).

Columns: text, meaning, example, categories (several categories separated by ";").
Files are UTF-8 with a byte-order mark, so Excel on Windows shows Chinese, Hindi, accents...
correctly. Cells that a spreadsheet would run as a formula (starting with = + - @) are
written with a leading apostrophe, which is removed again on import.
"""

import csv
import io
from dataclasses import dataclass, field

COLUMNS = ["text", "meaning", "example", "categories"]
MAX_ROWS = 2000
MAX_TEXT = 500

# Header names people commonly use, all mapped to our columns.
_ALIASES = {
    "text": ("text", "word", "words", "entry", "phrase", "term", "front", "question"),
    "meaning": ("meaning", "definition", "translation", "note", "notes", "back", "answer"),
    "example": ("example", "examples", "sentence", "usage"),
    "categories": ("categories", "category", "tags", "tag", "list", "deck"),
}
_FORMULA_START = ("=", "+", "-", "@")


def _safe_cell(value: str) -> str:
    return "'" + value if value.startswith(_FORMULA_START) else value


def _unsafe_cell(value: str) -> str:
    return value[1:] if value.startswith("'") and value[1:].startswith(_FORMULA_START) else value


def write_csv(rows: list[dict]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(COLUMNS)
    for row in rows:
        writer.writerow([_safe_cell(str(row.get(c, "") or "")) for c in COLUMNS])
    return "﻿" + out.getvalue()


@dataclass
class ParsedRow:
    line: int
    text: str
    meaning: str = ""
    example: str = ""
    categories: list[str] = field(default_factory=list)


@dataclass
class Parsed:
    rows: list[ParsedRow] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)


def _column_map(header: list[str]) -> dict[str, int] | None:
    """Which column holds what, from the header row; None if the first row isn't a header."""
    found = {}
    for i, name in enumerate(header):
        key = name.strip().lower()
        for col, aliases in _ALIASES.items():
            if key in aliases and col not in found:
                found[col] = i
    return found if "text" in found else None


def read_csv(content: str) -> Parsed:
    content = content.lstrip("﻿")
    try:
        dialect = csv.Sniffer().sniff(content[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel  # one column, or nothing to go on: plain commas
    lines = list(csv.reader(io.StringIO(content), dialect))

    result = Parsed()
    if not lines:
        return result
    columns = _column_map(lines[0])
    start = 1
    if columns is None:  # no header: text, meaning, example, categories in that order
        columns, start = {c: i for i, c in enumerate(COLUMNS)}, 0

    def cell(values: list[str], col: str) -> str:
        i = columns.get(col)
        return _unsafe_cell(values[i].strip()) if i is not None and i < len(values) else ""

    for number, values in enumerate(lines[start:], start=start + 1):
        if not any(v.strip() for v in values):
            continue  # blank line
        if len(result.rows) >= MAX_ROWS:
            result.errors.append({"line": number, "reason": f"only {MAX_ROWS} rows per file"})
            break
        text = cell(values, "text")
        if not text:
            result.errors.append({"line": number, "reason": "no text"})
            continue
        if len(text) > MAX_TEXT:
            result.errors.append({"line": number, "reason": f"text longer than {MAX_TEXT} characters"})
            continue
        cats = [c.strip()[:60] for c in cell(values, "categories").replace(",", ";").split(";")]
        result.rows.append(ParsedRow(
            line=number, text=text, meaning=cell(values, "meaning"), example=cell(values, "example"),
            categories=[c for c in dict.fromkeys(cats) if c],
        ))
    return result
