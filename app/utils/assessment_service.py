from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status

from ..schemas.assessment import (
    AssessmentPricingResult,
    InitialAssessmentRequest,
    InitialAssessmentResponse,
    LandlordEconomics,
    TenantEconomics,
)
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


DEFAULT_INSTALLATION_COST_PER_KW = 1450.0
DEFAULT_GRID_RATE_CENTS_PER_KWH = 35.69
DEFAULT_EXPORT_RATE_CENTS_PER_KWH = 4.0

OCCUPANCY_SELF_CONSUMPTION = {
    "most": (0.45, 0.65, 0.80),
    "sometimes": (0.35, 0.55, 0.75),
    "rarely": (0.20, 0.40, 0.60),
}

INITIAL_ASSESSMENTS: dict[str, InitialAssessmentResponse] = {}


def create_initial_assessment(
    request: InitialAssessmentRequest,
) -> InitialAssessmentResponse:
    gross_cost = request.installation.gross_installation_cost_dollars
    installation_cost_source = "provided"
    if gross_cost is None:
        gross_cost = request.system.system_size_kw * DEFAULT_INSTALLATION_COST_PER_KW
        installation_cost_source = "model_default"

    grid_rate = (
        request.household.grid_rate_cents_per_kwh
        if request.household.grid_rate_cents_per_kwh is not None
        else DEFAULT_GRID_RATE_CENTS_PER_KWH
    )
    export_rate = (
        request.pricing.export_rate_cents_per_kwh
        if request.pricing.export_rate_cents_per_kwh is not None
        else DEFAULT_EXPORT_RATE_CENTS_PER_KWH
    )
    scr_min, scr_mode, scr_max = OCCUPANCY_SELF_CONSUMPTION[
        request.household.daytime_occupancy
    ]
    monthly_generation_weights = None
    if request.system.monthly_generation_kwh:
        generation_total = sum(request.system.monthly_generation_kwh)
        monthly_generation_weights = [
            value / generation_total for value in request.system.monthly_generation_kwh
        ]
    monthly_usage_weights = None
    if request.household.monthly_usage_kwh:
        usage_total = sum(request.household.monthly_usage_kwh)
        monthly_usage_weights = [
            value / usage_total for value in request.household.monthly_usage_kwh
        ]

    estimate_request = InitialEstimateRequest(
        installation=InstallationData(
            gross_installation_cost_dollars=gross_cost,
            stc_benefit_dollars=request.installation.stc_benefit_dollars,
            other_rebates_dollars=request.installation.other_rebates_dollars,
            installed_capacity_kw=request.system.system_size_kw,
        ),
        simulation=MonteCarloSimulationConfig(
            iterations=request.simulation.iterations,
            forecast_years=request.simulation.forecast_years,
            random_seed=request.simulation.random_seed,
        ),
        generation=InitialGenerationAssumptions(
            expected_annual_generation_kwh=request.system.expected_annual_generation_kwh,
            annual_variability_percentage=10,
            annual_panel_degradation_rate=0.005,
            monthly_generation_weights=monthly_generation_weights,
        ),
        tenant_demand=InitialTenantDemandAssumptions(
            expected_annual_usage_kwh=request.household.expected_annual_usage_kwh,
            annual_usage_variability_percentage=15,
            monthly_usage_weights=monthly_usage_weights,
        ),
        solar_utilisation=InitialSolarUtilisationAssumptions(
            expected_self_consumption_ratio=scr_mode,
            minimum_self_consumption_ratio=scr_min,
            maximum_self_consumption_ratio=scr_max,
        ),
        pricing=InitialPricingAssumptions(
            pricing_mode=request.pricing.pricing_mode,
            grid_rate_cents_per_kwh=grid_rate,
            export_rate_cents_per_kwh=export_rate,
            fixed_tenant_solar_rate_cents_per_kwh=(
                request.pricing.fixed_tenant_solar_rate_cents_per_kwh
            ),
        ),
        costs=InitialCostAssumptions(
            annual_operating_cost_dollars=request.installation.annual_operating_cost_dollars
        ),
    )
    simulation = run_monte_carlo_roi(estimate_request)

    review_reasons: list[str] = []
    warnings = [warning.model_dump() for warning in simulation.warnings]
    if request.installation.stc_benefit_dollars == 0:
        warnings.append(
            {
                "code": "REBATE_NOT_INCLUDED",
                "message": "No STC benefit or rebate was supplied, so the estimate is conservative.",
            }
        )
    if installation_cost_source == "model_default":
        warnings.append(
            {
                "code": "INSTALLATION_COST_ESTIMATED",
                "message": "Installation cost uses the configurable $1,450 per kW model default until a quote is supplied.",
            }
        )
    if request.system.source in {"manual", "mock"}:
        review_reasons.append("Roof generation is based on manual or demonstration data.")
    if request.system.imagery_quality in {"MEDIUM", "BASE"}:
        review_reasons.append("Roof imagery quality requires confirmation before proposal acceptance.")

    probability_payback = 1 - simulation.probability_no_payback_within_horizon
    if (
        simulation.headline.median_first_year_tenant_savings_dollars <= 0
        or probability_payback < 0.5
    ):
        recommendation = "not_recommended"
    elif review_reasons:
        recommendation = "manual_review"
    else:
        recommendation = "viable"

    baseline_bill = request.household.current_annual_bill_dollars
    if baseline_bill is None:
        baseline_bill = request.household.expected_annual_usage_kwh * grid_rate / 100

    assessment = InitialAssessmentResponse(
        id=str(uuid4()),
        created_at=datetime.now(timezone.utc),
        recommendation=recommendation,
        review_reasons=review_reasons,
        installation_cost_source=installation_cost_source,
        address=request.address,
        system=request.system,
        tenant_economics=TenantEconomics(
            baseline_annual_bill_dollars=round(baseline_bill, 2),
            projected_annual_electricity_cost_dollars=(
                simulation.financial_distribution.first_year_tenant_total_electricity_cost_dollars
            ),
            annual_savings_dollars=(
                simulation.financial_distribution.first_year_tenant_savings_dollars
            ),
            solar_share_ratio=simulation.energy_distribution.tenant_solar_share_ratio,
            probability_saves_money=simulation.headline.probability_tenant_saves_money,
        ),
        landlord_economics=LandlordEconomics(
            net_installation_cost_dollars=simulation.installation.net_installation_cost_dollars,
            first_year_net_cashflow_dollars=(
                simulation.financial_distribution.first_year_net_cashflow_dollars
            ),
            simple_annual_yield_percentage=(
                simulation.financial_distribution.first_year_simple_annual_yield_percentage
            ),
            median_payback_years=simulation.headline.median_payback_years,
            payback_range_years={
                "lower": simulation.forecast_interval.lower_payback_years,
                "upper": simulation.forecast_interval.upper_payback_years,
            },
            probability_payback_within_7_years=(
                simulation.probability_of_payback.within_7_years
            ),
            probability_payback_within_10_years=(
                simulation.probability_of_payback.within_10_years
            ),
        ),
        pricing=AssessmentPricingResult(
            mode=request.pricing.pricing_mode,
            tenant_solar_rate_cents_per_kwh=(
                simulation.financial_distribution.first_year_tenant_solar_rate_cents_per_kwh
            ),
            grid_rate_cents_per_kwh=grid_rate,
            export_rate_cents_per_kwh=export_rate,
            method=(
                "fixed tenant solar tariff"
                if request.pricing.pricing_mode == "fixed"
                else "usage-normalised approximation of the interval dynamic pricing function"
            ),
        ),
        monte_carlo=simulation,
        sizing=request.sizing,
        warnings=warnings,
    )
    INITIAL_ASSESSMENTS[assessment.id] = assessment
    return assessment


def get_initial_assessment(assessment_id: str) -> InitialAssessmentResponse:
    assessment = INITIAL_ASSESSMENTS.get(assessment_id)
    if assessment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Initial assessment not found",
        )
    return assessment
