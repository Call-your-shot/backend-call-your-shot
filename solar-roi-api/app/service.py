"""Application orchestration shared by every API endpoint."""

from __future__ import annotations

from .analytics import analyse_history
from .models import (
    AnalysisRequest,
    AnalysisResponse,
    DataQualityWarning,
    ForecastOnlyResponse,
    HistoricalAnalysisResponse,
    SummaryResponse,
)
from .scenarios import run_scenario, scenario_result


def analyse_roi(request: AnalysisRequest) -> AnalysisResponse:
    historical = analyse_history(request)
    expected = run_scenario(request, request.scenarios.expected, include_timeline=True)
    conservative = run_scenario(request, request.scenarios.conservative)
    optimistic = run_scenario(request, request.scenarios.optimistic)

    warnings = list(historical.warnings)
    if request.revenue_forecast_mode == "energy_based":
        assumptions = expected.result.assumptions
        missing: list[str] = []
        if assumptions.tenant_rate_cents_per_kwh is None:
            missing.append("tenant solar rate")
        if assumptions.export_rate_cents_per_kwh is None:
            missing.append("export rate")
        if missing:
            warnings.append(
                DataQualityWarning(
                    code="MISSING_ENERGY_FORECAST_RATES",
                    message=(
                        "Energy-based forecasting has no "
                        + " or ".join(missing)
                        + "; the corresponding projected revenue is zero."
                    ),
                )
            )

    payload = historical.model_dump()
    payload["warnings"] = warnings
    return AnalysisResponse(
        **payload,
        forecast=expected.result,
        scenarios={
            "conservative": scenario_result(
                conservative, request.scenarios.conservative
            ),
            "expected": scenario_result(expected, request.scenarios.expected),
            "optimistic": scenario_result(optimistic, request.scenarios.optimistic),
        },
        forecast_months=expected.months,
    )


def build_summary(analysis: AnalysisResponse) -> SummaryResponse:
    return SummaryResponse(
        net_installation_cost_dollars=analysis.installation.net_installation_cost_dollars,
        capital_recovered_dollars=analysis.roi.capital_recovered_dollars,
        capital_recovered_percentage=analysis.roi.capital_recovered_percentage,
        remaining_cost_dollars=analysis.roi.remaining_cost_dollars,
        average_monthly_cashflow_dollars=analysis.historical_averages.monthly_cashflow_dollars,
        historical_self_consumption_percentage=(
            analysis.historical_performance.self_consumption_percentage
        ),
        historical_export_percentage=analysis.historical_performance.export_percentage,
        estimated_months_remaining=analysis.forecast.estimated_months_remaining,
        estimated_payback_date=analysis.forecast.estimated_payback_date,
        expected_payback_years=analysis.forecast.estimated_total_payback_years,
    )


def build_forecast_response(analysis: AnalysisResponse) -> ForecastOnlyResponse:
    return ForecastOnlyResponse(
        forecast=analysis.forecast,
        scenarios=analysis.scenarios,
        forecast_months=analysis.forecast_months,
        warnings=analysis.warnings,
    )


def build_history_response(request: AnalysisRequest) -> HistoricalAnalysisResponse:
    return analyse_history(request)
