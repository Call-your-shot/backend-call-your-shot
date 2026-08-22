from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from fastapi_app.main import app
from fastapi_app.ingestion_service import RAW_TELEMETRY_DB, ingest_raw_telemetry, query_raw_telemetry

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_telemetry_db():
    RAW_TELEMETRY_DB.clear()
    yield
    RAW_TELEMETRY_DB.clear()


@pytest.mark.anyio
async def test_ingest_raw_telemetry_service():
    mock_packets = [
        {
            "timestamp": "2026-08-22T12:00:00Z",
            "grid_meter": {
                "device_id": "meter_grid_01",
                "timestamp": "2026-08-22T12:00:00Z",
                "voltage_rms_v": 232.4,
                "current_rms_a": 0.0,
                "active_power_w": 0.0,
                "reactive_power_var": 0.0,
                "power_factor": 0.97,
                "frequency_hz": 50.08,
                "energy_import_total_kwh": 4120.72,
                "energy_export_total_kwh": 3546.66,
            },
            "solar_inverter": {
                "device_id": "inverter_pv_01",
                "timestamp": "2026-08-22T12:00:00Z",
                "pv_voltage_dc_v": 224.2,
                "pv_current_dc_a": 7.7,
                "pv_power_dc_w": 1726.3,
                "ac_power_w": 1657.2,
                "inverter_temp_c": 50.8,
                "operating_status": "Producing",
                "energy_total_generated_kwh": 5831.5,
            },
            "battery_bms": {
                "device_id": "bms_storage_01",
                "timestamp": "2026-08-22T12:00:00Z",
                "soc_percent": 100.0,
                "soh_percent": 98.5,
                "pack_voltage_v": 54.6,
                "pack_current_a": 0.0,
                "battery_power_w": 0.0,
                "cell_temp_c": 22.1,
                "bms_state": "Full",
                "cycle_count": 342,
                "energy_charged_total_kwh": 852.55,
                "energy_discharged_total_kwh": 780.4,
            },
        }
    ]

    with patch("fastapi_app.ingestion_service.fetch_timeseries_telemetry", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_packets

        res = await ingest_raw_telemetry("2026-08-22", "sunny")

        assert res.status == "success"
        assert res.count == 1
        assert res.date == "2026-08-22"
        assert len(RAW_TELEMETRY_DB) == 1
        assert RAW_TELEMETRY_DB[0]["grid_meter"]["device_id"] == "meter_grid_01"


def test_ingestion_endpoints_flow():
    mock_packets = [
        {
            "timestamp": "2026-08-22T00:00:00Z",
            "grid_meter": {
                "device_id": "meter_grid_01",
                "timestamp": "2026-08-22T00:00:00Z",
                "voltage_rms_v": 230.0,
                "current_rms_a": 0.0,
                "active_power_w": 0.0,
                "reactive_power_var": 0.0,
                "power_factor": 0.97,
                "frequency_hz": 50.0,
                "energy_import_total_kwh": 5000.0,
                "energy_export_total_kwh": 1000.0,
            },
            "solar_inverter": {
                "device_id": "inverter_pv_01",
                "timestamp": "2026-08-22T00:00:00Z",
                "pv_voltage_dc_v": 0.0,
                "pv_current_dc_a": 0.0,
                "pv_power_dc_w": 0.0,
                "ac_power_w": 0.0,
                "inverter_temp_c": 20.0,
                "operating_status": "Off",
                "energy_total_generated_kwh": 2000.0,
            },
            "battery_bms": {
                "device_id": "bms_storage_01",
                "timestamp": "2026-08-22T00:00:00Z",
                "soc_percent": 50.0,
                "soh_percent": 98.0,
                "pack_voltage_v": 51.2,
                "pack_current_a": 0.0,
                "battery_power_w": 0.0,
                "cell_temp_c": 22.0,
                "bms_state": "Idle",
                "cycle_count": 100,
                "energy_charged_total_kwh": 500.0,
                "energy_discharged_total_kwh": 400.0,
            },
        }
    ]

    with patch("fastapi_app.routers.ingestion.ingest_raw_telemetry", new_callable=AsyncMock) as mock_ingest:
        from fastapi_app.schemas import IngestTelemetryResponse, TelemetryPacket

        mock_ingest.return_value = IngestTelemetryResponse(
            status="success",
            message="Ingested",
            date="2026-08-22",
            weather="sunny",
            count=1,
            ingested_at="2026-08-22T00:00:00Z",
            records=[TelemetryPacket(**mock_packets[0])],
        )

        res = client.post("/api/v1/ingestion/telemetry?date=2026-08-22&weather=sunny")
        assert res.status_code == 201
        data = res.json()
        assert data["status"] == "success"
        assert data["count"] == 1

    # Test GET /api/v1/ingestion/telemetry query endpoint
    RAW_TELEMETRY_DB.append(
        {
            "date": "2026-08-22",
            "raw_payload": mock_packets[0],
        }
    )
    res_get = client.get("/api/v1/ingestion/telemetry?date=2026-08-22")
    assert res_get.status_code == 200
    query_data = res_get.json()
    assert query_data["count"] == 1
    assert query_data["data"][0]["grid_meter"]["device_id"] == "meter_grid_01"
