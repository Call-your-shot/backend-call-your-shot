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


@pytest.fixture
def initial_estimate_payload() -> dict:
    return {
        "installation": {
            "gross_installation_cost_dollars": 9000,
            "stc_benefit_dollars": 1500,
            "installed_capacity_kw": 6.6,
        },
        "simulation": {
            "iterations": 100,
            "forecast_years": 20,
            "random_seed": 42,
        },
        "generation": {
            "expected_annual_generation_kwh": 9108,
            "annual_variability_percentage": 10,
        },
        "tenant_demand": {
            "expected_annual_usage_kwh": 6500,
            "annual_usage_variability_percentage": 15,
        },
        "solar_utilisation": {
            "expected_self_consumption_ratio": 0.55,
            "minimum_self_consumption_ratio": 0.35,
            "maximum_self_consumption_ratio": 0.75,
        },
        "pricing": {
            "pricing_mode": "dynamic",
            "grid_rate_cents_per_kwh": 30,
            "export_rate_cents_per_kwh": 5,
        },
        "costs": {"annual_operating_cost_dollars": 100},
    }
