"""Command-line entry point: timetable from config → PDF courses → ICS file."""

from __future__ import annotations

from pathlib import Path

from .config import build_timetable, load_config, semester_info
from .ics import format_weeks, generate_ics
from .pdf import parse_pdf

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "data" / "configs" / "schedule.yaml"
PDF_PATH = ROOT / "assets" / "curric.pdf"
OUTPUT_PATH = ROOT / "output" / "curriculum.ics"

WEEKDAYS = ["", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


def main() -> None:
    cfg = load_config(CONFIG_PATH)
    timetable = build_timetable(cfg)
    semester = semester_info(cfg)

    # 1. Timetable derived from the config.
    print("== 节次 timetable (from schedule.yaml) ==")
    for idx in sorted(timetable.periods):
        p = timetable.periods[idx]
        print(f"  第{idx:>2}节  {p.start.strftime('%H:%M')} - {p.end.strftime('%H:%M')}")
    print(f"\n  semester start : {semester.start}")
    print(f"  week-1 Monday  : {semester.week1_monday}\n")

    # 2. Courses parsed from the PDF.
    courses = parse_pdf(PDF_PATH)
    print("== parsed courses ==")
    for c in sorted(courses, key=lambda c: (c.weekday, c.start_period)):
        period = f"第{c.start_period}-{c.end_period}节"
        teachers = ", ".join(c.teachers) if c.teachers else "—"
        print(
            f"  {WEEKDAYS[c.weekday]} {period}  {c.name}"
            f"  [{teachers}]  {c.location}  {format_weeks(c.weeks)}"
        )
    print(f"  ({len(courses)} courses)\n")

    # 3. ICS output.
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ics = generate_ics(courses, timetable, semester)
    OUTPUT_PATH.write_text(ics, encoding="utf-8")
    n_events = ics.count("BEGIN:VEVENT")
    print(f"wrote {OUTPUT_PATH} ({n_events} events)")


if __name__ == "__main__":
    main()
