from fastapi.testclient import TestClient

from ago.main import create_app


def test_liveness_independent_of_database(monkeypatch):
    monkeypatch.delenv("AGO_POSTGRES_DSN", raising=False)
    client = TestClient(create_app())
    assert client.get("/health/live").status_code == 200


def test_readiness_fails_closed_without_postgres(monkeypatch):
    monkeypatch.delenv("AGO_POSTGRES_DSN", raising=False)
    response = TestClient(create_app()).get("/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["postgres"]["healthy"] is False


def test_readiness_succeeds_when_probe_passes():
    app = create_app()
    app.state.readiness_checks._checks["postgres"] = lambda: True
    response = TestClient(app).get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_readiness_masks_database_errors():
    app = create_app()

    def failed():
        raise RuntimeError("secret DSN")

    app.state.readiness_checks._checks["postgres"] = failed
    response = TestClient(app).get("/health/ready")
    assert response.status_code == 503
    assert "secret DSN" not in response.text
