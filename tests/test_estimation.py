import pytest
from fastapi.testclient import TestClient

from app.estimation_service import parse_hours_bucket, calculate_annual_energy_estimation
from app.main import app
from app.schemas import AnnualEstimationRequest, SurveyFormData


client = TestClient(app)


def test_parse_hours_bucket():
    assert parse_hours_bucket("0-2") == 1.0
    assert parse_hours_bucket("2-4") == 3.0
    assert parse_hours_bucket("4-6") == 5.0
    assert parse_hours_bucket("6+") == 7.0
    assert parse_hours_bucket("0") == 0.0
    assert parse_hours_bucket(None) == 0.0
    assert parse_hours_bucket("none") == 0.0


def test_calculate_annual_energy_estimation_wollongong_payload():
    payload_dict = {
        "address": "64 Corrimal St, Wollongong NSW 2500, Australia",
        "scenario": "bellambi",
        "targetAnnualKwh": 9094,
        "targetSystemSizeKw": 6.5,
        "formData": {
            "address": "64 Corrimal St, Wollongong NSW 2500, Australia",
            "billUsageKwh": 785,
            "billingPeriodStart": "2024-03-20",
            "billingPeriodEnd": "2024-05-20",
            "billTotalCostDollars": 318.6,
            "homeDuringDay": "most",
            "heatingNotUsedThisMonth": True,
            "heatingHours": "2-4",
            "coolingNotUsedThisMonth": True,
            "coolingHours": "2-4",
            "poolNotUsedThisMonth": True,
            "poolHours": "0-2",
            "evNotUsedThisMonth": True,
            "evHours": "0-2",
            "hotWaterNotUsedThisMonth": True,
            "hotWaterHours": "0-2",
        },
        "mock": False,
    }

    req = AnnualEstimationRequest(**payload_dict)
    res = calculate_annual_energy_estimation(req)

    # 61 days bill: 785 / 61 = 12.86885 kWh/day baseline
    # 12 months extrapolation yielding approximately 5744 - 5746 kWh/year
    assert 5700.0 <= res.estimated_annual_usage_kwh <= 5800.0


def test_estimate_annual_load_endpoint_live():
    payload_json = {
        "address": "64 Corrimal St, Wollongong NSW 2500, Australia",
        "scenario": "bellambi",
        "targetAnnualKwh": 9094,
        "targetSystemSizeKw": 6.5,
        "formData": {
            "address": "64 Corrimal St, Wollongong NSW 2500, Australia",
            "billUsageKwh": 785,
            "billingPeriodStart": "2024-03-20",
            "billingPeriodEnd": "2024-05-20",
            "billTotalCostDollars": 318.6,
            "homeDuringDay": "most",
            "heatingNotUsedThisMonth": True,
            "heatingHours": "2-4",
            "coolingNotUsedThisMonth": True,
            "coolingHours": "2-4",
            "poolNotUsedThisMonth": True,
            "poolHours": "0-2",
            "evNotUsedThisMonth": True,
            "evHours": "0-2",
            "hotWaterNotUsedThisMonth": True,
            "hotWaterHours": "0-2",
        },
        "mock": False,
    }

    response = client.post("/api/v1/analytics/estimate-annual-load", json=payload_json)
    assert response.status_code == 200
    data = response.json()
    assert "estimated_annual_usage_kwh" in data
    assert isinstance(data["estimated_annual_usage_kwh"], float)
    assert data["estimated_annual_usage_kwh"] > 0


def test_invalid_date_ordering():
    payload_json = {
        "formData": {
            "billUsageKwh": 785,
            "billingPeriodStart": "2024-05-20",
            "billingPeriodEnd": "2024-03-20",  # End before start
        }
    }

    response = client.post("/api/v1/analytics/estimate-annual-load", json=payload_json)
    assert response.status_code == 400
    assert "billingPeriodEnd must be after billingPeriodStart" in response.json()["detail"]
