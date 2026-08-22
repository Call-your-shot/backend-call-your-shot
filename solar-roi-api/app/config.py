"""Central, environment-independent business defaults."""

from zoneinfo import ZoneInfo

API_TITLE = "Solar ROI API"
API_VERSION = "1.0.0"
SERVICE_TIMEZONE = ZoneInfo("Australia/Sydney")

DEFAULT_METER_TOLERANCE_RATIO = 0.01
DEFAULT_TREND_TOLERANCE_RATIO = 0.05
DEFAULT_FORECAST_HORIZON_MONTHS = 360
PERFORMANCE_MONTHS_AFTER_HISTORICAL_PAYBACK = 12

SCENARIOS: dict[str, dict[str, float]] = {
    "conservative": {
        "generation_multiplier": 0.90,
        "self_consumption_multiplier": 0.90,
        "tenant_rate_multiplier": 0.95,
        "operating_cost_multiplier": 1.10,
    },
    "expected": {
        "generation_multiplier": 1.00,
        "self_consumption_multiplier": 1.00,
        "tenant_rate_multiplier": 1.00,
        "operating_cost_multiplier": 1.00,
    },
    "optimistic": {
        "generation_multiplier": 1.05,
        "self_consumption_multiplier": 1.10,
        "tenant_rate_multiplier": 1.05,
        "operating_cost_multiplier": 1.00,
    },
}
