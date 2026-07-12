from dataclasses import dataclass

from app.application.vector_store import VectorMetadata
from app.core.logging import get_logger
from app.infrastructure.database.models import ChunkEmbedding

logger = get_logger(__name__)


@dataclass(frozen=True)
class ReconciliationReport:
    metadata_without_vectors: set[str]
    vectors_without_metadata: set[str]
    wrong_model_names: set[str]
    wrong_dimensions: set[str]

    @property
    def consistent(self) -> bool:
        return not any(
            (
                self.metadata_without_vectors,
                self.vectors_without_metadata,
                self.wrong_model_names,
                self.wrong_dimensions,
            )
        )


class EmbeddingReconciliationService:
    def compare(
        self,
        document_id: str,
        metadata: list[ChunkEmbedding],
        vectors: list[VectorMetadata],
        expected_model: str,
        expected_dimension: int,
    ) -> ReconciliationReport:
        postgres = {str(item.chunk_id): item for item in metadata}
        milvus = {item.chunk_id: item for item in vectors}
        shared = postgres.keys() & milvus.keys()
        report = ReconciliationReport(
            metadata_without_vectors=postgres.keys() - milvus.keys(),
            vectors_without_metadata=milvus.keys() - postgres.keys(),
            wrong_model_names={
                chunk_id
                for chunk_id in shared
                if postgres[chunk_id].model_name != expected_model
                or milvus[chunk_id].embedding_model != expected_model
                or postgres[chunk_id].model_name != milvus[chunk_id].embedding_model
            },
            wrong_dimensions={
                chunk_id
                for chunk_id in shared
                if postgres[chunk_id].embedding_dimension != expected_dimension
                or milvus[chunk_id].embedding_dimension != expected_dimension
                or postgres[chunk_id].embedding_dimension
                != milvus[chunk_id].embedding_dimension
            },
        )
        if not report.consistent:
            logger.warning(
                "embedding_reconciliation_mismatch_detected",
                extra={
                    "document_id": document_id,
                    "metadata_without_vectors": len(report.metadata_without_vectors),
                    "vectors_without_metadata": len(report.vectors_without_metadata),
                    "wrong_model_names": len(report.wrong_model_names),
                    "wrong_dimensions": len(report.wrong_dimensions),
                },
            )
        return report
