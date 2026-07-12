import os
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.application.prompting import PromptBuilder
from app.application.rag import RAGService
from app.application.retrieval import RetrievalService, RetrievalSource
from app.application.vector_store import VectorEmbedding
from app.core.config import get_settings
from app.core.security import create_access_token
from app.dependencies import (
    get_database_session,
    get_embedding_service,
    get_llm_provider_factory,
    get_vector_store,
)
from app.infrastructure.database.base import Base
from app.infrastructure.database.models import (
    ChunkEmbedding,
    Document,
    DocumentChunk,
    DocumentStatus,
    EmbeddingStatus,
    User,
)
from app.infrastructure.llm import OllamaLLMProvider
from app.infrastructure.vector.milvus import MilvusVectorStore
from app.main import create_application


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_OLLAMA_INTEGRATION") != "1",
    reason="real Ollama integration is opt-in",
)
def test_real_ollama_generation() -> None:
    settings = get_settings()
    provider = OllamaLLMProvider(settings.ollama_base_url, settings.ollama_model)

    result = provider.generate(
        "Answer concisely.", "Reply with the single word ready.", 0.0, 120
    )

    assert result.content.strip()


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_OLLAMA_STREAM_INTEGRATION") != "1",
    reason="real Ollama streaming integration is opt-in",
)
@pytest.mark.asyncio
async def test_real_ollama_streaming() -> None:
    settings = get_settings()
    provider = OllamaLLMProvider(settings.ollama_base_url, settings.ollama_model)

    tokens = [
        token
        async for token in provider.stream(
            "Answer concisely.", "Reply with the single word ready.", 0.0, 120
        )
    ]

    assert "".join(tokens).strip()


class StaticEmbeddingService:
    def embed(self, _: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0]]


class StaticRetrievalRepository:
    def __init__(self, source: RetrievalSource) -> None:
        self.source = source

    def hydrate_search_chunks(
        self, chunk_ids: list[UUID], user_id: UUID
    ) -> dict[UUID, RetrievalSource]:
        assert user_id
        return {self.source.chunk_id: self.source} if self.source.chunk_id in chunk_ids else {}


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_RAG_E2E_INTEGRATION") != "1",
    reason="real Milvus and Ollama RAG integration is opt-in",
)
def test_real_milvus_and_ollama_rag_pipeline() -> None:
    settings = get_settings()
    collection = f"knowledgehub_rag_test_{uuid4().hex}"
    user_id = uuid4()
    document_id = uuid4()
    chunk_id = uuid4()
    store = MilvusVectorStore(
        settings.milvus_uri,
        settings.milvus_token,
        collection,
        "COSINE",
        "HNSW",
        16,
        200,
    )
    source = RetrievalSource(
        chunk_id=chunk_id,
        document_id=document_id,
        chunk_index=0,
        content="Authentication uses signed access tokens.",
        page_number=1,
        original_filename="integration.txt",
        metadata={"test": True},
    )
    try:
        store.ensure_collection(3)
        store.upsert_embeddings(
            [
                VectorEmbedding(
                    chunk_id=str(chunk_id),
                    document_id=str(document_id),
                    user_id=str(user_id),
                    embedding=[1.0, 0.0, 0.0],
                    embedding_model="integration/model",
                    created_at=1,
                )
            ]
        )
        retrieval = RetrievalService(
            StaticRetrievalRepository(source), StaticEmbeddingService(), store, 3
        )
        service = RAGService(
            retrieval,
            PromptBuilder(8, 24000),
            OllamaLLMProvider(settings.ollama_base_url, settings.ollama_model),
            0.0,
            120,
            300,
        )

        answer = service.answer("How does authentication work?", user_id, None, 5, 0.0)

        assert answer.supported is True
        assert answer.citations[0].chunk_id == chunk_id
    finally:
        if store._client is not None and store._client.has_collection(collection_name=collection):
            store._client.drop_collection(collection_name=collection)
        store.close()


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_CONVERSATION_E2E_INTEGRATION") != "1",
    reason="real Milvus and Ollama persistent conversation integration is opt-in",
)
def test_real_persistent_conversation_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDING_DIMENSION", "3")
    get_settings.cache_clear()
    settings = get_settings()
    collection = f"knowledgehub_conversation_test_{uuid4().hex}"
    store = MilvusVectorStore(
        settings.milvus_uri,
        settings.milvus_token,
        collection,
        "COSINE",
        "HNSW",
        16,
        200,
    )
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as session:
        user = User(email="integration@example.com", password_hash="not-used")
        session.add(user)
        session.flush()
        document = Document(
            user_id=user.id,
            original_filename="integration.txt",
            stored_filename=f"{uuid4()}.txt",
            mime_type="text/plain",
            size_bytes=42,
            storage_path="not-exposed",
            status=DocumentStatus.READY,
            embedding_status=EmbeddingStatus.EMBEDDED,
            chunk_count=1,
        )
        session.add(document)
        session.flush()
        chunk = DocumentChunk(
            document_id=document.id,
            chunk_index=0,
            content="Authentication uses signed access tokens.",
            character_count=41,
            token_count=6,
        )
        session.add(chunk)
        session.flush()
        session.add(
            ChunkEmbedding(chunk_id=chunk.id, embedding_dimension=3, model_name="integration")
        )
        session.commit()
        user_id, document_id, chunk_id = user.id, document.id, chunk.id
    try:
        store.ensure_collection(3)
        store.upsert_embeddings(
            [
                VectorEmbedding(
                    str(chunk_id),
                    str(document_id),
                    str(user_id),
                    [1.0, 0.0, 0.0],
                    "integration",
                    1,
                )
            ]
        )

        def session_override():
            with sessions() as session:
                yield session

        class Factory:
            def create(self, provider: str | None = None):
                assert provider in {None, "ollama"}
                return OllamaLLMProvider(settings.ollama_base_url, settings.ollama_model)

        application = create_application()
        application.dependency_overrides[get_database_session] = session_override
        application.dependency_overrides[get_vector_store] = lambda: store
        application.dependency_overrides[get_embedding_service] = StaticEmbeddingService
        application.dependency_overrides[get_llm_provider_factory] = Factory
        headers = {"Authorization": f"Bearer {create_access_token(user_id)}"}
        with TestClient(application) as client:
            conversation = client.post("/conversations", headers=headers, json={}).json()
            response = client.post(
                f"/conversations/{conversation['id']}/messages/stream",
                headers=headers,
                json={"query": "How does authentication work?"},
            )
            messages = client.get(
                f"/conversations/{conversation['id']}/messages", headers=headers
            ).json()
        assert "event: completed" in response.text
        assert messages["total"] == 2
        assert messages["items"][1]["status"] == "completed"
    finally:
        if store._client is not None and store._client.has_collection(collection_name=collection):
            store._client.drop_collection(collection_name=collection)
        store.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
        get_settings.cache_clear()
