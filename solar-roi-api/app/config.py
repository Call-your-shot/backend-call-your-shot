"""Central, environment-independent business defaults."""

from zoneinfo import ZoneInfo

API_TITLE = "Solar ROI API"
API_VERSION = "1.1.0"
SERVICE_TIMEZONE = ZoneInfo("Australia/Sydney")

DEFAULT_METER_TOLERANCE_RATIO = 0.01
DEFAULT_TREND_TOLERANCE_RATIO = 0.05
DEFAULT_FORECAST_HORIZON_MONTHS = 360
PERFORMANCE_MONTHS_AFTER_HISTORICAL_PAYBACK = 12

# Normalised, editable defaults for assumption-based initial estimates. Core
# simulation functions receive these profiles as data and do not embed them.
DEFAULT_MONTHLY_GENERATION_WEIGHTS = (
    0.105,
    0.095,
    0.090,
    0.080,
    0.065,
    0.055,
    0.060,
    0.070,
    0.080,
    0.090,
    0.100,
    0.110,
)
DEFAULT_MONTHLY_USAGE_WEIGHTS = (
    0.085,
    0.080,
    0.075,
    0.075,
    0.080,
    0.090,
    0.100,
    0.095,
    0.080,
    0.075,
    0.080,
    0.085,
)

MONTE_CARLO_WARNING_THRESHOLDS = {
    "very_high_variability_percentage": 30.0,
    "wide_self_consumption_range": 0.40,
    "low_expected_self_consumption": 0.30,
    "export_to_grid_rate_ratio": 0.80,
    "many_no_payback_probability": 0.25,
}

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
