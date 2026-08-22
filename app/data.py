from __future__ import annotations

from datetime import datetime, timezone

PROPERTY_ID = "11111111-1111-4111-8111-111111111111"
BATTERY_ID = "22222222-2222-4222-8222-222222222222"
TARIFF_ID = "33333333-3333-4333-8333-333333333333"
TENANT_USER_ID = "44444444-4444-4444-8444-444444444444"
LANDLORD_USER_ID = "55555555-5555-4555-8555-555555555555"

PROPERTY = {
    "id": PROPERTY_ID,
    "name": "Call Your Shot Demo Home",
    "address_line_1": "42 Solar Circuit",
    "address_line_2": None,
    "suburb": "Wollongong",
    "state": "NSW",
    "postcode": "2500",
    "country": "AU",
    "roof_area_m2": 118,
    "usable_roof_area_m2": 82,
}

BATTERY = {
    "id": BATTERY_ID,
    "property_id": PROPERTY_ID,
    "name": "Garage Battery",
    "manufacturer": "Tesla",
    "model": "Powerwall 3",
    "capacity_kwh": 13.5,
    "usable_capacity_kwh": 13.5,
    "max_charge_kw": 5.0,
    "max_discharge_kw": 7.0,
    "reserve_pct": 10.0,
    "soc_pct": 62.0,
    "health_pct": 98.0,
    "status": "idle",
    "last_seen_at": datetime.now(timezone.utc).isoformat(),
}

TARIFF = {
    "id": TARIFF_ID,
    "property_id": PROPERTY_ID,
    "name": "Demo Solar Saver",
    "usage_rate_per_kwh": 0.34,
    "grid_rate_cents_per_kwh": 34.0,
    "feed_in_rate_per_kwh": 0.08,
    "daily_supply_charge": 1.12,
    "currency": "AUD",
}

ENERGY_READINGS: list[dict] = []
TARIFFS: list[dict] = [TARIFF.copy()]
SOLAR_ASSESSMENTS: list[dict] = []
SOLAR_INSTALLATIONS: list[dict] = []
PRICE_ADJUSTMENTS: list[dict] = []
LEASE_REQUESTS: list[dict] = []
CONTRACTS: list[dict] = []
NOTIFICATIONS: list[dict] = []
USERS: list[dict] = [
    {
        "id": TENANT_USER_ID,
        "email": "tenant@example.com",
        "full_name": "Demo Tenant",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "active",
    },
    {
        "id": LANDLORD_USER_ID,
        "email": "landlord@example.com",
        "full_name": "Demo Landlord",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "active",
    },
]
PROPERTIES: list[dict] = [PROPERTY.copy()]
PROPOSALS: list[dict] = []
PROPERTY_MEMBERSHIPS: list[dict] = [
    {
        "id": "66666666-6666-4666-8666-666666666666",
        "property_id": PROPERTY_ID,
        "email": "tenant@example.com",
        "user_id": TENANT_USER_ID,
        "role": "tenant",
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": "77777777-7777-4777-8777-777777777777",
        "property_id": PROPERTY_ID,
        "email": "landlord@example.com",
        "user_id": LANDLORD_USER_ID,
        "role": "landlord",
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
]

