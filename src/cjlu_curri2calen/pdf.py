"""Parse the curriculum PDF into a list of :class:`Course` objects.

The PDF is an A4 grid: one column per weekday (星期一..星期日) and one row per
period (第1节..第12节).  Course cells are merged vertically across their period
range, so we group words by weekday column and then cluster them into cells by
their vertical gap.
"""

from __future__ import annotations

import re
from pathlib import Path

import pymupdf as fitz

from .model import Course

DAY_HEADERS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

_WEEK_TOKEN = re.compile(r"^(\d+)(?:-(\d+))?(单|双)?$")
_CAMPUS = re.compile(r"\(([东南西北])\)")

# Two lines of the same cell are ~7.5pt apart; a gap larger than this starts a
# new cell in the same column.
LINE_GAP_THRESHOLD = 15.0


def parse_pdf(path: str | Path) -> list[Course]:
    doc = fitz.open(str(path))
    try:
        page = doc[0]
        words = page.get_text("words")  # (x0, y0, x1, y1, word, block, line, word_no)
    finally:
        doc.close()

    # --- locate day headers to derive column boundaries --------------------
    header = {}
    for w in words:
        text = w[4]
        if text in DAY_HEADERS:
            header[text] = w
    if len(header) != len(DAY_HEADERS):
        raise ValueError(f"expected {len(DAY_HEADERS)} day headers, found {len(header)}")

    centers = [(header[d][0] + header[d][2]) / 2 for d in DAY_HEADERS]
    edges = [(centers[i] + centers[i + 1]) / 2 for i in range(len(centers) - 1)]
    half = (centers[1] - centers[0]) / 2
    left = centers[0] - half
    right = centers[-1] + half
    col_edges = [left] + edges + [right]

    header_y0 = min(header[d][1] for d in DAY_HEADERS)

    # --- collect content words, tagged with their weekday column -----------
    by_day: dict[int, list[tuple[float, float, float, str]]] = {}
    for w in words:
        x0, y0, x1, y1, text = w[0], w[1], w[2], w[3], w[4]
        if text in DAY_HEADERS or text == "节次名称":
            continue
        if re.fullmatch(r"第\d+节", text):
            continue
        if y0 <= header_y0 + 5:  # drop the title line above the header row
            continue
        cx = (x0 + x1) / 2
        day = _column(cx, col_edges)
        if day is None:
            continue
        by_day.setdefault(day, []).append((y0, x0, x1, text))

    # --- cluster words into visual lines, then lines into course cells -----
    courses: list[Course] = []
    for day, items in by_day.items():
        items.sort(key=lambda it: (it[0], it[1]))  # top-to-bottom, left-to-right
        lines = _group_lines(items)  # [(y0, text), ...] sorted by y0
        for cell in _cluster_cells(lines):
            course = _parse_cell(cell, day)
            if course is not None:
                courses.append(course)

    return courses


def _column(cx: float, edges: list[float]) -> int | None:
    for i in range(len(edges) - 1):
        if edges[i] <= cx < edges[i + 1]:
            return i + 1  # 1=Monday .. 7=Sunday
    return None


def _group_lines(items: list[tuple[float, float, float, str]]) -> list[tuple[float, str]]:
    """Merge words sharing a baseline into (y0, text) lines, sorted by y0."""
    # Each group is [y0, [(x0, text), ...]] — y0 is the shared baseline.
    groups: list[list] = []
    for y0, x0, x1, text in items:
        for group in groups:
            if abs(group[0] - y0) <= 3.0:
                group[1].append((x0, text))
                break
        else:
            groups.append([y0, [(x0, text)]])

    # Each visual line: sort words by x, join without spaces (Chinese text).
    out: list[tuple[float, str]] = []
    for y0, words in groups:
        joined = "".join(t for _, t in sorted(words, key=lambda p: p[0]))
        out.append((y0, joined))
    out.sort(key=lambda p: p[0])
    return out


def _cluster_cells(lines: list[tuple[float, str]]) -> list[str]:
    """Split a column's lines into cells; a large vertical gap starts a new cell."""
    cells: list[list[str]] = []
    current: list[str] = []
    prev_y: float | None = None
    for y, text in lines:
        if current and (y - prev_y) > LINE_GAP_THRESHOLD:
            cells.append(current)
            current = []
        current.append(text)
        prev_y = y
    if current:
        cells.append(current)
    return ["\n".join(c) for c in cells]


def parse_weeks(raw: str) -> set[int]:
    """Expand a school week list like ``2,2-3,3-5单,5-6`` into a set of weeks."""
    weeks: set[int] = set()
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        m = _WEEK_TOKEN.match(token)
        if not m:
            continue
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else start
        parity = m.group(3)  # "单" odd weeks, "双" even weeks, or None
        for w in range(start, end + 1):
            if parity == "单" and w % 2 == 0:
                continue
            if parity == "双" and w % 2 == 1:
                continue
            weeks.add(w)
    return weeks


def parse_teachers(line: str) -> list[str]:
    line = line.replace("，", ",").replace("、", ",")
    return [p for p in (x.strip() for x in line.split(",")) if re.fullmatch(r"[一-龥]{2,4}", p)]


def clean_location(loc: str) -> str:
    return _CAMPUS.sub(r"\1校区 ", loc).strip()


def _parse_cell(text: str, weekday: int) -> Course | None:
    lines = [ln for ln in text.split("\n") if ln.strip()]
    if not lines:
        return None

    # Period range is the trailing line, e.g. "第3,4,5节".
    m = re.search(r"第([\d,]+)节", lines[-1])
    if not m:
        return None
    periods = [int(x) for x in m.group(1).split(",")]
    start_period, end_period = min(periods), max(periods)

    # Location is the line containing "楼" (building).
    loc_line = next((ln for ln in lines if "楼" in ln), "")
    loc_idx = lines.index(loc_line) if loc_line else len(lines)
    location = clean_location(loc_line)

    # Weeks live between the location line and the trailing period line.
    weeks_raw = "".join(lines[loc_idx + 1 : -1])
    m = re.search(r"\[([\d,\-单双]+)\]", weeks_raw)
    weeks = parse_weeks(m.group(1)) if m else set()

    # Header above the location: name lines, then optional code/note, then teachers.
    # The name is the leading block; teachers are any Chinese-name lines after the
    # code/note (which carries a digit or full-width parentheses). Teachers may wrap
    # across multiple lines when a cell is narrow.
    header = lines[:loc_idx]
    name_parts: list[str] = []
    teacher_parts: list[str] = []
    seen_code = False
    for ln in header:
        if re.search(r"[0-9]|（|）", ln):
            seen_code = True
        elif seen_code:
            teacher_parts.append(ln)
        else:
            name_parts.append(ln)
    name = "".join(name_parts).strip()
    teachers = parse_teachers("".join(teacher_parts))

    flat = text.replace("\n", "")
    m = re.search(r"（([^）]*)）", flat)
    note = m.group(1) if m else ""

    return Course(
        name=name,
        teachers=teachers,
        location=location,
        note=note,
        weekday=weekday,
        start_period=start_period,
        end_period=end_period,
        weeks=weeks,
    )
