"""Explainable calendar-month forecasting and month-by-month payback simulation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import fsum
from statistics import fmean

from .analytics import (
    SeasonalProfile,
    SeasonalValues,
    build_seasonal_profile,
    resolve_record,
)
from .config import PERFORMANCE_MONTHS_AFTER_HISTORICAL_PAYBACK
from .models import (
    AnalysisRequest,
    ForecastAssumptionsResult,
    ForecastMonth,
    ForecastResult,
    ScenarioMultipliers,
)
from .roi import (
    calculate_capital_recovery,
    calculate_monthly_cashflow,
    calculate_net_installation_cost,
    find_historical_payback_month,
)
from .utils import (
    add_months,
    calendar_months_between,
    circular_month_distance,
    month_key,
    month_start,
    round_currency,
    round_energy,
)


@dataclass(frozen=True)
class ForecastOutcome:
    result: ForecastResult
    months: list[ForecastMonth]


def _average_values(values: list[SeasonalValues]) -> SeasonalValues:
    return SeasonalValues(
        generation_kwh=fmean(value.generation_kwh for value in values),
        usage_kwh=fmean(value.usage_kwh for value in values),
        self_consumption_ratio=fmean(value.self_consumption_ratio for value in values),
        export_ratio=fmean(value.export_ratio for value in values),
        cashflow_dollars=fmean(value.cashflow_dollars for value in values),
        tenant_revenue_dollars=fmean(value.tenant_revenue_dollars for value in values),
        export_revenue_dollars=fmean(value.export_revenue_dollars for value in values),
        operating_cost_dollars=fmean(value.operating_cost_dollars for value in values),
    )


def seasonal_values_for_month(
    profile: SeasonalProfile, calendar_month: int
) -> tuple[SeasonalValues, str]:
    if calendar_month in profile.by_month:
        return profile.by_month[calendar_month], "calendar_month_average"
    nearby = [
        values
        for month, values in profile.by_month.items()
        if circular_month_distance(month, calendar_month) <= 2
    ]
    if nearby:
        return _average_values(nearby), "nearby_seasonal_average"
    return profile.overall, "overall_history_average_due_to_insufficient_history"


def forecast_monthly_generation(
    profile: SeasonalProfile,
    target_month: date,
    months_ahead: int,
    annual_degradation_rate: float,
    generation_multiplier: float = 1.0,
) -> tuple[float, str]:
    values, method = seasonal_values_for_month(profile, target_month.month)
    degradation = (1 - annual_degradation_rate) ** (months_ahead / 12)
    return values.generation_kwh * degradation * generation_multiplier, method


def _effective_rates(request: AnalysisRequest) -> tuple[float | None, float | None]:
    resolved = [resolve_record(record) for record in request.history]
    consumed = fsum(item.consumed_kwh for item in resolved)
    exported = fsum(item.source.solar_exported_kwh for item in resolved)
    tenant_revenue = fsum(item.source.tenant_revenue_dollars for item in resolved)
    export_revenue = fsum(item.source.export_revenue_dollars for item in resolved)
    tenant_rate = request.revenue_assumptions.tenant_solar_rate_cents_per_kwh
    export_rate = request.revenue_assumptions.export_rate_cents_per_kwh
    if tenant_rate is None:
        tenant_rate_weights = [
            (item.source.average_tenant_solar_rate_cents_per_kwh, item.consumed_kwh)
            for item in resolved
            if item.source.average_tenant_solar_rate_cents_per_kwh is not None
            and item.consumed_kwh > 0
        ]
        weighted_kwh = fsum(weight for _, weight in tenant_rate_weights)
        if weighted_kwh:
            tenant_rate = (
                fsum(rate * weight for rate, weight in tenant_rate_weights)
                / weighted_kwh
            )
        elif consumed:
            tenant_rate = tenant_revenue / consumed * 100
    if export_rate is None:
        export_rate_weights = [
            (
                item.source.average_export_rate_cents_per_kwh,
                item.source.solar_exported_kwh,
            )
            for item in resolved
            if item.source.average_export_rate_cents_per_kwh is not None
            and item.source.solar_exported_kwh > 0
        ]
        weighted_kwh = fsum(weight for _, weight in export_rate_weights)
        if weighted_kwh:
            export_rate = (
                fsum(rate * weight for rate, weight in export_rate_weights)
                / weighted_kwh
            )
        elif exported:
            export_rate = export_revenue / exported * 100
    return tenant_rate, export_rate


def _forecast_method(methods: set[str]) -> str:
    if methods == {"calendar_month_average"}:
        return "seasonal_calendar_month_average"
    if methods == {"overall_history_average_due_to_insufficient_history"}:
        return "overall_history_average_due_to_insufficient_history"
    if methods == {"nearby_seasonal_average"}:
        return "nearby_seasonal_average_due_to_insufficient_history"
    return "mixed_seasonal_with_fallback"


def _total_payback_months(
    installation_date: date | None,
    payback_month: date | None,
    fraction_in_month: float,
    historical: bool = False,
) -> float | None:
    if installation_date is None or payback_month is None:
        return None
    months = calendar_months_between(month_start(installation_date), payback_month)
    return float(months + (1.0 if historical else fraction_in_month))


def forecast_payback(
    request: AnalysisRequest,
    multipliers: ScenarioMultipliers,
    *,
    include_timeline: bool,
) -> ForecastOutcome:
    history = sorted(request.history, key=lambda item: item.month)
    net_cost = calculate_net_installation_cost(
        request.installation.gross_installation_cost_dollars,
        request.installation.stc_benefit_dollars,
        request.installation.other_rebates_dollars,
    )
    cashflows = [calculate_monthly_cashflow(record) for record in history]
    recovery = calculate_capital_recovery(net_cost, cashflows)
    historical_payback = find_historical_payback_month(net_cost, history)
    profile = build_seasonal_profile(history)
    tenant_rate, export_rate = _effective_rates(request)
    assumptions = request.forecast_assumptions
    start_month = add_months(history[-1].month, 1)

    immediate = net_cost == 0
    already_paid = immediate or recovery.recovered_dollars >= net_cost
    if already_paid:
        payback_month = (
            month_start(request.installation.installation_date)
            if immediate and request.installation.installation_date
            else historical_payback
        )
        fraction = 0.0 if immediate else 1.0
        total_months = (
            0.0
            if immediate
            else _total_payback_months(
                request.installation.installation_date,
                payback_month,
                fraction,
                historical=True,
            )
        )
        months_to_project = (
            PERFORMANCE_MONTHS_AFTER_HISTORICAL_PAYBACK if include_timeline else 0
        )
    else:
        payback_month = None
        fraction = 0.0
        total_months = None
        months_to_project = assumptions.forecast_horizon_months

    cumulative = recovery.recovered_dollars
    forecast_months: list[ForecastMonth] = []
    methods: set[str] = set()
    months_remaining: float | None = 0.0 if already_paid else None
    raw_projected_cashflows: list[float] = []

    for index in range(months_to_project):
        target = add_months(start_month, index)
        seasonal, method = seasonal_values_for_month(profile, target.month)
        methods.add(method)
        year_fraction = (index + 1) / 12
        degradation = (
            1 - assumptions.annual_generation_degradation_rate
        ) ** year_fraction
        generation = (
            seasonal.generation_kwh * degradation * multipliers.generation_multiplier
        )
        scr = min(
            max(
                seasonal.self_consumption_ratio
                * multipliers.self_consumption_multiplier,
                0.0,
            ),
            1.0,
        )
        consumed = generation * scr
        exported = max(generation - consumed, 0.0)
        tenant_growth = (1 + assumptions.annual_tenant_rate_growth) ** year_fraction
        export_growth = (1 + assumptions.annual_export_rate_growth) ** year_fraction
        cost_growth = (1 + assumptions.annual_operating_cost_growth) ** year_fraction

        if request.revenue_forecast_mode == "energy_based":
            tenant_revenue = (
                consumed
                * (tenant_rate or 0.0)
                * tenant_growth
                * multipliers.tenant_rate_multiplier
                / 100
            )
            export_revenue = exported * (export_rate or 0.0) * export_growth / 100
            operating_cost = (
                request.revenue_assumptions.annual_operating_cost_dollars
                / 12
                * cost_growth
                * multipliers.operating_cost_multiplier
            )
        else:
            generation_factor = degradation * multipliers.generation_multiplier
            tenant_share_factor = (
                scr / seasonal.self_consumption_ratio
                if seasonal.self_consumption_ratio
                else 0.0
            )
            export_share_factor = (
                (1 - scr) / seasonal.export_ratio if seasonal.export_ratio else 0.0
            )
            tenant_revenue = (
                seasonal.tenant_revenue_dollars
                * generation_factor
                * tenant_share_factor
                * tenant_growth
                * multipliers.tenant_rate_multiplier
            )
            export_revenue = (
                seasonal.export_revenue_dollars
                * generation_factor
                * export_share_factor
                * export_growth
            )
            operating_cost = (
                seasonal.operating_cost_dollars
                * cost_growth
                * multipliers.operating_cost_multiplier
            )

        net_cashflow = tenant_revenue + export_revenue - operating_cost
        raw_projected_cashflows.append(net_cashflow)
        entering_balance = net_cost - cumulative
        cumulative += net_cashflow
        remaining = max(net_cost - cumulative, 0.0)

        if (
            not already_paid
            and payback_month is None
            and net_cashflow > 0
            and cumulative >= net_cost
        ):
            fraction = min(max(entering_balance / net_cashflow, 0.0), 1.0)
            months_remaining = index + fraction
            payback_month = target
            total_months = _total_payback_months(
                request.installation.installation_date, target, fraction
            )

        if include_timeline:
            forecast_months.append(
                ForecastMonth(
                    month=month_key(target),
                    forecast_method=method,
                    projected_generation_kwh=round_energy(generation),
                    projected_solar_consumption_kwh=round_energy(consumed),
                    projected_export_kwh=round_energy(exported),
                    projected_tenant_revenue_dollars=round_currency(tenant_revenue),
                    projected_export_revenue_dollars=round_currency(export_revenue),
                    projected_operating_cost_dollars=round_currency(operating_cost),
                    projected_net_cashflow_dollars=round_currency(net_cashflow),
                    cumulative_recovered_capital_dollars=round_currency(cumulative),
                    remaining_cost_dollars=round_currency(remaining),
                )
            )
        if payback_month is not None and not already_paid:
            break

    method_summary = _forecast_method(methods) if methods else "forecast_not_required"
    if already_paid:
        payback_type = "immediate" if immediate else "historical"
        reason = None
    elif payback_month is not None:
        payback_type = "forecast"
        reason = None
    else:
        payback_type = "not_reached"
        average_projected = (
            fmean(raw_projected_cashflows) if raw_projected_cashflows else 0.0
        )
        reason = (
            "Projected net cash flow is insufficient to recover the remaining investment."
            if average_projected <= 0
            else "Payback not achieved within forecast horizon."
        )

    assumptions_result = ForecastAssumptionsResult(
        revenue_forecast_mode=request.revenue_forecast_mode,
        generation_forecast_method=method_summary,
        annual_panel_degradation_rate=assumptions.annual_generation_degradation_rate,
        annual_tenant_rate_growth=assumptions.annual_tenant_rate_growth,
        annual_export_rate_growth=assumptions.annual_export_rate_growth,
        annual_operating_cost_growth=assumptions.annual_operating_cost_growth,
        forecast_horizon_months=assumptions.forecast_horizon_months,
        tenant_rate_cents_per_kwh=round(tenant_rate, 4)
        if tenant_rate is not None
        else None,
        export_rate_cents_per_kwh=round(export_rate, 4)
        if export_rate is not None
        else None,
    )
    return ForecastOutcome(
        result=ForecastResult(
            method=method_summary,
            payback_reached=already_paid or payback_month is not None,
            payback_type=payback_type,
            estimated_months_remaining=round(months_remaining, 2)
            if months_remaining is not None
            else None,
            estimated_payback_date=month_key(payback_month) if payback_month else None,
            estimated_total_payback_months=round(total_months, 2)
            if total_months is not None
            else None,
            estimated_total_payback_years=round(total_months / 12, 2)
            if total_months is not None
            else None,
            reason=reason,
            assumptions=assumptions_result,
        ),
        months=forecast_months,
    )
