from fastapi.testclient import TestClient

from app.data import USERS
from app.main import app

client = TestClient(app)


def test_create_user_success():
    USERS.clear()
    response = client.post("/create-user", json={"email": "newuser@example.com"})

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert "id" in data
    assert "created_at" in data
    assert data["status"] == "active"
    assert len(USERS) == 1
    assert USERS[0]["email"] == "newuser@example.com"


def test_create_user_invalid_email():
    USERS.clear()
    response = client.post("/create-user", json={"email": "not-an-email"})

    assert response.status_code == 422
    assert len(USERS) == 0


def test_create_user_duplicate_email():
    USERS.clear()
    first_response = client.post("/create-user", json={"email": "user@example.com"})
    assert first_response.status_code == 201

    second_response = client.post("/create-user", json={"email": "user@example.com"})
    assert second_response.status_code == 400
    data = second_response.json()
    assert data["detail"] == "User with this email already exists"
    assert len(USERS) == 1
