from fastapi.testclient import TestClient

from app.data import LANDLORD_USER_ID, PROPERTY_ID, TENANT_USER_ID
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


def test_tenant_leave_request_status_flow_and_notifications():
    leave_response = client.post(
        f"/api/properties/{PROPERTY_ID}/lease-requests/leave",
        json={
            "tenantUserId": TENANT_USER_ID,
            "landlordUserId": LANDLORD_USER_ID,
            "message": "I need to leave at the end of the lease period.",
            "requestedMoveOutDate": "2026-10-01T00:00:00+00:00",
        },
    )
    assert leave_response.status_code == 201
    request_body = leave_response.json()
    assert request_body["request_type"] == "leave_house"
    assert request_body["status"] == "submitted"

    landlord_notifications = client.get(
        f"/api/properties/{PROPERTY_ID}/notifications",
        params={"recipientUserId": LANDLORD_USER_ID},
    )
    assert landlord_notifications.status_code == 200
    assert any(
        item["entity_id"] == request_body["id"] and item["recipient_role"] == "landlord"
        for item in landlord_notifications.json()["data"]
    )

    review_response = client.patch(
        f"/api/properties/{PROPERTY_ID}/lease-requests/{request_body['id']}/status",
        json={
            "status": "approved",
            "reviewedByUserId": LANDLORD_USER_ID,
            "reviewNotes": "Approved. Please arrange final inspection.",
        },
    )
    assert review_response.status_code == 200
    reviewed = review_response.json()
    assert reviewed["status"] == "approved"
    assert reviewed["reviewed_by_user_id"] == LANDLORD_USER_ID
    assert reviewed["status_history"][-1]["status"] == "approved"

    tenant_plan = client.get(
        f"/api/properties/{PROPERTY_ID}/my-plan",
        params={"tenantUserId": TENANT_USER_ID},
    )
    assert tenant_plan.status_code == 200
    assert any(item["id"] == request_body["id"] and item["status"] == "approved" for item in tenant_plan.json()["current_requests"])
    assert any(item["recipient_role"] == "tenant" for item in tenant_plan.json()["notifications"])


def test_new_house_application_can_be_declined_and_seen_by_landlord():
    application_response = client.post(
        f"/api/properties/{PROPERTY_ID}/house-applications",
        json={
            "tenantUserId": TENANT_USER_ID,
            "landlordUserId": LANDLORD_USER_ID,
            "message": "I want to apply for this house.",
            "proposedMoveInDate": "2026-11-01T00:00:00+00:00",
        },
    )
    assert application_response.status_code == 201
    application = application_response.json()
    assert application["request_type"] == "new_house_application"

    decline_response = client.patch(
        f"/api/properties/{PROPERTY_ID}/lease-requests/{application['id']}/status",
        json={
            "status": "declined",
            "reviewedByUserId": LANDLORD_USER_ID,
            "reviewNotes": "Application declined for this property.",
        },
    )
    assert decline_response.status_code == 200
    assert decline_response.json()["status"] == "declined"

    landlord_properties = client.get(
        f"/api/properties/{PROPERTY_ID}/my-properties",
        params={"landlordUserId": LANDLORD_USER_ID},
    )
    assert landlord_properties.status_code == 200
    property_requests = landlord_properties.json()["properties"][0]["lease_requests"]
    assert any(item["id"] == application["id"] and item["status"] == "declined" for item in property_requests)
