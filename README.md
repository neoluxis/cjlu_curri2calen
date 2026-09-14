# cjlu-curri2calen

Parse a school curriculum PDF (中国计量大学 / CJLU) into an `.ics` calendar file.

- `assets/curric.pdf` — the curriculum timetable downloaded from the school system.
- `data/configs/schedule.yaml` — semester dates and class-period timing config.

## Usage

```bash
uv sync
uv run curri2calen
```

This prints the computed timetable (period → time slots), the parsed courses, and writes
`output/curriculum.ics`.
