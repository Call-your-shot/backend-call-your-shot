from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from .common import ApiModel


HoursBucket = Literal["0", "none", "0-2", "2-4", "4-6", "4-8", "6+", "8+"]


class Property(ApiModel):
    id: str
    name: str
    address_line_1: str
    address_line_2: Optional[str] = None
    suburb: str
    state: str
    postcode: str
    country: str
    roof_area_m2: Optional[float] = None
    usable_roof_area_m2: Optional[float] = None


class Battery(ApiModel):
    id: str
    property_id: str
    name: str
    manufacturer: str
    model: str
    capacity_kwh: float = Field(ge=0)
    usable_capacity_kwh: float = Field(ge=0)
    max_charge_kw: float = Field(ge=0)
    max_discharge_kw: float = Field(ge=0)
    reserve_pct: float = Field(ge=0, le=100)
    soc_pct: float = Field(ge=0, le=100)
    health_pct: float = Field(ge=0, le=100)
    status: Literal["charging", "discharging", "idle", "reserve", "offline"]
    last_seen_at: str


class Tariff(ApiModel):
    id: str
    property_id: str
    name: str
    usage_rate_per_kwh: float = Field(ge=0)
    grid_rate_cents_per_kwh: float = Field(ge=0)
    feed_in_rate_per_kwh: float = Field(ge=0)
    daily_supply_charge: float = Field(ge=0)
    currency: str = "AUD"


class EnergyReading(ApiModel):
    id: Optional[str] = None
    property_id: Optional[str] = None
    meter_id: Optional[str] = None
    interval_start: str
    interval_end: str
    consumption_kwh: float = Field(ge=0)
    solar_generation_kwh: float = Field(ge=0)
    solar_consumed_by_tenant_kwh: float = Field(default=0, ge=0)
    grid_import_kwh: float = Field(ge=0)
    grid_export_kwh: float = Field(ge=0)
    battery_charge_kwh: float = Field(ge=0)
    battery_discharge_kwh: float = Field(ge=0)
    battery_soc_pct: float = Field(ge=0, le=100)
    interval_minutes: int = Field(default=60, ge=1)
    quality_status: str = "estimated"
    raw_packet_id: Optional[str] = None
    source: str
    finalized_at: Optional[str] = None


class EnergyReadingInput(ApiModel):
    meter_id: Optional[UUID] = Field(default=None, alias="meterId")
    interval_start: datetime = Field(alias="intervalStart")
    interval_end: datetime = Field(alias="intervalEnd")
    consumption_kwh: float = Field(default=0, ge=0, alias="consumptionKwh")
    solar_generation_kwh: float = Field(default=0, ge=0, alias="solarGenerationKwh")
    solar_consumed_by_tenant_kwh: float = Field(default=0, ge=0, alias="solarConsumedByTenantKwh")
    grid_import_kwh: float = Field(default=0, ge=0, alias="gridImportKwh")
    grid_export_kwh: float = Field(default=0, ge=0, alias="gridExportKwh")
    battery_charge_kwh: float = Field(default=0, ge=0, alias="batteryChargeKwh")
    battery_discharge_kwh: float = Field(default=0, ge=0, alias="batteryDischargeKwh")
    battery_soc_pct: Optional[float] = Field(default=None, ge=0, le=100, alias="batterySocPct")
    interval_minutes: int = Field(default=60, ge=1, alias="intervalMinutes")
    quality_status: Literal["raw", "validated", "estimated", "corrected", "missing"] = Field(default="raw", alias="qualityStatus")
    raw_packet_id: Optional[UUID] = Field(default=None, alias="rawPacketId")
    source: Literal["mock", "meter_api", "manual", "simulation"] = "manual"
    finalized_at: Optional[datetime] = Field(default=None, alias="finalizedAt")

    @model_validator(mode="after")
    def check_interval(self) -> "EnergyReadingInput":
        if self.interval_end <= self.interval_start:
            raise ValueError("intervalEnd must be after intervalStart")
        if (
            self.solar_consumed_by_tenant_kwh is not None
            and self.solar_consumed_by_tenant_kwh > self.consumption_kwh + 0.001
        ):
            raise ValueError(
                "solarConsumedByTenantKwh cannot exceed interval consumption"
            )
        if (
            self.solar_consumed_by_tenant_kwh is not None
            and self.solar_consumed_by_tenant_kwh
            > self.solar_generation_kwh + 0.001
        ):
            raise ValueError(
                "solarConsumedByTenantKwh cannot exceed interval solar generation"
            )
        return self


class MeterReadingInput(EnergyReadingInput):
    property_id: UUID = Field(alias="propertyId")


class MeterIngestionRequest(ApiModel):
    readings: list[MeterReadingInput] = Field(min_length=1, max_length=1000)


class TariffInput(ApiModel):
    name: str = Field(min_length=1, max_length=120)
    usage_rate_per_kwh: float = Field(ge=0, alias="usageRatePerKwh")
    grid_rate_cents_per_kwh: Optional[float] = Field(default=None, ge=0, alias="gridRateCentsPerKwh")
    feed_in_rate_per_kwh: float = Field(default=0, ge=0, alias="feedInRatePerKwh")
    daily_supply_charge: float = Field(default=0, ge=0, alias="dailySupplyCharge")
    currency: str = "AUD"
    valid_from: datetime = Field(alias="validFrom")
    valid_to: Optional[datetime] = Field(default=None, alias="validTo")

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        currency = value.upper()
        if len(currency) != 3:
            raise ValueError("currency must be a 3-letter code")
        return currency

    @model_validator(mode="after")
    def check_validity(self) -> "TariffInput":
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("validTo must be after validFrom")
        return self


class SolarAssessmentInput(ApiModel):
    provider: Optional[str] = None
    image_path: Optional[str] = Field(default=None, alias="imagePath")
    image_source: Optional[str] = Field(default=None, alias="imageSource")
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    imagery_date: Optional[datetime] = Field(default=None, alias="imageryDate")
    imagery_quality: Optional[str] = Field(default=None, alias="imageryQuality")
    roof_area_m2: Optional[float] = Field(default=None, ge=0, alias="roofAreaM2")
    usable_roof_area_m2: Optional[float] = Field(default=None, ge=0, alias="usableRoofAreaM2")
    panel_count: Optional[int] = Field(default=None, ge=0, alias="panelCount")
    panel_wattage: Optional[float] = Field(default=None, ge=0, alias="panelWattage")
    monthly_generation_weights: Optional[list[float]] = Field(default=None, alias="monthlyGenerationWeights")
    generation_uncertainty_percentage: Optional[float] = Field(default=None, ge=0, alias="generationUncertaintyPercentage")
    roof_segments_json: dict[str, Any] = Field(default_factory=dict, alias="roofSegmentsJson")
    selected_configuration_json: dict[str, Any] = Field(default_factory=dict, alias="selectedConfigurationJson")
    assumptions: dict[str, Any] = Field(default_factory=dict)


class SolarInstallation(ApiModel):
    id: str
    property_id: str
    solar_assessment_id: Optional[str] = None
    installation_date: Optional[str] = None
    commissioned_at: Optional[str] = None
    installed_capacity_kw: float = Field(ge=0)
    gross_installation_cost_cents: int = Field(ge=0)
    stc_benefit_cents: int = Field(default=0, ge=0)
    other_rebates_cents: int = Field(default=0, ge=0)
    currency: str = "AUD"
    status: str


class SolarInstallationInput(ApiModel):
    solar_assessment_id: Optional[UUID] = Field(default=None, alias="solarAssessmentId")
    installation_date: Optional[datetime] = Field(default=None, alias="installationDate")
    commissioned_at: Optional[datetime] = Field(default=None, alias="commissionedAt")
    installed_capacity_kw: float = Field(ge=0, alias="installedCapacityKw")
    gross_installation_cost_cents: int = Field(ge=0, alias="grossInstallationCostCents")
    stc_benefit_cents: int = Field(default=0, ge=0, alias="stcBenefitCents")
    other_rebates_cents: int = Field(default=0, ge=0, alias="otherRebatesCents")
    currency: str = "AUD"
    status: Literal["planned", "installed", "commissioned", "decommissioned"] = "planned"


class Dashboard(BaseModel):
    property: Property
    viewer: dict[str, str]
    period: dict[str, str]
    energy: dict[str, Union[float, None]]
    battery: Battery
    financial: dict[str, Union[float, str]]
    sustainability: dict[str, float]
    units: dict[str, str]
    series: list[EnergyReading]
    role_panels: dict[str, Any] = Field(default_factory=dict)
    roi_analytics: Optional[dict[str, Any]] = None
    price_adjustments: list[Any] = Field(default_factory=list)
    lease_requests: list[Any] = Field(default_factory=list)
    contracts: list[Any] = Field(default_factory=list)
class ListResponse(BaseModel):
    data: list[Any]


class GridMeterTelemetry(ApiModel):
    device_id: str
    timestamp: str
    voltage_rms_v: float
    current_rms_a: float
    active_power_w: float
    reactive_power_var: float
    power_factor: float
    frequency_hz: float
    energy_import_total_kwh: float
    energy_export_total_kwh: float


class SolarInverterTelemetry(ApiModel):
    device_id: str
    timestamp: str
    pv_voltage_dc_v: float
    pv_current_dc_a: float
    pv_power_dc_w: float
    ac_power_w: float
    inverter_temp_c: float
    operating_status: str
    energy_total_generated_kwh: float


class BatteryBMSTelemetry(ApiModel):
    device_id: str
    timestamp: str
    soc_percent: float
    soh_percent: float
    pack_voltage_v: float
    pack_current_a: float
    battery_power_w: float
    cell_temp_c: float
    bms_state: str
    cycle_count: int
    energy_charged_total_kwh: float
    energy_discharged_total_kwh: float


class TelemetryPacket(ApiModel):
    timestamp: str
    grid_meter: GridMeterTelemetry
    solar_inverter: SolarInverterTelemetry
    battery_bms: BatteryBMSTelemetry


class HourlyBreakdownItem(ApiModel):
    timestamp: str
    solar_gen_kwh: float
    grid_import_kwh: float
    grid_export_kwh: float
    bat_charge_kwh: float
    bat_discharge_kwh: float
    room_load_kwh: float
    solar_self_consumed_kwh: float
    soc_percent: float
    import_rate: float
    cost_without_solar: float
    actual_cost: float
    hourly_savings: float
    co2_offset_kg: float


class DashboardAnalyticsResponse(ApiModel):
    date: str
    total_load_kwh: float
    total_solar_generated_kwh: float
    total_grid_imported_kwh: float
    total_grid_exported_kwh: float
    total_energy_saved_kwh: float
    total_money_saved_usd: float
    self_sufficiency_percent: float
    total_co2_offset_kg: float
    hourly_breakdown: list[HourlyBreakdownItem]


class IngestTelemetryResponse(ApiModel):
    status: str
    message: str
    date: str
    weather: str
    count: int
    ingested_at: str
    records: list[TelemetryPacket]


class RawTelemetryQueryResponse(ApiModel):
    date: Optional[str] = None
    count: int
    data: list[TelemetryPacket]


class ObservedMonthlyUsage(ApiModel):
    month: date
    usage_kwh: float = Field(ge=0, alias="usageKwh")

    @field_validator("month")
    @classmethod
    def validate_first_day(cls, value: date) -> date:
        if value.day != 1:
            raise ValueError("observed monthly usage month must be the first day of the month")
        return value


class SurveyFormData(ApiModel):
    address: Optional[str] = None
    bill_usage_kwh: float = Field(..., ge=0, alias="billUsageKwh")
    billing_period_start: date = Field(..., alias="billingPeriodStart")
    billing_period_end: date = Field(..., alias="billingPeriodEnd")
    bill_total_cost_dollars: Optional[float] = Field(default=None, ge=0, alias="billTotalCostDollars")
    home_during_day: Optional[Literal["most", "sometimes", "rarely"]] = Field(default="most", alias="homeDuringDay")
    occupant_count: int = Field(default=1, ge=1, le=20, alias="occupantCount")
    heating_not_used_this_month: bool = Field(default=True, alias="heatingNotUsedThisMonth")
    heating_hours: Optional[HoursBucket] = Field(default="2-4", alias="heatingHours")
    cooling_not_used_this_month: bool = Field(default=True, alias="coolingNotUsedThisMonth")
    cooling_hours: Optional[HoursBucket] = Field(default="2-4", alias="coolingHours")
    pool_not_used_this_month: bool = Field(default=True, alias="poolNotUsedThisMonth")
    pool_hours: Optional[HoursBucket] = Field(default="0-2", alias="poolHours")
    ev_not_used_this_month: bool = Field(default=True, alias="evNotUsedThisMonth")
    ev_hours: Optional[HoursBucket] = Field(default="0-2", alias="evHours")
    hot_water_not_used_this_month: bool = Field(default=True, alias="hotWaterNotUsedThisMonth")
    hot_water_hours: Optional[HoursBucket] = Field(default="0-2", alias="hotWaterHours")
    observed_monthly_usage: list[ObservedMonthlyUsage] = Field(
        default_factory=list,
        alias="observedMonthlyUsage",
        description="Optional canonical monthly bill totals. These override survey-derived values for matching months.",
    )

    @model_validator(mode="after")
    def validate_observed_months(self) -> "SurveyFormData":
        months = [record.month.month for record in self.observed_monthly_usage]
        if len(months) != len(set(months)):
            raise ValueError("observedMonthlyUsage contains duplicate calendar months")
        return self
class AnnualEstimationRequest(ApiModel):
    address: Optional[str] = None
    scenario: Optional[str] = None
    target_annual_kwh: Optional[float] = Field(default=None, alias="targetAnnualKwh")
    target_system_size_kw: Optional[float] = Field(default=6.5, alias="targetSystemSizeKw")
    form_data: SurveyFormData = Field(..., alias="formData")
    mock: bool = False


class MonthlyDemandEstimate(ApiModel):
    calendar_month: int = Field(ge=1, le=12)
    month_name: str
    usage_kwh: float = Field(ge=0)
    daytime_usage_ratio: float = Field(ge=0, le=1)
    source: Literal["observed_bill", "bill_period_derived", "survey_derived"]


class AnnualEstimationResponse(ApiModel):
    estimated_annual_usage_kwh: float
    monthly_usage: list[MonthlyDemandEstimate]
    observed_month_count: int = Field(ge=0, le=12)
    profile_source: Literal[
        "observed_bills",
        "observed_and_survey_derived",
        "single_bill_and_survey",
    ]
    data_quality: Literal["high", "medium", "low"]
