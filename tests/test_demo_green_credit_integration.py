from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.demo_green_credit_repository import reset_demo_green_credit_state
from app.green_credit_repository import GreenCreditRepositoryError
from app.main import app
from app.routers import green_credits

SARAH_EMAIL = "sarah.chen@example.com"
PROJECT_ID = "13131313-1313-4131-8131-131313131313"


@pytest.fixture(autouse=True)
def clean_demo_state(monkeypatch):
    app.dependency_overrides.clear()
    monkeypatch.setenv("GREEN_CREDIT_DEMO_AUTH", "true")
    reset_demo_green_credit_state()
    yield
    app.dependency_overrides.clear()
    reset_demo_green_credit_state()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_demo_email_returns_frontend_wallet(client):
    response = client.get(
        "/api/v1/green-credits/wallet", params={"email": SARAH_EMAIL}
    )

    assert response.status_code == 200
    assert response.json() == {
        "account_id": response.json()["account_id"],
        "status": "active",
        "available_credits": "2310.000000",
        "lifetime_earned_credits": "3510.000000",
        "lifetime_allocated_credits": "1200.000000",
        "verified_solar_kwh": 5014.0,
    }


def test_demo_project_catalog_exposes_frontend_sponsor_metadata(client):
    response = client.get(
        "/api/v1/green-projects", params={"email": SARAH_EMAIL}
    )

    assert response.status_code == 200
    project = next(item for item in response.json()["data"] if item["id"] == PROJECT_ID)
    assert project["target_credits"] == "250000.000000"
    assert project["funded_credits"] == "162450.000000"
    assert project["image_path"] == "/green-projects/illawarra-community-battery.webp"
    assert project["metadata"] == {
        "curated": True,
        "sponsor_name": "BrightGrid Community Fund",
        "sponsor_commitment_dollars": 2500,
        "credits_per_sponsor_dollar": 100,
    }


def test_demo_allocation_persists_and_is_idempotent(client):
    request = {
        "requested_credits": "250.000000",
        "idempotency_key": "frontend-allocation-001",
    }
    params = {"email": SARAH_EMAIL}

    first = client.post(
        f"/api/v1/green-projects/{PROJECT_ID}/allocations",
        params=params,
        json=request,
    )
    replay = client.post(
        f"/api/v1/green-projects/{PROJECT_ID}/allocations",
        params=params,
        json=request,
    )
    wallet = client.get("/api/v1/green-credits/wallet", params=params)
    allocations = client.get("/api/v1/green-credits/allocations", params=params)
    ledger = client.get("/api/v1/green-credits/ledger", params=params)

    assert first.status_code == 201
    assert first.json()["allocated_credits"] == "250.000000"
    assert first.json()["available_balance_credits"] == "2060.000000"
    assert first.json()["idempotent_replay"] is False
    assert replay.status_code == 201
    assert replay.json()["allocation_id"] == first.json()["allocation_id"]
    assert replay.json()["idempotent_replay"] is True
    assert wallet.json()["available_credits"] == "2060.000000"
    assert wallet.json()["lifetime_allocated_credits"] == "1450.000000"
    assert len(allocations.json()["data"]) == 1
    assert ledger.json()["data"][0]["entry_type"] == "allocate"


def test_new_demo_email_gets_empty_wallet(client):
    response = client.get(
        "/api/v1/green-credits/wallet", params={"email": "new.user@example.com"}
    )

    assert response.status_code == 200
    assert response.json()["available_credits"] == "0.000000"


def test_invalid_demo_email_is_a_validation_error(client):
    response = client.get(
        "/api/v1/green-credits/wallet", params={"email": "not-an-email"}
    )

    assert response.status_code == 422


def test_demo_email_auth_can_be_disabled_for_production(client, monkeypatch):
    monkeypatch.setenv("GREEN_CREDIT_DEMO_AUTH", "false")

    response = client.get(
        "/api/v1/green-credits/wallet", params={"email": SARAH_EMAIL}
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTHENTICATION_ERROR"


def test_invalid_bearer_does_not_fall_back_to_demo_email(client, monkeypatch):
    def reject_token(_token: str):
        raise GreenCreditRepositoryError(
            "Invalid or expired bearer token", 401, "AUTHENTICATION_ERROR"
        )

    monkeypatch.setattr(green_credits, "create_user_repository", reject_token)

    response = client.get(
        "/api/v1/green-credits/wallet",
        params={"email": SARAH_EMAIL},
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["message"] == "Invalid or expired bearer token"
