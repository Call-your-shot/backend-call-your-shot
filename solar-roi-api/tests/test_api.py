import asyncio
from copy import deepcopy

import httpx

from app.main import app


def request(method: str, path: str, json: dict | None = None) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.request(method, path, json=json)

    return asyncio.run(send())


def test_health() -> None:
    assert request("GET", "/health").json() == {"status": "ok"}


def test_analyse_returns_primary_metrics(valid_payload: dict) -> None:
    response = request("POST", "/api/v1/roi/analyse", valid_payload)
    assert response.status_code == 200
    body = response.json()
    assert body["installation"]["net_installation_cost_dollars"] == 7500
    assert body["roi"]["capital_recovered_dollars"] == 179.9
    assert body["roi"]["remaining_cost_dollars"] == 7320.1
    assert len(body["monthly_history"]) == 2
    assert body["scenarios"]["expected"]["payback_reached"] is True


def test_summary_reuses_analysis(valid_payload: dict) -> None:
    response = request("POST", "/api/v1/roi/summary", valid_payload)
    assert response.status_code == 200
    body = response.json()
    assert body["capital_recovered_percentage"] == 2.4
    assert "forecast_months" not in body


def test_forecast_endpoint_is_focused(valid_payload: dict) -> None:
    response = request("POST", "/api/v1/roi/forecast", valid_payload)
    assert response.status_code == 200
    assert set(response.json()) == {
        "forecast",
        "scenarios",
        "forecast_months",
        "warnings",
    }


def test_history_endpoint_has_no_forecast(valid_payload: dict) -> None:
    response = request("POST", "/api/v1/roi/history-analysis", valid_payload)
    assert response.status_code == 200
    assert "forecast" not in response.json()
    assert "seasonality" in response.json()


def test_invalid_input_returns_validation_error(valid_payload: dict) -> None:
    payload = deepcopy(valid_payload)
    payload["installation"]["gross_installation_cost_dollars"] = -1
    assert request("POST", "/api/v1/roi/analyse", payload).status_code == 422


def test_missing_optional_values_are_accepted(valid_payload: dict) -> None:
    payload = deepcopy(valid_payload)
    payload["installation"].pop("installed_capacity_kw")
    for month in payload["history"]:
        month.pop("solar_consumed_by_tenant_kwh")
    response = request("POST", "/api/v1/roi/analyse", payload)
    assert response.status_code == 200
    codes = {warning["code"] for warning in response.json()["warnings"]}
    assert {"DERIVED_SOLAR_CONSUMPTION", "MISSING_INSTALLED_CAPACITY"} <= codes


def test_already_paid_back_is_historical(valid_payload: dict) -> None:
    payload = deepcopy(valid_payload)
    payload["installation"].update(
        {"gross_installation_cost_dollars": 100, "stc_benefit_dollars": 0}
    )
    response = request("POST", "/api/v1/roi/analyse", payload)
    assert response.status_code == 200
    forecast = response.json()["forecast"]
    assert forecast["payback_type"] == "historical"
    assert forecast["estimated_months_remaining"] == 0
    assert forecast["estimated_payback_date"] == "2025-08"


def test_zero_cost_is_immediate(valid_payload: dict) -> None:
    payload = deepcopy(valid_payload)
    payload["installation"].update(
        {"gross_installation_cost_dollars": 0, "stc_benefit_dollars": 0}
    )
    response = request("POST", "/api/v1/roi/analyse", payload)
    assert response.status_code == 200
    assert response.json()["forecast"]["payback_type"] == "immediate"


def test_negative_cashflow_returns_null_payback(valid_payload: dict) -> None:
    payload = deepcopy(valid_payload)
    for month in payload["history"]:
        month.update(
            {
                "tenant_revenue_dollars": 0,
                "export_revenue_dollars": 0,
                "operating_cost_dollars": 20,
            }
        )
    payload["forecast_assumptions"]["forecast_horizon_months"] = 12
    response = request("POST", "/api/v1/roi/analyse", payload)
    assert response.status_code == 200
    assert response.json()["forecast"]["payback_reached"] is False


def test_openapi_exposes_all_roi_routes() -> None:
    schema = request("GET", "/openapi.json").json()
    paths = schema["paths"]
    assert "/api/v1/roi/analyse" in paths
    assert "/api/v1/roi/summary" in paths
    assert "/api/v1/roi/forecast" in paths
    assert "/api/v1/roi/history-analysis" in paths
    assert "/api/v1/roi/estimate-initial" in paths


def test_initial_estimate_dynamic_request(initial_estimate_payload: dict) -> None:
    response = request("POST", "/api/v1/roi/estimate-initial", initial_estimate_payload)
    assert response.status_code == 200
    body = response.json()
    assert body["forecast_source"] == "assumption_based"
    assert body["simulation"]["iterations"] == 100
    assert body["headline"]["median_payback_years"] is not None
    assert body["forecast_interval"]["level"] == 90


def test_initial_estimate_fixed_request(initial_estimate_payload: dict) -> None:
    payload = deepcopy(initial_estimate_payload)
    payload["pricing"].update(
        {
            "pricing_mode": "fixed",
            "fixed_tenant_solar_rate_cents_per_kwh": 15,
        }
    )
    response = request("POST", "/api/v1/roi/estimate-initial", payload)
    assert response.status_code == 200
    assert response.json()["assumptions"]["pricing_mode"] == "fixed"


def test_initial_estimate_seed_is_reproducible(initial_estimate_payload: dict) -> None:
    first = request(
        "POST", "/api/v1/roi/estimate-initial", initial_estimate_payload
    ).json()
    second = request(
        "POST", "/api/v1/roi/estimate-initial", initial_estimate_payload
    ).json()
    assert first == second


def test_initial_estimate_rejects_invalid_distribution(
    initial_estimate_payload: dict,
) -> None:
    payload = deepcopy(initial_estimate_payload)
    payload["generation"]["annual_variability_percentage"] = -1
    response = request("POST", "/api/v1/roi/estimate-initial", payload)
    assert response.status_code == 422


def test_initial_estimate_rejects_invalid_self_consumption(
    initial_estimate_payload: dict,
) -> None:
    payload = deepcopy(initial_estimate_payload)
    payload["solar_utilisation"]["minimum_self_consumption_ratio"] = 0.8
    response = request("POST", "/api/v1/roi/estimate-initial", payload)
    assert response.status_code == 422


def test_initial_estimate_no_payback(initial_estimate_payload: dict) -> None:
    payload = deepcopy(initial_estimate_payload)
    payload["pricing"].update(
        {"grid_rate_cents_per_kwh": 0, "export_rate_cents_per_kwh": 0}
    )
    payload["costs"]["annual_operating_cost_dollars"] = 0
    response = request("POST", "/api/v1/roi/estimate-initial", payload)
    assert response.status_code == 200
    assert response.json()["probability_no_payback_within_horizon"] == 1
