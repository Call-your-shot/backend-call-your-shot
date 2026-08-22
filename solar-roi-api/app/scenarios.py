"""Configurable conservative, expected, and optimistic scenario modelling."""

from __future__ import annotations

from .forecasting import ForecastOutcome, forecast_payback
from .models import AnalysisRequest, ScenarioMultipliers, ScenarioResult


def run_scenario(
    request: AnalysisRequest,
    multipliers: ScenarioMultipliers,
    *,
    include_timeline: bool = False,
) -> ForecastOutcome:
    return forecast_payback(request, multipliers, include_timeline=include_timeline)


def scenario_result(
    outcome: ForecastOutcome, multipliers: ScenarioMultipliers
) -> ScenarioResult:
    result = outcome.result
    return ScenarioResult(
        payback_reached=result.payback_reached,
        estimated_months_remaining=result.estimated_months_remaining,
        estimated_payback_date=result.estimated_payback_date,
        estimated_total_payback_years=result.estimated_total_payback_years,
        reason=result.reason,
        multipliers=multipliers,
    )
