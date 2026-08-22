from fastapi.testclient import TestClient

from app.data import PROPERTY_ID
from app.main import app


client = TestClient(app)


def test_landlord_dashboard_exposes_final_scope_panels():
    response = client.get(f"/api/properties/{PROPERTY_ID}/dashboard?role=landlord")

    assert response.status_code == 200
    data = response.json()
    assert data["viewer"]["role"] == "landlord"
    assert "usage" in data["role_panels"]
    assert "pricing" in data["role_panels"]
    assert "create_price_adjustment" in data["role_panels"]["actions"]
    assert "generate_ppa_contract" in data["role_panels"]["actions"]
    assert "roi_analytics" in data


def test_tenant_dashboard_focuses_usage_and_savings():
    response = client.get(f"/api/properties/{PROPERTY_ID}/dashboard?role=tenant")

    assert response.status_code == 200
    data = response.json()
    assert data["viewer"]["role"] == "tenant"
    assert data["role_panels"]["usage"]["electricUsageKwh"] > 0
    assert "view_savings" in data["role_panels"]["actions"]
    assert data["roi_analytics"] is None


def test_price_adjustment_lease_request_and_contract_generation():
    price_response = client.post(
        f"/api/properties/{PROPERTY_ID}/price-adjustments",
        json={
            "fixedSolarRateCentsPerKwh": 22,
            "reason": "Fixed price for landlord/agent approval",
            "effectiveFrom": "2026-09-01T00:00:00+00:00",
        },
    )
    assert price_response.status_code == 201
    assert price_response.json()["fixed_solar_rate_cents_per_kwh"] == 22

    lease_response = client.post(
        f"/api/properties/{PROPERTY_ID}/lease-requests",
        json={"requestType": "solar_installation_notice", "message": "Please review the solar PPA terms."},
    )
    assert lease_response.status_code == 201
    assert lease_response.json()["status"] == "submitted"

    contract_response = client.post(
        f"/api/properties/{PROPERTY_ID}/contracts/generate",
        json={
            "contractType": "ppa",
            "title": "Demo Solar PPA Draft",
            "terms": {"fixedSolarRateCentsPerKwh": 22, "exportRateCentsPerKwh": 8},
        },
    )
    assert contract_response.status_code == 201
    contract = contract_response.json()
    assert contract["contract_type"] == "ppa"
    assert "DRAFT" in contract["document_text"]
