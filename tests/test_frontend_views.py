from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_list_tenant_plans_by_email():
    response = client.get("/api/plans", params={"email": "tenant@example.com"})

    assert response.status_code == 200
    data = response.json()
    assert "plans" in data
    assert data["plans"][0]["id"] == "ten-priya-wollongong"
    assert data["plans"][0]["address"]["suburb"] == "Wollongong"
    assert data["plans"][0]["lastMonth"]["savingsDollars"] == 42.6


def test_get_tenant_plan_detail_by_email():
    response = client.get(
        "/api/plans/ten-priya-wollongong",
        params={"email": "tenant@example.com"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["propertyId"] == "prop-owned-1"
    assert data["ratePerKwhCents"] == 15
    assert data["gridRateCents"] == 29
    assert data["monthly"][0]["solarUsedKwh"] == 200
    assert data["leaveRequest"] is None


def test_list_landlord_properties_by_email():
    response = client.get("/api/properties", params={"email": "landlord@example.com"})

    assert response.status_code == 200
    data = response.json()
    assert "properties" in data
    assert data["properties"][0]["id"] == "prop-owned-1"
    assert data["properties"][0]["occupancyStatus"] == "occupied"
    assert data["properties"][0]["currentTenantName"] == "Amelia Rossi"


def test_get_landlord_property_detail_by_email():
    response = client.get(
        "/api/properties/prop-owned-1",
        params={"email": "landlord@example.com"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["system"]["sizeKw"] == 7.9
    assert len(data["system"]["dailyOutputKwh30d"]) == 30
    assert data["currentTenant"]["name"] == "Amelia Rossi"
    assert data["maintenanceReserve"]["nextCostDescription"] == "Inverter replacement"
    assert data["leaveRequest"] is None


def test_email_scoped_frontend_views_return_empty_lists():
    assert client.get("/api/plans", params={"email": "missing@example.com"}).json() == {"plans": []}
    assert client.get("/api/properties", params={"email": "missing@example.com"}).json() == {"properties": []}


def test_tenant_leave_request_owner_approval_and_notifications():
    leave_response = client.post(
        "/api/plans/ten-priya-wollongong/leave",
        json={
            "email": "tenant@example.com",
            "moveOutDate": "2026-11-01",
            "reason": "Moving for work",
            "note": None,
        },
    )

    assert leave_response.status_code == 200
    leaving_plan = leave_response.json()
    assert leaving_plan["status"] == "leaving"
    assert leaving_plan["leaveRequest"]["moveOutDate"] == "2026-11-01"
    assert leaving_plan["leaveRequest"]["status"] == "pending"
    assert leaving_plan["leaveRequest"]["timeline"]["noticeGiven"] == "2026-08-22"

    owner_notifications = client.get(
        "/api/notifications",
        params={"email": "owner@example.com"},
    )
    assert owner_notifications.status_code == 200
    assert any(
        item["type"] == "leave_request_submitted"
        and item["actionRequired"] is True
        and item["relatedId"] == "prop-owned-1"
        for item in owner_notifications.json()["notifications"]
    )

    forbidden = client.post(
        "/api/properties/prop-owned-1/leave-request/approve",
        json={"email": "not-owner@example.com"},
    )
    assert forbidden.status_code == 403

    approve_response = client.post(
        "/api/properties/prop-owned-1/leave-request/approve",
        json={"email": "owner@example.com"},
    )

    assert approve_response.status_code == 200
    approved_property = approve_response.json()
    assert approved_property["leaveRequest"]["tenantName"] == "Amelia Rossi"
    assert approved_property["leaveRequest"]["moveOutDate"] == "2026-11-01"
    assert approved_property["leaveRequest"]["reason"] == "Moving for work"
    assert approved_property["leaveRequest"]["status"] == "approved"

    ended_plan = client.get(
        "/api/plans/ten-priya-wollongong",
        params={"email": "tenant@example.com"},
    ).json()
    assert ended_plan["status"] == "ended"
    assert ended_plan["leaveRequest"]["status"] == "approved"

    tenant_notifications = client.get(
        "/api/notifications",
        params={"email": "tenant@example.com"},
    )
    assert any(
        item["type"] == "leave_request_approved"
        and item["actionRequired"] is False
        and item["relatedId"] == "ten-priya-wollongong"
        for item in tenant_notifications.json()["notifications"]
    )

    no_pending = client.post(
        "/api/properties/prop-owned-1/leave-request/approve",
        json={"email": "owner@example.com"},
    )
    assert no_pending.status_code == 404


def test_landlord_invites_new_tenant_and_tenant_accepts():
    invite_response = client.post(
        "/api/properties/prop-owned-1/invite",
        json={"email": "owner@example.com", "inviteEmail": "new.tenant@example.com"},
    )

    assert invite_response.status_code == 200
    invited_property = invite_response.json()
    assert invited_property["occupancyStatus"] == "pending_invitation"
    assert invited_property["pendingInvitationEmail"] == "new.tenant@example.com"

    invite_notifications = client.get(
        "/api/notifications",
        params={"email": "new.tenant@example.com"},
    )
    assert any(
        item["type"] == "tenant_invitation"
        and item["actionRequired"] is True
        and item["relatedId"] == "prop-owned-1"
        for item in invite_notifications.json()["notifications"]
    )

    accept_response = client.post(
        "/api/properties/prop-owned-1/invite/accept",
        json={"email": "new.tenant@example.com"},
    )

    assert accept_response.status_code == 200
    accepted_property = accept_response.json()
    assert accepted_property["occupancyStatus"] == "occupied"
    assert accepted_property["pendingInvitationEmail"] is None
    assert accepted_property["currentTenant"]["name"] == "New Tenant"
