import os
from uuid import UUID, uuid4

import pytest

from app.application.prompting import PromptBuilder
from app.application.rag import RAGService
from app.application.retrieval import RetrievalService, RetrievalSource
from app.application.vector_store import VectorEmbedding
from app.core.config import get_settings
from app.infrastructure.llm import OllamaLLMProvider
from app.infrastructure.vector.milvus import MilvusVectorStore


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
