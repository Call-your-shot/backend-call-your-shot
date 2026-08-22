"""
Integration tests for the FastAPI endpoints.

Uses ``httpx.AsyncClient`` via the FastAPI test-client pattern.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ═══════════════════════════════════════════════════════════════════════════
# Health
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
async def test_health(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ═══════════════════════════════════════════════════════════════════════════
# Tariffs
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
async def test_tariffs(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/tariffs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["location"] == "Wollongong, NSW"
    assert data["timezone"] == "Australia/Sydney"
    assert len(data["grid_tariffs"]) == 5
    assert len(data["export_tariffs"]) == 5


# ═══════════════════════════════════════════════════════════════════════════
# Single-interval calculation
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
async def test_calculate_dynamic(client: AsyncClient) -> None:
    payload = {
        "usage_kwh": 2.5,
        "solar_available_kwh": 3.0,
        "timestamp": "2026-08-22T12:30:00+10:00",
        "pricing_mode": "dynamic",
        "alpha_min": 0.40,
        "alpha_max": 0.75,
        "discount_sensitivity": 0.50,
    }
    resp = await client.post("/api/v1/price/calculate", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["pricing_mode"] == "dynamic"
    assert data["solar_usage_kwh"] == 2.5
    assert data["grid_usage_kwh"] == 0.0
    assert data["alpha"] is not None
    assert data["total_charge_dollars"] > 0
    assert data["tenant_saving_dollars"] >= 0
    assert data["landlord_additional_revenue_dollars"] >= 0

    # P_export ≤ P_solar ≤ P_grid
    assert data["export_rate_cents_per_kwh"] <= data["solar_rate_cents_per_kwh"]
    assert data["solar_rate_cents_per_kwh"] <= data["grid_rate_cents_per_kwh"]


@pytest.mark.anyio
async def test_calculate_fixed(client: AsyncClient) -> None:
    payload = {
        "usage_kwh": 2.0,
        "solar_available_kwh": 5.0,
        "timestamp": "2026-08-22T12:30:00+10:00",
        "pricing_mode": "fixed",
        "fixed_solar_rate_cents_per_kwh": 22.0,
    }
    resp = await client.post("/api/v1/price/calculate", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["pricing_mode"] == "fixed"
    assert data["solar_rate_cents_per_kwh"] == 22.0
    assert data["alpha"] is None


# ═══════════════════════════════════════════════════════════════════════════
# Batch calculation
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
async def test_calculate_batch(client: AsyncClient) -> None:
    payload = {
        "intervals": [
            {
                "usage_kwh": 0.8,
                "solar_available_kwh": 1.2,
                "timestamp": "2026-08-22T11:00:00+10:00",
            },
            {
                "usage_kwh": 2.0,
                "solar_available_kwh": 3.5,
                "timestamp": "2026-08-22T12:00:00+10:00",
            },
            {
                "usage_kwh": 3.1,
                "solar_available_kwh": 1.0,
                "timestamp": "2026-08-22T18:00:00+10:00",
            },
        ],
        "pricing_mode": "dynamic",
        "alpha_min": 0.40,
        "alpha_max": 0.75,
        "discount_sensitivity": 0.50,
    }
    resp = await client.post("/api/v1/price/calculate-batch", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["intervals"]) == 3
    summary = data["summary"]
    assert summary["total_usage_kwh"] == pytest.approx(5.9, abs=0.01)
    assert summary["total_charge_dollars"] > 0
    assert summary["tenant_saving_dollars"] >= 0


# ═══════════════════════════════════════════════════════════════════════════
# Preview
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
async def test_preview(client: AsyncClient) -> None:
    resp = await client.get(
        "/api/v1/price/preview",
        params={
            "usage_kwh": 3.0,
            "solar_available_kwh": 4.0,
            "timestamp": "2026-08-22T12:00:00+10:00",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["pricing_mode"] == "dynamic"
    assert data["solar_usage_kwh"] == 3.0
    assert data["grid_usage_kwh"] == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# Validation errors
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
async def test_negative_usage_rejected(client: AsyncClient) -> None:
    payload = {
        "usage_kwh": -1.0,
        "timestamp": "2026-08-22T12:30:00+10:00",
    }
    resp = await client.post("/api/v1/price/calculate", json=payload)
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_alpha_min_gt_alpha_max_rejected(client: AsyncClient) -> None:
    payload = {
        "usage_kwh": 1.0,
        "timestamp": "2026-08-22T12:30:00+10:00",
        "alpha_min": 0.80,
        "alpha_max": 0.40,
    }
    resp = await client.post("/api/v1/price/calculate", json=payload)
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_sensitivity_zero_rejected(client: AsyncClient) -> None:
    payload = {
        "usage_kwh": 1.0,
        "timestamp": "2026-08-22T12:30:00+10:00",
        "discount_sensitivity": 0,
    }
    resp = await client.post("/api/v1/price/calculate", json=payload)
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_export_exceeds_grid_rejected(client: AsyncClient) -> None:
    payload = {
        "usage_kwh": 1.0,
        "solar_available_kwh": 2.0,
        "timestamp": "2026-08-22T12:30:00+10:00",
        "pricing_mode": "dynamic",
        "grid_rate_cents_per_kwh": 10.0,
        "export_rate_cents_per_kwh": 20.0,
    }
    resp = await client.post("/api/v1/price/calculate", json=payload)
    assert resp.status_code == 422
    assert "Export rate cannot exceed grid rate" in resp.json()["detail"]


@pytest.mark.anyio
async def test_invalid_pricing_mode_rejected(client: AsyncClient) -> None:
    payload = {
        "usage_kwh": 1.0,
        "timestamp": "2026-08-22T12:30:00+10:00",
        "pricing_mode": "wholesale",
    }
    resp = await client.post("/api/v1/price/calculate", json=payload)
    assert resp.status_code == 422
