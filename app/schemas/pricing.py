from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import Field, model_validator

from .common import ApiModel


class PricingRequest(ApiModel):
    usage_kwh: float = Field(ge=0)
    solar_available_kwh: Optional[float] = Field(default=None, ge=0)
    timestamp: datetime
    pricing_mode: Literal["fixed", "dynamic"] = "dynamic"
    grid_rate_cents_per_kwh: Optional[float] = Field(default=None, ge=0)
    export_rate_cents_per_kwh: Optional[float] = Field(default=None, ge=0)
    fixed_solar_rate_cents_per_kwh: float = Field(default=22.0, ge=0)
    alpha_min: float = Field(default=0.40, ge=0, le=1)
    alpha_max: float = Field(default=0.75, ge=0, le=1)
    discount_sensitivity: float = Field(default=0.50, gt=0)

    @model_validator(mode="after")
    def validate_request(self) -> "PricingRequest":
        if self.alpha_min > self.alpha_max:
            raise ValueError("alpha_min must be <= alpha_max")
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return self


class IntervalInput(ApiModel):
    usage_kwh: float = Field(ge=0)
    solar_available_kwh: Optional[float] = Field(default=None, ge=0)
    timestamp: datetime
    grid_rate_cents_per_kwh: Optional[float] = Field(default=None, ge=0)
    export_rate_cents_per_kwh: Optional[float] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_timestamp(self) -> "IntervalInput":
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return self


class BatchPricingRequest(ApiModel):
    intervals: list[IntervalInput] = Field(min_length=1)
    pricing_mode: Literal["fixed", "dynamic"] = "dynamic"
    fixed_solar_rate_cents_per_kwh: float = Field(default=22.0, ge=0)
    alpha_min: float = Field(default=0.40, ge=0, le=1)
    alpha_max: float = Field(default=0.75, ge=0, le=1)
    discount_sensitivity: float = Field(default=0.50, gt=0)

    @model_validator(mode="after")
    def validate_request(self) -> "BatchPricingRequest":
        if self.alpha_min > self.alpha_max:
            raise ValueError("alpha_min must be <= alpha_max")
        return self


class PricingResult(ApiModel):
    timestamp: datetime
    pricing_mode: str
    usage_kwh: float
    solar_available_kwh: Optional[float] = None
    solar_usage_kwh: float
    grid_usage_kwh: float
    grid_rate_cents_per_kwh: float
    export_rate_cents_per_kwh: float
    alpha: Optional[float] = None
    solar_rate_cents_per_kwh: float
    solar_charge_dollars: float
    grid_charge_dollars: float
    total_charge_dollars: float
    tenant_grid_cost_without_solar_dollars: float
    tenant_saving_dollars: float
    tenant_saving_percentage: Optional[float] = None
    landlord_export_value_dollars: float
    landlord_additional_revenue_dollars: float


class BatchSummary(ApiModel):
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


class BatchPricingResponse(ApiModel):
    intervals: list[PricingResult]
    summary: BatchSummary


class TariffPeriod(ApiModel):
    start_hour: int
    end_hour: int
    rate_cents_per_kwh: float


class TariffInfoResponse(ApiModel):
    location: str
    timezone: str
    grid_tariffs: list[TariffPeriod]
    export_tariffs: list[TariffPeriod]
