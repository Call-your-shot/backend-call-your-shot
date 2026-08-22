from __future__ import annotations

from copy import deepcopy

import pytest


@pytest.fixture
def valid_payload() -> dict:
    return {
        "installation": {
            "gross_installation_cost_dollars": 9000,
            "stc_benefit_dollars": 1500,
            "other_rebates_dollars": 0,
            "installed_capacity_kw": 6.6,
            "installation_date": "2025-06-15",
        },
        "history": [
            {
                "month": "2025-07-01",
                "total_usage_kwh": 620,
                "solar_generation_kwh": 540,
                "solar_consumed_by_tenant_kwh": 330,
                "solar_exported_kwh": 210,
                "tenant_revenue_dollars": 72.6,
                "export_revenue_dollars": 10.5,
                "operating_cost_dollars": 0,
            },
            {
                "month": "2025-08-01",
                "total_usage_kwh": 660,
                "solar_generation_kwh": 610,
                "solar_consumed_by_tenant_kwh": 390,
                "solar_exported_kwh": 220,
                "tenant_revenue_dollars": 85.8,
                "export_revenue_dollars": 11,
                "operating_cost_dollars": 0,
            },
        ],
        "forecast_assumptions": {
            "annual_generation_degradation_rate": 0.005,
            "forecast_horizon_months": 360,
        },
    }


@pytest.fixture
def copy_payload():
    return deepcopy
