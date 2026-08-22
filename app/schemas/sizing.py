from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from ..utils.roi_engine.models import DistributionSummary


class SizingModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel,
        serialize_by_alias=True,
    )


class MonthlyDemandInput(SizingModel):
    calendar_month: int = Field(ge=1, le=12)
    usage_kwh: float = Field(ge=0)
    daytime_usage_ratio: float = Field(default=0.4, ge=0, le=1)
    source: Literal["observed_bill", "bill_period_derived", "survey_derived"] = (
        "survey_derived"
    )


class RoofSystemCandidate(SizingModel):
    candidate_id: str = Field(min_length=1, max_length=100)
    source: Literal["google", "manual", "mock"]
    panel_count: int = Field(gt=0, le=500)
    panel_watts: int = Field(gt=0, le=1_000)
    system_size_kw: float = Field(gt=0)
    annual_generation_kwh: float = Field(gt=0)
    monthly_generation_kwh: list[float] | None = None
    gross_installation_cost_dollars: float | None = Field(default=None, ge=0)
    stc_benefit_dollars: float = Field(default=0, ge=0)
    other_rebates_dollars: float = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_generation_profile(self) -> "RoofSystemCandidate":
        if self.monthly_generation_kwh is not None:
            if len(self.monthly_generation_kwh) != 12:
                raise ValueError("monthlyGenerationKwh must contain exactly 12 values")
            if any(value < 0 for value in self.monthly_generation_kwh):
                raise ValueError("monthlyGenerationKwh values cannot be negative")
            if sum(self.monthly_generation_kwh) <= 0:
                raise ValueError("monthlyGenerationKwh must contain positive generation")
        return self


class SizingPricing(SizingModel):
    pricing_mode: Literal["dynamic", "fixed"] = "dynamic"
    grid_rate_cents_per_kwh: float = Field(default=35.69, ge=0)
    export_rate_cents_per_kwh: float = Field(default=4.0, ge=0)
    fixed_tenant_solar_rate_cents_per_kwh: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_pricing(self) -> "SizingPricing":
        if self.export_rate_cents_per_kwh > self.grid_rate_cents_per_kwh:
            raise ValueError("export rate cannot exceed grid rate")
        if self.pricing_mode == "fixed" and self.fixed_tenant_solar_rate_cents_per_kwh is None:
            raise ValueError("fixedTenantSolarRateCentsPerKwh is required for fixed pricing")
        return self


class SizingCosts(SizingModel):
    installation_cost_per_kw: float = Field(default=1_450, gt=0)
    annual_operating_cost_dollars: float = Field(default=100, ge=0)


class SizingConstraints(SizingModel):
    minimum_probability_tenant_saves: float = Field(default=0.80, ge=0, le=1)
    minimum_probability_payback_within_horizon: float = Field(default=0.50, ge=0, le=1)
    maximum_median_payback_years: float = Field(default=12, gt=0)
    maximum_export_ratio: float = Field(default=0.60, ge=0, le=1)
    maximum_marginal_payback_years: float = Field(default=12, gt=0)
    maximum_system_size_kw: float | None = Field(default=None, gt=0)


class SizingSimulation(SizingModel):
    iterations: int = Field(default=1_000, ge=100, le=10_000)
    forecast_years: int = Field(default=25, ge=1, le=40)
    random_seed: int | None = 42


class SolarSizingRequest(SizingModel):
    monthly_demand: list[MonthlyDemandInput] = Field(min_length=12, max_length=12)
    candidates: list[RoofSystemCandidate] = Field(min_length=1, max_length=40)
    daytime_occupancy: Literal["most", "sometimes", "rarely"] = "sometimes"
    pricing: SizingPricing = Field(default_factory=SizingPricing)
    costs: SizingCosts = Field(default_factory=SizingCosts)
    constraints: SizingConstraints = Field(default_factory=SizingConstraints)
    simulation: SizingSimulation = Field(default_factory=SizingSimulation)

    @model_validator(mode="after")
    def validate_unique_inputs(self) -> "SolarSizingRequest":
        months = [item.calendar_month for item in self.monthly_demand]
        if sorted(months) != list(range(1, 13)):
            raise ValueError("monthlyDemand must contain each calendar month exactly once")
        candidate_ids = [item.candidate_id for item in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidateId values must be unique")
        if sum(item.usage_kwh for item in self.monthly_demand) <= 0:
            raise ValueError("annual household usage must be positive")
        return self


class CandidateSizingResult(SizingModel):
    candidate_id: str
    panel_count: int
    system_size_kw: float
    annual_generation_kwh: float
    net_installation_cost_dollars: float
    median_tenant_solar_consumption_kwh: float
    median_export_kwh: float
    self_consumption_ratio: float
    export_ratio: float
    solar_coverage_ratio: float
    first_year_tenant_savings_dollars: DistributionSummary
    first_year_net_cashflow_dollars: DistributionSummary
    median_payback_years: float | None
    payback_range_years: dict[str, float | None]
    probability_tenant_saves: float
    probability_payback_within_horizon: float
    marginal_payback_years: float | None
    qualified: bool
    rejection_reasons: list[str]


class SolarSizingResponse(SizingModel):
    status: Literal["viable", "manual_review", "not_recommended"]
    recommended_candidate_id: str | None
    recommended_panel_count: int | None
    recommended_system_size_kw: float | None
    roof_maximum_panel_count: int
    annual_usage_kwh: float
    monthly_usage_weights: list[float]
    recommendation_reason: str
    selection_method: Literal["monthly_demand_economic_candidate_simulation"]
    alternatives: list[CandidateSizingResult]
    warnings: list[dict[str, str]]
