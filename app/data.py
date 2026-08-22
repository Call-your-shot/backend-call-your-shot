from __future__ import annotations

from datetime import datetime, timezone

PROPERTY_ID = "11111111-1111-4111-8111-111111111111"
BATTERY_ID = "22222222-2222-4222-8222-222222222222"
TARIFF_ID = "33333333-3333-4333-8333-333333333333"
TENANT_USER_ID = "44444444-4444-4444-8444-444444444444"
LANDLORD_USER_ID = "55555555-5555-4555-8555-555555555555"
DEMO_TODAY = "2026-08-22"
DEMO_NOW = "2026-08-22T09:30:00+10:00"

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
TENANCY_PLANS: list[dict] = [
    {
        "id": "ten-priya-wollongong",
        "email": "tenant@example.com",
        "tenant_name": "Priya Sharma",
        "property_id": "prop-priya-figtree",

        "status": "active",
        "address": {
            "street": "12/88 Corrimal Street",
            "suburb": "Wollongong",
            "state": "NSW",
            "postcode": "2500",
        },
        "image_variant": 1,
        "start_date": "2025-03-01",
        "rate_per_kwh_cents": 15,
        "grid_rate_cents": 29,
        "max_term_years": 9,
        "monthly_reserve_contribution": 14,
        "balance_repaid": 1120,
        "balance_total": 4100,
        "estimated_completion_date": "2032-01-01",
        "landlord_name": "Coastal Realty Group",
        "property_manager": "Coastal Realty Group",
        "landlord_agreed_date": "2025-02-14",
        "system_size_kw": 5.3,
        "leave_request": None,
        "monthly": [
            {
                "month": "Jul 2026",
                "solarUsedKwh": 200,
                "gridUsedKwh": 205,
                "chargeDollars": 30.0,
                "withoutSolarDollars": 58.0,
                "savingsDollars": 30.0,
            },
            {
                "month": "Aug 2026",
                "solarUsedKwh": 214,
                "gridUsedKwh": 198,
                "chargeDollars": 32.1,
                "withoutSolarDollars": 74.7,
                "savingsDollars": 42.6,
            },
        ],
    }
]
LANDLORD_PROPERTY_VIEWS: list[dict] = [
    {
        "id": "prop-owned-1",
        "aliases": ["prop-priya-figtree"],
        "email": "landlord@example.com",

        "owner_emails": ["owner@example.com", "landlord@example.com"],
        "address": {
            "street": "42 Bellambi Lane",
            "suburb": "Bellambi",
            "state": "NSW",
            "postcode": "2518",
        },
        "image_variant": 0,
        "occupancy_status": "occupied",
        "system": {
            "sizeKw": 7.9,
            "panelCount": 18,
            "installDate": "2023-02-01",
            "inverterModel": "Fronius Primo 7.0-1",
            "warrantyExpiry": "2033-02-01",
            "status": "normal",
            "todayGenerationKwh": 24.6,
            "currentOutputKw": 3.2,
            "performancePercent": 96,
            "lastReadingAt": "2026-08-21T14:30:00+10:00",
            "dailyOutputKwh30d": [
                22.4, 23.1, 20.8, 24.6, 25.0, 18.9, 21.7, 23.8, 24.2, 22.9,
                19.4, 20.1, 21.5, 25.6, 26.2, 24.9, 23.3, 22.0, 21.1, 19.8,
                20.7, 22.8, 23.4, 24.1, 25.3, 26.0, 24.6, 23.7, 22.5, 24.6,
            ],
            "serviceHistory": [
                {"date": "2025-08-01", "description": "Annual inspection & panel clean"}
            ],
        },
        "current_tenant": {
            "name": "Amelia Rossi",
            "tenancyStart": "2024-11-01",
            "tenancyEnd": None,
            "ratePerKwhCents": 15,
            "contributionToBalance": 948,
            "current": True,
        },
        "tenant_history": [
            {
                "name": "Amelia Rossi",
                "tenancyStart": "2024-11-01",
                "tenancyEnd": None,
                "ratePerKwhCents": 15,
                "contributionToBalance": 948,
                "current": True,
            },
            {
                "name": "Ben Carter",
                "tenancyStart": "2023-02-01",
                "tenancyEnd": "2024-10-15",
                "ratePerKwhCents": 14,
                "contributionToBalance": 1866,
                "current": False,
            },
        ],
        "monthly_income": 428,
        "balance_outstanding": 3985,
        "balance_total": 6700,
        "total_earned": 2815,
        "total_invested": 6700,
        "monthly": [
            {
                "month": "Aug 2026",
                "generationKwh": 712,
                "tenantChargeCollected": 69.4,
                "exportCredits": 12.5,
                "reserveContribution": 18,
                "netIncome": 63.9,
            }
        ],
        "maintenance_reserve": {
            "accrued": 486,
            "nextCostDescription": "Inverter replacement",
            "nextCostDate": "2035-02-01",
            "nextCostEstimate": 1500,
        },
        "pending_invitation_email": None,
        "performance_alert": None,
        "leave_request": None,
    }
]
FRONTEND_NOTIFICATIONS: list[dict] = []
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
