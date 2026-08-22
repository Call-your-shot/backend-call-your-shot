"""
Pydantic v2 request / response models for the Solar Pricing API.

Convention
----------
* All **rates** are in *cents per kWh*.
* All **charges / costs / savings** are in *Australian dollars*.
"""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


# ═══════════════════════════════════════════════════════════════════════════
# Request models
# ═══════════════════════════════════════════════════════════════════════════


class PricingRequest(BaseModel):
    """Request body for ``POST /api/v1/price/calculate``."""

    usage_kwh: float = Field(
        ...,
        ge=0,
        description="Electricity consumed by the tenant during the interval (kWh).",
        json_schema_extra={"examples": [2.5]},
    )
    solar_available_kwh: Optional[float] = Field(
        None,
        ge=0,
        description=(
            "Solar electricity available during the interval (kWh). "
            "If omitted, usage_kwh is treated as solar usage directly."
        ),
        json_schema_extra={"examples": [3.0]},
    )
    timestamp: datetime = Field(
        ...,
        description="Timezone-aware datetime for the usage interval.",
        json_schema_extra={"examples": ["2026-08-22T12:30:00+10:00"]},
    )
    pricing_mode: Literal["fixed", "dynamic"] = Field(
        "dynamic",
        description="Pricing mode: 'fixed' for a flat solar rate, 'dynamic' for usage-responsive pricing.",
    )

    # Rate overrides --------------------------------------------------------
    grid_rate_cents_per_kwh: Optional[float] = Field(
        None,
        ge=0,
        description="Manual override for the grid electricity rate (cents/kWh). Falls back to configured TOU rate.",
    )
    export_rate_cents_per_kwh: Optional[float] = Field(
        None,
        ge=0,
        description="Manual override for the solar export rate (cents/kWh). Falls back to configured TOU rate.",
    )

    # Fixed mode ------------------------------------------------------------
    fixed_solar_rate_cents_per_kwh: float = Field(
        22.0,
        ge=0,
        description="Solar rate (cents/kWh) used only in 'fixed' pricing mode.",
    )

    # Dynamic mode parameters -----------------------------------------------
    alpha_min: float = Field(
        0.40,
        ge=0,
        le=1,
        description="Landlord share factor floor — approached at high usage.",
    )
    alpha_max: float = Field(
        0.75,
        ge=0,
        le=1,
        description="Landlord share factor ceiling — used at near-zero usage.",
    )
    discount_sensitivity: float = Field(
        0.50,
        gt=0,
        description="Exponential decay constant (k) controlling how quickly the share factor drops.",
    )

    # Validators ------------------------------------------------------------

    @model_validator(mode="after")
    def _validate_constraints(self) -> "PricingRequest":
        if self.alpha_min > self.alpha_max:
            raise ValueError("alpha_min must be <= alpha_max")
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return self


class IntervalInput(BaseModel):
    """A single usage interval inside a batch request."""

    usage_kwh: float = Field(..., ge=0, description="Electricity consumed (kWh).")
    solar_available_kwh: Optional[float] = Field(
        None, ge=0, description="Solar available (kWh)."
    )
    timestamp: datetime = Field(
        ..., description="Timezone-aware datetime for this interval."
    )
    grid_rate_cents_per_kwh: Optional[float] = Field(
        None, ge=0, description="Optional grid rate override (cents/kWh)."
    )
    export_rate_cents_per_kwh: Optional[float] = Field(
        None, ge=0, description="Optional export rate override (cents/kWh)."
    )

    @model_validator(mode="after")
    def _validate_timestamp(self) -> "IntervalInput":
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return self


class BatchPricingRequest(BaseModel):
    """Request body for ``POST /api/v1/price/calculate-batch``."""

    intervals: List[IntervalInput] = Field(
        ..., min_length=1, description="One or more usage intervals."
    )
    pricing_mode: Literal["fixed", "dynamic"] = Field("dynamic")
    fixed_solar_rate_cents_per_kwh: float = Field(22.0, ge=0)
    alpha_min: float = Field(0.40, ge=0, le=1)
    alpha_max: float = Field(0.75, ge=0, le=1)
    discount_sensitivity: float = Field(0.50, gt=0)

    @model_validator(mode="after")
    def _validate_constraints(self) -> "BatchPricingRequest":
        if self.alpha_min > self.alpha_max:
            raise ValueError("alpha_min must be <= alpha_max")
        return self


# ═══════════════════════════════════════════════════════════════════════════
# Response models
# ═══════════════════════════════════════════════════════════════════════════


class PricingResult(BaseModel):
    """Full pricing breakdown for one usage interval."""

    timestamp: datetime
    pricing_mode: str

    usage_kwh: float
    solar_available_kwh: Optional[float] = None
    solar_usage_kwh: float
    grid_usage_kwh: float

    grid_rate_cents_per_kwh: float
    export_rate_cents_per_kwh: float

    alpha: Optional[float] = Field(
        None, description="Landlord share factor α(q). None for fixed pricing."
    )

    solar_rate_cents_per_kwh: float

    solar_charge_dollars: float
    grid_charge_dollars: float
    total_charge_dollars: float

    tenant_grid_cost_without_solar_dollars: float
    tenant_saving_dollars: float
    tenant_saving_percentage: Optional[float] = None

    landlord_export_value_dollars: float
    landlord_additional_revenue_dollars: float


class BatchSummary(BaseModel):
    """Aggregated totals across all intervals in a batch."""

    total_usage_kwh: float
    total_solar_usage_kwh: float
    total_grid_usage_kwh: float
    total_charge_dollars: float
    baseline_grid_cost_dollars: float
    tenant_saving_dollars: float
    tenant_saving_percentage: Optional[float] = None
    landlord_solar_revenue_dollars: float
    landlord_export_value_dollars: float
    landlord_additional_revenue_dollars: float


class BatchPricingResponse(BaseModel):
    """Response body for ``POST /api/v1/price/calculate-batch``."""

    intervals: List[PricingResult]
    summary: BatchSummary


class TariffPeriod(BaseModel):
    """One time-of-use period inside a tariff schedule."""

    start_hour: int
    end_hour: int
    rate_cents_per_kwh: float


class TariffInfoResponse(BaseModel):
    """Response body for ``GET /api/v1/tariffs``."""

    location: str
    timezone: str
    grid_tariffs: List[TariffPeriod]
    export_tariffs: List[TariffPeriod]


class HealthResponse(BaseModel):
    """Response body for ``GET /health``."""

    status: str = "ok"
