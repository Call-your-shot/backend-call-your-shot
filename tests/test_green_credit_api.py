from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from fastapi_app.main import app
from fastapi_app.routers.green_credits import (
    get_service_green_credit_repository,
    get_user_green_credit_repository,
)

NOW = "2026-08-22T10:00:00+00:00"
ACCOUNT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
PROJECT_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
ALLOCATION_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
LEDGER_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"


class FakeGreenCreditRepository:
    def __init__(self) -> None:
        self.allocate_calls: list[tuple[str, int, str]] = []
        self.accrue_calls: list[tuple[str, datetime, datetime]] = []
        self.wallet_row: dict[str, Any] | None = {
            "account_id": ACCOUNT_ID,
            "status": "active",
            "available_microcredits": 8_500_000,
            "lifetime_earned_microcredits": 10_000_000,
            "lifetime_allocated_microcredits": 1_500_000,
        }

    def get_wallet(self):
        return self.wallet_row

    def list_ledger(self, limit, cursor):
        return [
            {
                "id": LEDGER_ID,
                "entry_type": "earn",
                "amount_microcredits": 700_000,
                "property_id": ACCOUNT_ID,
                "project_id": None,
                "source_energy_reading_id": LEDGER_ID,
                "source_solar_kwh": "1.0",
                "beneficiary_role": "tenant",
                "description": "Verified solar reward",
                "occurred_at": NOW,
                "created_at": NOW,
            }
        ]

    def list_allocations(self, limit, cursor):
        return [
            {
                "id": ALLOCATION_ID,
                "project_id": PROJECT_ID,
                "requested_microcredits": 2_000_000,
                "allocated_microcredits": 1_500_000,
                "status": "confirmed",
                "idempotency_key": "allocate-123",
                "allocated_at": NOW,
            }
        ]

    def _project(self):
        return {
            "id": PROJECT_ID,
            "slug": "community-battery",
            "title": "Community Battery",
            "description": "Shared renewable storage.",
            "category": "energy_storage",
            "location": "Wollongong, NSW",
            "image_path": None,
            "target_microcredits": 100_000_000,
            "funded_microcredits": 99_000_000,
            "remaining_microcredits": 1_000_000,
            "minimum_allocation_microcredits": 1_000_000,
            "status": "open",
            "impact_unit": "kWh storage",
            "expected_impact": "100",
            "verification_method": "Commissioning evidence",
            "opens_at": NOW,
            "closes_at": "2027-08-22T10:00:00+00:00",
            "metadata": {"curated": True},
            "created_at": NOW,
        }

    def list_projects(self, status, limit, cursor):
        assert status == "open"
        return [self._project()]

    def get_project(self, project_id):
        return self._project() if project_id == PROJECT_ID else None

    def allocate(self, project_id, requested_microcredits, idempotency_key):
        self.allocate_calls.append(
            (project_id, requested_microcredits, idempotency_key)
        )
        return {
            "allocation_id": ALLOCATION_ID,
            "requested_microcredits": requested_microcredits,
            "allocated_microcredits": 1_000_000,
            "partial": True,
            "available_balance_microcredits": 7_500_000,
            "project_remaining_microcredits": 0,
            "project_status": "funded",
            "idempotent_replay": False,
        }

    def accrue(self, property_id, period_start, period_end):
        self.accrue_calls.append((property_id, period_start, period_end))
        return {
            "processed_readings": 24,
            "skipped_readings": 1,
            "ledger_entries_created": 48,
            "tenant_issued_microcredits": 7_000_000,
            "owner_issued_microcredits": 3_000_000,
            "unissued_microcredits": 250_000,
        }


@pytest.fixture
def repository():
    return FakeGreenCreditRepository()


@pytest.fixture
def client(repository):
    app.dependency_overrides[get_user_green_credit_repository] = lambda: repository
    app.dependency_overrides[get_service_green_credit_repository] = lambda: repository
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_wallet_returns_exact_display_credits(client):
    response = client.get("/api/v1/green-credits/wallet")
    assert response.status_code == 200
    assert response.json() == {
        "account_id": ACCOUNT_ID,
        "status": "active",
        "available_credits": "8.500000",
        "lifetime_earned_credits": "10.000000",
        "lifetime_allocated_credits": "1.500000",
    }


def test_empty_wallet_is_valid(client, repository):
    repository.wallet_row = None
    response = client.get("/api/v1/green-credits/wallet")
    assert response.status_code == 200
    assert response.json()["available_credits"] == "0.000000"


def test_ledger_and_allocations_are_frontend_ready(client):
    ledger = client.get("/api/v1/green-credits/ledger").json()
    allocations = client.get("/api/v1/green-credits/allocations").json()
    assert ledger["data"][0]["amount_credits"] == "0.700000"
    assert allocations["data"][0]["allocated_credits"] == "1.500000"


def test_project_catalog_and_detail_include_funding_progress(client):
    catalog = client.get("/api/v1/green-projects").json()
    detail = client.get(f"/api/v1/green-projects/{PROJECT_ID}").json()
    assert catalog["data"][0]["funding_percentage"] == 99.0
    assert detail["remaining_credits"] == "1.000000"


def test_unknown_project_returns_404(client):
    response = client.get("/api/v1/green-projects/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
    assert response.status_code == 404


def test_allocation_reports_partial_target_cap(client, repository):
    response = client.post(
        f"/api/v1/green-projects/{PROJECT_ID}/allocations",
        json={
            "requested_credits": "2.000000",
            "idempotency_key": "allocate-123",
        },
    )
    assert response.status_code == 201
    assert response.json()["allocated_credits"] == "1.000000"
    assert response.json()["partial"] is True
    assert repository.allocate_calls == [(PROJECT_ID, 2_000_000, "allocate-123")]


def test_invalid_allocation_is_validation_error(client):
    response = client.post(
        f"/api/v1/green-projects/{PROJECT_ID}/allocations",
        json={"requested_credits": "0", "idempotency_key": "allocate-123"},
    )
    assert response.status_code == 422


def test_internal_accrual_returns_role_totals_and_warning(client, repository):
    response = client.post(
        "/api/v1/internal/green-credits/accrue",
        json={
            "property_id": ACCOUNT_ID,
            "period_start": "2026-08-21T00:00:00+00:00",
            "period_end": "2026-08-22T00:00:00+00:00",
        },
    )
    assert response.status_code == 200
    assert response.json()["tenant_issued_credits"] == "7.000000"
    assert response.json()["warnings"][0]["code"] == "MISSING_ROLE_BENEFICIARY"
    assert len(repository.accrue_calls) == 1


def test_public_endpoint_requires_bearer_token_without_override():
    app.dependency_overrides.clear()
    with TestClient(app) as unauthenticated_client:
        response = unauthenticated_client.get("/api/v1/green-credits/wallet")
    assert response.status_code == 401


def test_internal_endpoint_rejects_missing_key_without_override(monkeypatch):
    app.dependency_overrides.clear()
    monkeypatch.setenv("GREEN_CREDIT_INTERNAL_KEY", "valid-internal-key")
    with TestClient(app) as unauthenticated_client:
        response = unauthenticated_client.post(
            "/api/v1/internal/green-credits/accrue",
            json={
                "property_id": ACCOUNT_ID,
                "period_start": "2026-08-21T00:00:00+00:00",
                "period_end": "2026-08-22T00:00:00+00:00",
            },
        )
    assert response.status_code == 403


def test_accrual_requires_timezone_aware_period(client):
    response = client.post(
        "/api/v1/internal/green-credits/accrue",
        json={
            "property_id": ACCOUNT_ID,
            "period_start": "2026-08-21T00:00:00",
            "period_end": "2026-08-22T00:00:00",
        },
    )
    assert response.status_code == 422
