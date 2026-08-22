"""Pydantic v2 request and response contracts."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .config import (
    DEFAULT_FORECAST_HORIZON_MONTHS,
    DEFAULT_METER_TOLERANCE_RATIO,
    DEFAULT_TREND_TOLERANCE_RATIO,
    SCENARIOS,
)

NonNegative = Annotated[float, Field(ge=0)]
Positive = Annotated[float, Field(gt=0)]
GrowthRate = Annotated[float, Field(gt=-1)]


class MonthlySolarRecord(BaseModel):
    month: date
    total_usage_kwh: NonNegative
    solar_generation_kwh: NonNegative
    solar_consumed_by_tenant_kwh: NonNegative | None = None
    solar_exported_kwh: NonNegative
    tenant_revenue_dollars: NonNegative
    export_revenue_dollars: NonNegative
    operating_cost_dollars: NonNegative = 0.0
    average_grid_rate_cents_per_kwh: NonNegative | None = None
    average_export_rate_cents_per_kwh: NonNegative | None = None
    average_tenant_solar_rate_cents_per_kwh: NonNegative | None = None
    actual_grid_cost_dollars: NonNegative | None = None

    @model_validator(mode="after")
    def validate_calendar_month_and_exports(self) -> MonthlySolarRecord:
        if self.month.day != 1:
            raise ValueError("month must be the first day of its calendar month")
        if self.solar_exported_kwh > self.solar_generation_kwh:
            raise ValueError("solar_exported_kwh cannot exceed solar_generation_kwh")
        return self


class InstallationData(BaseModel):
    gross_installation_cost_dollars: NonNegative
    stc_benefit_dollars: NonNegative = 0.0
    other_rebates_dollars: NonNegative = 0.0
    installed_capacity_kw: Positive | None = None
    installation_date: date | None = None

    @model_validator(mode="after")
    def validate_net_cost(self) -> InstallationData:
        net = (
            self.gross_installation_cost_dollars
            - self.stc_benefit_dollars
            - self.other_rebates_dollars
        )
        if net < 0:
            raise ValueError(
                "STC benefit and rebates cannot exceed gross installation cost"
            )
        return self


class RevenueAssumptions(BaseModel):
    tenant_solar_rate_cents_per_kwh: NonNegative | None = None
    export_rate_cents_per_kwh: NonNegative | None = None
    annual_operating_cost_dollars: NonNegative = 0.0
    potential_tenant_rate_cents_per_kwh: NonNegative | None = None
    average_grid_rate_cents_per_kwh: NonNegative | None = None


class ForecastAssumptions(BaseModel):
    annual_generation_degradation_rate: Annotated[float, Field(ge=0, lt=1)] = 0.005
    annual_tenant_rate_growth: GrowthRate = 0.0
    annual_export_rate_growth: GrowthRate = 0.0
    annual_operating_cost_growth: GrowthRate = 0.0
    forecast_horizon_months: Annotated[int, Field(ge=1, le=1200)] = (
        DEFAULT_FORECAST_HORIZON_MONTHS
    )


class ScenarioMultipliers(BaseModel):
    generation_multiplier: NonNegative
    self_consumption_multiplier: NonNegative
    tenant_rate_multiplier: NonNegative
    operating_cost_multiplier: NonNegative


def _scenario(name: str) -> ScenarioMultipliers:
    return ScenarioMultipliers(**SCENARIOS[name])


class ScenarioConfiguration(BaseModel):
    conservative: ScenarioMultipliers = Field(
        default_factory=lambda: _scenario("conservative")
    )
    expected: ScenarioMultipliers = Field(default_factory=lambda: _scenario("expected"))
    optimistic: ScenarioMultipliers = Field(
        default_factory=lambda: _scenario("optimistic")
    )


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "installation": {
                        "gross_installation_cost_dollars": 9000,
                        "stc_benefit_dollars": 1500,
                        "installed_capacity_kw": 6.6,
                        "installation_date": "2025-06-15",
                    },
                    "history": [
                        {
                            "month": "2025-07-01",
                            "total_usage_kwh": 620,
                            "solar_generation_kwh": 540,
                            "solar_consumed_by_tenant_kwh": 330,
                            "solar_exported_kwh": 210,
                            "tenant_revenue_dollars": 72.6,
                            "export_revenue_dollars": 10.5,
                        }
                    ],
                }
            ]
        }
    )

    installation: InstallationData
    history: Annotated[list[MonthlySolarRecord], Field(min_length=1)]
    revenue_forecast_mode: Literal["historical_cashflow", "energy_based"] = (
        "historical_cashflow"
    )
    revenue_assumptions: RevenueAssumptions = Field(default_factory=RevenueAssumptions)
    forecast_assumptions: ForecastAssumptions = Field(
        default_factory=ForecastAssumptions
    )
    scenarios: ScenarioConfiguration = Field(default_factory=ScenarioConfiguration)
    meter_tolerance_ratio: Annotated[float, Field(ge=0, le=0.25)] = (
        DEFAULT_METER_TOLERANCE_RATIO
    )
    trend_tolerance_ratio: Annotated[float, Field(ge=0, le=1)] = (
        DEFAULT_TREND_TOLERANCE_RATIO
    )

    @model_validator(mode="after")
    def validate_history(self) -> AnalysisRequest:
        months = [record.month for record in self.history]
        if len(months) != len(set(months)):
            raise ValueError("history contains duplicate calendar months")
        for record in self.history:
            consumed = record.solar_consumed_by_tenant_kwh
            if consumed is None:
                continue
            measured = consumed + record.solar_exported_kwh
            allowed = record.solar_generation_kwh * (1 + self.meter_tolerance_ratio)
            if measured > allowed + 1e-9:
                raise ValueError(
                    f"{record.month:%Y-%m}: solar consumption plus exports exceeds "
                    "generation beyond the configured meter tolerance"
                )
        return self


class DataQualityWarning(BaseModel):
    code: str
    message: str


class InstallationAnalysis(BaseModel):
    gross_installation_cost_dollars: float
    stc_benefit_dollars: float
    other_rebates_dollars: float
    net_installation_cost_dollars: float
    installed_capacity_kw: float | None
    installation_date: date | None


class MonthlyHistoryResult(BaseModel):
    month: str
    total_usage_kwh: float
    solar_generation_kwh: float
    solar_consumed_by_tenant_kwh: float
    solar_consumption_source: Literal["explicit", "derived"]
    solar_exported_kwh: float
    tenant_revenue_dollars: float
    export_revenue_dollars: float
    operating_cost_dollars: float
    net_cashflow_dollars: float
    self_consumption_ratio: float | None
    export_ratio: float | None
    specific_yield_kwh_per_kw: float | None


class CapitalRecoveryPoint(BaseModel):
    month: str
    cumulative_cashflow_dollars: float
    remaining_cost_dollars: float


class HistoricalPerformance(BaseModel):
    months_observed: int
    first_month: str
    last_month: str
    total_usage_kwh: float
    solar_generation_kwh: float
    solar_consumed_by_tenant_kwh: float
    solar_consumption_source: Literal["explicit", "derived", "mixed"]
    solar_exported_kwh: float
    self_consumption_ratio: float | None
    self_consumption_percentage: float | None
    export_ratio: float | None
    export_percentage: float | None
    tenant_revenue_dollars: float
    export_revenue_dollars: float
    operating_cost_dollars: float
    net_cashflow_dollars: float
    average_annual_cashflow_dollars: float
    simple_annual_yield_percentage: float | None


class RoiMetrics(BaseModel):
    capital_recovered_dollars: float
    capital_recovered_percentage: float
    remaining_cost_dollars: float
    net_roi_percentage: float | None


class HistoricalAverages(BaseModel):
    monthly_usage_kwh: float
    monthly_generation_kwh: float
    monthly_cashflow_dollars: float


class RevenueMetrics(BaseModel):
    revenue_per_generated_kwh_dollars: float | None
    revenue_per_tenant_solar_kwh_dollars: float | None
    export_revenue_per_kwh_dollars: float | None


class MonthlySpecificYield(BaseModel):
    month: str
    specific_yield_kwh_per_kw: float


class SpecificYieldAnalysis(BaseModel):
    monthly: list[MonthlySpecificYield]
    average_monthly_kwh_per_kw: float | None
    annualised_kwh_per_kw: float | None


class SeasonalMetric(BaseModel):
    calendar_month: int
    month_name: str
    observations: int
    average_generation_kwh: float
    average_tenant_usage_kwh: float
    average_self_consumption_ratio: float | None
    average_export_ratio: float | None
    average_cashflow_dollars: float


class TrendMetric(BaseModel):
    classification: Literal["increasing", "stable", "decreasing", "insufficient_data"]
    estimated_change_over_period_percentage: float | None


class YearOverYearComparison(BaseModel):
    calendar_month: int
    month_name: str
    previous_year: int
    current_year: int
    generation_change_percentage: float | None
    cashflow_change_percentage: float | None
    self_consumption_change_percentage: float | None


class ExportOpportunity(BaseModel):
    exported_energy_kwh: float
    assumed_tenant_rate_cents_per_kwh: float
    effective_export_rate_cents_per_kwh: float | None
    maximum_theoretical_export_conversion_value_dollars: float | None
    qualification: str


class TenantSavingsAnalysis(BaseModel):
    baseline_grid_cost_dollars: float
    actual_electricity_cost_dollars: float
    estimated_tenant_savings_dollars: float


class ForecastAssumptionsResult(BaseModel):
    revenue_forecast_mode: Literal["historical_cashflow", "energy_based"]
    generation_forecast_method: str
    annual_panel_degradation_rate: float
    annual_tenant_rate_growth: float
    annual_export_rate_growth: float
    annual_operating_cost_growth: float
    forecast_horizon_months: int
    tenant_rate_cents_per_kwh: float | None
    export_rate_cents_per_kwh: float | None


class ForecastMonth(BaseModel):
    month: str
    forecast_method: str
    projected_generation_kwh: float
    projected_solar_consumption_kwh: float
    projected_export_kwh: float
    projected_tenant_revenue_dollars: float
    projected_export_revenue_dollars: float
    projected_operating_cost_dollars: float
    projected_net_cashflow_dollars: float
    cumulative_recovered_capital_dollars: float
    remaining_cost_dollars: float


class ForecastResult(BaseModel):
    method: str
    payback_reached: bool
    payback_type: Literal["immediate", "historical", "forecast", "not_reached"]
    estimated_months_remaining: float | None
    estimated_payback_date: str | None
    estimated_total_payback_months: float | None
    estimated_total_payback_years: float | None
    reason: str | None = None
    assumptions: ForecastAssumptionsResult


class ScenarioResult(BaseModel):
    payback_reached: bool
    estimated_months_remaining: float | None
    estimated_payback_date: str | None
    estimated_total_payback_years: float | None
    reason: str | None = None
    multipliers: ScenarioMultipliers


class HistoricalAnalysisResponse(BaseModel):
    installation: InstallationAnalysis
    historical_performance: HistoricalPerformance
    roi: RoiMetrics
    historical_averages: HistoricalAverages
    revenue_metrics: RevenueMetrics
    specific_yield: SpecificYieldAnalysis
    seasonality: list[SeasonalMetric]
    trends: dict[str, TrendMetric]
    year_over_year: list[YearOverYearComparison]
    export_opportunity: ExportOpportunity | None
    tenant_savings: TenantSavingsAnalysis | None
    monthly_history: list[MonthlyHistoryResult]
    capital_recovery_timeline: list[CapitalRecoveryPoint]
    warnings: list[DataQualityWarning]


class AnalysisResponse(HistoricalAnalysisResponse):
    forecast: ForecastResult
    scenarios: dict[Literal["conservative", "expected", "optimistic"], ScenarioResult]
    forecast_months: list[ForecastMonth]


class SummaryResponse(BaseModel):
    net_installation_cost_dollars: float
    capital_recovered_dollars: float
    capital_recovered_percentage: float
    remaining_cost_dollars: float
    average_monthly_cashflow_dollars: float
    historical_self_consumption_percentage: float | None
    historical_export_percentage: float | None
    estimated_months_remaining: float | None
    estimated_payback_date: str | None
    expected_payback_years: float | None


class ForecastOnlyResponse(BaseModel):
    forecast: ForecastResult
    scenarios: dict[Literal["conservative", "expected", "optimistic"], ScenarioResult]
    forecast_months: list[ForecastMonth]
    warnings: list[DataQualityWarning]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
