from fastapi.testclient import TestClient

from app.data import PROPERTIES, PROPERTY_MEMBERSHIPS, PROPOSALS, USERS
from app.main import app

client = TestClient(app)


def _sample_payload(address="42 Solar Circuit, Wollongong NSW 2500", tenant_name="John Tenant", tenant_email="john@example.com"):
    return {
        "address": address,
        "tenant": {
            "name": tenant_name,
            "email": tenant_email,
        },
        "system": {
            "panelCount": 16,
            "systemSizeKw": 6.5,
            "panelWatts": 410,
            "orientation": "NORTH",
            "pitchDegrees": 22.5,
            "estimatedAnnualAcKwh": 8450.0,
            "source": "google",
        },
        "consumption": {
            "billUsageKwh": 750.0,
            "billingPeriodStart": "2026-05-01",
            "billingPeriodEnd": "2026-07-31",
            "estimatedAnnualKwh": 3000.0,
            "ratePerKwhCents": 34.0,
            "rateSource": "bill",
            "recommendedSystemSizeKw": 6.5,
            "systemSizeSource": "backend",
        },
    }


def setup_function():
    PROPOSALS.clear()
    PROPERTY_MEMBERSHIPS.clear()


def test_create_proposal_success():
    payload = _sample_payload()
    response = client.post("/create-proposal", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "propertyId" in data
    assert data["status"] == "sent"
    assert "inviteToken" in data
    assert data["inviteUrl"].endswith(f"/invite/{data['inviteToken']}")
    assert data["tenant"]["name"] == "John Tenant"
    assert data["tenant"]["email"] == "john@example.com"
    assert data["financialSummary"]["estimatedAnnualSavings"] > 0
    assert len(PROPOSALS) == 1


def test_get_proposal_by_invite_token():
    create_res = client.post("/create-proposal", json=_sample_payload())
    assert create_res.status_code == 201
    created = create_res.json()
    invite_token = created["inviteToken"]

    get_res = client.get(f"/proposals/{invite_token}")
    assert get_res.status_code == 200
    fetched = get_res.json()
    assert fetched["id"] == created["id"]
    assert fetched["inviteToken"] == invite_token


def test_accept_proposal_landlord():
    create_res = client.post("/create-proposal", json=_sample_payload())
    created = create_res.json()
    invite_token = created["inviteToken"]

    accept_res = client.post(
        f"/proposals/{invite_token}/accept",
        json={"landlordName": "Sarah Landlord", "landlordEmail": "sarah@example.com"},
    )
    assert accept_res.status_code == 200
    accepted = accept_res.json()
    assert accepted["status"] == "accepted"

    # Check landlord membership registered
    memberships = [m for m in PROPERTY_MEMBERSHIPS if m["email"] == "sarah@example.com"]
    assert len(memberships) == 1
    assert memberships[0]["role"] == "landlord"


def test_multi_property_landlord_dashboard():
    # Tenant 1 creates proposal for House A
    payload1 = _sample_payload(address="10 Ocean Drive, Wollongong NSW 2500", tenant_name="Alice", tenant_email="alice@example.com")
    res1 = client.post("/create-proposal", json=payload1)
    token1 = res1.json()["inviteToken"]

    # Tenant 2 creates proposal for House B
    payload2 = _sample_payload(address="25 Mountain View, Wollongong NSW 2500", tenant_name="Bob", tenant_email="bob@example.com")
    res2 = client.post("/create-proposal", json=payload2)
    token2 = res2.json()["inviteToken"]

    landlord_email = "landlord_multi@example.com"

    # Landlord accepts both proposals
    client.post(f"/proposals/{token1}/accept", json={"landlordName": "Multi Landlord", "landlordEmail": landlord_email})
    client.post(f"/proposals/{token2}/accept", json={"landlordName": "Multi Landlord", "landlordEmail": landlord_email})

    # Fetch properties for this landlord via standard query parameter
    props_res = client.get("/user-properties", params={"email": landlord_email, "role": "landlord"})
    assert props_res.status_code == 200

    data = props_res.json()["data"]

    # Should contain 2 distinct properties for the 2 tabs in the landlord dashboard
    assert len(data) == 2
    addresses = {item["property"]["name"] for item in data}
    assert "10 Ocean Drive, Wollongong NSW 2500" in addresses
    assert "25 Mountain View, Wollongong NSW 2500" in addresses
