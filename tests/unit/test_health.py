from fastapi.testclient import TestClient

from apps.api.app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["service"] == "insightops-api"
    assert payload["version"] == "0.1.0"
