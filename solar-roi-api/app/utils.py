"""Small date, numeric, and presentation helpers."""

from __future__ import annotations

from datetime import date


def month_start(value: date) -> date:
    return value.replace(day=1)


def add_months(value: date, months: int) -> date:
    absolute = value.year * 12 + value.month - 1 + months
    return date(absolute // 12, absolute % 12 + 1, 1)


def calendar_months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + end.month - start.month


def month_key(value: date) -> str:
    return value.strftime("%Y-%m")


def round_currency(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


def round_energy(value: float | None) -> float | None:
    return None if value is None else round(value, 3)


def round_ratio(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def round_percentage(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


def safe_percentage_change(previous: float, current: float) -> float | None:
    if previous == 0:
        return None
    return (current - previous) / abs(previous) * 100


def circular_month_distance(first: int, second: int) -> int:
    distance = abs(first - second)
    return min(distance, 12 - distance)
