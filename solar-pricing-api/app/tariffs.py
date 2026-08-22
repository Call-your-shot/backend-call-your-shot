"""
Time-of-use tariff configuration for Wollongong / Endeavour Energy area.

Rates are stored as a list of ``(start_hour, end_hour, rate_cents_per_kwh)``
tuples where ``start_hour`` is inclusive and ``end_hour`` is exclusive.

The ``resolve_*`` functions accept a timezone-aware datetime and return the
applicable rate after converting to the configured local timezone.

These are **modelling defaults** — they will later be replaced by retailer
API lookups or database-stored contracts.
"""

from datetime import datetime
from typing import List, Tuple
from zoneinfo import ZoneInfo

from app.config import TIMEZONE

# ---------------------------------------------------------------------------
# Time-of-Use grid electricity rates (cents / kWh)
# (start_hour_inclusive, end_hour_exclusive, rate_cents_per_kwh)
# ---------------------------------------------------------------------------

TOU_GRID_RATES: List[Tuple[int, int, float]] = [
    (0, 10, 35.69),   # Off-peak overnight / morning
    (10, 14, 12.35),  # Solar soak / shoulder
    (14, 16, 35.69),  # Shoulder
    (16, 20, 46.85),  # Peak
    (20, 24, 35.69),  # Off-peak evening
]

# ---------------------------------------------------------------------------
# Time-of-Use solar export / feed-in rates (cents / kWh)
# ---------------------------------------------------------------------------

TOU_EXPORT_RATES: List[Tuple[int, int, float]] = [
    (0, 10, 4.0),
    (10, 14, 3.2),
    (14, 16, 6.0),
    (16, 20, 18.0),
    (20, 24, 4.0),
]

# ---------------------------------------------------------------------------
# Fallback defaults (should not be reached with complete schedules)
# ---------------------------------------------------------------------------

DEFAULT_GRID_RATE: float = 35.69
DEFAULT_EXPORT_RATE: float = 4.0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SYDNEY_TZ = ZoneInfo(TIMEZONE)


def _resolve_rate(
    timestamp: datetime,
    schedule: List[Tuple[int, int, float]],
    fallback: float,
) -> float:
    """Look up the rate for *timestamp* from a TOU schedule."""
    local_dt = timestamp.astimezone(_SYDNEY_TZ)
    hour = local_dt.hour
    for start, end, rate in schedule:
        if start <= hour < end:
            return rate
    return fallback


def resolve_grid_rate(timestamp: datetime) -> float:
    """Return the grid electricity rate (cents/kWh) for *timestamp*."""
    return _resolve_rate(timestamp, TOU_GRID_RATES, DEFAULT_GRID_RATE)


def resolve_export_rate(timestamp: datetime) -> float:
    """Return the solar export / feed-in rate (cents/kWh) for *timestamp*."""
    return _resolve_rate(timestamp, TOU_EXPORT_RATES, DEFAULT_EXPORT_RATE)
