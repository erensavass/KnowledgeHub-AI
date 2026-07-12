from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.application.embedding import EmbeddingError
from app.application.vector_store import VectorSearchResult
from app.dependencies import get_database_session, get_embedding_service
from app.infrastructure.database.models import DocumentChunk
from tests.conftest import FakeVectorStore
from tests.test_documents import auth, create_user
from tests.test_embeddings import FakeEmbeddingService, ready_document


def embedded_document(
    client: TestClient, token: str, content: bytes = b"authentication uses signed tokens"
) -> dict:
    document = ready_document(client, token, content)
    client.app.dependency_overrides[get_embedding_service] = FakeEmbeddingService
    response = client.post(f"/documents/{document['id']}/embed", headers=auth(token))
    assert response.status_code == 200
    return document


def test_successful_semantic_search_hydrates_source_metadata(
    client: TestClient, vector_store: FakeVectorStore
) -> None:
    token = create_user(client, "search-success@example.com")
    document = embedded_document(client, token)

    response = client.post("/search", headers=auth(token), json={"query": "authentication"})

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["document_id"] == document["id"]
    assert result["content"] == "authentication uses signed tokens"
    assert result["chunk_index"] == 0
    assert result["original_filename"] == "embedding.txt"
    assert result["score"] == 17.0
    assert vector_store.last_search["top_k"] == 5


def test_search_is_owner_scoped(client: TestClient, vector_store: FakeVectorStore) -> None:
    owner = create_user(client, "search-owner@example.com")
    other = create_user(client, "search-other@example.com")
    embedded_document(client, owner)

    response = client.post("/search", headers=auth(other), json={"query": "tokens"})

    assert response.status_code == 200
    assert response.json() == {"results": []}
    assert vector_store.last_search["user_id"] != next(iter(vector_store.vectors.values())).user_id


def test_cross_user_and_unknown_document_filters_return_404(client: TestClient) -> None:
    owner = create_user(client, "filter-owner@example.com")
    other = create_user(client, "filter-other@example.com")
    document = embedded_document(client, owner)

    for document_id in (document["id"], str(uuid4())):
        response = client.post(
            "/search",
            headers=auth(other),
            json={"query": "tokens", "document_ids": [document_id]},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "document_not_found"


def test_optional_document_filter_is_forwarded(
    client: TestClient, vector_store: FakeVectorStore
) -> None:
    token = create_user(client, "filter-success@example.com")
    first = embedded_document(client, token, b"first searchable content")
    second = embedded_document(client, token, b"second searchable content")

    response = client.post(
        "/search",
        headers=auth(token),
        json={"query": "content", "document_ids": [second["id"]]},
    )

    assert response.status_code == 200
    assert {item["document_id"] for item in response.json()["results"]} == {second["id"]}
    assert vector_store.last_search["document_ids"] == [second["id"]]
    assert first["id"] not in vector_store.last_search["document_ids"]


@pytest.mark.parametrize("top_k", [0, 21])
def test_top_k_bounds(client: TestClient, top_k: int) -> None:
    token = create_user(client, f"bounds-{top_k}@example.com")
    response = client.post(
        "/search", headers=auth(token), json={"query": "valid", "top_k": top_k}
    )
    assert response.status_code == 422


@pytest.mark.parametrize("query", ["", "   "])
def test_empty_query_validation(client: TestClient, query: str) -> None:
    token = create_user(client, f"empty-{len(query)}@example.com")
    response = client.post("/search", headers=auth(token), json={"query": query})
    assert response.status_code == 422


def test_score_threshold_filters_results(client: TestClient, vector_store: FakeVectorStore) -> None:
    token = create_user(client, "threshold@example.com")
    embedded_document(client, token)
    chunk_id = next(iter(vector_store.vectors))
    vector_store.search_results = [VectorSearchResult(chunk_id, 0.4)]

    response = client.post(
        "/search", headers=auth(token), json={"query": "tokens", "score_threshold": 0.5}
    )

    assert response.json() == {"results": []}


def test_relevance_order_and_duplicate_prevention(
    client: TestClient, vector_store: FakeVectorStore
) -> None:
    token = create_user(client, "order@example.com")
    embedded_document(client, token, b"first")
    embedded_document(client, token, b"second")
    chunk_ids = list(vector_store.vectors)
    vector_store.search_results = [
        VectorSearchResult(chunk_ids[1], 0.9),
        VectorSearchResult(chunk_ids[1], 0.8),
        VectorSearchResult(chunk_ids[0], 0.7),
    ]

    results = client.post("/search", headers=auth(token), json={"query": "x"}).json()["results"]

    assert [item["chunk_id"] for item in results] == [chunk_ids[1], chunk_ids[0]]
    assert [item["score"] for item in results] == [0.9, 0.7]


def test_missing_postgres_chunk_is_omitted_with_warning(
    client: TestClient, vector_store: FakeVectorStore, caplog: pytest.LogCaptureFixture
) -> None:
    token = create_user(client, "stale@example.com")
    embedded_document(client, token)
    vector_store.search_results = [VectorSearchResult(str(uuid4()), 0.9)]

    response = client.post("/search", headers=auth(token), json={"query": "x"})

    assert response.json() == {"results": []}
    assert "search_reconciliation_warning" in caplog.text


def test_missing_embedding_metadata_is_not_hydrated(
    client: TestClient, vector_store: FakeVectorStore
) -> None:
    token = create_user(client, "metadata-stale@example.com")
    embedded_document(client, token)
    chunk_id = next(iter(vector_store.vectors))
    session_dependency = client.app.dependency_overrides[get_database_session]
    with next(session_dependency()) as session:
        chunk = session.get(DocumentChunk, UUID(chunk_id))
        session.delete(chunk.embedding)
        session.commit()

    response = client.post("/search", headers=auth(token), json={"query": "x"})
    assert response.json() == {"results": []}


def test_vector_store_failure_is_safe(client: TestClient, vector_store: FakeVectorStore) -> None:
    token = create_user(client, "vector-failure@example.com")
    client.app.dependency_overrides[get_embedding_service] = FakeEmbeddingService
    vector_store.fail_search = True
    response = client.post("/search", headers=auth(token), json={"query": "x"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "vector_store_unavailable"


def test_unauthenticated_search_is_rejected(client: TestClient) -> None:
    response = client.post("/search", json={"query": "x"})
    assert response.status_code == 401


def test_no_results(client: TestClient) -> None:
    token = create_user(client, "none@example.com")
    client.app.dependency_overrides[get_embedding_service] = FakeEmbeddingService
    response = client.post("/search", headers=auth(token), json={"query": "x"})
    assert response.status_code == 200
    assert response.json() == {"results": []}


def test_query_embedding_failure_is_safe(client: TestClient) -> None:
    class FailingEmbeddingService:
        model_name = "test/model"

        def embed(self, _: list[str]) -> list[list[float]]:
            raise EmbeddingError("private model failure")

    token = create_user(client, "query-failure@example.com")
    client.app.dependency_overrides[get_embedding_service] = FailingEmbeddingService
    response = client.post("/search", headers=auth(token), json={"query": "secret query"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "query_embedding_failed"
    assert "secret query" not in response.text
