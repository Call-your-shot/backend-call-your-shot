from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


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
    grid_import_kwh: float = Field(ge=0)
    grid_export_kwh: float = Field(ge=0)
    battery_charge_kwh: float = Field(ge=0)
    battery_discharge_kwh: float = Field(ge=0)
    battery_soc_pct: float = Field(ge=0, le=100)
    source: str


class EnergyReadingInput(ApiModel):
    meter_id: Optional[UUID] = Field(default=None, alias="meterId")
    interval_start: datetime = Field(alias="intervalStart")
    interval_end: datetime = Field(alias="intervalEnd")
    consumption_kwh: float = Field(default=0, ge=0, alias="consumptionKwh")
    solar_generation_kwh: float = Field(default=0, ge=0, alias="solarGenerationKwh")
    grid_import_kwh: float = Field(default=0, ge=0, alias="gridImportKwh")
    grid_export_kwh: float = Field(default=0, ge=0, alias="gridExportKwh")
    battery_charge_kwh: float = Field(default=0, ge=0, alias="batteryChargeKwh")
    battery_discharge_kwh: float = Field(default=0, ge=0, alias="batteryDischargeKwh")
    battery_soc_pct: Optional[float] = Field(default=None, ge=0, le=100, alias="batterySocPct")
    source: Literal["mock", "meter_api", "manual", "simulation"] = "manual"

    @model_validator(mode="after")
    def check_interval(self) -> "EnergyReadingInput":
        if self.interval_end <= self.interval_start:
            raise ValueError("intervalEnd must be after intervalStart")
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
    image_path: Optional[str] = Field(default=None, alias="imagePath")
    image_source: Optional[str] = Field(default=None, alias="imageSource")
    roof_area_m2: Optional[float] = Field(default=None, ge=0, alias="roofAreaM2")
    usable_roof_area_m2: Optional[float] = Field(default=None, ge=0, alias="usableRoofAreaM2")
    assumptions: dict[str, Any] = Field(default_factory=dict)


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


class ListResponse(BaseModel):
    data: list[Any]
