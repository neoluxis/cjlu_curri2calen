"""Render courses as an iCalendar (`.ics`) document."""

from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import md5
from zoneinfo import ZoneInfo

from .model import Course, Semester, Timetable

TZ = ZoneInfo("Asia/Shanghai")


def generate_ics(courses: list[Course], timetable: Timetable, semester: Semester) -> str:
    """Build the full ICS text. Each (course, week) becomes one VEVENT."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//CJLU Curriculum to Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:课程表",
        "X-WR-TIMEZONE:Asia/Shanghai",
    ]
    lines += _vtimezone_lines()

    now = datetime.now(TZ)
    for course in courses:
        for week in sorted(course.weeks):
            day = semester.week1_monday + timedelta(
                days=(course.weekday - 1) + (week - 1) * 7
            )
            start_t, end_t = timetable.slot(course.start_period, course.end_period)
            dtstart = datetime.combine(day, start_t, tzinfo=TZ)
            dtend = datetime.combine(day, end_t, tzinfo=TZ)

            uid = _uid(course, day)
            lines += [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{now.strftime('%Y%m%dT%H%M%S')}",
                f"DTSTART;TZID=Asia/Shanghai:{dtstart.strftime('%Y%m%dT%H%M%S')}",
                f"DTEND;TZID=Asia/Shanghai:{dtend.strftime('%Y%m%dT%H%M%S')}",
                f"SUMMARY:{_escape(course.name)}",
                f"LOCATION:{_escape(course.location)}",
                f"DESCRIPTION:{_escape(_description(course))}",
                "END:VEVENT",
            ]

    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(ln) for ln in lines) + "\r\n"


def format_weeks(weeks: set[int]) -> str:
    """Compress a week set into human ranges, e.g. ``第1-3,5-7周``."""
    ws = sorted(weeks)
    if not ws:
        return ""
    ranges: list[tuple[int, int]] = []
    start = prev = ws[0]
    for w in ws[1:]:
        if w == prev + 1:
            prev = w
        else:
            ranges.append((start, prev))
            start = prev = w
    ranges.append((start, prev))
    parts = [str(s) if s == e else f"{s}-{e}" for s, e in ranges]
    return "第" + ",".join(parts) + "周"


def _description(course: Course) -> str:
    parts: list[str] = []
    if course.teachers:
        parts.append("教师: " + ", ".join(course.teachers))
    parts.append("地点: " + course.location)
    parts.append("周次: " + format_weeks(course.weeks))
    if course.note:
        parts.append("备注: " + course.note)
    return "\n".join(parts)


def _uid(course: Course, day) -> str:
    digest = md5(course.name.encode("utf-8")).hexdigest()[:8]
    return f"cjlu-{digest}-{day.isoformat()}-{course.start_period:02d}{course.end_period:02d}"


def _vtimezone_lines() -> list[str]:
    # China observes no DST; a single STANDARD block with a fixed +08:00 offset.
    return [
        "BEGIN:VTIMEZONE",
        "TZID:Asia/Shanghai",
        "BEGIN:STANDARD",
        "DTSTART:19700101T000000",
        "TZOFFSETFROM:+0800",
        "TZOFFSETTO:+0800",
        "TZNAME:CST",
        "END:STANDARD",
        "END:VTIMEZONE",
    ]


def _escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """Fold a line to RFC 5545's 75-octet limit (continuation lines get a space)."""
    if len(line.encode("utf-8")) <= 75:
        return line
    parts: list[str] = []
    cur = line
    while cur:
        limit = 75 if not parts else 74  # continuation carries a leading space
        used = 0
        n = 0
        for ch in cur:
            w = len(ch.encode("utf-8"))
            if used + w > limit:
                break
            used += w
            n += 1
        if n == 0:  # a single char exceeds the limit (cannot happen for limit >= 4)
            n = 1
        parts.append(cur[:n])
        cur = cur[n:]
    return "\r\n ".join(parts)
