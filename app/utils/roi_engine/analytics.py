"""Historical energy, revenue, seasonality, trend, and data-quality analytics."""

from __future__ import annotations

import calendar
from collections import defaultdict
from dataclasses import dataclass
from math import fsum
from statistics import fmean

from .models import (
    AnalysisRequest,
    CapitalRecoveryPoint,
    DataQualityWarning,
    ExportOpportunity,
    HistoricalAnalysisResponse,
    HistoricalAverages,
    HistoricalPerformance,
    InstallationAnalysis,
    MonthlyHistoryResult,
    MonthlySolarRecord,
    MonthlySpecificYield,
    RevenueMetrics,
    RoiMetrics,
    SeasonalMetric,
    SpecificYieldAnalysis,
    TenantSavingsAnalysis,
    TrendMetric,
    YearOverYearComparison,
)
from .roi import (
    calculate_capital_recovery,
    calculate_export_ratio,
    calculate_monthly_cashflow,
    calculate_net_installation_cost,
    calculate_self_consumption_ratio,
)
from .utils import (
    add_months,
    month_key,
    round_currency,
    round_energy,
    round_percentage,
    round_ratio,
    safe_percentage_change,
)


@dataclass(frozen=True)
class ResolvedRecord:
    source: MonthlySolarRecord
    consumed_kwh: float
    consumption_source: str
    cashflow: float
    self_consumption_ratio: float | None
    export_ratio: float | None


@dataclass(frozen=True)
class SeasonalValues:
    generation_kwh: float
    usage_kwh: float
    self_consumption_ratio: float
    export_ratio: float
    cashflow_dollars: float
    tenant_revenue_dollars: float
    export_revenue_dollars: float
    operating_cost_dollars: float


@dataclass(frozen=True)
class SeasonalProfile:
    by_month: dict[int, SeasonalValues]
    overall: SeasonalValues
    counts: dict[int, int]


def resolve_record(record: MonthlySolarRecord) -> ResolvedRecord:
    supplied = record.solar_consumed_by_tenant_kwh
    consumed = (
        supplied
        if supplied is not None
        else max(record.solar_generation_kwh - record.solar_exported_kwh, 0.0)
    )
    return ResolvedRecord(
        source=record,
        consumed_kwh=consumed,
        consumption_source="explicit" if supplied is not None else "derived",
        cashflow=calculate_monthly_cashflow(record),
        self_consumption_ratio=calculate_self_consumption_ratio(
            record.solar_generation_kwh, consumed
        ),
        export_ratio=calculate_export_ratio(
            record.solar_generation_kwh, record.solar_exported_kwh
        ),
    )


def _mean_optional(values: list[float | None], fallback: float = 0.0) -> float:
    present = [value for value in values if value is not None]
    return fmean(present) if present else fallback


def _seasonal_values(records: list[ResolvedRecord]) -> SeasonalValues:
    return SeasonalValues(
        generation_kwh=fmean(item.source.solar_generation_kwh for item in records),
        usage_kwh=fmean(item.source.total_usage_kwh for item in records),
        self_consumption_ratio=_mean_optional(
            [item.self_consumption_ratio for item in records]
        ),
        export_ratio=_mean_optional([item.export_ratio for item in records]),
        cashflow_dollars=fmean(item.cashflow for item in records),
        tenant_revenue_dollars=fmean(
            item.source.tenant_revenue_dollars for item in records
        ),
        export_revenue_dollars=fmean(
            item.source.export_revenue_dollars for item in records
        ),
        operating_cost_dollars=fmean(
            item.source.operating_cost_dollars for item in records
        ),
    )


def build_seasonal_profile(history: list[MonthlySolarRecord]) -> SeasonalProfile:
    resolved = [
        resolve_record(record)
        for record in sorted(history, key=lambda item: item.month)
    ]
    grouped: dict[int, list[ResolvedRecord]] = defaultdict(list)
    for item in resolved:
        grouped[item.source.month.month].append(item)
    return SeasonalProfile(
        by_month={month: _seasonal_values(items) for month, items in grouped.items()},
        overall=_seasonal_values(resolved),
        counts={month: len(items) for month, items in grouped.items()},
    )


def _trend(values: list[float | None], tolerance: float) -> TrendMetric:
    usable = [value for value in values if value is not None]
    if len(usable) < 3:
        return TrendMetric(
            classification="insufficient_data",
            estimated_change_over_period_percentage=None,
        )
    x_mean = (len(usable) - 1) / 2
    y_mean = fmean(usable)
    denominator = fsum((index - x_mean) ** 2 for index in range(len(usable)))
    slope = (
        fsum((index - x_mean) * (value - y_mean) for index, value in enumerate(usable))
        / denominator
    )
    change_ratio = 0.0 if y_mean == 0 else slope * (len(usable) - 1) / abs(y_mean)
    if change_ratio > tolerance:
        classification = "increasing"
    elif change_ratio < -tolerance:
        classification = "decreasing"
    else:
        classification = "stable"
    return TrendMetric(
        classification=classification,
        estimated_change_over_period_percentage=round_percentage(change_ratio * 100),
    )


def _warnings(
    request: AnalysisRequest, records: list[ResolvedRecord]
) -> list[DataQualityWarning]:
    warnings: list[DataQualityWarning] = []
    count = len(records)
    if count < 6:
        warnings.append(
            DataQualityWarning(
                code="SHORT_HISTORY",
                message=f"Only {count} months of history were provided.",
            )
        )
    if count < 12:
        warnings.append(
            DataQualityWarning(
                code="INSUFFICIENT_SEASONAL_HISTORY",
                message=(
                    f"Only {count} months of history were provided. Nearby seasonal or "
                    "overall averages are used for missing calendar months."
                ),
            )
        )
    if any(item.consumption_source == "derived" for item in records):
        warnings.append(
            DataQualityWarning(
                code="DERIVED_SOLAR_CONSUMPTION",
                message="Missing tenant solar consumption was derived as generation minus exports.",
            )
        )
    for item in records:
        if (
            item.consumption_source != "explicit"
            or item.source.solar_generation_kwh == 0
        ):
            continue
        difference = (
            item.consumed_kwh
            + item.source.solar_exported_kwh
            - item.source.solar_generation_kwh
        )
        tolerance = item.source.solar_generation_kwh * request.meter_tolerance_ratio
        if difference > 0 and difference <= tolerance + 1e-9:
            warnings.append(
                DataQualityWarning(
                    code="METER_TOLERANCE_APPLIED",
                    message=f"{item.source.month:%Y-%m} exceeds the energy balance by {difference:.3f} kWh within the configured tolerance.",
                )
            )
        elif abs(difference) > tolerance:
            warnings.append(
                DataQualityWarning(
                    code="ENERGY_NOT_RECONCILED",
                    message=f"{item.source.month:%Y-%m} generation does not reconcile with consumption plus exports.",
                )
            )
    ordered = [item.source.month for item in records]
    expected = ordered[0]
    gaps: list[str] = []
    for actual in ordered:
        while expected < actual:
            gaps.append(month_key(expected))
            expected = add_months(expected, 1)
        expected = add_months(actual, 1)
    if gaps:
        warnings.append(
            DataQualityWarning(
                code="MISSING_MONTHS",
                message=f"Historical month gaps detected: {', '.join(gaps)}. Missing months were not fabricated.",
            )
        )
    if request.installation.installed_capacity_kw is None:
        warnings.append(
            DataQualityWarning(
                code="MISSING_INSTALLED_CAPACITY",
                message="Installed capacity is missing; specific yield is unavailable.",
            )
        )
    if fmean(item.cashflow for item in records) <= 0:
        warnings.append(
            DataQualityWarning(
                code="NON_POSITIVE_HISTORICAL_CASHFLOW",
                message="Average historical net cash flow is zero or negative.",
            )
        )
    if request.installation.installation_date and ordered[
        0
    ] < request.installation.installation_date.replace(day=1):
        warnings.append(
            DataQualityWarning(
                code="HISTORY_BEFORE_INSTALLATION",
                message="History contains a month before the supplied installation date.",
            )
        )
    if (
        calculate_net_installation_cost(
            request.installation.gross_installation_cost_dollars,
            request.installation.stc_benefit_dollars,
            request.installation.other_rebates_dollars,
        )
        == 0
    ):
        warnings.append(
            DataQualityWarning(
                code="ZERO_NET_INSTALLATION_COST",
                message="Net installation cost is zero; net ROI percentage is undefined and payback is immediate.",
            )
        )
    return warnings


def analyse_history(request: AnalysisRequest) -> HistoricalAnalysisResponse:
    records = [
        resolve_record(item)
        for item in sorted(request.history, key=lambda item: item.month)
    ]
    net_cost = calculate_net_installation_cost(
        request.installation.gross_installation_cost_dollars,
        request.installation.stc_benefit_dollars,
        request.installation.other_rebates_dollars,
    )
    cashflows = [item.cashflow for item in records]
    recovery = calculate_capital_recovery(net_cost, cashflows)
    total_generation = fsum(item.source.solar_generation_kwh for item in records)
    total_consumed = fsum(item.consumed_kwh for item in records)
    total_exports = fsum(item.source.solar_exported_kwh for item in records)
    total_usage = fsum(item.source.total_usage_kwh for item in records)
    total_tenant_revenue = fsum(item.source.tenant_revenue_dollars for item in records)
    total_export_revenue = fsum(item.source.export_revenue_dollars for item in records)
    total_cost = fsum(item.source.operating_cost_dollars for item in records)
    total_cashflow = fsum(cashflows)
    scr = calculate_self_consumption_ratio(total_generation, total_consumed)
    export_ratio = calculate_export_ratio(total_generation, total_exports)

    cumulative = 0.0
    monthly: list[MonthlyHistoryResult] = []
    timeline: list[CapitalRecoveryPoint] = []
    capacity = request.installation.installed_capacity_kw
    for item in records:
        cumulative += item.cashflow
        specific = item.source.solar_generation_kwh / capacity if capacity else None
        monthly.append(
            MonthlyHistoryResult(
                month=month_key(item.source.month),
                total_usage_kwh=round_energy(item.source.total_usage_kwh),
                solar_generation_kwh=round_energy(item.source.solar_generation_kwh),
                solar_consumed_by_tenant_kwh=round_energy(item.consumed_kwh),
                solar_consumption_source=item.consumption_source,
                solar_exported_kwh=round_energy(item.source.solar_exported_kwh),
                tenant_revenue_dollars=round_currency(
                    item.source.tenant_revenue_dollars
                ),
                export_revenue_dollars=round_currency(
                    item.source.export_revenue_dollars
                ),
                operating_cost_dollars=round_currency(
                    item.source.operating_cost_dollars
                ),
                net_cashflow_dollars=round_currency(item.cashflow),
                self_consumption_ratio=round_ratio(item.self_consumption_ratio),
                export_ratio=round_ratio(item.export_ratio),
                specific_yield_kwh_per_kw=round_energy(specific),
            )
        )
        timeline.append(
            CapitalRecoveryPoint(
                month=month_key(item.source.month),
                cumulative_cashflow_dollars=round_currency(cumulative),
                remaining_cost_dollars=round_currency(max(net_cost - cumulative, 0.0)),
            )
        )

    profile = build_seasonal_profile(request.history)
    seasonality = [
        SeasonalMetric(
            calendar_month=month,
            month_name=calendar.month_name[month],
            observations=profile.counts[month],
            average_generation_kwh=round_energy(values.generation_kwh),
            average_tenant_usage_kwh=round_energy(values.usage_kwh),
            average_self_consumption_ratio=round_ratio(values.self_consumption_ratio),
            average_export_ratio=round_ratio(values.export_ratio),
            average_cashflow_dollars=round_currency(values.cashflow_dollars),
        )
        for month, values in sorted(profile.by_month.items())
    ]

    specific_values = (
        [
            MonthlySpecificYield(
                month=month_key(item.source.month),
                specific_yield_kwh_per_kw=round_energy(
                    item.source.solar_generation_kwh / capacity
                ),
            )
            for item in records
        ]
        if capacity
        else []
    )
    annualised_cashflow = total_cashflow / len(records) * 12
    sources = {item.consumption_source for item in records}
    source_label = next(iter(sources)) if len(sources) == 1 else "mixed"

    trends = {
        "solar_generation": _trend(
            [item.source.solar_generation_kwh for item in records],
            request.trend_tolerance_ratio,
        ),
        "specific_yield": _trend(
            [
                item.source.solar_generation_kwh / capacity if capacity else None
                for item in records
            ],
            request.trend_tolerance_ratio,
        ),
        "self_consumption_ratio": _trend(
            [item.self_consumption_ratio for item in records],
            request.trend_tolerance_ratio,
        ),
        "export_ratio": _trend(
            [item.export_ratio for item in records], request.trend_tolerance_ratio
        ),
        "monthly_net_cashflow": _trend(
            [item.cashflow for item in records], request.trend_tolerance_ratio
        ),
        "revenue_per_generated_kwh": _trend(
            [
                (
                    (
                        item.source.tenant_revenue_dollars
                        + item.source.export_revenue_dollars
                    )
                    / item.source.solar_generation_kwh
                )
                if item.source.solar_generation_kwh
                else None
                for item in records
            ],
            request.trend_tolerance_ratio,
        ),
    }

    grouped: dict[int, list[ResolvedRecord]] = defaultdict(list)
    for item in records:
        grouped[item.source.month.month].append(item)
    yoy: list[YearOverYearComparison] = []
    for month, items in sorted(grouped.items()):
        if len(items) < 2:
            continue
        previous, current = items[-2], items[-1]
        if previous.source.month.year == current.source.month.year:
            continue
        yoy.append(
            YearOverYearComparison(
                calendar_month=month,
                month_name=calendar.month_name[month],
                previous_year=previous.source.month.year,
                current_year=current.source.month.year,
                generation_change_percentage=round_percentage(
                    safe_percentage_change(
                        previous.source.solar_generation_kwh,
                        current.source.solar_generation_kwh,
                    )
                ),
                cashflow_change_percentage=round_percentage(
                    safe_percentage_change(previous.cashflow, current.cashflow)
                ),
                self_consumption_change_percentage=round_percentage(
                    safe_percentage_change(
                        previous.self_consumption_ratio or 0.0,
                        current.self_consumption_ratio or 0.0,
                    )
                ),
            )
        )

    potential_rate = request.revenue_assumptions.potential_tenant_rate_cents_per_kwh
    effective_export_rate = (
        total_export_revenue / total_exports * 100 if total_exports else None
    )
    opportunity = None
    if potential_rate is not None:
        value = (
            None
            if effective_export_rate is None
            else max(
                total_exports * (potential_rate - effective_export_rate) / 100, 0.0
            )
        )
        opportunity = ExportOpportunity(
            exported_energy_kwh=round_energy(total_exports),
            assumed_tenant_rate_cents_per_kwh=round(potential_rate, 4),
            effective_export_rate_cents_per_kwh=round(effective_export_rate, 4)
            if effective_export_rate is not None
            else None,
            maximum_theoretical_export_conversion_value_dollars=round_currency(value),
            qualification="Maximum theoretical value only; coincident tenant demand is not established.",
        )

    baseline = 0.0
    actual = 0.0
    savings_available = True
    assumed_grid_rate = request.revenue_assumptions.average_grid_rate_cents_per_kwh
    for item in records:
        grid_rate = (
            item.source.average_grid_rate_cents_per_kwh
            if item.source.average_grid_rate_cents_per_kwh is not None
            else assumed_grid_rate
        )
        if grid_rate is None or item.source.actual_grid_cost_dollars is None:
            savings_available = False
            break
        baseline += item.source.total_usage_kwh * grid_rate / 100
        actual += (
            item.source.actual_grid_cost_dollars + item.source.tenant_revenue_dollars
        )
    tenant_savings = (
        TenantSavingsAnalysis(
            baseline_grid_cost_dollars=round_currency(baseline),
            actual_electricity_cost_dollars=round_currency(actual),
            estimated_tenant_savings_dollars=round_currency(baseline - actual),
        )
        if savings_available
        else None
    )

    return HistoricalAnalysisResponse(
        installation=InstallationAnalysis(
            gross_installation_cost_dollars=round_currency(
                request.installation.gross_installation_cost_dollars
            ),
            stc_benefit_dollars=round_currency(
                request.installation.stc_benefit_dollars
            ),
            other_rebates_dollars=round_currency(
                request.installation.other_rebates_dollars
            ),
            net_installation_cost_dollars=round_currency(net_cost),
            installed_capacity_kw=request.installation.installed_capacity_kw,
            installation_date=request.installation.installation_date,
        ),
        historical_performance=HistoricalPerformance(
            months_observed=len(records),
            first_month=month_key(records[0].source.month),
            last_month=month_key(records[-1].source.month),
            total_usage_kwh=round_energy(total_usage),
            solar_generation_kwh=round_energy(total_generation),
            solar_consumed_by_tenant_kwh=round_energy(total_consumed),
            solar_consumption_source=source_label,
            solar_exported_kwh=round_energy(total_exports),
            self_consumption_ratio=round_ratio(scr),
            self_consumption_percentage=round_percentage(
                scr * 100 if scr is not None else None
            ),
            export_ratio=round_ratio(export_ratio),
            export_percentage=round_percentage(
                export_ratio * 100 if export_ratio is not None else None
            ),
            tenant_revenue_dollars=round_currency(total_tenant_revenue),
            export_revenue_dollars=round_currency(total_export_revenue),
            operating_cost_dollars=round_currency(total_cost),
            net_cashflow_dollars=round_currency(total_cashflow),
            average_annual_cashflow_dollars=round_currency(annualised_cashflow),
            simple_annual_yield_percentage=round_percentage(
                annualised_cashflow / net_cost * 100
            )
            if net_cost
            else None,
        ),
        roi=RoiMetrics(
            capital_recovered_dollars=round_currency(recovery.recovered_dollars),
            capital_recovered_percentage=round_percentage(
                recovery.capital_recovered_percentage
            ),
            remaining_cost_dollars=round_currency(recovery.remaining_dollars),
            net_roi_percentage=round_percentage(recovery.net_roi_percentage),
        ),
        historical_averages=HistoricalAverages(
            monthly_usage_kwh=round_energy(total_usage / len(records)),
            monthly_generation_kwh=round_energy(total_generation / len(records)),
            monthly_cashflow_dollars=round_currency(total_cashflow / len(records)),
        ),
        revenue_metrics=RevenueMetrics(
            revenue_per_generated_kwh_dollars=round(
                (total_tenant_revenue + total_export_revenue) / total_generation, 4
            )
            if total_generation
            else None,
            revenue_per_tenant_solar_kwh_dollars=round(
                total_tenant_revenue / total_consumed, 4
            )
            if total_consumed
            else None,
            export_revenue_per_kwh_dollars=round(
                total_export_revenue / total_exports, 4
            )
            if total_exports
            else None,
        ),
        specific_yield=SpecificYieldAnalysis(
            monthly=specific_values,
            average_monthly_kwh_per_kw=round_energy(
                total_generation / len(records) / capacity
            )
            if capacity
            else None,
            annualised_kwh_per_kw=round_energy(
                total_generation / len(records) * 12 / capacity
            )
            if capacity
            else None,
        ),
        seasonality=seasonality,
        trends=trends,
        year_over_year=yoy,
        export_opportunity=opportunity,
        tenant_savings=tenant_savings,
        monthly_history=monthly,
        capital_recovery_timeline=timeline,
        warnings=_warnings(request, records),
    )
