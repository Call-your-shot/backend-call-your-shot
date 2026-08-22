from __future__ import annotations

import math
from datetime import datetime
from zoneinfo import ZoneInfo

from ..schemas.pricing import BatchPricingRequest, BatchPricingResponse, BatchSummary, PricingResult

TIMEZONE = "Australia/Sydney"
TOU_GRID_RATES = [(0, 10, 35.69), (10, 14, 12.35), (14, 16, 35.69), (16, 20, 46.85), (20, 24, 35.69)]
TOU_EXPORT_RATES = [(0, 10, 4.0), (10, 14, 3.2), (14, 16, 6.0), (16, 20, 18.0), (20, 24, 4.0)]
DEFAULT_GRID_RATE = 35.69
DEFAULT_EXPORT_RATE = 4.0


def cents_to_dollars(cents: float) -> float:
    return cents / 100.0


def resolve_rate(timestamp: datetime, schedule: list[tuple[int, int, float]], fallback: float) -> float:
    local_dt = timestamp.astimezone(ZoneInfo(TIMEZONE))
    for start, end, rate in schedule:
        if start <= local_dt.hour < end:
            return rate
    return fallback


def resolve_grid_rate(timestamp: datetime) -> float:
    return resolve_rate(timestamp, TOU_GRID_RATES, DEFAULT_GRID_RATE)


def resolve_export_rate(timestamp: datetime) -> float:
    return resolve_rate(timestamp, TOU_EXPORT_RATES, DEFAULT_EXPORT_RATE)


def calculate_alpha(usage_kwh: float, alpha_min: float, alpha_max: float, sensitivity: float) -> float:
    return alpha_min + (alpha_max - alpha_min) * math.exp(-sensitivity * usage_kwh)


def calculate_dynamic_rate(
    usage_kwh: float,
    grid_rate: float,
    export_rate: float,
    alpha_min: float,
    alpha_max: float,
    sensitivity: float,
) -> tuple[float, float]:
    alpha = calculate_alpha(usage_kwh, alpha_min, alpha_max, sensitivity)
    solar_rate = export_rate + alpha * (grid_rate - export_rate)
    return max(export_rate, min(solar_rate, grid_rate)), alpha


def calculate_interval_price(
    usage_kwh: float,
    solar_available_kwh: float | None,
    timestamp: datetime,
    pricing_mode: str,
    grid_rate_override: float | None = None,
    export_rate_override: float | None = None,
    fixed_solar_rate: float = 22.0,
    alpha_min: float = 0.40,
    alpha_max: float = 0.75,
    discount_sensitivity: float = 0.50,
) -> PricingResult:
    grid_rate = grid_rate_override if grid_rate_override is not None else resolve_grid_rate(timestamp)
    export_rate = export_rate_override if export_rate_override is not None else resolve_export_rate(timestamp)

    if solar_available_kwh is None:
        solar_usage = usage_kwh
        grid_usage = 0.0
        solar_export = 0.0
    else:
        solar_usage = min(usage_kwh, solar_available_kwh)
        grid_usage = max(usage_kwh - solar_available_kwh, 0.0)
        solar_export = max(solar_available_kwh - solar_usage, 0.0)

    if pricing_mode == "fixed":
        solar_rate = fixed_solar_rate
        alpha = None
    else:
        if export_rate > grid_rate:
            raise ValueError("Export rate cannot exceed grid rate for dynamic tenant pricing.")
        solar_rate, alpha = calculate_dynamic_rate(solar_usage, grid_rate, export_rate, alpha_min, alpha_max, discount_sensitivity)

    solar_charge = cents_to_dollars(solar_usage * solar_rate)
    grid_charge = cents_to_dollars(grid_usage * grid_rate)
    total_charge = solar_charge + grid_charge
    baseline_cost = cents_to_dollars(usage_kwh * grid_rate)
    tenant_saving = baseline_cost - total_charge
    tenant_saving_pct = round(tenant_saving / baseline_cost * 100, 2) if baseline_cost > 0 else None
    export_value = cents_to_dollars(solar_usage * export_rate)
    actual_export_revenue = cents_to_dollars(solar_export * export_rate)

    return PricingResult(
        timestamp=timestamp,
        pricing_mode=pricing_mode,
        usage_kwh=round(usage_kwh, 4),
        solar_available_kwh=round(solar_available_kwh, 4) if solar_available_kwh is not None else None,
        solar_usage_kwh=round(solar_usage, 4),
        solar_export_kwh=round(solar_export, 4),
        grid_usage_kwh=round(grid_usage, 4),
        grid_rate_cents_per_kwh=round(grid_rate, 4),
        export_rate_cents_per_kwh=round(export_rate, 4),
        alpha=round(alpha, 4) if alpha is not None else None,
        solar_rate_cents_per_kwh=round(solar_rate, 4),
        solar_charge_dollars=round(solar_charge, 4),
        grid_charge_dollars=round(grid_charge, 4),
        total_charge_dollars=round(total_charge, 4),
        tenant_grid_cost_without_solar_dollars=round(baseline_cost, 4),
        tenant_saving_dollars=round(tenant_saving, 4),
        tenant_saving_percentage=tenant_saving_pct,
        landlord_export_value_dollars=round(export_value, 4),
        actual_export_revenue_dollars=round(actual_export_revenue, 4),
        landlord_total_revenue_dollars=round(solar_charge + actual_export_revenue, 4),
        landlord_additional_revenue_dollars=round(solar_charge - export_value, 4),
    )


def calculate_batch_price(request: BatchPricingRequest) -> BatchPricingResponse:
    intervals = [
        calculate_interval_price(
            usage_kwh=interval.usage_kwh,
            solar_available_kwh=interval.solar_available_kwh,
            timestamp=interval.timestamp,
            pricing_mode=request.pricing_mode,
            grid_rate_override=interval.grid_rate_cents_per_kwh,
            export_rate_override=interval.export_rate_cents_per_kwh,
            fixed_solar_rate=request.fixed_solar_rate_cents_per_kwh,
            alpha_min=request.alpha_min,
            alpha_max=request.alpha_max,
            discount_sensitivity=request.discount_sensitivity,
        )
        for interval in request.intervals
    ]
    baseline = sum(item.tenant_grid_cost_without_solar_dollars for item in intervals)
    tenant_saving = sum(item.tenant_saving_dollars for item in intervals)
    summary = BatchSummary(
        total_usage_kwh=round(sum(item.usage_kwh for item in intervals), 4),
        total_solar_usage_kwh=round(sum(item.solar_usage_kwh for item in intervals), 4),
        total_solar_export_kwh=round(sum(item.solar_export_kwh for item in intervals), 4),
        total_grid_usage_kwh=round(sum(item.grid_usage_kwh for item in intervals), 4),
        total_charge_dollars=round(sum(item.total_charge_dollars for item in intervals), 4),
        baseline_grid_cost_dollars=round(baseline, 4),
        tenant_saving_dollars=round(tenant_saving, 4),
        tenant_saving_percentage=round(tenant_saving / baseline * 100, 2) if baseline > 0 else None,
        landlord_solar_revenue_dollars=round(sum(item.solar_charge_dollars for item in intervals), 4),
        landlord_export_value_dollars=round(sum(item.landlord_export_value_dollars for item in intervals), 4),
        actual_export_revenue_dollars=round(sum(item.actual_export_revenue_dollars for item in intervals), 4),
        landlord_total_revenue_dollars=round(sum(item.landlord_total_revenue_dollars for item in intervals), 4),
        landlord_additional_revenue_dollars=round(sum(item.landlord_additional_revenue_dollars for item in intervals), 4),
    )
    return BatchPricingResponse(intervals=intervals, summary=summary)
