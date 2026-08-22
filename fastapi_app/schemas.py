from __future__ import annotations

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field


class Property(BaseModel):
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


class Battery(BaseModel):
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


class Tariff(BaseModel):
    id: str
    property_id: str
    name: str
    usage_rate_per_kwh: float = Field(ge=0)
    grid_rate_cents_per_kwh: float = Field(ge=0)
    feed_in_rate_per_kwh: float = Field(ge=0)
    daily_supply_charge: float = Field(ge=0)
    currency: str = "AUD"


class EnergyReading(BaseModel):
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
