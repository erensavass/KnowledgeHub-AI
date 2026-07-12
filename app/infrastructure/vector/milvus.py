from typing import Any

from app.application.vector_store import (
    VectorEmbedding,
    VectorMetadata,
    VectorSearchResult,
    VectorStoreError,
)
from app.core.logging import get_logger

logger = get_logger(__name__)
REQUIRED_FIELDS = {
    "id",
    "chunk_id",
    "document_id",
    "user_id",
    "embedding",
    "embedding_model",
    "embedding_dimension",
    "created_at",
}


class MilvusVectorStore:
    def __init__(
        self,
        uri: str,
        token: str,
        collection: str,
        metric_type: str,
        index_type: str,
        hnsw_m: int,
        hnsw_ef_construction: int,
    ) -> None:
        self.uri = uri
        self.token = token
        self.collection = collection
        self.metric_type = metric_type
        self.index_type = index_type
        self.hnsw_m = hnsw_m
        self.hnsw_ef_construction = hnsw_ef_construction
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from pymilvus import MilvusClient

                kwargs = {"uri": self.uri}
                if self.token:
                    kwargs["token"] = self.token
                self._client = MilvusClient(**kwargs)
                logger.info("milvus_connection_established", extra={"collection": self.collection})
            except Exception as exc:
                raise VectorStoreError("milvus_connection_failed") from exc
        return self._client

    def health_check(self) -> bool:
        try:
            self._get_client().list_collections()
            return True
        except Exception as exc:
            raise VectorStoreError("milvus_health_check_failed") from exc

    def ensure_collection(self, dimension: int) -> None:
        client = self._get_client()
        try:
            if not client.has_collection(collection_name=self.collection):
                self._create_collection(client, dimension)
                logger.info("milvus_collection_created", extra={"collection": self.collection})
                return
            description = client.describe_collection(collection_name=self.collection)
            fields = {field["name"]: field for field in description.get("fields", [])}
            missing = REQUIRED_FIELDS - fields.keys()
            vector_field = fields.get("embedding", {})
            params = vector_field.get("params", {})
            existing_dimension = int(params.get("dim", vector_field.get("dim", 0)))
            from pymilvus import DataType

            expected_types = {
                "id": DataType.VARCHAR,
                "chunk_id": DataType.VARCHAR,
                "document_id": DataType.VARCHAR,
                "user_id": DataType.VARCHAR,
                "embedding": DataType.FLOAT_VECTOR,
                "embedding_model": DataType.VARCHAR,
                "embedding_dimension": DataType.INT64,
                "created_at": DataType.INT64,
            }
            wrong_types = {
                name
                for name, datatype in expected_types.items()
                if name in fields and int(fields[name].get("type", -1)) != int(datatype)
            }
            primary_is_valid = bool(fields.get("id", {}).get("is_primary"))
            if missing or wrong_types or not primary_is_valid or existing_dimension != dimension:
                raise VectorStoreError("incompatible_milvus_collection")
            indexes = client.list_indexes(collection_name=self.collection)
            if "embedding" not in indexes:
                raise VectorStoreError("incompatible_milvus_collection")
            index = client.describe_index(
                collection_name=self.collection, index_name="embedding"
            )
            if (
                str(index.get("index_type", "")).upper() != self.index_type.upper()
                or str(index.get("metric_type", "")).upper() != self.metric_type.upper()
            ):
                raise VectorStoreError("incompatible_milvus_collection")
            logger.info("milvus_collection_validated", extra={"collection": self.collection})
        except VectorStoreError:
            raise
        except Exception as exc:
            raise VectorStoreError("milvus_collection_validation_failed") from exc

    def _create_collection(self, client: Any, dimension: int) -> None:
        from pymilvus import DataType

        schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=36)
        schema.add_field("chunk_id", DataType.VARCHAR, max_length=36)
        schema.add_field("document_id", DataType.VARCHAR, max_length=36)
        schema.add_field("user_id", DataType.VARCHAR, max_length=36)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=dimension)
        schema.add_field("embedding_model", DataType.VARCHAR, max_length=512)
        schema.add_field("embedding_dimension", DataType.INT64)
        schema.add_field("created_at", DataType.INT64)
        indexes = client.prepare_index_params()
        index_params = {"M": self.hnsw_m, "efConstruction": self.hnsw_ef_construction}
        indexes.add_index(
            field_name="embedding",
            index_name="embedding",
            index_type=self.index_type,
            metric_type=self.metric_type,
            params=index_params,
        )
        client.create_collection(
            collection_name=self.collection, schema=schema, index_params=indexes
        )

    def upsert_embeddings(self, embeddings: list[VectorEmbedding]) -> None:
        if not embeddings:
            return
        logger.info(
            "milvus_batch_upsert_started",
            extra={"collection": self.collection, "vector_count": len(embeddings)},
        )
        data = [
            {
                "id": item.chunk_id,
                "chunk_id": item.chunk_id,
                "document_id": item.document_id,
                "user_id": item.user_id,
                "embedding": item.embedding,
                "embedding_model": item.embedding_model,
                "embedding_dimension": len(item.embedding),
                "created_at": item.created_at,
            }
            for item in embeddings
        ]
        try:
            self._get_client().upsert(collection_name=self.collection, data=data)
        except Exception as exc:
            raise VectorStoreError("milvus_upsert_failed") from exc
        logger.info(
            "milvus_batch_upsert_completed",
            extra={"collection": self.collection, "vector_count": len(embeddings)},
        )

    def delete_by_chunk_ids(self, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return
        try:
            self._get_client().delete(collection_name=self.collection, ids=chunk_ids)
        except Exception as exc:
            raise VectorStoreError("milvus_delete_failed") from exc
        logger.info(
            "milvus_vector_deletion_completed",
            extra={"collection": self.collection, "vector_count": len(chunk_ids)},
        )

    def delete_by_document_id(self, document_id: str) -> None:
        try:
            self._get_client().delete(
                collection_name=self.collection, filter=f'document_id == "{document_id}"'
            )
        except Exception as exc:
            raise VectorStoreError("milvus_delete_failed") from exc
        logger.info(
            "milvus_vector_deletion_completed",
            extra={"collection": self.collection, "document_id": document_id},
        )

    def has_chunk_vectors(self, chunk_ids: list[str]) -> set[str]:
        if not chunk_ids:
            return set()
        try:
            rows = self._get_client().get(
                collection_name=self.collection, ids=chunk_ids, output_fields=["chunk_id"]
            )
            return {str(row["chunk_id"]) for row in rows}
        except Exception as exc:
            raise VectorStoreError("milvus_query_failed") from exc

    def count_vectors_for_document(self, document_id: str) -> int:
        return len(self.list_vector_metadata(document_id))

    def list_vector_metadata(self, document_id: str) -> list[VectorMetadata]:
        try:
            rows = self._get_client().query(
                collection_name=self.collection,
                filter=f'document_id == "{document_id}"',
                output_fields=[
                    "chunk_id",
                    "document_id",
                    "embedding_model",
                    "embedding_dimension",
                ],
            )
            return [
                VectorMetadata(
                    chunk_id=str(row["chunk_id"]),
                    document_id=str(row["document_id"]),
                    embedding_model=str(row["embedding_model"]),
                    embedding_dimension=int(row["embedding_dimension"]),
                )
                for row in rows
            ]
        except Exception as exc:
            raise VectorStoreError("milvus_query_failed") from exc

    def search(
        self,
        query_vector: list[float],
        user_id: str,
        document_ids: list[str] | None = None,
        top_k: int = 5,
        score_threshold: float | None = None,
    ) -> list[VectorSearchResult]:
        filters = [f'user_id == "{user_id}"']
        if document_ids:
            values = ", ".join(f'"{document_id}"' for document_id in document_ids)
            filters.append(f"document_id in [{values}]")
        try:
            response = self._get_client().search(
                collection_name=self.collection,
                data=[query_vector],
                anns_field="embedding",
                filter=" and ".join(filters),
                limit=top_k,
                output_fields=["chunk_id"],
                search_params={"metric_type": self.metric_type, "params": {"ef": max(64, top_k)}},
            )
            hits = response[0] if response else []
            results = []
            for hit in hits:
                entity = hit.get("entity", {})
                chunk_id = entity.get("chunk_id", hit.get("id"))
                raw_score = float(hit.get("distance", hit.get("score", 0.0)))
                score = 1.0 / (1.0 + raw_score) if self.metric_type.upper() == "L2" else raw_score
                if chunk_id is not None and (
                    score_threshold is None or score >= score_threshold
                ):
                    results.append(VectorSearchResult(chunk_id=str(chunk_id), score=score))
            return results
        except Exception as exc:
            raise VectorStoreError("milvus_search_failed") from exc

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
