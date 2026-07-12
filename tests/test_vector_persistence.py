import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pymilvus import DataType
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.application.reconciliation import EmbeddingReconciliationService
from app.application.vector_store import VectorEmbedding, VectorMetadata
from app.core.config import get_settings
from app.dependencies import get_embedding_service
from app.infrastructure.database.models import ChunkEmbedding, Document, EmbeddingStatus
from app.infrastructure.vector.milvus import MilvusVectorStore
from tests.conftest import FakeVectorStore
from tests.test_documents import auth, create_user
from tests.test_embeddings import FakeEmbeddingService, ready_document


def use_embedding_service(
    client: TestClient, model_name: str = "test/embedding-model", dimension: int = 3
) -> FakeEmbeddingService:
    service = FakeEmbeddingService()
    service.model_name = model_name

    def embed(texts: list[str]) -> list[list[float]]:
        service.calls.append(texts)
        return [[float(index) for index in range(dimension)] for _ in texts]

    service.embed = embed  # type: ignore[method-assign]
    client.app.dependency_overrides[get_embedding_service] = lambda: service
    return service


def test_vector_upsert_is_duplicate_safe_and_force_replaces(
    client: TestClient, vector_store: FakeVectorStore
) -> None:
    token = create_user(client, "vector-upsert@example.com")
    document = ready_document(client, token)
    service = use_embedding_service(client)
    url = f"/documents/{document['id']}/embed"

    first = client.post(url, headers=auth(token))
    vector_ids = set(vector_store.vectors)
    second = client.post(url, headers=auth(token))
    forced = client.post(f"{url}?force=true", headers=auth(token))

    assert first.status_code == second.status_code == forced.status_code == 200
    assert set(vector_store.vectors) == vector_ids
    assert len(vector_store.vectors) == 1
    assert len(service.calls) == 2


def test_model_change_replaces_vector_and_metadata(
    client: TestClient, vector_store: FakeVectorStore
) -> None:
    token = create_user(client, "model-change@example.com")
    document = ready_document(client, token)
    url = f"/documents/{document['id']}/embed"
    use_embedding_service(client, "model/one")
    assert client.post(url, headers=auth(token)).status_code == 200

    use_embedding_service(client, "model/two")
    response = client.post(url, headers=auth(token))

    assert response.status_code == 200
    assert {item.embedding_model for item in vector_store.vectors.values()} == {"model/two"}
    assert response.json()["skipped_chunks"] == 0


def test_dimension_mismatch_rejects_without_metadata_or_vectors(
    client: TestClient, vector_store: FakeVectorStore
) -> None:
    token = create_user(client, "dimension-mismatch@example.com")
    document = ready_document(client, token)
    use_embedding_service(client, dimension=2)

    response = client.post(f"/documents/{document['id']}/embed", headers=auth(token))
    status = client.get(
        f"/documents/{document['id']}/embedding-status", headers=auth(token)
    ).json()

    assert response.status_code == 422
    assert not vector_store.vectors
    assert status["embedded_chunks_in_postgres"] == 0
    assert status["vectors_in_milvus"] == 0


def test_milvus_failure_does_not_commit_metadata(
    client: TestClient, vector_store: FakeVectorStore
) -> None:
    token = create_user(client, "milvus-failure@example.com")
    document = ready_document(client, token)
    use_embedding_service(client)
    vector_store.fail_upsert = True

    response = client.post(f"/documents/{document['id']}/embed", headers=auth(token))
    status = client.get(
        f"/documents/{document['id']}/embedding-status", headers=auth(token)
    ).json()

    assert response.status_code == 422
    assert status["embedded_chunks_in_postgres"] == 0
    assert not vector_store.vectors


def test_postgres_failure_compensates_milvus(
    client: TestClient, vector_store: FakeVectorStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = create_user(client, "compensation@example.com")
    document = ready_document(client, token)
    use_embedding_service(client)
    original_commit = Session.commit
    failed = False

    def fail_ready_commit(session: Session) -> None:
        nonlocal failed
        embedding_ready = any(
            isinstance(item, Document) and item.embedding_status == EmbeddingStatus.EMBEDDED
            for item in session.dirty
        )
        if embedding_ready and not failed:
            failed = True
            raise SQLAlchemyError("simulated commit failure")
        original_commit(session)

    monkeypatch.setattr(Session, "commit", fail_ready_commit)
    response = client.post(f"/documents/{document['id']}/embed", headers=auth(token))

    assert response.status_code == 422
    assert failed
    assert not vector_store.vectors


def test_compensation_failure_is_logged(
    client: TestClient,
    vector_store: FakeVectorStore,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = create_user(client, "compensation-log@example.com")
    document = ready_document(client, token)
    use_embedding_service(client)
    original_commit = Session.commit
    failed = False

    def fail_and_disable_cleanup(session: Session) -> None:
        nonlocal failed
        if not failed and any(
            isinstance(item, Document) and item.embedding_status == EmbeddingStatus.EMBEDDED
            for item in session.dirty
        ):
            failed = True
            vector_store.fail_delete = True
            raise SQLAlchemyError("simulated commit failure")
        original_commit(session)

    monkeypatch.setattr(Session, "commit", fail_and_disable_cleanup)
    response = client.post(f"/documents/{document['id']}/embed", headers=auth(token))

    assert response.status_code == 422
    assert "milvus_reconciliation_required" in caplog.text


def test_document_deletion_and_reprocessing_remove_vectors(
    client: TestClient, vector_store: FakeVectorStore
) -> None:
    token = create_user(client, "vector-cleanup@example.com")
    first = ready_document(client, token, b"first document")
    second = ready_document(client, token, b"second document")
    use_embedding_service(client)
    for document in (first, second):
        assert client.post(
            f"/documents/{document['id']}/embed", headers=auth(token)
        ).status_code == 200
    assert len(vector_store.vectors) == 2

    assert client.post(
        f"/documents/{first['id']}/process", headers=auth(token)
    ).status_code == 200
    assert all(item.document_id != first["id"] for item in vector_store.vectors.values())
    assert client.delete(f"/documents/{second['id']}", headers=auth(token)).status_code == 204
    assert not vector_store.vectors


def test_deletion_fails_safely_when_vector_store_is_unavailable(
    client: TestClient, vector_store: FakeVectorStore
) -> None:
    token = create_user(client, "delete-unavailable@example.com")
    document = ready_document(client, token)
    vector_store.fail_delete = True

    response = client.delete(f"/documents/{document['id']}", headers=auth(token))

    assert response.status_code == 503
    assert client.get(f"/documents/{document['id']}", headers=auth(token)).status_code == 200


def test_embedding_status_detects_missing_vector(
    client: TestClient, vector_store: FakeVectorStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EMBEDDING_MODEL", "test/embedding-model")
    get_settings.cache_clear()
    token = create_user(client, "missing-vector@example.com")
    document = ready_document(client, token)
    use_embedding_service(client)
    url = f"/documents/{document['id']}"
    assert client.post(f"{url}/embed", headers=auth(token)).status_code == 200
    vector_store.vectors.clear()

    status = client.get(f"{url}/embedding-status", headers=auth(token)).json()

    assert status["embedded_chunks_in_postgres"] == 1
    assert status["vectors_in_milvus"] == 0
    assert status["consistent"] is False
    assert status["status"] == "pending"


def test_reconciliation_detects_missing_orphan_model_and_dimension() -> None:
    shared_id = uuid4()
    missing_id = uuid4()
    metadata = [
        ChunkEmbedding(
            chunk_id=shared_id,
            embedding_dimension=2,
            model_name="old/model",
            created_at=datetime.now(UTC),
        ),
        ChunkEmbedding(
            chunk_id=missing_id,
            embedding_dimension=3,
            model_name="expected/model",
            created_at=datetime.now(UTC),
        ),
    ]
    orphan_id = str(uuid4())
    vectors = [
        VectorMetadata(str(shared_id), "doc", "expected/model", 3),
        VectorMetadata(orphan_id, "doc", "expected/model", 3),
    ]

    report = EmbeddingReconciliationService().compare(
        "doc", metadata, vectors, "expected/model", 3
    )

    assert report.metadata_without_vectors == {str(missing_id)}
    assert report.vectors_without_metadata == {orphan_id}
    assert report.wrong_model_names == {str(shared_id)}
    assert report.wrong_dimensions == {str(shared_id)}
    assert not report.consistent


class CollectionClient:
    def __init__(self, exists: bool) -> None:
        self.exists = exists
        self.created = 0

    def has_collection(self, **_: object) -> bool:
        return self.exists

    def describe_collection(self, **_: object) -> dict:
        names = [
            "id",
            "chunk_id",
            "document_id",
            "user_id",
            "embedding_model",
            "embedding_dimension",
            "created_at",
        ]
        fields = [
            {
                "name": name,
                "type": int(
                    DataType.VARCHAR
                    if name not in {"created_at", "embedding_dimension"}
                    else DataType.INT64
                ),
                "is_primary": name == "id",
            }
            for name in names
        ]
        fields.append(
            {"name": "embedding", "type": int(DataType.FLOAT_VECTOR), "params": {"dim": 3}}
        )
        return {"fields": fields}

    def list_indexes(self, **_: object) -> list[str]:
        return ["embedding"]

    def describe_index(self, **_: object) -> dict[str, str]:
        return {"index_type": "HNSW", "metric_type": "COSINE"}


def milvus_store(client: CollectionClient) -> MilvusVectorStore:
    store = MilvusVectorStore("uri", "", "collection", "COSINE", "HNSW", 16, 200)
    store._client = client
    return store


def test_collection_creation_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    client = CollectionClient(False)
    store = milvus_store(client)

    def create(_: object, dimension: int) -> None:
        assert dimension == 3
        client.created += 1
        client.exists = True

    monkeypatch.setattr(store, "_create_collection", create)
    store.ensure_collection(3)
    store.ensure_collection(3)

    assert client.created == 1


def test_collection_validation_rejects_wrong_dimension() -> None:
    store = milvus_store(CollectionClient(True))

    with pytest.raises(Exception, match="incompatible_milvus_collection"):
        store.ensure_collection(4)


class SearchClient:
    def search(self, **kwargs: object) -> list[list[dict]]:
        assert kwargs["filter"] == (
            'user_id == "user-id" and document_id in ["doc-one", "doc-two"]'
        )
        return [
            [
                {"id": "chunk-one", "distance": 0.8, "entity": {"chunk_id": "chunk-one"}},
                {"id": "chunk-two", "distance": 0.2, "entity": {"chunk_id": "chunk-two"}},
            ]
        ]


def test_milvus_search_scopes_filters_and_thresholds() -> None:
    store = milvus_store(SearchClient())  # type: ignore[arg-type]

    results = store.search([1.0, 0.0, 0.0], "user-id", ["doc-one", "doc-two"], 5, 0.5)

    assert [(item.chunk_id, item.score) for item in results] == [("chunk-one", 0.8)]


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_MILVUS_INTEGRATION") != "1", reason="real Milvus integration is opt-in"
)
def test_real_milvus_collection_lifecycle() -> None:
    settings = get_settings()
    collection = f"knowledgehub_test_{uuid4().hex}"
    store = MilvusVectorStore(
        settings.milvus_uri,
        settings.milvus_token,
        collection,
        "COSINE",
        "HNSW",
        16,
        200,
    )
    try:
        store.ensure_collection(3)
        store.ensure_collection(3)
        user_id = str(uuid4())
        document_id = str(uuid4())
        chunk_id = str(uuid4())
        store.upsert_embeddings(
            [
                VectorEmbedding(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    user_id=user_id,
                    embedding=[1.0, 0.0, 0.0],
                    embedding_model="integration/model",
                    created_at=1,
                )
            ]
        )
        results = store.search([1.0, 0.0, 0.0], user_id, [document_id], 1, 0.0)
        assert results[0].chunk_id == chunk_id
    finally:
        if store._client is not None and store._client.has_collection(collection_name=collection):
            store._client.drop_collection(collection_name=collection)
        store.close()
