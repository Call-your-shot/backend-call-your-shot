"""
FastAPI application — Solar Tenant Pricing API.

Endpoints
---------
* ``POST /api/v1/price/calculate``      — single-interval pricing
* ``POST /api/v1/price/calculate-batch`` — multi-interval pricing
* ``GET  /api/v1/price/preview``         — quick pricing preview
* ``GET  /api/v1/tariffs``               — current tariff schedule
* ``GET  /health``                       — health check
"""

from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query

from app.config import LOCATION_NAME, TIMEZONE
from app.models import (
    BatchPricingRequest,
    BatchPricingResponse,
    BatchSummary,
    HealthResponse,
    PricingRequest,
    PricingResult,
    TariffInfoResponse,
    TariffPeriod,
)
from app.pricing import calculate_interval_price
from app.tariffs import TOU_EXPORT_RATES, TOU_GRID_RATES

# ═══════════════════════════════════════════════════════════════════════════
# Application
# ═══════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="Solar Tenant Pricing API",
    summary="Dynamic electricity pricing for solar-equipped rental properties",
    description=(
        "Calculates the electricity price a landlord / solar provider charges "
        "a tenant, ensuring the tenant pays less than grid retail while the "
        "landlord earns more than the solar export feed-in tariff.\n\n"
        "**Core formula:**\n\n"
        "```\n"
        "P_tenant = P_export + α(q) × (P_grid − P_export)\n"
        "α(q)     = α_min + (α_max − α_min) × e^(−k × q)\n"
        "```\n\n"
        "Designed for Wollongong, NSW (Endeavour Energy network area)."
    ),
    version="1.0.0",
)


# ═══════════════════════════════════════════════════════════════════════════
# Health
# ═══════════════════════════════════════════════════════════════════════════


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns service health status.",
    tags=["Operations"],
)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


# ═══════════════════════════════════════════════════════════════════════════
# Tariffs
# ═══════════════════════════════════════════════════════════════════════════


@app.get(
    "/api/v1/tariffs",
    response_model=TariffInfoResponse,
    summary="Current tariff schedule",
    description="Returns the configured time-of-use grid and export tariffs.",
    tags=["Tariffs"],
)
async def get_tariffs() -> TariffInfoResponse:
    return TariffInfoResponse(
        location=LOCATION_NAME,
        timezone=TIMEZONE,
        grid_tariffs=[
            TariffPeriod(start_hour=s, end_hour=e, rate_cents_per_kwh=r)
            for s, e, r in TOU_GRID_RATES
        ],
        export_tariffs=[
            TariffPeriod(start_hour=s, end_hour=e, rate_cents_per_kwh=r)
            for s, e, r in TOU_EXPORT_RATES
        ],
    )


# ═══════════════════════════════════════════════════════════════════════════
# Single-interval calculation
# ═══════════════════════════════════════════════════════════════════════════


@app.post(
    "/api/v1/price/calculate",
    response_model=PricingResult,
    summary="Calculate price for one interval",
    description=(
        "Computes the electricity charge, tenant savings, and landlord "
        "benefit for a single usage interval."
    ),
    tags=["Pricing"],
)
async def calculate_price(request: PricingRequest) -> PricingResult:
    try:
        return calculate_interval_price(
            usage_kwh=request.usage_kwh,
            solar_available_kwh=request.solar_available_kwh,
            timestamp=request.timestamp,
            pricing_mode=request.pricing_mode,
            grid_rate_override=request.grid_rate_cents_per_kwh,
            export_rate_override=request.export_rate_cents_per_kwh,
            fixed_solar_rate=request.fixed_solar_rate_cents_per_kwh,
            alpha_min=request.alpha_min,
            alpha_max=request.alpha_max,
            discount_sensitivity=request.discount_sensitivity,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ═══════════════════════════════════════════════════════════════════════════
# Batch calculation
# ═══════════════════════════════════════════════════════════════════════════


@app.post(
    "/api/v1/price/calculate-batch",
    response_model=BatchPricingResponse,
    summary="Calculate prices for multiple intervals",
    description=(
        "Computes per-interval pricing and returns an aggregated summary "
        "across all intervals."
    ),
    tags=["Pricing"],
)
async def calculate_batch(request: BatchPricingRequest) -> BatchPricingResponse:
    results: List[PricingResult] = []

    for interval in request.intervals:
        try:
            result = calculate_interval_price(
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
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        results.append(result)

    # ── Aggregate summary ─────────────────────────────────────────────────
    total_usage = sum(r.usage_kwh for r in results)
    total_solar = sum(r.solar_usage_kwh for r in results)
    total_grid = sum(r.grid_usage_kwh for r in results)
    total_charge = sum(r.total_charge_dollars for r in results)
    baseline = sum(r.tenant_grid_cost_without_solar_dollars for r in results)
    total_saving = sum(r.tenant_saving_dollars for r in results)
    solar_revenue = sum(r.solar_charge_dollars for r in results)
    export_value = sum(r.landlord_export_value_dollars for r in results)
    additional = sum(r.landlord_additional_revenue_dollars for r in results)

    saving_pct: Optional[float] = (
        round(total_saving / baseline * 100, 2) if baseline > 0 else None
    )

    summary = BatchSummary(
        total_usage_kwh=round(total_usage, 4),
        total_solar_usage_kwh=round(total_solar, 4),
        total_grid_usage_kwh=round(total_grid, 4),
        total_charge_dollars=round(total_charge, 4),
        baseline_grid_cost_dollars=round(baseline, 4),
        tenant_saving_dollars=round(total_saving, 4),
        tenant_saving_percentage=saving_pct,
        landlord_solar_revenue_dollars=round(solar_revenue, 4),
        landlord_export_value_dollars=round(export_value, 4),
        landlord_additional_revenue_dollars=round(additional, 4),
    )

    return BatchPricingResponse(intervals=results, summary=summary)


# ═══════════════════════════════════════════════════════════════════════════
# Preview (GET convenience endpoint)
# ═══════════════════════════════════════════════════════════════════════════


@app.get(
    "/api/v1/price/preview",
    response_model=PricingResult,
    summary="Quick pricing preview",
    description=(
        "Returns a dynamic pricing prediction using query parameters. "
        "Convenience endpoint for quick lookups."
    ),
    tags=["Pricing"],
)
async def preview_price(
    usage_kwh: float = Query(..., ge=0, description="Usage (kWh)"),
    timestamp: datetime = Query(..., description="Timezone-aware datetime"),
    solar_available_kwh: Optional[float] = Query(
        None, ge=0, description="Solar available (kWh)"
    ),
) -> PricingResult:
    if timestamp.tzinfo is None:
        raise HTTPException(
            status_code=422, detail="timestamp must be timezone-aware"
        )
    try:
        return calculate_interval_price(
            usage_kwh=usage_kwh,
            solar_available_kwh=solar_available_kwh,
            timestamp=timestamp,
            pricing_mode="dynamic",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
