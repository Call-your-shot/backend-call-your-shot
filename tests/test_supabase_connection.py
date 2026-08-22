from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_supabase_health_without_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    response = client.get("/api/supabase/health")

    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is False
    assert data["configured"] is False
    assert "DATABASE_URL" in data["detail"]
