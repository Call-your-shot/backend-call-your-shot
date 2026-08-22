from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from .data import PROPERTY, PROPERTY_ID, TARIFF
from .schemas import Battery, Dashboard, EnergyReading, ListResponse, Property, Tariff
from .services import battery_snapshot, build_readings, dashboard_summary

router = APIRouter(prefix="/api")


def require_property(property_id: str) -> None:
    if property_id != PROPERTY_ID:
        raise HTTPException(status_code=404, detail="Property not found")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "energy-platform-fastapi"}


@router.get("/properties", response_model=ListResponse)
def list_properties() -> dict[str, list[Property]]:
    return {"data": [Property(**PROPERTY)]}


@router.get("/properties/{property_id}", response_model=Property)
def get_property(property_id: str) -> Property:
    require_property(property_id)
    return Property(**PROPERTY)


@router.get("/properties/{property_id}/dashboard", response_model=Dashboard)
def get_dashboard(
    property_id: str,
    granularity: Literal["hour", "day", "week", "month"] = Query("day"),
) -> dict:
    require_property(property_id)
    return {
        "property": PROPERTY,
        "viewer": {"role": "landlord", "mode": "fastapi_demo"},
        **dashboard_summary(granularity),
    }


@router.get("/properties/{property_id}/energy-readings", response_model=ListResponse)
def list_energy_readings(property_id: str, limit: int = Query(24, ge=1, le=168)) -> dict[str, list[EnergyReading]]:
    require_property(property_id)
    return {"data": [EnergyReading(**row) for row in build_readings(limit)]}


@router.get("/properties/{property_id}/batteries", response_model=ListResponse)
def list_batteries(property_id: str) -> dict[str, list[Battery]]:
    require_property(property_id)
    return {"data": [Battery(**battery_snapshot(build_readings()))]}


@router.get("/properties/{property_id}/tariffs", response_model=ListResponse)
def list_tariffs(property_id: str) -> dict[str, list[Tariff]]:
    require_property(property_id)
    return {"data": [Tariff(**TARIFF)]}


@router.get("/v1/telemetry/live")
def get_live_telemetry_snapshot() -> dict:
    readings = build_readings(1)
    latest = readings[-1]
    battery = battery_snapshot(readings)
    return {
        "property_id": PROPERTY_ID,
        "timestamp": latest["interval_end"],
        "consumption_kwh": latest["consumption_kwh"],
        "solar_generation_kwh": latest["solar_generation_kwh"],
        "grid_import_kwh": latest["grid_import_kwh"],
        "grid_export_kwh": latest["grid_export_kwh"],
        "battery": battery,
        "grid_rate_cents_per_kwh": TARIFF["grid_rate_cents_per_kwh"],
    }
