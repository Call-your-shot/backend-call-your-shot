from fastapi import APIRouter, HTTPException

from ..schemas.pricing import BatchPricingRequest, BatchPricingResponse, PricingRequest, PricingResult, TariffInfoResponse, TariffPeriod
from ..utils.pricing import TOU_EXPORT_RATES, TOU_GRID_RATES, TIMEZONE, calculate_batch_price, calculate_interval_price

router = APIRouter(prefix="/api/v1/pricing", tags=["pricing"])


@router.post("/calculate", response_model=PricingResult)
def calculate_price(request: PricingRequest) -> PricingResult:
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


@router.post("/calculate-batch", response_model=BatchPricingResponse)
def calculate_batch(request: BatchPricingRequest) -> BatchPricingResponse:
    try:
        return calculate_batch_price(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/tariffs", response_model=TariffInfoResponse)
def tariffs() -> TariffInfoResponse:
    return TariffInfoResponse(
        location="Wollongong / Endeavour Energy",
        timezone=TIMEZONE,
        grid_tariffs=[TariffPeriod(start_hour=start, end_hour=end, rate_cents_per_kwh=rate) for start, end, rate in TOU_GRID_RATES],
        export_tariffs=[TariffPeriod(start_hour=start, end_hour=end, rate_cents_per_kwh=rate) for start, end, rate in TOU_EXPORT_RATES],
    )
