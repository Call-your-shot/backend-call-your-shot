from fastapi.testclient import TestClient

from app.main import app
from app.schemas.sizing import SolarSizingRequest
from app.utils.solar_sizing import recommend_solar_system


client = TestClient(app)


def sizing_payload(monthly_usage_kwh: float = 350) -> dict:
    return {
        "monthlyDemand": [
            {
                "calendarMonth": month,
                "usageKwh": monthly_usage_kwh,
                "daytimeUsageRatio": 0.4,
                "source": "survey_derived",
            }
            for month in range(1, 13)
        ],
        "candidates": [
            {
                "candidateId": f"manual-{panels}",
                "source": "manual",
                "panelCount": panels,
                "panelWatts": 440,
                "systemSizeKw": panels * 0.44,
                "annualGenerationKwh": panels * 0.44 * 1400,
            }
            for panels in (6, 10, 14, 18, 22)
        ],
        "simulation": {"iterations": 100, "forecastYears": 25, "randomSeed": 42},
    }


def test_sizing_recommends_economic_system_not_roof_maximum():
    result = recommend_solar_system(
        SolarSizingRequest.model_validate(sizing_payload())
    )

    assert result.status == "viable"
    assert result.recommended_panel_count is not None
    assert result.recommended_panel_count < result.roof_maximum_panel_count
    assert len(result.monthly_usage_weights) == 12
    assert sum(result.monthly_usage_weights) == 1
    assert result.alternatives[-1].panel_count == result.roof_maximum_panel_count
    assert result.alternatives[-1].qualified is False


def test_higher_household_demand_does_not_reduce_recommended_panel_count():
    low = recommend_solar_system(
        SolarSizingRequest.model_validate(sizing_payload(250))
    )
    high = recommend_solar_system(
        SolarSizingRequest.model_validate(sizing_payload(650))
    )

    assert low.recommended_panel_count is not None
    assert high.recommended_panel_count is not None
    assert high.recommended_panel_count >= low.recommended_panel_count


def test_sizing_is_reproducible_with_same_seed():
    request = SolarSizingRequest.model_validate(sizing_payload())

    first = recommend_solar_system(request).model_dump()
    second = recommend_solar_system(request).model_dump()

    assert first == second


def test_sizing_endpoint_and_aliases():
    response = client.post("/api/v1/solar-sizing/recommend", json=sizing_payload())

    assert response.status_code == 200
    data = response.json()
    assert data["recommendedPanelCount"] < data["roofMaximumPanelCount"]
    assert data["selectionMethod"] == "monthly_demand_economic_candidate_simulation"


def test_sizing_rejects_missing_or_duplicate_months():
    payload = sizing_payload()
    payload["monthlyDemand"][-1]["calendarMonth"] = 11

    response = client.post("/api/v1/solar-sizing/recommend", json=payload)

    assert response.status_code == 422
