import argparse
import json
from uuid import UUID

from sqlalchemy import select

from app.application.reconciliation import EmbeddingReconciliationService
from app.core.config import get_settings
from app.dependencies import get_vector_store
from app.infrastructure.database.models import Document
from app.infrastructure.database.session import get_session_factory
from app.infrastructure.repositories.documents import DocumentRepository


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile one document's embedding metadata")
    parser.add_argument("document_id", type=UUID)
    arguments = parser.parse_args()
    settings = get_settings()
    with get_session_factory()() as session:
        document = session.scalar(select(Document).where(Document.id == arguments.document_id))
        if document is None:
            parser.error("document was not found")
        repository = DocumentRepository(session)
        vector_store = get_vector_store()
        vector_store.ensure_collection(settings.embedding_dimension)
        report = EmbeddingReconciliationService().compare(
            str(document.id),
            repository.embedding_metadata(document.id),
            vector_store.list_vector_metadata(str(document.id)),
            settings.embedding_model,
            settings.embedding_dimension,
        )
        print(
            json.dumps(
                {
                    "document_id": str(document.id),
                    "consistent": report.consistent,
                    "metadata_without_vectors": sorted(report.metadata_without_vectors),
                    "vectors_without_metadata": sorted(report.vectors_without_metadata),
                    "wrong_model_names": sorted(report.wrong_model_names),
                    "wrong_dimensions": sorted(report.wrong_dimensions),
                }
            )
        )
        return 0 if report.consistent else 1


if __name__ == "__main__":
    raise SystemExit(main())
