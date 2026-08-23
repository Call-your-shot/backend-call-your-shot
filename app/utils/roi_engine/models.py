"""Pydantic v2 request and response contracts."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .config import (
    DEFAULT_FORECAST_HORIZON_MONTHS,
    DEFAULT_METER_TOLERANCE_RATIO,
    DEFAULT_MONTE_CARLO_ALPHA_MAX,
    DEFAULT_MONTE_CARLO_ALPHA_MIN,
    DEFAULT_MONTE_CARLO_ALPHA_MODE,
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


# ---------------------------------------------------------------------------
# Assumption-based initial Monte Carlo estimation
# ---------------------------------------------------------------------------

ForecastSource = Literal["assumption_based", "historical", "hybrid"]


def _validate_monthly_weights(values: list[float] | None) -> list[float] | None:
    if values is None:
        return None
    if len(values) != 12:
        raise ValueError("monthly weights must contain exactly 12 values")
    if any(value < 0 for value in values):
        raise ValueError("monthly weights cannot be negative")
    if abs(sum(values) - 1.0) > 1e-6:
        raise ValueError("monthly weights must sum to 1")
    return values


class MonteCarloSimulationConfig(BaseModel):
    iterations: Annotated[
        int,
        Field(
            ge=100,
            le=100_000,
            description="Number of plausible investment futures to simulate.",
        ),
    ] = 10_000
    forecast_years: Annotated[
        int,
        Field(
            ge=1,
            le=40,
            description="Maximum duration simulated; unrecovered paths remain no-payback outcomes.",
        ),
    ] = 25
    random_seed: int | None = Field(
        default=None,
        description="Optional NumPy seed for exactly reproducible simulation output.",
    )


class InitialGenerationAssumptions(BaseModel):
    expected_annual_generation_kwh: NonNegative = Field(
        description="First-year annual AC generation estimate before random variation."
    )
    annual_variability_percentage: NonNegative = Field(
        default=10.0,
        description="Expected year-to-year standard deviation around annual generation, as a percentage.",
    )
    annual_panel_degradation_rate: Annotated[
        float,
        Field(
            ge=0,
            lt=1,
            description="Fractional annual reduction in expected panel generation; 0.005 means 0.5%.",
        ),
    ] = 0.005
    minimum_generation_multiplier: NonNegative = Field(
        default=0.60,
        description="Hard lower bound applied to the expected generation for each year.",
    )
    maximum_generation_multiplier: Positive = Field(
        default=1.30,
        description="Hard upper bound applied to the expected generation for each year.",
    )
    monthly_generation_weights: list[float] | None = Field(
        default=None,
        description="Optional 12-value seasonal profile summing to one; configurable defaults apply when omitted.",
    )

    _weights = field_validator("monthly_generation_weights")(_validate_monthly_weights)

    @model_validator(mode="after")
    def validate_generation_bounds(self) -> InitialGenerationAssumptions:
        if self.minimum_generation_multiplier > self.maximum_generation_multiplier:
            raise ValueError(
                "minimum_generation_multiplier cannot exceed maximum_generation_multiplier"
            )
        return self


class InitialTenantDemandAssumptions(BaseModel):
    expected_annual_usage_kwh: NonNegative = Field(
        description="Expected first-year tenant electricity demand across solar and grid supply."
    )
    annual_usage_variability_percentage: NonNegative = Field(
        default=15.0,
        description="Expected year-to-year standard deviation around tenant demand, as a percentage.",
    )
    annual_usage_growth_rate: GrowthRate = Field(
        default=0.0,
        description="Optional fractional annual demand growth or decline; zero assumes no trend.",
    )
    monthly_usage_weights: list[float] | None = Field(
        default=None,
        description="Optional 12-value tenant demand profile summing to one.",
    )

    _weights = field_validator("monthly_usage_weights")(_validate_monthly_weights)


class InitialSolarUtilisationAssumptions(BaseModel):
    expected_self_consumption_ratio: Annotated[
        float,
        Field(
            ge=0,
            le=1,
            description="Most likely share of generated solar consumed by the tenant rather than exported.",
        ),
    ]
    minimum_self_consumption_ratio: Annotated[
        float,
        Field(
            ge=0,
            le=1,
            description="Plausible low endpoint of the triangular utilisation assumption.",
        ),
    ]
    maximum_self_consumption_ratio: Annotated[
        float,
        Field(
            ge=0,
            le=1,
            description="Plausible high endpoint of the triangular utilisation assumption.",
        ),
    ]

    @model_validator(mode="after")
    def validate_triangular_order(self) -> InitialSolarUtilisationAssumptions:
        if not (
            self.minimum_self_consumption_ratio
            <= self.expected_self_consumption_ratio
            <= self.maximum_self_consumption_ratio
        ):
            raise ValueError(
                "self-consumption values must satisfy minimum <= expected <= maximum"
            )
        return self


class InitialPricingAssumptions(BaseModel):
    pricing_mode: Literal["fixed", "dynamic"] = Field(
        default="dynamic",
        description="Fixed tenant solar tariff or an internal approximation compatible with the separate dynamic pricing service.",
    )
    grid_rate_cents_per_kwh: NonNegative = Field(
        description="Expected first-year retail grid tariff in cents per kWh."
    )
    export_rate_cents_per_kwh: NonNegative = Field(
        description="Expected first-year feed-in tariff in cents per kWh."
    )
    grid_rate_variability_percentage: NonNegative = Field(
        default=0.0,
        description="Standard deviation of simulated grid tariffs as a percentage; zero keeps the tariff fixed.",
    )
    export_rate_variability_percentage: NonNegative = Field(
        default=0.0,
        description="Standard deviation of simulated feed-in tariffs as a percentage; zero keeps the tariff fixed.",
    )
    annual_grid_rate_growth: GrowthRate = Field(
        default=0.0,
        description="Optional fractional annual grid-tariff growth or decline.",
    )
    annual_export_rate_growth: GrowthRate = Field(
        default=0.0,
        description="Optional fractional annual feed-in-tariff growth or decline.",
    )
    fixed_tenant_solar_rate_cents_per_kwh: NonNegative | None = Field(
        default=None,
        description="Required tenant tariff for fixed pricing; ignored by dynamic pricing.",
    )
    alpha_estimation_mode: Literal["usage_function", "triangular"] = Field(
        default="usage_function",
        description="Derive alpha from simulated consumption, or sample it from a stated triangular assumption.",
    )
    alpha_min: Annotated[float, Field(ge=0, le=1)] = DEFAULT_MONTE_CARLO_ALPHA_MIN
    alpha_mode: Annotated[float, Field(ge=0, le=1)] = DEFAULT_MONTE_CARLO_ALPHA_MODE
    alpha_max: Annotated[float, Field(ge=0, le=1)] = DEFAULT_MONTE_CARLO_ALPHA_MAX
    discount_sensitivity: Positive = Field(
        default=0.50,
        description="Positive k coefficient in alpha(q) = alpha_min + spread * exp(-k*q).",
    )
    active_solar_use_hours_per_day: Annotated[
        float,
        Field(
            gt=0,
            le=24,
            description="Hours used to convert annual tenant solar consumption into representative interval usage.",
        ),
    ] = 6.0
    effective_solar_usage_kwh_per_interval: NonNegative | None = Field(
        default=None,
        description="Optional direct q override for the dynamic alpha equation.",
    )

    @model_validator(mode="after")
    def validate_pricing(self) -> InitialPricingAssumptions:
        if self.export_rate_cents_per_kwh > self.grid_rate_cents_per_kwh:
            raise ValueError("export rate cannot exceed grid rate")
        if self.alpha_min > self.alpha_max:
            raise ValueError("alpha_min cannot exceed alpha_max")
        if not self.alpha_min <= self.alpha_mode <= self.alpha_max:
            raise ValueError("alpha_mode must be between alpha_min and alpha_max")
        if (
            self.pricing_mode == "fixed"
            and self.fixed_tenant_solar_rate_cents_per_kwh is None
        ):
            raise ValueError(
                "fixed_tenant_solar_rate_cents_per_kwh is required for fixed pricing"
            )
        return self


class InitialCostAssumptions(BaseModel):
    annual_operating_cost_dollars: NonNegative = Field(
        default=0.0,
        description="Expected annual owner operating and maintenance cost.",
    )
    annual_operating_cost_variability_percentage: NonNegative = Field(
        default=0.0,
        description="Standard deviation of annual operating cost as a percentage; zero keeps it fixed.",
    )


class InitialEstimateRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "installation": {
                        "gross_installation_cost_dollars": 9000,
                        "stc_benefit_dollars": 1500,
                        "installed_capacity_kw": 6.6,
                    },
                    "simulation": {
                        "iterations": 10000,
                        "forecast_years": 20,
                        "random_seed": 42,
                    },
                    "generation": {
                        "expected_annual_generation_kwh": 9108,
                        "annual_variability_percentage": 10,
                    },
                    "tenant_demand": {
                        "expected_annual_usage_kwh": 6500,
                        "annual_usage_variability_percentage": 15,
                    },
                    "solar_utilisation": {
                        "expected_self_consumption_ratio": 0.55,
                        "minimum_self_consumption_ratio": 0.35,
                        "maximum_self_consumption_ratio": 0.75,
                    },
                    "pricing": {
                        "pricing_mode": "dynamic",
                        "grid_rate_cents_per_kwh": 30,
                        "export_rate_cents_per_kwh": 5,
                    },
                    "costs": {"annual_operating_cost_dollars": 100},
                }
            ]
        }
    )

    installation: InstallationData
    simulation: MonteCarloSimulationConfig = Field(
        default_factory=MonteCarloSimulationConfig
    )
    generation: InitialGenerationAssumptions
    tenant_demand: InitialTenantDemandAssumptions
    solar_utilisation: InitialSolarUtilisationAssumptions
    pricing: InitialPricingAssumptions
    costs: InitialCostAssumptions = Field(default_factory=InitialCostAssumptions)


class DistributionSummary(BaseModel):
    mean: float
    median: float
    std_dev: float
    p05: float
    p25: float
    p50: float
    p75: float
    p95: float
    minimum: float
    maximum: float


class SimulationMetadata(BaseModel):
    iterations: int
    forecast_years: int
    random_seed: int | None
    payback_reached_iterations: int


class InitialInstallationResult(BaseModel):
    gross_installation_cost_dollars: float
    stc_benefit_dollars: float
    other_rebates_dollars: float
    net_installation_cost_dollars: float
    installed_capacity_kw: float | None


class ForecastRange(BaseModel):
    lower: float | None
    upper: float | None


class InitialEstimateHeadline(BaseModel):
    median_payback_years: float | None
    mean_payback_years: float | None
    median_first_year_tenant_savings_dollars: float
    probability_tenant_saves_money: float
    forecast_interval_level: int = 90
    forecast_payback_range_years: ForecastRange
    probability_payback_within_7_years: float


class ForecastInterval(BaseModel):
    level: int = 90
    lower_payback_years: float | None
    upper_payback_years: float | None


class PaybackProbability(BaseModel):
    within_5_years: float
    within_7_years: float
    within_10_years: float
    within_15_years: float


class InitialEnergyDistribution(BaseModel):
    first_year_generation_kwh: DistributionSummary
    first_year_tenant_usage_kwh: DistributionSummary
    self_consumption_ratio: DistributionSummary
    first_year_tenant_solar_consumption_kwh: DistributionSummary
    first_year_export_kwh: DistributionSummary
    first_year_grid_import_kwh: DistributionSummary
    tenant_solar_share_ratio: DistributionSummary


class InitialFinancialDistribution(BaseModel):
    first_year_tenant_solar_rate_cents_per_kwh: DistributionSummary
    first_year_tenant_revenue_dollars: DistributionSummary
    first_year_export_revenue_dollars: DistributionSummary
    first_year_total_revenue_dollars: DistributionSummary
    first_year_grid_cost_dollars: DistributionSummary
    first_year_tenant_total_electricity_cost_dollars: DistributionSummary
    first_year_tenant_savings_dollars: DistributionSummary
    first_year_operating_cost_dollars: DistributionSummary
    first_year_net_cashflow_dollars: DistributionSummary
    first_year_simple_annual_yield_percentage: DistributionSummary | None
    average_annual_net_cashflow_dollars: DistributionSummary
    cumulative_roi_percentage: DistributionSummary | None


class SensitivityResult(BaseModel):
    variable: str
    correlation_with_payback: float
    absolute_influence: float
    interpretation: str


class PaybackHistogram(BaseModel):
    bins_years: list[float]
    counts: list[int]


class PaybackCdfPoint(BaseModel):
    years: int
    probability: float


class InitialEstimateAssumptionsResult(BaseModel):
    generation_distribution: Literal["bounded_truncated_normal"]
    usage_distribution: Literal["non_negative_truncated_normal"]
    self_consumption_distribution: Literal["triangular"]
    tariff_distribution: Literal["fixed_or_non_negative_truncated_normal"]
    operating_cost_distribution: Literal["non_negative_truncated_normal"]
    expected_annual_generation_kwh: float
    generation_variability_percentage: float
    generation_bounds_multipliers: list[float]
    monthly_generation_weights: list[float]
    expected_annual_usage_kwh: float
    usage_variability_percentage: float
    monthly_usage_weights: list[float]
    self_consumption_minimum: float
    self_consumption_mode: float
    self_consumption_maximum: float
    pricing_mode: Literal["fixed", "dynamic"]
    alpha_estimation_mode: Literal["usage_function", "triangular"]
    alpha_minimum: float
    alpha_mode: float
    alpha_maximum: float
    alpha_usage_normalisation: str
    annual_panel_degradation_rate: float
    annual_usage_growth_rate: float
    annual_grid_rate_growth: float
    annual_export_rate_growth: float
    grid_rate_cents_per_kwh: float
    export_rate_cents_per_kwh: float
    annual_operating_cost_dollars: float


class InitialEstimateResponse(BaseModel):
    forecast_source: ForecastSource
    simulation: SimulationMetadata
    installation: InitialInstallationResult
    headline: InitialEstimateHeadline
    payback_distribution_years: DistributionSummary | None
    forecast_interval: ForecastInterval
    probability_of_payback: PaybackProbability
    probability_no_payback_within_horizon: float
    energy_distribution: InitialEnergyDistribution
    financial_distribution: InitialFinancialDistribution
    sensitivity: list[SensitivityResult]
    payback_histogram: PaybackHistogram
    payback_cdf: list[PaybackCdfPoint]
    assumptions: InitialEstimateAssumptionsResult
    warnings: list[DataQualityWarning]
