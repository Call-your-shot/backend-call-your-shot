from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, status

from ..data import ENERGY_READINGS, PROPERTY, PROPERTY_ID, SOLAR_ASSESSMENTS, SOLAR_INSTALLATIONS, TARIFF, TARIFFS
from ..schemas import (
    Battery,
    Dashboard,
    EnergyReading,
    EnergyReadingInput,
    ListResponse,
    MeterIngestionRequest,
    Property,
    SolarAssessmentInput,
    SolarInstallation,
    SolarInstallationInput,
    Tariff,
    TariffInput,
)
from ..utils import battery_snapshot, build_readings, dashboard_summary, estimate_solar, normalize_reading

router = APIRouter(prefix="/api", tags=["energy"])


def require_property(property_id: str) -> None:
    if property_id != PROPERTY_ID:
        raise HTTPException(status_code=404, detail="Property not found")


def property_readings(property_id: str) -> list[dict]:
    return [reading for reading in ENERGY_READINGS if reading["property_id"] == property_id]


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
    readings = [*build_readings(limit), *property_readings(property_id)]
    readings = sorted(readings, key=lambda row: row["interval_start"], reverse=True)[:limit]
    return {"data": [EnergyReading(**row) for row in readings]}


@router.post(
    "/properties/{property_id}/energy-readings",
    response_model=EnergyReading,
    status_code=status.HTTP_201_CREATED,
)
def create_energy_reading(property_id: str, payload: EnergyReadingInput) -> EnergyReading:
    require_property(property_id)
    row = normalize_reading(payload.model_dump(), property_id, str(uuid4()))
    ENERGY_READINGS.append(row)
    return EnergyReading(**row)


@router.get("/properties/{property_id}/batteries", response_model=ListResponse)
def list_batteries(property_id: str) -> dict[str, list[Battery]]:
    require_property(property_id)
    return {"data": [Battery(**battery_snapshot(build_readings()))]}


@router.get("/properties/{property_id}/tariffs", response_model=ListResponse)
def list_tariffs(property_id: str) -> dict[str, list[Tariff]]:
    require_property(property_id)
    return {"data": [Tariff(**tariff) for tariff in TARIFFS if tariff["property_id"] == property_id]}


@router.post(
    "/properties/{property_id}/tariffs",
    response_model=Tariff,
    status_code=status.HTTP_201_CREATED,
)
def create_tariff(property_id: str, payload: TariffInput) -> Tariff:
    require_property(property_id)
    body = payload.model_dump()
    tariff = {
        "id": str(uuid4()),
        "property_id": property_id,
        "name": body["name"],
        "usage_rate_per_kwh": body["usage_rate_per_kwh"],
        "grid_rate_cents_per_kwh": body["grid_rate_cents_per_kwh"] or body["usage_rate_per_kwh"] * 100,
        "feed_in_rate_per_kwh": body["feed_in_rate_per_kwh"],
        "daily_supply_charge": body["daily_supply_charge"],
        "currency": body["currency"],
        "valid_from": body["valid_from"].isoformat(),
        "valid_to": body["valid_to"].isoformat() if body["valid_to"] else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    TARIFFS.insert(0, tariff)
    return Tariff(**tariff)


@router.get("/properties/{property_id}/solar-assessments", response_model=ListResponse)
def list_solar_assessments(property_id: str) -> dict:
    require_property(property_id)
    return {"data": [row for row in SOLAR_ASSESSMENTS if row["property_id"] == property_id]}


@router.post(
    "/properties/{property_id}/solar-assessments",
    status_code=status.HTTP_201_CREATED,
)
def create_solar_assessment(property_id: str, payload: SolarAssessmentInput) -> dict:
    require_property(property_id)
    body = payload.model_dump()
    estimate = estimate_solar(body)
    assessment = {
        "id": str(uuid4()),
        "property_id": property_id,
        "provider": body["provider"],
        "image_path": body["image_path"],
        "image_source": body["image_source"],
        "latitude": body["latitude"],
        "longitude": body["longitude"],
        "imagery_date": body["imagery_date"].isoformat() if body["imagery_date"] else None,
        "imagery_quality": body["imagery_quality"],
        "roof_area_m2": body["roof_area_m2"],
        "panel_count": body["panel_count"] or estimate["estimated_panel_count"],
        "panel_wattage": body["panel_wattage"],
        "monthly_generation_weights": body["monthly_generation_weights"],
        "generation_uncertainty_percentage": body["generation_uncertainty_percentage"],
        "roof_segments_json": body["roof_segments_json"],
        "selected_configuration_json": body["selected_configuration_json"],
        **estimate,
        "status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    SOLAR_ASSESSMENTS.insert(0, assessment)
    return {"data": assessment, "label": "Estimate only"}


@router.get("/properties/{property_id}/solar-installations", response_model=ListResponse)
def list_solar_installations(property_id: str) -> dict:
    require_property(property_id)
    return {"data": [SolarInstallation(**row) for row in SOLAR_INSTALLATIONS if row["property_id"] == property_id]}


@router.post(
    "/properties/{property_id}/solar-installations",
    response_model=SolarInstallation,
    status_code=status.HTTP_201_CREATED,
)
def create_solar_installation(property_id: str, payload: SolarInstallationInput) -> SolarInstallation:
    require_property(property_id)
    body = payload.model_dump()
    installation = {
        "id": str(uuid4()),
        "property_id": property_id,
        "solar_assessment_id": str(body["solar_assessment_id"]) if body["solar_assessment_id"] else None,
        "installation_date": body["installation_date"].date().isoformat() if body["installation_date"] else None,
        "commissioned_at": body["commissioned_at"].isoformat() if body["commissioned_at"] else None,
        "installed_capacity_kw": body["installed_capacity_kw"],
        "gross_installation_cost_cents": body["gross_installation_cost_cents"],
        "stc_benefit_cents": body["stc_benefit_cents"],
        "other_rebates_cents": body["other_rebates_cents"],
        "currency": body["currency"].upper(),
        "status": body["status"],
    }
    SOLAR_INSTALLATIONS.insert(0, installation)
    return SolarInstallation(**installation)


@router.post("/internal/meter-readings", status_code=status.HTTP_201_CREATED)
def ingest_meter_readings(payload: MeterIngestionRequest) -> dict:
    ingested = []
    for reading in payload.readings:
        property_id = str(reading.property_id)
        require_property(property_id)
        row = normalize_reading(reading.model_dump(exclude={"property_id"}), property_id, str(uuid4()))
        ENERGY_READINGS.append(row)
        ingested.append(
            {
                "id": row["id"],
                "property_id": row["property_id"],
                "interval_start": row["interval_start"],
                "interval_end": row["interval_end"],
            }
        )
    return {"data": ingested, "ingested": len(ingested)}


@router.get("/v1/telemetry/live")
def get_live_telemetry_snapshot() -> dict:
    readings = property_readings(PROPERTY_ID) or build_readings(1)
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
