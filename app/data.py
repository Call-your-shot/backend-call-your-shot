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
        "id": "aaaaaaaa-1111-4111-8111-111111111111",
        "email": "sarah.chen@example.com",
        "full_name": "Sarah Chen",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "active",
    },
    {
        "id": "aaaaaaaa-2222-4222-8222-222222222222",
        "email": "david.marino@example.com",
        "full_name": "David Marino",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "active",
    },
    {
        "id": "aaaaaaaa-3333-4333-8333-333333333333",
        "email": "qimatx@example.com",
        "full_name": "Qimatx",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "active",
    },
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
USER_PREFERENCES: dict[str, dict] = {}
SUPPORT_REPORTS: list[dict] = []
TENANCY_PLANS: list[dict] = [
    {
        "id": "ten-qimatx-wollongong",
        "email": "tenant@example.com",
        "emails": ["tenant@example.com", "qimatx@example.com", "sarah.chen@example.com"],
        "tenant_name": "Qimatx",
        "property_id": "prop-qimatx-figtree",

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
            {"month": "Jul 2025", "solarUsedKwh": 190, "gridUsedKwh": 210, "chargeDollars": 28.5, "withoutSolarDollars": 116.0, "savingsDollars": 24.7},
            {"month": "Aug 2025", "solarUsedKwh": 210, "gridUsedKwh": 195, "chargeDollars": 31.5, "withoutSolarDollars": 117.5, "savingsDollars": 26.3},
            {"month": "Sep 2025", "solarUsedKwh": 220, "gridUsedKwh": 180, "chargeDollars": 33.0, "withoutSolarDollars": 116.0, "savingsDollars": 30.8},
            {"month": "Oct 2025", "solarUsedKwh": 240, "gridUsedKwh": 160, "chargeDollars": 36.0, "withoutSolarDollars": 116.0, "savingsDollars": 33.6},
            {"month": "Nov 2025", "solarUsedKwh": 250, "gridUsedKwh": 150, "chargeDollars": 37.5, "withoutSolarDollars": 116.0, "savingsDollars": 35.0},
            {"month": "Dec 2025", "solarUsedKwh": 260, "gridUsedKwh": 140, "chargeDollars": 39.0, "withoutSolarDollars": 116.0, "savingsDollars": 36.4},
            {"month": "Jan 2026", "solarUsedKwh": 270, "gridUsedKwh": 130, "chargeDollars": 40.5, "withoutSolarDollars": 116.0, "savingsDollars": 37.8},
            {"month": "Feb 2026", "solarUsedKwh": 250, "gridUsedKwh": 150, "chargeDollars": 37.5, "withoutSolarDollars": 116.0, "savingsDollars": 35.0},
            {"month": "Mar 2026", "solarUsedKwh": 230, "gridUsedKwh": 170, "chargeDollars": 34.5, "withoutSolarDollars": 116.0, "savingsDollars": 32.2},
            {"month": "Apr 2026", "solarUsedKwh": 210, "gridUsedKwh": 190, "chargeDollars": 31.5, "withoutSolarDollars": 116.0, "savingsDollars": 29.4},
            {"month": "May 2026", "solarUsedKwh": 180, "gridUsedKwh": 220, "chargeDollars": 27.0, "withoutSolarDollars": 116.0, "savingsDollars": 25.2},
            {"month": "Jun 2026", "solarUsedKwh": 170, "gridUsedKwh": 230, "chargeDollars": 25.5, "withoutSolarDollars": 116.0, "savingsDollars": 23.8},
            {"month": "Jul 2026", "solarUsedKwh": 190, "gridUsedKwh": 210, "chargeDollars": 28.5, "withoutSolarDollars": 116.0, "savingsDollars": 26.6},
            {"month": "Aug 2026", "solarUsedKwh": 210, "gridUsedKwh": 195, "chargeDollars": 31.5, "withoutSolarDollars": 117.5, "savingsDollars": 26.3},
        ],
    }
]
LANDLORD_PROPERTY_VIEWS: list[dict] = [
    {
        "id": "prop-owned-1",
        "aliases": ["prop-qimatx-figtree"],
        "email": "landlord@example.com",

        "owner_emails": [
            "owner@example.com",
            "landlord@example.com",
            "david.marino@example.com",
            "qimatx@example.com",
        ],
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
            "dailyOutputKwh30d": [22.4, 23.1],
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
        ],
        "monthly_income": 64,
        "balance_outstanding": 3885,
        "balance_total": 6700,
        "total_earned": 2815,
        "total_invested": 6700,
        "monthly": [
            {"month": "Jul 2025", "generationKwh": 640, "tenantChargeCollected": 62.1, "exportCredits": 10.8, "reserveContribution": 18, "netIncome": 54.9},
            {"month": "Aug 2025", "generationKwh": 712, "tenantChargeCollected": 69.4, "exportCredits": 12.5, "reserveContribution": 18, "netIncome": 63.9},
            {"month": "Sep 2025", "generationKwh": 760, "tenantChargeCollected": 74.0, "exportCredits": 14.0, "reserveContribution": 18, "netIncome": 70.0},
            {"month": "Oct 2025", "generationKwh": 820, "tenantChargeCollected": 80.0, "exportCredits": 16.0, "reserveContribution": 18, "netIncome": 78.0},
            {"month": "Nov 2025", "generationKwh": 860, "tenantChargeCollected": 84.0, "exportCredits": 18.0, "reserveContribution": 18, "netIncome": 84.0},
            {"month": "Dec 2025", "generationKwh": 910, "tenantChargeCollected": 89.0, "exportCredits": 20.0, "reserveContribution": 18, "netIncome": 91.0},
            {"month": "Jan 2026", "generationKwh": 940, "tenantChargeCollected": 92.0, "exportCredits": 22.0, "reserveContribution": 18, "netIncome": 96.0},
            {"month": "Feb 2026", "generationKwh": 880, "tenantChargeCollected": 86.0, "exportCredits": 19.0, "reserveContribution": 18, "netIncome": 87.0},
            {"month": "Mar 2026", "generationKwh": 810, "tenantChargeCollected": 79.0, "exportCredits": 15.0, "reserveContribution": 18, "netIncome": 76.0},
            {"month": "Apr 2026", "generationKwh": 740, "tenantChargeCollected": 72.0, "exportCredits": 12.0, "reserveContribution": 18, "netIncome": 66.0},
            {"month": "May 2026", "generationKwh": 650, "tenantChargeCollected": 63.0, "exportCredits": 9.0, "reserveContribution": 18, "netIncome": 54.0},
            {"month": "Jun 2026", "generationKwh": 590, "tenantChargeCollected": 57.0, "exportCredits": 7.0, "reserveContribution": 18, "netIncome": 46.0},
            {"month": "Jul 2026", "generationKwh": 640, "tenantChargeCollected": 62.1, "exportCredits": 10.8, "reserveContribution": 18, "netIncome": 54.9},
            {"month": "Aug 2026", "generationKwh": 712, "tenantChargeCollected": 69.4, "exportCredits": 12.5, "reserveContribution": 18, "netIncome": 63.9},
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
