from fastapi.testclient import TestClient

from app.main import app
from app.utils.assessment_service import INITIAL_ASSESSMENTS


client = TestClient(app)


def payload(seed: int = 42) -> dict:
    return {
        "address": {
            "formattedAddress": "42 Bellambi Lane, Bellambi NSW 2518",
            "latitude": -34.36,
            "longitude": 150.91,
        },
        "system": {
            "source": "google",
            "imageryQuality": "HIGH",
            "imageryDate": "2025-01-01",
            "panelCount": 18,
            "panelWatts": 440,
            "systemSizeKw": 7.92,
            "expectedAnnualGenerationKwh": 9108,
            "roofAreaM2": 118,
            "usableRoofAreaM2": 36,
        },
        "household": {
            "expectedAnnualUsageKwh": 6500,
            "currentAnnualBillDollars": 1950,
            "gridRateCentsPerKwh": 30,
            "daytimeOccupancy": "sometimes",
        },
        "installation": {
            "grossInstallationCostDollars": 9000,
            "stcBenefitDollars": 1500,
            "annualOperatingCostDollars": 100,
        },
        "pricing": {"pricingMode": "dynamic", "exportRateCentsPerKwh": 5},
        "simulation": {"iterations": 200, "forecastYears": 20, "randomSeed": seed},
    }


def test_initial_assessment_is_reproducible_and_retrievable():
    INITIAL_ASSESSMENTS.clear()
    first = client.post("/api/v1/assessments/initial", json=payload())
    second = client.post("/api/v1/assessments/initial", json=payload())
    assert first.status_code == 201
    assert second.status_code == 201
    first_data = first.json()
    second_data = second.json()
    assert first_data["tenantEconomics"] == second_data["tenantEconomics"]
    assert first_data["landlordEconomics"] == second_data["landlordEconomics"]
    assert first_data["pricing"] == second_data["pricing"]
    assert first_data["tenantEconomics"]["annualSavingsDollars"]["p05"] <= first_data["tenantEconomics"]["annualSavingsDollars"]["median"]
    assert first_data["tenantEconomics"]["solarShareRatio"]["maximum"] <= 1
    fetched = client.get(f"/api/v1/assessments/{first_data['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == first_data["id"]


def test_initial_assessment_uses_conservative_cost_defaults():
    body = payload()
    body["installation"] = {}
    response = client.post("/api/v1/assessments/initial", json=body)
    assert response.status_code == 201
    data = response.json()
    assert data["installationCostSource"] == "model_default"
    assert data["landlordEconomics"]["netInstallationCostDollars"] == 11484
    assert {warning["code"] for warning in data["warnings"]} >= {
        "INSTALLATION_COST_ESTIMATED",
        "REBATE_NOT_INCLUDED",
    }


def test_initial_assessment_uses_optimistic_monte_carlo_alpha_defaults():
    response = client.post("/api/v1/assessments/initial", json=payload())
    assert response.status_code == 201
    data = response.json()
    assumptions = data["monteCarlo"]["assumptions"]
    assert assumptions["alpha_minimum"] == 0.65
    assert assumptions["alpha_mode"] == 0.80
    assert assumptions["alpha_maximum"] == 0.95
    assert (
        data["pricing"]["exportRateCentsPerKwh"]
        <= data["pricing"]["tenantSolarRateCentsPerKwh"]["median"]
        <= data["pricing"]["gridRateCentsPerKwh"]
    )


def test_proposal_snapshots_saved_assessment_economics():
    assessment = client.post("/api/v1/assessments/initial", json=payload()).json()
    response = client.post(
        "/create-proposal",
        json={
            "assessmentId": assessment["id"],
            "address": "42 Bellambi Lane, Bellambi NSW 2518",
            "tenant": {"name": "Sarah Chen", "email": "sarah.chen@example.com"},
            "landlord": {"name": "Property owner", "email": "owner@example.com"},
            "system": {
                "panelCount": 18,
                "systemSizeKw": 7.92,
                "panelWatts": 440,
                "orientation": "North",
                "pitchDegrees": 20,
                "estimatedAnnualAcKwh": 9108,
                "source": "google",
            },
            "consumption": {
                "billUsageKwh": 500,
                "billingPeriodStart": "2026-07-01",
                "billingPeriodEnd": "2026-08-01",
                "estimatedAnnualKwh": 6500,
                "ratePerKwhCents": 30,
                "rateSource": "bill",
                "recommendedSystemSizeKw": 7.92,
                "systemSizeSource": "backend",
            },
        },
    )
    assert response.status_code == 201
    summary = response.json()["financialSummary"]
    assert response.json()["landlord"] == {
        "name": "Property owner",
        "email": "owner@example.com",
    }
    assert summary["assessmentId"] == assessment["id"]
    assert summary["estimatedAnnualTenantSavings"] == assessment["tenantEconomics"]["annualSavingsDollars"]["median"]
    assert summary["medianPaybackYears"] == assessment["landlordEconomics"]["medianPaybackYears"]


def test_interval_pricing_separates_tenant_solar_and_actual_exports():
    response = client.post(
        "/api/v1/pricing/calculate",
        json={
            "usage_kwh": 2,
            "solar_available_kwh": 5,
            "timestamp": "2026-08-22T01:00:00Z",
            "pricing_mode": "dynamic",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["solar_usage_kwh"] == 2
    assert data["solar_export_kwh"] == 3
    assert data["grid_usage_kwh"] == 0
    assert data["export_rate_cents_per_kwh"] <= data["solar_rate_cents_per_kwh"] <= data["grid_rate_cents_per_kwh"]
    assert data["actual_export_revenue_dollars"] == 0.096
    assert data["landlord_total_revenue_dollars"] == round(
        data["solar_charge_dollars"] + data["actual_export_revenue_dollars"], 4
    )
