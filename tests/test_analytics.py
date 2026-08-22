import pytest
from unittest.mock import patch, AsyncMock
import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.analytics_service import (
    get_import_rate,
    parse_timestamp_hour,
    process_telemetry_timeseries,
)

from app.clients.mock_iot_client import fetch_timeseries_telemetry, get_mock_iot_api_url


client = TestClient(app)


def test_import_tariff_rates():
    # Peak: 17:00 - 21:00 (hours 17, 18, 19, 20)
    for hour in [17, 18, 19, 20]:
        assert get_import_rate(hour) == 0.38

    # Shoulder: 07:00 - 17:00 (hours 7 to 16)
    for hour in [7, 8, 12, 16]:
        assert get_import_rate(hour) == 0.24

    # Off-Peak: 21:00 - 07:00 (hours 21..23, 0..6)
    for hour in [21, 22, 23, 0, 1, 5, 6]:
        assert get_import_rate(hour) == 0.16


def test_parse_timestamp_hour():
    assert parse_timestamp_hour("2026-08-22T17:00:00Z") == 17
    assert parse_timestamp_hour("2026-08-22T08:30:00+00:00") == 8
    assert parse_timestamp_hour("invalid-date") == 0


def test_process_telemetry_timeseries_calculations():
    # Construct 2 mock telemetry packets (hour 00:00 and hour 01:00)
    packet_0 = {
        "timestamp": "2026-08-22T00:00:00Z",
        "grid_meter": {"energy_import_total_kwh": 5000.0, "energy_export_total_kwh": 1000.0},
        "solar_inverter": {"energy_total_generated_kwh": 2000.0},
        "battery_bms": {"energy_charged_total_kwh": 500.0, "energy_discharged_total_kwh": 400.0, "soc_percent": 50.0},
    }
    packet_1 = {
        "timestamp": "2026-08-22T01:00:00Z",
        "grid_meter": {"energy_import_total_kwh": 5002.0, "energy_export_total_kwh": 1000.5},
        "solar_inverter": {"energy_total_generated_kwh": 2003.0},
        "battery_bms": {"energy_charged_total_kwh": 501.0, "energy_discharged_total_kwh": 400.2, "soc_percent": 48.0},
    }

    response = process_telemetry_timeseries("2026-08-22", [packet_0, packet_1])

    assert response.date == "2026-08-22"
    assert len(response.hourly_breakdown) == 2

    # Hour 1 calculations:
    # solar_gen = 2003 - 2000 = 3.0
    # grid_import = 5002 - 5000 = 2.0
    # grid_export = 1000.5 - 1000 = 0.5
    # bat_charge = 501 - 500 = 1.0
    # bat_discharge = 400.2 - 400 = 0.2
    # room_load = max(0, 3.0 + 2.0 - 0.5 - 1.0 + 0.2) = 3.7
    # solar_self_consumed = max(0, 3.0 - 0.5 - 1.0) = 1.5
    item_1 = response.hourly_breakdown[1]
    assert item_1.solar_gen_kwh == 3.0
    assert item_1.grid_import_kwh == 2.0
    assert item_1.grid_export_kwh == 0.5
    assert item_1.bat_charge_kwh == 1.0
    assert item_1.bat_discharge_kwh == 0.2
    assert item_1.room_load_kwh == 3.7
    assert item_1.solar_self_consumed_kwh == 1.5

    # Hour 01:00 is off-peak ($0.16)
    assert item_1.import_rate == 0.16
    # cost_without_solar = 3.7 * 0.16 = 0.592
    assert item_1.cost_without_solar == 0.592
    # actual_cost = (2.0 * 0.16) - (0.5 * 0.07) = 0.32 - 0.035 = 0.285
    assert item_1.actual_cost == 0.285
    # hourly_savings = 0.592 - 0.285 = 0.307
    assert item_1.hourly_savings == 0.307
    # co2_offset = 3.0 * 0.70 = 2.1
    assert item_1.co2_offset_kg == 2.1


@pytest.mark.anyio
async def test_fetch_timeseries_telemetry_502_error_handling():

    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Connection refused")):
        with pytest.raises(HTTPException) as exc_info:
            await fetch_timeseries_telemetry("2026-08-22", "sunny")
        assert exc_info.value.status_code == 502
        assert "Failed to fetch telemetry from external IoT mock server" in exc_info.value.detail


def test_dashboard_endpoint_success():
    mock_packets = [
        {
            "timestamp": "2026-08-22T00:00:00Z",
            "grid_meter": {"energy_import_total_kwh": 5000.0, "energy_export_total_kwh": 1000.0},
            "solar_inverter": {"energy_total_generated_kwh": 2000.0},
            "battery_bms": {"energy_charged_total_kwh": 500.0, "energy_discharged_total_kwh": 400.0, "soc_percent": 50.0},
        }
    ]

    with patch("app.routers.analytics.fetch_timeseries_telemetry", new_callable=AsyncMock) as mock_fetch:

        mock_fetch.return_value = mock_packets

        res = client.get("/api/v1/analytics/dashboard?date=2026-08-22&weather=sunny")
        assert res.status_code == 200
        json_data = res.json()
        assert json_data["date"] == "2026-08-22"
        assert "total_load_kwh" in json_data
        assert "hourly_breakdown" in json_data
        assert len(json_data["hourly_breakdown"]) == 1
