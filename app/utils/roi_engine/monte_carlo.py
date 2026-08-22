"""Assumption-based Monte Carlo ROI simulation with no FastAPI dependency."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .config import (
    DEFAULT_MONTHLY_GENERATION_WEIGHTS,
    DEFAULT_MONTHLY_USAGE_WEIGHTS,
    MONTE_CARLO_WARNING_THRESHOLDS,
)
from .distributions import (
    FloatArray,
    sample_triangular,
    sample_truncated_normal,
    spearman_rank_correlation,
    summarise_distribution,
)
from .models import (
    DataQualityWarning,
    ForecastInterval,
    ForecastRange,
    InitialEnergyDistribution,
    InitialEstimateAssumptionsResult,
    InitialEstimateHeadline,
    InitialEstimateRequest,
    InitialEstimateResponse,
    InitialFinancialDistribution,
    InitialInstallationResult,
    PaybackCdfPoint,
    PaybackHistogram,
    PaybackProbability,
    SensitivityResult,
    SimulationMetadata,
)
from .roi import calculate_net_installation_cost


@dataclass(frozen=True)
class SimulationYear:
    year: int
    generation_kwh: float
    tenant_usage_kwh: float
    self_consumption_ratio: float
    tenant_solar_consumption_kwh: float
    export_kwh: float
    grid_rate_cents_per_kwh: float
    export_rate_cents_per_kwh: float
    tenant_rate_cents_per_kwh: float
    grid_import_kwh: float
    tenant_total_electricity_cost_dollars: float
    tenant_savings_dollars: float
    tenant_revenue_dollars: float
    export_revenue_dollars: float
    operating_cost_dollars: float
    net_cashflow_dollars: float
    monthly_net_cashflows_dollars: tuple[float, ...]


@dataclass(frozen=True)
class SimulationPath:
    payback_months: float | None
    payback_reached: bool
    years: tuple[SimulationYear, ...]


@dataclass
class _SimulationArrays:
    payback_months: FloatArray
    first_generation: FloatArray
    first_usage: FloatArray
    first_self_consumption: FloatArray
    first_solar_consumption: FloatArray
    first_exports: FloatArray
    first_grid_imports: FloatArray
    first_solar_share: FloatArray
    first_grid_rate: FloatArray
    first_export_rate: FloatArray
    first_tenant_rate: FloatArray
    first_grid_cost: FloatArray
    first_tenant_total_cost: FloatArray
    first_tenant_savings: FloatArray
    first_operating_cost: FloatArray
    first_tenant_revenue: FloatArray
    first_export_revenue: FloatArray
    first_net_cashflow: FloatArray
    first_simple_annual_yield: FloatArray | None
    average_annual_cashflow: FloatArray
    cumulative_roi_percentage: FloatArray | None
    tariff_clamp_used: bool
    single_path_years: list[SimulationYear]


def calculate_usage_alpha(
    effective_usage_kwh: float | FloatArray,
    alpha_min: float,
    alpha_max: float,
    discount_sensitivity: float,
) -> float | FloatArray:
    values = np.asarray(effective_usage_kwh, dtype=np.float64)
    alpha = alpha_min + (alpha_max - alpha_min) * np.exp(-discount_sensitivity * values)
    alpha = np.clip(alpha, alpha_min, alpha_max)
    return float(alpha) if alpha.ndim == 0 else alpha


def calculate_dynamic_tenant_rate(
    export_rate: float | FloatArray,
    grid_rate: float | FloatArray,
    alpha: float | FloatArray,
) -> float | FloatArray:
    export_values = np.asarray(export_rate, dtype=np.float64)
    grid_values = np.asarray(grid_rate, dtype=np.float64)
    alpha_values = np.asarray(alpha, dtype=np.float64)
    rate = export_values + alpha_values * (grid_values - export_values)
    rate = np.minimum(np.maximum(rate, export_values), grid_values)
    return float(rate) if rate.ndim == 0 else rate


def _array(value: float | FloatArray) -> FloatArray:
    return np.asarray(value, dtype=np.float64)


def _sample_tariffs(
    rng: np.random.Generator,
    request: InitialEstimateRequest,
    year_index: int,
    iterations: int,
) -> tuple[FloatArray, FloatArray, bool]:
    pricing = request.pricing
    grid_mean = (
        pricing.grid_rate_cents_per_kwh
        * (1 + pricing.annual_grid_rate_growth) ** year_index
    )
    export_mean = (
        pricing.export_rate_cents_per_kwh
        * (1 + pricing.annual_export_rate_growth) ** year_index
    )
    grid_std = grid_mean * pricing.grid_rate_variability_percentage / 100
    export_std = export_mean * pricing.export_rate_variability_percentage / 100

    grid = _array(
        sample_truncated_normal(rng, grid_mean, grid_std, 0.0, size=iterations)
    )
    export = _array(
        sample_truncated_normal(rng, export_mean, export_std, 0.0, size=iterations)
    )
    invalid = export > grid
    attempts = 0
    while np.any(invalid) and attempts < 100:
        count = int(np.count_nonzero(invalid))
        grid[invalid] = _array(
            sample_truncated_normal(rng, grid_mean, grid_std, 0.0, size=count)
        )
        export[invalid] = _array(
            sample_truncated_normal(rng, export_mean, export_std, 0.0, size=count)
        )
        invalid = export > grid
        attempts += 1
    clamped = bool(np.any(invalid))
    if clamped:
        export[invalid] = grid[invalid]
    return grid, export, clamped


def _simulate_paths(
    request: InitialEstimateRequest,
    rng: np.random.Generator,
    iterations: int,
    *,
    collect_single_path: bool = False,
) -> _SimulationArrays:
    generation_assumptions = request.generation
    demand_assumptions = request.tenant_demand
    utilisation = request.solar_utilisation
    pricing = request.pricing
    costs = request.costs
    years = request.simulation.forecast_years
    generation_weights = np.asarray(
        generation_assumptions.monthly_generation_weights
        or DEFAULT_MONTHLY_GENERATION_WEIGHTS,
        dtype=np.float64,
    )
    usage_weights = np.asarray(
        demand_assumptions.monthly_usage_weights or DEFAULT_MONTHLY_USAGE_WEIGHTS,
        dtype=np.float64,
    )
    net_cost = calculate_net_installation_cost(
        request.installation.gross_installation_cost_dollars,
        request.installation.stc_benefit_dollars,
        request.installation.other_rebates_dollars,
    )

    structural_scr = _array(
        sample_triangular(
            rng,
            utilisation.minimum_self_consumption_ratio,
            utilisation.expected_self_consumption_ratio,
            utilisation.maximum_self_consumption_ratio,
            size=iterations,
        )
    )
    cumulative_cashflow = np.zeros(iterations, dtype=np.float64)
    total_cashflow = np.zeros(iterations, dtype=np.float64)
    payback_months = np.full(iterations, np.nan, dtype=np.float64)
    if net_cost == 0:
        payback_months.fill(0.0)

    first_generation = np.zeros(iterations)
    first_usage = np.zeros(iterations)
    first_actual_scr = np.zeros(iterations)
    first_consumed = np.zeros(iterations)
    first_exports = np.zeros(iterations)
    first_grid_imports = np.zeros(iterations)
    first_solar_share = np.zeros(iterations)
    first_grid_rate = np.zeros(iterations)
    first_export_rate = np.zeros(iterations)
    first_tenant_rate = np.zeros(iterations)
    first_grid_cost = np.zeros(iterations)
    first_tenant_total_cost = np.zeros(iterations)
    first_tenant_savings = np.zeros(iterations)
    first_operating_cost = np.zeros(iterations)
    first_tenant_revenue = np.zeros(iterations)
    first_export_revenue = np.zeros(iterations)
    first_net_cashflow = np.zeros(iterations)
    tariff_clamp_used = False
    single_path_years: list[SimulationYear] = []

    for year_index in range(years):
        generation_mean = (
            generation_assumptions.expected_annual_generation_kwh
            * (1 - generation_assumptions.annual_panel_degradation_rate) ** year_index
        )
        generation = _array(
            sample_truncated_normal(
                rng,
                generation_mean,
                generation_mean
                * generation_assumptions.annual_variability_percentage
                / 100,
                generation_mean * generation_assumptions.minimum_generation_multiplier,
                generation_mean * generation_assumptions.maximum_generation_multiplier,
                size=iterations,
            )
        )
        usage_mean = (
            demand_assumptions.expected_annual_usage_kwh
            * (1 + demand_assumptions.annual_usage_growth_rate) ** year_index
        )
        usage = _array(
            sample_truncated_normal(
                rng,
                usage_mean,
                usage_mean
                * demand_assumptions.annual_usage_variability_percentage
                / 100,
                0.0,
                size=iterations,
            )
        )
        grid_rate, export_rate, clamped = _sample_tariffs(
            rng, request, year_index, iterations
        )
        tariff_clamp_used |= clamped
        operating_cost = _array(
            sample_truncated_normal(
                rng,
                costs.annual_operating_cost_dollars,
                costs.annual_operating_cost_dollars
                * costs.annual_operating_cost_variability_percentage
                / 100,
                0.0,
                size=iterations,
            )
        )

        annual_consumed = np.zeros(iterations, dtype=np.float64)
        for month_index in range(12):
            month_generation = generation * generation_weights[month_index]
            month_usage = usage * usage_weights[month_index]
            annual_consumed += np.minimum(
                month_generation * structural_scr, month_usage
            )
        annual_exports = np.maximum(generation - annual_consumed, 0.0)
        annual_grid_imports = np.maximum(usage - annual_consumed, 0.0)
        actual_scr = np.divide(
            annual_consumed,
            generation,
            out=np.zeros_like(annual_consumed),
            where=generation > 0,
        )
        solar_share = np.divide(
            annual_consumed,
            usage,
            out=np.zeros_like(annual_consumed),
            where=usage > 0,
        )

        if pricing.pricing_mode == "fixed":
            tenant_rate = np.full(
                iterations,
                pricing.fixed_tenant_solar_rate_cents_per_kwh or 0.0,
                dtype=np.float64,
            )
        elif pricing.alpha_estimation_mode == "triangular":
            alpha = _array(
                sample_triangular(
                    rng,
                    pricing.alpha_min,
                    pricing.alpha_mode,
                    pricing.alpha_max,
                    size=iterations,
                )
            )
            tenant_rate = _array(
                calculate_dynamic_tenant_rate(export_rate, grid_rate, alpha)
            )
        else:
            if pricing.effective_solar_usage_kwh_per_interval is not None:
                effective_usage = np.full(
                    iterations,
                    pricing.effective_solar_usage_kwh_per_interval,
                    dtype=np.float64,
                )
            else:
                effective_usage = annual_consumed / (
                    365 * pricing.active_solar_use_hours_per_day
                )
            alpha = _array(
                calculate_usage_alpha(
                    effective_usage,
                    pricing.alpha_min,
                    pricing.alpha_max,
                    pricing.discount_sensitivity,
                )
            )
            tenant_rate = _array(
                calculate_dynamic_tenant_rate(export_rate, grid_rate, alpha)
            )

        annual_tenant_revenue = annual_consumed * tenant_rate / 100
        annual_export_revenue = annual_exports * export_rate / 100
        annual_grid_cost = annual_grid_imports * grid_rate / 100
        annual_tenant_total_cost = annual_grid_cost + annual_tenant_revenue
        annual_baseline_cost = usage * grid_rate / 100
        annual_tenant_savings = annual_baseline_cost - annual_tenant_total_cost
        annual_net_cashflow = (
            annual_tenant_revenue + annual_export_revenue - operating_cost
        )
        total_cashflow += annual_net_cashflow

        single_monthly_cashflows: list[float] = []
        for month_index in range(12):
            month_generation = generation * generation_weights[month_index]
            month_usage = usage * usage_weights[month_index]
            month_consumed = np.minimum(month_generation * structural_scr, month_usage)
            month_exports = np.maximum(month_generation - month_consumed, 0.0)
            month_cashflow = (
                month_consumed * tenant_rate / 100
                + month_exports * export_rate / 100
                - operating_cost / 12
            )
            entering_balance = net_cost - cumulative_cashflow
            newly_reached = (
                np.isnan(payback_months)
                & (month_cashflow > 0)
                & (cumulative_cashflow + month_cashflow >= net_cost)
            )
            if np.any(newly_reached):
                fraction = np.clip(
                    entering_balance[newly_reached] / month_cashflow[newly_reached],
                    0.0,
                    1.0,
                )
                payback_months[newly_reached] = year_index * 12 + month_index + fraction
            cumulative_cashflow += month_cashflow
            if collect_single_path:
                single_monthly_cashflows.append(float(month_cashflow[0]))

        if year_index == 0:
            first_generation = generation.copy()
            first_usage = usage.copy()
            first_actual_scr = actual_scr.copy()
            first_consumed = annual_consumed.copy()
            first_exports = annual_exports.copy()
            first_grid_imports = annual_grid_imports.copy()
            first_solar_share = solar_share.copy()
            first_grid_rate = grid_rate.copy()
            first_export_rate = export_rate.copy()
            first_tenant_rate = tenant_rate.copy()
            first_grid_cost = annual_grid_cost.copy()
            first_tenant_total_cost = annual_tenant_total_cost.copy()
            first_tenant_savings = annual_tenant_savings.copy()
            first_operating_cost = operating_cost.copy()
            first_tenant_revenue = annual_tenant_revenue.copy()
            first_export_revenue = annual_export_revenue.copy()
            first_net_cashflow = annual_net_cashflow.copy()

        if collect_single_path:
            single_path_years.append(
                SimulationYear(
                    year=year_index + 1,
                    generation_kwh=float(generation[0]),
                    tenant_usage_kwh=float(usage[0]),
                    self_consumption_ratio=float(actual_scr[0]),
                    tenant_solar_consumption_kwh=float(annual_consumed[0]),
                    export_kwh=float(annual_exports[0]),
                    grid_rate_cents_per_kwh=float(grid_rate[0]),
                    export_rate_cents_per_kwh=float(export_rate[0]),
                    tenant_rate_cents_per_kwh=float(tenant_rate[0]),
                    grid_import_kwh=float(annual_grid_imports[0]),
                    tenant_total_electricity_cost_dollars=float(annual_tenant_total_cost[0]),
                    tenant_savings_dollars=float(annual_tenant_savings[0]),
                    tenant_revenue_dollars=float(annual_tenant_revenue[0]),
                    export_revenue_dollars=float(annual_export_revenue[0]),
                    operating_cost_dollars=float(operating_cost[0]),
                    net_cashflow_dollars=float(annual_net_cashflow[0]),
                    monthly_net_cashflows_dollars=tuple(single_monthly_cashflows),
                )
            )

    cumulative_roi = (
        (total_cashflow - net_cost) / net_cost * 100 if net_cost > 0 else None
    )
    return _SimulationArrays(
        payback_months=payback_months,
        first_generation=first_generation,
        first_usage=first_usage,
        first_self_consumption=first_actual_scr,
        first_solar_consumption=first_consumed,
        first_exports=first_exports,
        first_grid_imports=first_grid_imports,
        first_solar_share=first_solar_share,
        first_grid_rate=first_grid_rate,
        first_export_rate=first_export_rate,
        first_tenant_rate=first_tenant_rate,
        first_grid_cost=first_grid_cost,
        first_tenant_total_cost=first_tenant_total_cost,
        first_tenant_savings=first_tenant_savings,
        first_operating_cost=first_operating_cost,
        first_tenant_revenue=first_tenant_revenue,
        first_export_revenue=first_export_revenue,
        first_net_cashflow=first_net_cashflow,
        first_simple_annual_yield=(
            first_net_cashflow / net_cost * 100 if net_cost > 0 else None
        ),
        average_annual_cashflow=total_cashflow / years,
        cumulative_roi_percentage=cumulative_roi,
        tariff_clamp_used=tariff_clamp_used,
        single_path_years=single_path_years,
    )


def simulate_single_investment_path(
    rng: np.random.Generator,
    request: InitialEstimateRequest,
    forecast_years: int | None = None,
) -> SimulationPath:
    """Simulate one inspectable path without constructing API response models."""
    if forecast_years is not None:
        request = request.model_copy(
            update={
                "simulation": request.simulation.model_copy(
                    update={"forecast_years": forecast_years}
                )
            }
        )
    arrays = _simulate_paths(request, rng, 1, collect_single_path=True)
    payback = arrays.payback_months[0]
    return SimulationPath(
        payback_months=float(payback) if np.isfinite(payback) else None,
        payback_reached=bool(np.isfinite(payback)),
        years=tuple(arrays.single_path_years),
    )


def _warnings(
    request: InitialEstimateRequest,
    probability_no_payback: float,
    tariff_clamp_used: bool,
) -> list[DataQualityWarning]:
    thresholds = MONTE_CARLO_WARNING_THRESHOLDS
    warnings: list[DataQualityWarning] = []
    if (
        request.generation.annual_variability_percentage
        > thresholds["very_high_variability_percentage"]
    ):
        warnings.append(
            DataQualityWarning(
                code="VERY_HIGH_GENERATION_UNCERTAINTY",
                message="Generation variability exceeds 30%, producing a wide forecast range.",
            )
        )
    if (
        request.tenant_demand.annual_usage_variability_percentage
        > thresholds["very_high_variability_percentage"]
    ):
        warnings.append(
            DataQualityWarning(
                code="VERY_HIGH_USAGE_UNCERTAINTY",
                message="Tenant usage variability exceeds 30%, producing a wide forecast range.",
            )
        )
    utilisation = request.solar_utilisation
    if (
        utilisation.maximum_self_consumption_ratio
        - utilisation.minimum_self_consumption_ratio
        > thresholds["wide_self_consumption_range"]
    ):
        warnings.append(
            DataQualityWarning(
                code="WIDE_SELF_CONSUMPTION_RANGE",
                message="The assumed self-consumption range is wide, so payback uncertainty is substantial.",
            )
        )
    if (
        utilisation.expected_self_consumption_ratio
        < thresholds["low_expected_self_consumption"]
    ):
        warnings.append(
            DataQualityWarning(
                code="LOW_EXPECTED_SELF_CONSUMPTION",
                message="Low expected tenant solar consumption increases reliance on export revenue.",
            )
        )
    pricing = request.pricing
    if (
        pricing.grid_rate_cents_per_kwh > 0
        and pricing.export_rate_cents_per_kwh / pricing.grid_rate_cents_per_kwh
        >= thresholds["export_to_grid_rate_ratio"]
    ):
        warnings.append(
            DataQualityWarning(
                code="EXPORT_RATE_CLOSE_TO_GRID_RATE",
                message="The export tariff is close to the grid tariff, leaving little dynamic-pricing spread.",
            )
        )
    if probability_no_payback > thresholds["many_no_payback_probability"]:
        warnings.append(
            DataQualityWarning(
                code="PAYBACK_NOT_REACHED_IN_MANY_SIMULATIONS",
                message="More than 25% of simulated outcomes did not pay back within the forecast horizon.",
            )
        )
    if tariff_clamp_used:
        warnings.append(
            DataQualityWarning(
                code="TARIFF_SAMPLES_CLAMPED",
                message="Rare tariff samples could not be resampled within constraints and were clamped so export did not exceed grid price.",
            )
        )
    net_cost = calculate_net_installation_cost(
        request.installation.gross_installation_cost_dollars,
        request.installation.stc_benefit_dollars,
        request.installation.other_rebates_dollars,
    )
    if net_cost == 0:
        warnings.append(
            DataQualityWarning(
                code="ZERO_NET_INSTALLATION_COST",
                message="Net installation cost is zero; payback is immediate and cumulative ROI percentage is undefined.",
            )
        )
    return warnings


def _sensitivity(
    arrays: _SimulationArrays, forecast_years: int
) -> list[SensitivityResult]:
    payback_for_ranking = np.where(
        np.isfinite(arrays.payback_months),
        arrays.payback_months,
        forecast_years * 12 + 12,
    )
    inputs = {
        "annual_generation_kwh": arrays.first_generation,
        "tenant_usage_kwh": arrays.first_usage,
        "self_consumption_ratio": arrays.first_self_consumption,
        "grid_tariff_cents_per_kwh": arrays.first_grid_rate,
        "export_tariff_cents_per_kwh": arrays.first_export_rate,
        "annual_operating_cost_dollars": arrays.first_operating_cost,
    }
    results: list[SensitivityResult] = []
    for variable, values in inputs.items():
        correlation = spearman_rank_correlation(values, payback_for_ranking)
        direction = (
            "Higher values tend to shorten payback."
            if correlation < 0
            else "Higher values tend to lengthen payback."
            if correlation > 0
            else "No rank association was detected under these assumptions."
        )
        results.append(
            SensitivityResult(
                variable=variable,
                correlation_with_payback=round(correlation, 4),
                absolute_influence=round(abs(correlation), 4),
                interpretation=direction,
            )
        )
    return sorted(results, key=lambda item: item.absolute_influence, reverse=True)


def run_monte_carlo_roi(request: InitialEstimateRequest) -> InitialEstimateResponse:
    """Run and summarise an assumption-based initial ROI simulation."""
    rng = np.random.default_rng(request.simulation.random_seed)
    arrays = _simulate_paths(request, rng, request.simulation.iterations)
    iterations = request.simulation.iterations
    reached_mask: NDArray[np.bool_] = np.isfinite(arrays.payback_months)
    reached_count = int(np.count_nonzero(reached_mask))
    reached_years = arrays.payback_months[reached_mask] / 12
    probability_no_payback = 1 - reached_count / iterations
    payback_summary = (
        summarise_distribution(reached_years, 2) if reached_count else None
    )

    def payback_probability(years: int) -> float:
        return round(
            float(np.count_nonzero(arrays.payback_months <= years * 12)) / iterations,
            4,
        )

    if reached_count:
        bin_count = min(20, max(5, int(np.sqrt(reached_count))))
        counts, edges = np.histogram(reached_years, bins=bin_count)
        centers = (edges[:-1] + edges[1:]) / 2
        histogram = PaybackHistogram(
            bins_years=[round(float(value), 2) for value in centers],
            counts=[int(value) for value in counts],
        )
    else:
        histogram = PaybackHistogram(bins_years=[], counts=[])

    cdf = [
        PaybackCdfPoint(
            years=year,
            probability=payback_probability(year),
        )
        for year in range(1, request.simulation.forecast_years + 1)
    ]
    total_revenue = arrays.first_tenant_revenue + arrays.first_export_revenue
    net_cost = calculate_net_installation_cost(
        request.installation.gross_installation_cost_dollars,
        request.installation.stc_benefit_dollars,
        request.installation.other_rebates_dollars,
    )
    generation_weights = list(
        request.generation.monthly_generation_weights
        or DEFAULT_MONTHLY_GENERATION_WEIGHTS
    )
    usage_weights = list(
        request.tenant_demand.monthly_usage_weights or DEFAULT_MONTHLY_USAGE_WEIGHTS
    )
    alpha_normalisation = (
        f"direct override of {request.pricing.effective_solar_usage_kwh_per_interval} kWh per interval"
        if request.pricing.effective_solar_usage_kwh_per_interval is not None
        else (
            "annual tenant solar consumption divided by 365 days and "
            f"{request.pricing.active_solar_use_hours_per_day:g} active solar-use hours per day"
        )
    )

    return InitialEstimateResponse(
        forecast_source="assumption_based",
        simulation=SimulationMetadata(
            iterations=iterations,
            forecast_years=request.simulation.forecast_years,
            random_seed=request.simulation.random_seed,
            payback_reached_iterations=reached_count,
        ),
        installation=InitialInstallationResult(
            gross_installation_cost_dollars=round(
                request.installation.gross_installation_cost_dollars, 2
            ),
            stc_benefit_dollars=round(request.installation.stc_benefit_dollars, 2),
            other_rebates_dollars=round(request.installation.other_rebates_dollars, 2),
            net_installation_cost_dollars=round(net_cost, 2),
            installed_capacity_kw=request.installation.installed_capacity_kw,
        ),
        headline=InitialEstimateHeadline(
            median_payback_years=payback_summary.median if payback_summary else None,
            mean_payback_years=payback_summary.mean if payback_summary else None,
            median_first_year_tenant_savings_dollars=float(
                np.median(arrays.first_tenant_savings)
            ),
            probability_tenant_saves_money=round(
                float(np.count_nonzero(arrays.first_tenant_savings > 0)) / iterations,
                4,
            ),
            forecast_payback_range_years=ForecastRange(
                lower=payback_summary.p05 if payback_summary else None,
                upper=payback_summary.p95 if payback_summary else None,
            ),
            probability_payback_within_7_years=payback_probability(7),
        ),
        payback_distribution_years=payback_summary,
        forecast_interval=ForecastInterval(
            lower_payback_years=payback_summary.p05 if payback_summary else None,
            upper_payback_years=payback_summary.p95 if payback_summary else None,
        ),
        probability_of_payback=PaybackProbability(
            within_5_years=payback_probability(5),
            within_7_years=payback_probability(7),
            within_10_years=payback_probability(10),
            within_15_years=payback_probability(15),
        ),
        probability_no_payback_within_horizon=round(probability_no_payback, 4),
        energy_distribution=InitialEnergyDistribution(
            first_year_generation_kwh=summarise_distribution(
                arrays.first_generation, 2
            ),
            first_year_tenant_usage_kwh=summarise_distribution(arrays.first_usage, 2),
            self_consumption_ratio=summarise_distribution(
                arrays.first_self_consumption, 4
            ),
            first_year_tenant_solar_consumption_kwh=summarise_distribution(
                arrays.first_solar_consumption, 2
            ),
            first_year_export_kwh=summarise_distribution(arrays.first_exports, 2),
            first_year_grid_import_kwh=summarise_distribution(
                arrays.first_grid_imports, 2
            ),
            tenant_solar_share_ratio=summarise_distribution(
                arrays.first_solar_share, 4
            ),
        ),
        financial_distribution=InitialFinancialDistribution(
            first_year_tenant_solar_rate_cents_per_kwh=summarise_distribution(
                arrays.first_tenant_rate, 4
            ),
            first_year_tenant_revenue_dollars=summarise_distribution(
                arrays.first_tenant_revenue, 2
            ),
            first_year_export_revenue_dollars=summarise_distribution(
                arrays.first_export_revenue, 2
            ),
            first_year_total_revenue_dollars=summarise_distribution(total_revenue, 2),
            first_year_grid_cost_dollars=summarise_distribution(
                arrays.first_grid_cost, 2
            ),
            first_year_tenant_total_electricity_cost_dollars=summarise_distribution(
                arrays.first_tenant_total_cost, 2
            ),
            first_year_tenant_savings_dollars=summarise_distribution(
                arrays.first_tenant_savings, 2
            ),
            first_year_operating_cost_dollars=summarise_distribution(
                arrays.first_operating_cost, 2
            ),
            first_year_net_cashflow_dollars=summarise_distribution(
                arrays.first_net_cashflow, 2
            ),
            first_year_simple_annual_yield_percentage=(
                summarise_distribution(arrays.first_simple_annual_yield, 2)
                if arrays.first_simple_annual_yield is not None
                else None
            ),
            average_annual_net_cashflow_dollars=summarise_distribution(
                arrays.average_annual_cashflow, 2
            ),
            cumulative_roi_percentage=summarise_distribution(
                arrays.cumulative_roi_percentage, 2
            )
            if arrays.cumulative_roi_percentage is not None
            else None,
        ),
        sensitivity=_sensitivity(arrays, request.simulation.forecast_years),
        payback_histogram=histogram,
        payback_cdf=cdf,
        assumptions=InitialEstimateAssumptionsResult(
            generation_distribution="bounded_truncated_normal",
            usage_distribution="non_negative_truncated_normal",
            self_consumption_distribution="triangular",
            tariff_distribution="fixed_or_non_negative_truncated_normal",
            operating_cost_distribution="non_negative_truncated_normal",
            expected_annual_generation_kwh=request.generation.expected_annual_generation_kwh,
            generation_variability_percentage=request.generation.annual_variability_percentage,
            generation_bounds_multipliers=[
                request.generation.minimum_generation_multiplier,
                request.generation.maximum_generation_multiplier,
            ],
            monthly_generation_weights=generation_weights,
            expected_annual_usage_kwh=request.tenant_demand.expected_annual_usage_kwh,
            usage_variability_percentage=request.tenant_demand.annual_usage_variability_percentage,
            monthly_usage_weights=usage_weights,
            self_consumption_minimum=request.solar_utilisation.minimum_self_consumption_ratio,
            self_consumption_mode=request.solar_utilisation.expected_self_consumption_ratio,
            self_consumption_maximum=request.solar_utilisation.maximum_self_consumption_ratio,
            pricing_mode=request.pricing.pricing_mode,
            alpha_estimation_mode=request.pricing.alpha_estimation_mode,
            alpha_usage_normalisation=alpha_normalisation,
            annual_panel_degradation_rate=request.generation.annual_panel_degradation_rate,
            annual_usage_growth_rate=request.tenant_demand.annual_usage_growth_rate,
            annual_grid_rate_growth=request.pricing.annual_grid_rate_growth,
            annual_export_rate_growth=request.pricing.annual_export_rate_growth,
            grid_rate_cents_per_kwh=request.pricing.grid_rate_cents_per_kwh,
            export_rate_cents_per_kwh=request.pricing.export_rate_cents_per_kwh,
            annual_operating_cost_dollars=request.costs.annual_operating_cost_dollars,
        ),
        warnings=_warnings(request, probability_no_payback, arrays.tariff_clamp_used),
    )
