from fastapi.testclient import TestClient

from app.main import app


def test_health_and_config_endpoints():
    client = TestClient(app)
    assert client.get("/api/health").json()["status"] == "ok"
    config = client.get("/api/config").json()
    assert config["features"]["provenance"] is True


def test_ask_endpoint_has_evidence():
    client = TestClient(app)
    response = client.post("/api/ask", json={"question": "What does GraphMind preserve?"})
    assert response.status_code == 200
    assert response.json()["evidence"]
