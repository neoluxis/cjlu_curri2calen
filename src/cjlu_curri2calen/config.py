"""Load the schedule config and derive the period timetable + semester week 1."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path

import yaml

from .model import Period, Semester, Timetable

# Order in which the three daily blocks (morning/afternoon/evening) are listed.
BLOCKS = ("am", "pm", "noct")


def load_config(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def parse_time(value: str) -> time:
    if not isinstance(value, str):
        raise TypeError(
            f"clock time must be a quoted string like \"8:00\", got {value!r} — "
            "unquoted YAML times are parsed as sexagesimal integers"
        )
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def add_minutes(t: time, minutes: int) -> time:
    base = datetime(2000, 1, 1, t.hour, t.minute)
    return (base + timedelta(minutes=minutes)).time()


def build_timetable(cfg: dict) -> Timetable:
    """Expand the config's three blocks into 12 absolute period slots (1..12)."""
    lasting = int(cfg["schedule"]["lasting"])
    gap = int(cfg["schedule"]["gap"])

    periods: dict[int, Period] = {}
    index = 1
    for block in BLOCKS:
        spec = cfg["schedule"]["times"][block]
        begin = parse_time(spec["begin"])
        count = int(spec["count"])
        split = spec.get("split")  # optional {index, gap} — a longer break after that class

        cursor = begin
        for i in range(1, count + 1):
            start = cursor
            end = add_minutes(start, lasting)
            periods[index] = Period(index=index, start=start, end=end)
            index += 1

            # Break after class `i`: use the larger split gap, else the normal gap.
            if split and i == int(split["index"]):
                cursor = add_minutes(end, int(split["gap"]))
            else:
                cursor = add_minutes(end, gap)

    return Timetable(periods=periods)


def semester_info(cfg: dict) -> Semester:
    """Resolve the Monday of week 1 from the semester start + `monday_prima`."""
    start = date.fromisoformat(str(cfg["semester"]["start"]))
    prima = cfg["semester"].get("monday_prima", "next")

    offset = start.weekday()  # Monday=0 .. Sunday=6
    if prima == "this":
        # The Monday of the week containing the start date.
        week1 = start - timedelta(days=offset)
    else:
        # The first Monday strictly after the start date.
        days = (7 - offset) % 7
        if days == 0:
            days = 7
        week1 = start + timedelta(days=days)

    return Semester(start=start, week1_monday=week1)
