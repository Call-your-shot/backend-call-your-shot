"""
Application configuration for the Solar Pricing API.

Centralises default values and location settings.
Designed to be replaced later by environment variables, database lookups,
or tenant-specific configuration.
"""

# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------

LOCATION_NAME: str = "Wollongong, NSW"
TIMEZONE: str = "Australia/Sydney"

# ---------------------------------------------------------------------------
# Default dynamic pricing parameters
# ---------------------------------------------------------------------------

DEFAULT_ALPHA_MIN: float = 0.40
DEFAULT_ALPHA_MAX: float = 0.75
DEFAULT_DISCOUNT_SENSITIVITY: float = 0.50

# ---------------------------------------------------------------------------
# Default fixed solar rate (cents per kWh)
# ---------------------------------------------------------------------------

DEFAULT_FIXED_SOLAR_RATE: float = 22.0
