"""Data model shared across the parser and generator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time


@dataclass(frozen=True)
class Period:
    """A single class period (节) with its start and end wall-clock time."""

    index: int  # 1-based, 1..12
    start: time
    end: time


@dataclass(frozen=True)
class Timetable:
    """Mapping of period index (1..12) to its time slot."""

    periods: dict[int, Period]

    def slot(self, start_period: int, end_period: int) -> tuple[time, time]:
        """Start/end wall-clock time for a course spanning [start, end] periods."""
        return self.periods[start_period].start, self.periods[end_period].end


@dataclass(frozen=True)
class Semester:
    """Semester dates: the configured start date and the Monday of week 1."""

    start: date
    week1_monday: date


@dataclass
class Course:
    """A parsed course occurrence (day + period range + weeks)."""

    name: str
    teachers: list[str]
    location: str
    note: str
    weekday: int  # 1=Monday .. 7=Sunday
    start_period: int
    end_period: int
    weeks: set[int] = field(default_factory=set)
