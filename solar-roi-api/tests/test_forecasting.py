from datetime import date

import pytest

from app.analytics import build_seasonal_profile
from app.forecasting import forecast_monthly_generation, forecast_payback
from app.models import AnalysisRequest
from app.scenarios import run_scenario


def _simple_payload(cost: float = 250, revenue: float = 100) -> dict:
    return {
        "installation": {
            "gross_installation_cost_dollars": cost,
            "installation_date": "2025-12-01",
        },
        "history": [
            {
                "month": "2026-01-01",
                "total_usage_kwh": 100,
                "solar_generation_kwh": 100,
                "solar_consumed_by_tenant_kwh": 50,
                "solar_exported_kwh": 50,
                "tenant_revenue_dollars": revenue,
                "export_revenue_dollars": 0,
                "operating_cost_dollars": 0,
            }
        ],
        "forecast_assumptions": {
            "annual_generation_degradation_rate": 0,
            "forecast_horizon_months": 360,
        },
    }


def test_january_forecast_uses_january_history() -> None:
    request = AnalysisRequest.model_validate(_simple_payload())
    profile = build_seasonal_profile(request.history)
    generation, method = forecast_monthly_generation(profile, date(2027, 1, 1), 12, 0)
    assert generation == 100
    assert method == "calendar_month_average"


def test_degradation_reduces_output_gradually() -> None:
    request = AnalysisRequest.model_validate(_simple_payload())
    profile = build_seasonal_profile(request.history)
    generation, _ = forecast_monthly_generation(profile, date(2027, 1, 1), 12, 0.1)
    assert generation == pytest.approx(90)


def test_future_payback_is_simulated_month_by_month_with_fraction() -> None:
    request = AnalysisRequest.model_validate(_simple_payload(cost=250, revenue=100))
    outcome = forecast_payback(
        request, request.scenarios.expected, include_timeline=True
    )
    assert outcome.result.payback_type == "forecast"
    assert outcome.result.estimated_months_remaining == 1.5
    assert outcome.result.estimated_payback_date == "2026-03"


def test_scenario_payback_ordering() -> None:
    request = AnalysisRequest.model_validate(_simple_payload(cost=1000, revenue=50))
    conservative = run_scenario(request, request.scenarios.conservative).result
    expected = run_scenario(request, request.scenarios.expected).result
    optimistic = run_scenario(request, request.scenarios.optimistic).result
    assert optimistic.estimated_months_remaining <= expected.estimated_months_remaining
    assert (
        expected.estimated_months_remaining <= conservative.estimated_months_remaining
    )


def test_negative_future_cashflow_returns_no_payback() -> None:
    payload = _simple_payload(cost=1000, revenue=0)
    payload["history"][0]["operating_cost_dollars"] = 10
    payload["forecast_assumptions"]["forecast_horizon_months"] = 24
    request = AnalysisRequest.model_validate(payload)
    outcome = forecast_payback(
        request, request.scenarios.expected, include_timeline=True
    )
    assert outcome.result.payback_reached is False
    assert outcome.result.estimated_payback_date is None
    assert "insufficient" in outcome.result.reason.lower()


def test_forecast_stops_at_configured_horizon() -> None:
    payload = _simple_payload(cost=1_000_000, revenue=1)
    payload["forecast_assumptions"]["forecast_horizon_months"] = 360
    request = AnalysisRequest.model_validate(payload)
    outcome = forecast_payback(
        request, request.scenarios.expected, include_timeline=True
    )
    assert outcome.result.payback_reached is False
    assert len(outcome.months) == 360


def test_energy_based_mode_uses_supplied_rates() -> None:
    payload = _simple_payload(cost=1000, revenue=0)
    payload["revenue_forecast_mode"] = "energy_based"
    payload["revenue_assumptions"] = {
        "tenant_solar_rate_cents_per_kwh": 20,
        "export_rate_cents_per_kwh": 5,
        "annual_operating_cost_dollars": 12,
    }
    request = AnalysisRequest.model_validate(payload)
    outcome = forecast_payback(
        request, request.scenarios.expected, include_timeline=True
    )
    first = outcome.months[0]
    assert first.projected_tenant_revenue_dollars == 10
    assert first.projected_export_revenue_dollars == 2.5
    assert first.projected_operating_cost_dollars == 1


def test_energy_mode_uses_historical_average_rates_as_fallback() -> None:
    payload = _simple_payload(cost=1000, revenue=0)
    payload["revenue_forecast_mode"] = "energy_based"
    payload["history"][0].update(
        {
            "average_tenant_solar_rate_cents_per_kwh": 20,
            "average_export_rate_cents_per_kwh": 5,
        }
    )
    request = AnalysisRequest.model_validate(payload)
    outcome = forecast_payback(
        request, request.scenarios.expected, include_timeline=True
    )
    assert outcome.months[0].projected_tenant_revenue_dollars == 10
    assert outcome.months[0].projected_export_revenue_dollars == 2.5
