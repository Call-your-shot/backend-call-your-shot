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

    assert len(res.monthly_usage) == 12
    assert res.estimated_annual_usage_kwh == pytest.approx(
        sum(month.usage_kwh for month in res.monthly_usage), abs=0.1
    )
    assert res.observed_month_count == 1
    assert res.profile_source == "single_bill_and_survey"
    assert res.data_quality == "low"
    assert res.estimated_annual_usage_kwh > 785 / 61 * 365


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


def test_estimation_schema_accepts_nullable_home_during_day():
    response = client.post(
        "/api/v1/analytics/estimate-annual-load",
        json={
            "formData": {
                "address": "64 Corrimal St, Wollongong NSW 2500, Australia",
                "billUsageKwh": 785,
                "billingPeriodStart": "2024-03-20",
                "billingPeriodEnd": "2024-05-20",
                "billTotalCostDollars": None,
                "homeDuringDay": None,
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
            }
        },
    )

    assert response.status_code == 200
    assert response.json()["estimated_annual_usage_kwh"] > 0


def test_estimation_schema_rejects_unknown_hours_bucket():
    response = client.post(
        "/api/v1/analytics/estimate-annual-load",
        json={
            "formData": {
                "billUsageKwh": 785,
                "billingPeriodStart": "2024-03-20",
                "billingPeriodEnd": "2024-05-20",
                "heatingHours": "all-day",
            }
        },
    )

    assert response.status_code == 422


def test_estimation_openapi_marks_billing_dates_as_date_fields():
    schema = app.openapi()["components"]["schemas"]["SurveyFormData"]

    assert schema["properties"]["billingPeriodStart"]["format"] == "date"
    assert schema["properties"]["billingPeriodEnd"]["format"] == "date"


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


def test_observed_months_are_preserved_and_profiles_reconcile():
    request = AnnualEstimationRequest.model_validate(
        {
            "formData": {
                "billUsageKwh": 620,
                "billingPeriodStart": "2026-01-01",
                "billingPeriodEnd": "2026-02-01",
                "homeDuringDay": "sometimes",
                "observedMonthlyUsage": [
                    {"month": "2026-01-01", "usageKwh": 620},
                    {"month": "2026-07-01", "usageKwh": 810},
                ],
            }
        }
    )

    result = calculate_annual_energy_estimation(request)
    monthly = {item.calendar_month: item for item in result.monthly_usage}

    assert monthly[1].usage_kwh == 620
    assert monthly[7].usage_kwh == 810
    assert monthly[1].source == "observed_bill"
    assert result.observed_month_count == 2
    assert result.profile_source == "observed_and_survey_derived"
    assert result.estimated_annual_usage_kwh == pytest.approx(
        sum(item.usage_kwh for item in result.monthly_usage), abs=0.1
    )


def test_daytime_occupancy_changes_overlap_not_measured_energy():
    base = {
        "billUsageKwh": 620,
        "billingPeriodStart": "2026-01-01",
        "billingPeriodEnd": "2026-02-01",
    }
    most = calculate_annual_energy_estimation(
        AnnualEstimationRequest.model_validate(
            {"formData": {**base, "homeDuringDay": "most"}}
        )
    )
    rarely = calculate_annual_energy_estimation(
        AnnualEstimationRequest.model_validate(
            {"formData": {**base, "homeDuringDay": "rarely"}}
        )
    )

    assert most.estimated_annual_usage_kwh == rarely.estimated_annual_usage_kwh
    assert most.monthly_usage[0].daytime_usage_ratio > rarely.monthly_usage[0].daytime_usage_ratio


def test_duplicate_observed_calendar_months_are_rejected():
    response = client.post(
        "/api/v1/analytics/estimate-annual-load",
        json={
            "formData": {
                "billUsageKwh": 620,
                "billingPeriodStart": "2026-01-01",
                "billingPeriodEnd": "2026-02-01",
                "observedMonthlyUsage": [
                    {"month": "2025-01-01", "usageKwh": 500},
                    {"month": "2026-01-01", "usageKwh": 510},
                ],
            }
        },
    )

    assert response.status_code == 422
