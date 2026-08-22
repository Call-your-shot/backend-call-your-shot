from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from ..utils.roi_engine.models import DistributionSummary, InitialEstimateResponse


class AssessmentModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel,
        serialize_by_alias=True,
    )


class AssessmentAddress(AssessmentModel):
    formatted_address: str = Field(min_length=3)
    latitude: float | None = None
    longitude: float | None = None


class AssessmentSystem(AssessmentModel):
    source: Literal["google", "manual", "mock"]
    imagery_quality: Literal["HIGH", "MEDIUM", "BASE"] | None = None
    imagery_date: str | None = None
    panel_count: int = Field(ge=0)
    panel_watts: int = Field(gt=0)
    system_size_kw: float = Field(gt=0)
    expected_annual_generation_kwh: float = Field(gt=0)
    roof_area_m2: float | None = Field(default=None, ge=0)
    usable_roof_area_m2: float | None = Field(default=None, ge=0)
    monthly_generation_kwh: list[float] | None = None

    @field_validator("monthly_generation_kwh")
    @classmethod
    def validate_monthly_generation(cls, value: list[float] | None) -> list[float] | None:
        if value is not None and (len(value) != 12 or any(item < 0 for item in value) or sum(value) <= 0):
            raise ValueError("monthlyGenerationKwh must contain 12 non-negative values with a positive total")
        return value


class AssessmentHousehold(AssessmentModel):
    expected_annual_usage_kwh: float = Field(gt=0)
    current_annual_bill_dollars: float | None = Field(default=None, ge=0)
    grid_rate_cents_per_kwh: float | None = Field(default=None, ge=0)
    daytime_occupancy: Literal["most", "sometimes", "rarely"]
    monthly_usage_kwh: list[float] | None = None

    @field_validator("monthly_usage_kwh")
    @classmethod
    def validate_monthly_usage(cls, value: list[float] | None) -> list[float] | None:
        if value is not None and (len(value) != 12 or any(item < 0 for item in value) or sum(value) <= 0):
            raise ValueError("monthlyUsageKwh must contain 12 non-negative values with a positive total")
        return value


class AssessmentSizingSelection(AssessmentModel):
    recommended_candidate_id: str
    recommended_panel_count: int = Field(gt=0)
    roof_maximum_panel_count: int = Field(gt=0)
    selection_method: str
    recommendation_reason: str


class AssessmentInstallationAssumptions(AssessmentModel):
    gross_installation_cost_dollars: float | None = Field(default=None, ge=0)
    stc_benefit_dollars: float = Field(default=0, ge=0)
    other_rebates_dollars: float = Field(default=0, ge=0)
    annual_operating_cost_dollars: float = Field(default=100, ge=0)


class AssessmentPricingAssumptions(AssessmentModel):
    pricing_mode: Literal["dynamic", "fixed"] = "dynamic"
    export_rate_cents_per_kwh: float | None = Field(default=None, ge=0)
    fixed_tenant_solar_rate_cents_per_kwh: float | None = Field(default=None, ge=0)


class AssessmentSimulationConfig(AssessmentModel):
    iterations: int = Field(default=10_000, ge=100, le=100_000)
    forecast_years: int = Field(default=25, ge=1, le=40)
    random_seed: int | None = None


class InitialAssessmentRequest(AssessmentModel):
    property_id: str | None = None
    address: AssessmentAddress
    system: AssessmentSystem
    household: AssessmentHousehold
    installation: AssessmentInstallationAssumptions = Field(
        default_factory=AssessmentInstallationAssumptions
    )
    pricing: AssessmentPricingAssumptions = Field(
        default_factory=AssessmentPricingAssumptions
    )
    simulation: AssessmentSimulationConfig = Field(
        default_factory=AssessmentSimulationConfig
    )
    sizing: AssessmentSizingSelection | None = None


class TenantEconomics(AssessmentModel):
    baseline_annual_bill_dollars: float
    projected_annual_electricity_cost_dollars: DistributionSummary
    annual_savings_dollars: DistributionSummary
    solar_share_ratio: DistributionSummary
    probability_saves_money: float


class LandlordEconomics(AssessmentModel):
    net_installation_cost_dollars: float
    first_year_net_cashflow_dollars: DistributionSummary
    simple_annual_yield_percentage: DistributionSummary | None
    median_payback_years: float | None
    payback_range_years: dict[str, float | None]
    probability_payback_within_7_years: float
    probability_payback_within_10_years: float


class AssessmentPricingResult(AssessmentModel):
    mode: Literal["dynamic", "fixed"]
    tenant_solar_rate_cents_per_kwh: DistributionSummary
    grid_rate_cents_per_kwh: float
    export_rate_cents_per_kwh: float
    method: str


class InitialAssessmentResponse(AssessmentModel):
    id: str
    created_at: datetime
    forecast_source: Literal["assumption_based"] = "assumption_based"
    recommendation: Literal["viable", "manual_review", "not_recommended"]
    review_reasons: list[str]
    installation_cost_source: Literal["provided", "model_default"]
    address: AssessmentAddress
    system: AssessmentSystem
    tenant_economics: TenantEconomics
    landlord_economics: LandlordEconomics
    pricing: AssessmentPricingResult
    monte_carlo: InitialEstimateResponse
    sizing: AssessmentSizingSelection | None = None
    warnings: list[dict[str, str]]
