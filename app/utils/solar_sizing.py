from __future__ import annotations

from ..schemas.sizing import (
    CandidateSizingResult,
    RoofSystemCandidate,
    SolarSizingRequest,
    SolarSizingResponse,
)
from .assessment_service import OCCUPANCY_SELF_CONSUMPTION
from .roi_engine.models import (
    InitialCostAssumptions,
    InitialEstimateRequest,
    InitialGenerationAssumptions,
    InitialPricingAssumptions,
    InitialSolarUtilisationAssumptions,
    InitialTenantDemandAssumptions,
    InstallationData,
    MonteCarloSimulationConfig,
)
from .roi_engine.monte_carlo import run_monte_carlo_roi


def _normalise(values: list[float]) -> list[float]:
    total = sum(values)
    if total <= 0:
        raise ValueError("profile total must be positive")
    return [value / total for value in values]


def _candidate_request(
    request: SolarSizingRequest,
    candidate: RoofSystemCandidate,
    annual_usage_kwh: float,
    usage_weights: list[float],
) -> InitialEstimateRequest:
    scr_min, scr_mode, scr_max = OCCUPANCY_SELF_CONSUMPTION[request.daytime_occupancy]
    generation_weights = (
        _normalise(candidate.monthly_generation_kwh)
        if candidate.monthly_generation_kwh
        else None
    )
    gross_cost = candidate.gross_installation_cost_dollars
    if gross_cost is None:
        gross_cost = candidate.system_size_kw * request.costs.installation_cost_per_kw

    return InitialEstimateRequest(
        installation=InstallationData(
            gross_installation_cost_dollars=gross_cost,
            stc_benefit_dollars=candidate.stc_benefit_dollars,
            other_rebates_dollars=candidate.other_rebates_dollars,
            installed_capacity_kw=candidate.system_size_kw,
        ),
        simulation=MonteCarloSimulationConfig(
            iterations=request.simulation.iterations,
            forecast_years=request.simulation.forecast_years,
            random_seed=request.simulation.random_seed,
        ),
        generation=InitialGenerationAssumptions(
            expected_annual_generation_kwh=candidate.annual_generation_kwh,
            annual_variability_percentage=10,
            annual_panel_degradation_rate=0.005,
            monthly_generation_weights=generation_weights,
        ),
        tenant_demand=InitialTenantDemandAssumptions(
            expected_annual_usage_kwh=annual_usage_kwh,
            annual_usage_variability_percentage=15,
            monthly_usage_weights=usage_weights,
        ),
        solar_utilisation=InitialSolarUtilisationAssumptions(
            expected_self_consumption_ratio=scr_mode,
            minimum_self_consumption_ratio=scr_min,
            maximum_self_consumption_ratio=scr_max,
        ),
        pricing=InitialPricingAssumptions(
            pricing_mode=request.pricing.pricing_mode,
            grid_rate_cents_per_kwh=request.pricing.grid_rate_cents_per_kwh,
            export_rate_cents_per_kwh=request.pricing.export_rate_cents_per_kwh,
            fixed_tenant_solar_rate_cents_per_kwh=(
                request.pricing.fixed_tenant_solar_rate_cents_per_kwh
            ),
        ),
        costs=InitialCostAssumptions(
            annual_operating_cost_dollars=request.costs.annual_operating_cost_dollars
        ),
    )


def recommend_solar_system(request: SolarSizingRequest) -> SolarSizingResponse:
    ordered_demand = sorted(request.monthly_demand, key=lambda item: item.calendar_month)
    monthly_usage = [item.usage_kwh for item in ordered_demand]
    annual_usage = sum(monthly_usage)
    if annual_usage <= 0:
        raise ValueError("annual household usage must be positive")
    usage_weights = _normalise(monthly_usage)

    candidates = sorted(
        request.candidates,
        key=lambda candidate: (candidate.panel_count, candidate.system_size_kw),
    )
    results: list[CandidateSizingResult] = []
    previous_cost: float | None = None
    previous_cashflow: float | None = None

    for candidate in candidates:
        simulation = run_monte_carlo_roi(
            _candidate_request(request, candidate, annual_usage, usage_weights)
        )
        energy = simulation.energy_distribution
        financial = simulation.financial_distribution
        median_generation = energy.first_year_generation_kwh.median
        median_consumed = energy.first_year_tenant_solar_consumption_kwh.median
        median_export = energy.first_year_export_kwh.median
        median_cashflow = financial.first_year_net_cashflow_dollars.median
        net_cost = simulation.installation.net_installation_cost_dollars
        probability_payback = 1 - simulation.probability_no_payback_within_horizon

        marginal_payback: float | None = None
        if previous_cost is None:
            if median_cashflow > 0:
                marginal_payback = net_cost / median_cashflow
        else:
            cashflow_gain = median_cashflow - (previous_cashflow or 0)
            cost_increase = net_cost - previous_cost
            if cost_increase <= 0:
                marginal_payback = 0
            elif cashflow_gain > 0:
                marginal_payback = cost_increase / cashflow_gain

        self_consumption_ratio = (
            median_consumed / median_generation if median_generation > 0 else 0
        )
        export_ratio = median_export / median_generation if median_generation > 0 else 0
        solar_coverage_ratio = median_consumed / annual_usage if annual_usage > 0 else 0
        reasons: list[str] = []
        constraints = request.constraints
        if (
            constraints.maximum_system_size_kw is not None
            and candidate.system_size_kw > constraints.maximum_system_size_kw
        ):
            reasons.append("System exceeds the configured maximum capacity.")
        if simulation.headline.probability_tenant_saves_money < constraints.minimum_probability_tenant_saves:
            reasons.append("Tenant savings probability is below the required threshold.")
        if probability_payback < constraints.minimum_probability_payback_within_horizon:
            reasons.append("Payback probability is below the required threshold.")
        if (
            simulation.headline.median_payback_years is None
            or simulation.headline.median_payback_years > constraints.maximum_median_payback_years
        ):
            reasons.append("Median payback exceeds the configured limit.")
        if export_ratio > constraints.maximum_export_ratio:
            reasons.append("Too much generation is expected to be exported rather than used onsite.")
        if (
            marginal_payback is None
            or marginal_payback > constraints.maximum_marginal_payback_years
        ):
            reasons.append("The additional panels do not recover their incremental cost quickly enough.")

        results.append(
            CandidateSizingResult(
                candidate_id=candidate.candidate_id,
                panel_count=candidate.panel_count,
                system_size_kw=candidate.system_size_kw,
                annual_generation_kwh=candidate.annual_generation_kwh,
                net_installation_cost_dollars=net_cost,
                median_tenant_solar_consumption_kwh=median_consumed,
                median_export_kwh=median_export,
                self_consumption_ratio=self_consumption_ratio,
                export_ratio=export_ratio,
                solar_coverage_ratio=solar_coverage_ratio,
                first_year_tenant_savings_dollars=financial.first_year_tenant_savings_dollars,
                first_year_net_cashflow_dollars=financial.first_year_net_cashflow_dollars,
                median_payback_years=simulation.headline.median_payback_years,
                payback_range_years={
                    "lower": simulation.forecast_interval.lower_payback_years,
                    "upper": simulation.forecast_interval.upper_payback_years,
                },
                probability_tenant_saves=simulation.headline.probability_tenant_saves_money,
                probability_payback_within_horizon=probability_payback,
                marginal_payback_years=marginal_payback,
                qualified=not reasons,
                rejection_reasons=reasons,
            )
        )
        previous_cost = net_cost
        previous_cashflow = median_cashflow

    qualified = [result for result in results if result.qualified]
    recommended: CandidateSizingResult | None
    if qualified:
        recommended = qualified[-1]
        status = "viable"
    else:
        payable = [result for result in results if result.median_payback_years is not None]
        recommended = min(payable, key=lambda item: item.median_payback_years) if payable else None
        status = "manual_review" if recommended else "not_recommended"

    roof_max = max(candidate.panel_count for candidate in candidates)
    warnings: list[dict[str, str]] = []
    if any(item.source != "observed_bill" for item in ordered_demand):
        warnings.append(
            {
                "code": "PARTLY_DERIVED_DEMAND_PROFILE",
                "message": "Some monthly demand values are survey-derived; confirm sizing after 12 months of meter data.",
            }
        )

    if recommended is None:
        reason = "No roof candidate produced positive payback within the forecast horizon."
    elif recommended.qualified:
        next_larger = next(
            (item for item in results if item.panel_count > recommended.panel_count), None
        )
        reason = (
            f"Recommend {recommended.panel_count} panels ({recommended.system_size_kw:.2f} kW): "
            f"about {recommended.solar_coverage_ratio:.0%} of annual demand is served directly, "
            f"{recommended.export_ratio:.0%} is exported, and median payback is "
            f"{recommended.median_payback_years:.1f} years."
        )
        if next_larger and next_larger.rejection_reasons:
            reason += f" The next larger option was rejected because {next_larger.rejection_reasons[0].lower()}"
    else:
        reason = (
            f"No candidate met every sizing guardrail. {recommended.panel_count} panels has the "
            "shortest simulated median payback and requires manual review."
        )

    return SolarSizingResponse(
        status=status,
        recommended_candidate_id=recommended.candidate_id if recommended else None,
        recommended_panel_count=recommended.panel_count if recommended else None,
        recommended_system_size_kw=recommended.system_size_kw if recommended else None,
        roof_maximum_panel_count=roof_max,
        annual_usage_kwh=annual_usage,
        monthly_usage_weights=usage_weights,
        recommendation_reason=reason,
        selection_method="monthly_demand_economic_candidate_simulation",
        alternatives=results,
        warnings=warnings,
    )
