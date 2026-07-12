from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.application.embedding import EmbeddingService
from app.core.config import get_settings
from app.dependencies import get_database_session, get_embedding_service
from tests.test_documents import auth, create_user, upload


class FakeEmbeddingService:
    model_name = "test/embedding-model"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[float(len(text)), 1.0, 2.0] for text in texts]


def ready_document(client: TestClient, token: str, content: bytes = b"embedded content") -> dict:
    document = upload(client, token, "embedding.txt", content, "text/plain").json()
    response = client.post(f"/documents/{document['id']}/process", headers=auth(token))
    assert response.status_code == 200
    return response.json()


def install_fake(client: TestClient) -> FakeEmbeddingService:
    service = FakeEmbeddingService()
    client.app.dependency_overrides[get_embedding_service] = lambda: service
    return service


def test_successful_embedding_stores_metadata_only(client: TestClient) -> None:
    token = create_user(client, "embed-success@example.com")
    document = ready_document(client, token)
    service = install_fake(client)

    response = client.post(f"/documents/{document['id']}/embed", headers=auth(token))

    assert response.status_code == 200
    assert response.json() == {
        "document_id": document["id"],
        "total_chunks": 1,
        "embedded_chunks": 1,
        "skipped_chunks": 0,
        "embedding_model": service.model_name,
        "status": "embedded",
    }
    assert service.calls == [["embedded content"]]
    session_dependency = client.app.dependency_overrides[get_database_session]
    session = next(session_dependency())
    columns = {column["name"] for column in inspect(session.bind).get_columns("chunk_embeddings")}
    assert columns == {"chunk_id", "embedding_dimension", "model_name", "created_at"}
    session.close()


def test_embedding_is_owner_scoped(client: TestClient) -> None:
    owner = create_user(client, "embed-owner@example.com")
    other = create_user(client, "embed-other@example.com")
    document = ready_document(client, owner)
    install_fake(client)

    response = client.post(f"/documents/{document['id']}/embed", headers=auth(other))

    assert response.status_code == 404
    assert client.get(
        f"/documents/{document['id']}/embedding-status", headers=auth(other)
    ).status_code == 404


def test_duplicate_embedding_skips_existing_chunks(client: TestClient) -> None:
    token = create_user(client, "embed-duplicate@example.com")
    document = ready_document(client, token)
    service = install_fake(client)
    url = f"/documents/{document['id']}/embed"

    assert client.post(url, headers=auth(token)).status_code == 200
    second = client.post(url, headers=auth(token))

    assert second.status_code == 200
    assert second.json()["skipped_chunks"] == 1
    assert len(service.calls) == 1


def test_force_reembedding_generates_again(client: TestClient) -> None:
    token = create_user(client, "embed-force@example.com")
    document = ready_document(client, token)
    service = install_fake(client)
    url = f"/documents/{document['id']}/embed"

    assert client.post(url, headers=auth(token)).status_code == 200
    forced = client.post(f"{url}?force=true", headers=auth(token))

    assert forced.status_code == 200
    assert forced.json()["skipped_chunks"] == 0
    assert len(service.calls) == 2


def test_embedding_rejects_non_ready_document(client: TestClient) -> None:
    token = create_user(client, "embed-state@example.com")
    document = upload(client, token, "unprocessed.txt", b"text", "text/plain").json()
    install_fake(client)

    response = client.post(f"/documents/{document['id']}/embed", headers=auth(token))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "document_not_ready"


def test_embedding_failure_sets_safe_status(client: TestClient) -> None:
    class FailingService(FakeEmbeddingService):
        def embed(self, texts: list[str]) -> list[list[float]]:
            raise RuntimeError("sensitive model details")

    token = create_user(client, "embed-failure@example.com")
    document = ready_document(client, token)
    client.app.dependency_overrides[get_embedding_service] = FailingService

    response = client.post(f"/documents/{document['id']}/embed", headers=auth(token))
    stored = client.get(f"/documents/{document['id']}", headers=auth(token)).json()

    assert response.status_code == 422
    assert "sensitive" not in response.text
    assert stored["embedding_status"] == "embedding_failed"
    assert stored["embedding_error_code"] == "embedding_failed"


def test_embedding_status_counts_chunks(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_MODEL", "test/embedding-model")
    get_settings.cache_clear()
    token = create_user(client, "embed-status@example.com")
    document = ready_document(client, token)
    install_fake(client)
    url = f"/documents/{document['id']}"

    before = client.get(f"{url}/embedding-status", headers=auth(token)).json()
    client.post(f"{url}/embed", headers=auth(token))
    after = client.get(f"{url}/embedding-status", headers=auth(token)).json()

    assert before["total_chunks"] == before["remaining_chunks"] == 1
    assert before["embedded_chunks_in_postgres"] == 0
    assert before["vectors_in_milvus"] == 0
    assert before["status"] == "pending"
    assert after["embedded_chunks_in_postgres"] == 1
    assert after["vectors_in_milvus"] == 1
    assert after["remaining_chunks"] == 0
    assert after["status"] == "embedded"
    assert after["consistent"] is True


def test_embedding_model_is_lazy_and_output_is_validated() -> None:
    class ArrayResult:
        def tolist(self) -> list[list[int]]:
            return [[1, 2, 3]]

    class Model:
        def encode(self, sentences: list[str], **_: Any) -> ArrayResult:
            assert sentences == ["text"]
            return ArrayResult()

    service = EmbeddingService("test/model")
    assert not service.is_loaded
    service._model = Model()

    assert service.embed(["text"]) == [[1.0, 2.0, 3.0]]
    assert service.is_loaded


def test_embedding_configuration_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDING_MODEL", "   ")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="embedding configuration"):
            get_settings()
    finally:
        get_settings.cache_clear()
