from typing import Iterable, Sequence

from app.schemas.work_schedules import WorkScheduleEntry


def validate_week_entries(entries: Sequence[WorkScheduleEntry]) -> None:
    if len(entries) != 7:
        raise ValueError("Work schedule must include 7 entries.")
    days = [entry.day_of_week for entry in entries]
    if sorted(days) != list(range(7)):
        raise ValueError("Work schedule must include day_of_week 0-6 once each.")


def normalize_week_entries(entries: Iterable[WorkScheduleEntry]) -> list[WorkScheduleEntry]:
    day_map = {entry.day_of_week: entry.day_type for entry in entries}
    normalized: list[WorkScheduleEntry] = []
    for day in range(7):
        normalized.append(
            WorkScheduleEntry(
                day_of_week=day, day_type=day_map.get(day, "off")
            )
        )
    return normalized
