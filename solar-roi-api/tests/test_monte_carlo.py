from copy import deepcopy

import numpy as np
import pytest
from pydantic import ValidationError

from app.models import InitialEstimateRequest
from app.monte_carlo import run_monte_carlo_roi, simulate_single_investment_path


def initial_payload(iterations: int = 500, seed: int = 42) -> dict:
    return {
        "installation": {
            "gross_installation_cost_dollars": 9_000,
            "stc_benefit_dollars": 1_500,
            "other_rebates_dollars": 0,
            "installed_capacity_kw": 6.6,
        },
        "simulation": {
            "iterations": iterations,
            "forecast_years": 20,
            "random_seed": seed,
        },
        "generation": {
            "expected_annual_generation_kwh": 9_108,
            "annual_variability_percentage": 10,
            "annual_panel_degradation_rate": 0.005,
        },
        "tenant_demand": {
            "expected_annual_usage_kwh": 6_500,
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
            "alpha_min": 0.40,
            "alpha_max": 0.75,
            "discount_sensitivity": 0.50,
        },
        "costs": {
            "annual_operating_cost_dollars": 100,
            "annual_operating_cost_variability_percentage": 10,
        },
    }


def run(payload: dict):
    return run_monte_carlo_roi(InitialEstimateRequest.model_validate(payload))


def test_same_seed_produces_identical_output() -> None:
    payload = initial_payload()
    assert run(payload).model_dump() == run(payload).model_dump()


def test_different_seed_changes_simulation() -> None:
    first = run(initial_payload(seed=1))
    second = run(initial_payload(seed=2))
    assert first.energy_distribution.first_year_generation_kwh != (
        second.energy_distribution.first_year_generation_kwh
    )


def test_net_installation_cost_is_reported() -> None:
    assert run(initial_payload()).installation.net_installation_cost_dollars == 7_500


def test_single_path_preserves_energy_and_price_constraints() -> None:
    request = InitialEstimateRequest.model_validate(initial_payload())
    path = simulate_single_investment_path(np.random.default_rng(42), request, 2)
    for year in path.years:
        assert 0 <= year.self_consumption_ratio <= 1
        assert year.generation_kwh == pytest.approx(
            year.tenant_solar_consumption_kwh + year.export_kwh
        )
        assert year.tenant_solar_consumption_kwh <= year.tenant_usage_kwh
        assert year.export_rate_cents_per_kwh <= year.tenant_rate_cents_per_kwh
        assert year.tenant_rate_cents_per_kwh <= year.grid_rate_cents_per_kwh


def test_higher_generation_generally_shortens_median_payback() -> None:
    baseline = initial_payload(iterations=1_000)
    higher = deepcopy(baseline)
    higher["generation"]["expected_annual_generation_kwh"] = 12_000
    assert (
        run(higher).headline.median_payback_years
        < run(baseline).headline.median_payback_years
    )


def test_higher_self_consumption_generally_shortens_payback() -> None:
    low = initial_payload(iterations=1_000)
    low["solar_utilisation"].update(
        {
            "minimum_self_consumption_ratio": 0.2,
            "expected_self_consumption_ratio": 0.3,
            "maximum_self_consumption_ratio": 0.4,
        }
    )
    high = deepcopy(low)
    high["solar_utilisation"].update(
        {
            "minimum_self_consumption_ratio": 0.6,
            "expected_self_consumption_ratio": 0.7,
            "maximum_self_consumption_ratio": 0.8,
        }
    )
    assert (
        run(high).headline.median_payback_years < run(low).headline.median_payback_years
    )


def test_higher_installation_cost_increases_payback() -> None:
    baseline = initial_payload(iterations=1_000)
    expensive = deepcopy(baseline)
    expensive["installation"]["gross_installation_cost_dollars"] = 12_000
    assert (
        run(expensive).headline.median_payback_years
        > run(baseline).headline.median_payback_years
    )


def test_zero_revenue_returns_no_payback() -> None:
    payload = initial_payload()
    payload["pricing"].update(
        {"grid_rate_cents_per_kwh": 0, "export_rate_cents_per_kwh": 0}
    )
    payload["costs"]["annual_operating_cost_dollars"] = 0
    result = run(payload)
    assert result.headline.median_payback_years is None
    assert result.probability_no_payback_within_horizon == 1
    assert result.payback_distribution_years is None


def test_forecast_horizon_terminates_safely() -> None:
    payload = initial_payload()
    payload["simulation"]["forecast_years"] = 1
    payload["installation"]["gross_installation_cost_dollars"] = 1_000_000
    result = run(payload)
    assert result.probability_no_payback_within_horizon == 1
    assert len(result.payback_cdf) == 1


def test_percentile_output_is_ordered() -> None:
    result = run(initial_payload())
    summary = result.payback_distribution_years
    assert summary.p05 <= summary.p25 <= summary.p50 <= summary.p75 <= summary.p95


def test_fixed_pricing_mode_is_supported() -> None:
    payload = initial_payload()
    payload["pricing"].update(
        {
            "pricing_mode": "fixed",
            "fixed_tenant_solar_rate_cents_per_kwh": 15,
        }
    )
    result = run(payload)
    assert result.assumptions.pricing_mode == "fixed"
    assert result.headline.median_payback_years is not None


def test_triangular_alpha_mode_is_supported() -> None:
    payload = initial_payload()
    payload["pricing"].update(
        {
            "alpha_estimation_mode": "triangular",
            "alpha_min": 0.3,
            "alpha_mode": 0.5,
            "alpha_max": 0.8,
        }
    )
    result = run(payload)
    assert result.assumptions.alpha_estimation_mode == "triangular"
    assert result.headline.median_payback_years is not None


def test_weak_assumptions_return_structured_warnings() -> None:
    payload = initial_payload()
    payload["installation"]["gross_installation_cost_dollars"] = 1_000_000
    payload["generation"]["annual_variability_percentage"] = 31
    payload["tenant_demand"]["annual_usage_variability_percentage"] = 31
    payload["solar_utilisation"].update(
        {
            "minimum_self_consumption_ratio": 0.05,
            "expected_self_consumption_ratio": 0.2,
            "maximum_self_consumption_ratio": 0.75,
        }
    )
    result = run(payload)
    codes = {warning.code for warning in result.warnings}
    assert {
        "VERY_HIGH_GENERATION_UNCERTAINTY",
        "VERY_HIGH_USAGE_UNCERTAINTY",
        "WIDE_SELF_CONSUMPTION_RANGE",
        "LOW_EXPECTED_SELF_CONSUMPTION",
        "PAYBACK_NOT_REACHED_IN_MANY_SIMULATIONS",
    } <= codes


def test_deterministic_degradation_declines_generation() -> None:
    payload = initial_payload(iterations=100)
    payload["generation"]["annual_variability_percentage"] = 0
    request = InitialEstimateRequest.model_validate(payload)
    path = simulate_single_investment_path(np.random.default_rng(42), request, 2)
    assert path.years[1].generation_kwh == pytest.approx(
        path.years[0].generation_kwh * 0.995
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [("iterations", 99), ("iterations", 100_001), ("forecast_years", 0)],
)
def test_invalid_simulation_configuration_is_rejected(field: str, value: int) -> None:
    payload = initial_payload()
    payload["simulation"][field] = value
    with pytest.raises(ValidationError):
        InitialEstimateRequest.model_validate(payload)


def test_invalid_self_consumption_order_is_rejected() -> None:
    payload = initial_payload()
    payload["solar_utilisation"].update(
        {
            "minimum_self_consumption_ratio": 0.7,
            "expected_self_consumption_ratio": 0.5,
        }
    )
    with pytest.raises(ValidationError, match="minimum <= expected <= maximum"):
        InitialEstimateRequest.model_validate(payload)


def test_invalid_monthly_weights_are_rejected() -> None:
    payload = initial_payload()
    payload["generation"]["monthly_generation_weights"] = [0.1] * 12
    with pytest.raises(ValidationError, match="sum to 1"):
        InitialEstimateRequest.model_validate(payload)
