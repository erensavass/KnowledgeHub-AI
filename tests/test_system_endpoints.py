from fastapi.testclient import TestClient

from app.main import create_application


def test_health_check_returns_ok() -> None:
    with TestClient(create_application()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version_returns_application_metadata() -> None:
    with TestClient(create_application()) as client:
        response = client.get("/version")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Enterprise RAG Assistant"
    assert body["version"] == "0.1.0"


def test_api_documentation_is_not_exposed_in_sprint_one() -> None:
    with TestClient(create_application()) as client:
        response = client.get("/docs")

    assert response.status_code == 404
