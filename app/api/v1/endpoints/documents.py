import codecs
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, BinaryIO
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.endpoints.auth import DatabaseSession, get_current_user
from app.api.v1.schemas.documents import (
    ChunkListResponse,
    DocumentResponse,
    EmbeddingStatusResponse,
    EmbedResponse,
)
from app.application.chunking import DocumentChunker
from app.application.embedding import EmbeddingError, EmbeddingService
from app.application.extraction import ExtractionError, TextExtractor
from app.application.vector_store import VectorEmbedding, VectorStore, VectorStoreError
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.metrics import metrics
from app.dependencies import get_embedding_service, get_vector_store
from app.infrastructure.database.models import (
    ChunkEmbedding,
    Document,
    DocumentChunk,
    DocumentStatus,
    EmbeddingStatus,
    User,
)
from app.infrastructure.repositories.documents import DocumentRepository

router = APIRouter(prefix="/documents", tags=["documents"])
CurrentUser = Annotated[User, Depends(get_current_user)]
EmbeddingServiceDependency = Annotated[EmbeddingService, Depends(get_embedding_service)]
VectorStoreDependency = Annotated[VectorStore, Depends(get_vector_store)]

ALLOWED_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}
CHUNK_SIZE = 1024 * 1024
logger = get_logger(__name__)


def upload_error(code: str, message: str, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def sanitize_filename(filename: str | None) -> str:
    candidate = (filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    candidate = re.sub(r"[^A-Za-z0-9._ -]", "_", candidate).strip(" .")
    if not candidate:
        return "document"
    suffix = Path(candidate).suffix[:16]
    return f"{candidate[: 255 - len(suffix)]}{suffix}" if len(candidate) > 255 else candidate


def validate_content(file: BinaryIO, extension: str) -> None:
    file.seek(0)
    if extension == ".pdf" and not file.read(5).startswith(b"%PDF-"):
        raise upload_error("invalid_file_content", "File content is not a valid PDF")
    if extension == ".docx":
        try:
            with zipfile.ZipFile(file) as archive:
                names = set(archive.namelist())
                if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                    raise zipfile.BadZipFile
        except (zipfile.BadZipFile, OSError) as exc:
            raise upload_error("invalid_file_content", "File content is not a valid DOCX") from exc
    if extension == ".txt":
        file.seek(0)
        try:
            decoder = codecs.getincrementaldecoder("utf-8")()
            while chunk := file.read(CHUNK_SIZE):
                if b"\x00" in chunk:
                    raise UnicodeError
                decoder.decode(chunk)
            decoder.decode(b"", final=True)
        except UnicodeError as exc:
            raise upload_error("invalid_file_content", "TXT files must contain UTF-8 text") from exc
    file.seek(0)


def prepare_upload(upload: UploadFile) -> tuple[str, str]:
    safe_name = sanitize_filename(upload.filename)
    extension = Path(safe_name).suffix.lower()
    if extension not in ALLOWED_TYPES:
        raise upload_error("unsupported_file_type", "Only PDF, DOCX, and TXT files are allowed")
    content_type = (upload.content_type or "").split(";", 1)[0].strip().lower()
    if content_type != ALLOWED_TYPES[extension]:
        raise upload_error("invalid_mime_type", "File extension and MIME type do not match")
    return safe_name, extension


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    file: Annotated[UploadFile, File()], current_user: CurrentUser, session: DatabaseSession
) -> Document:
    safe_name, extension = prepare_upload(file)
    settings = get_settings()
    maximum_bytes = settings.max_upload_size_mb * 1024 * 1024
    storage_root = settings.document_storage_path.resolve()
    storage_root.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid4()}{extension}"
    destination = storage_root / stored_filename
    temporary = storage_root / f".{stored_filename}.upload"
    size = 0
    try:
        with temporary.open("xb") as output:
            while chunk := file.file.read(CHUNK_SIZE):
                size += len(chunk)
                if size > maximum_bytes:
                    raise upload_error(
                        "file_too_large",
                        f"File exceeds the {settings.max_upload_size_mb} MB limit",
                        413,
                    )
                output.write(chunk)
        if size == 0:
            raise upload_error("empty_file", "Uploaded file must not be empty")
        with temporary.open("rb") as uploaded_content:
            validate_content(uploaded_content, extension)
        temporary.replace(destination)
        document = Document(
            user_id=current_user.id,
            original_filename=safe_name,
            stored_filename=stored_filename,
            mime_type=ALLOWED_TYPES[extension],
            size_bytes=size,
            storage_path=str(destination),
        )
        try:
            result = DocumentRepository(session).create(document)
            metrics.increment("knowledgehub_uploads_total")
            return result
        except SQLAlchemyError:
            session.rollback()
            destination.unlink(missing_ok=True)
            raise
    finally:
        temporary.unlink(missing_ok=True)
        file.file.close()


@router.get("", response_model=list[DocumentResponse])
def list_documents(current_user: CurrentUser, session: DatabaseSession) -> list[Document]:
    return DocumentRepository(session).list_for_user(current_user.id)


def owned_document(document_id: UUID, current_user: User, session: DatabaseSession) -> Document:
    document = DocumentRepository(session).get_for_user(document_id, current_user.id)
    if document is None:
        raise upload_error("document_not_found", "Document was not found", 404)
    return document


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: UUID, current_user: CurrentUser, session: DatabaseSession
) -> Document:
    return owned_document(document_id, current_user, session)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
    vector_store: VectorStoreDependency,
) -> None:
    document = owned_document(document_id, current_user, session)
    try:
        vector_store.ensure_collection(get_settings().embedding_dimension)
        vector_store.delete_by_document_id(str(document.id))
    except VectorStoreError as exc:
        logger.error(
            "document_vector_deletion_failed",
            extra={"document_id": str(document.id), "error_code": exc.args[0]},
        )
        raise upload_error(
            "vector_cleanup_unavailable", "Document could not be safely deleted", 503
        ) from exc
    Path(document.storage_path).unlink(missing_ok=True)
    DocumentRepository(session).delete(document)


@router.post("/{document_id}/process", response_model=DocumentResponse)
def process_document(
    document_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
    vector_store: VectorStoreDependency,
) -> Document:
    document = owned_document(document_id, current_user, session)
    if document.status == DocumentStatus.PROCESSING:
        raise upload_error("document_already_processing", "Document is already processing", 409)

    try:
        vector_store.ensure_collection(get_settings().embedding_dimension)
        vector_store.delete_by_document_id(str(document.id))
    except VectorStoreError as exc:
        raise upload_error(
            "vector_cleanup_unavailable", "Document could not be safely reprocessed", 503
        ) from exc

    document.status = DocumentStatus.PROCESSING
    document.processing_error_code = None
    session.commit()
    logger.info("document_processing_started", extra={"document_id": str(document.id)})
    repository = DocumentRepository(session)
    try:
        sections = TextExtractor().extract(Path(document.storage_path), document.mime_type)
        logger.info(
            "document_extraction_completed",
            extra={"document_id": str(document.id), "section_count": len(sections)},
        )
        settings = get_settings()
        generated = DocumentChunker(settings.chunk_size, settings.chunk_overlap).chunk(sections)
        if not generated:
            raise ExtractionError("empty_extracted_content")
        logger.info(
            "document_chunking_completed",
            extra={"document_id": str(document.id), "chunk_count": len(generated)},
        )
        chunks = [
            DocumentChunk(
                document_id=document.id,
                chunk_index=index,
                content=item.content,
                character_count=item.character_count,
                token_count=item.token_count,
                page_number=item.page_number,
                metadata_json=item.metadata_json,
            )
            for index, item in enumerate(generated)
        ]
        repository.replace_chunks(document.id, chunks)
        document.status = DocumentStatus.READY
        document.processed_at = datetime.now(UTC)
        document.chunk_count = len(chunks)
        document.processing_error_code = None
        document.embedding_status = EmbeddingStatus.PENDING
        document.embedding_error_code = None
        session.commit()
        session.refresh(document)
        logger.info(
            "document_processing_succeeded",
            extra={"document_id": str(document.id), "chunk_count": len(chunks)},
        )
        return document
    except Exception as exc:
        metrics.increment("knowledgehub_processing_failures_total")
        session.rollback()
        error_code = exc.args[0] if isinstance(exc, ExtractionError) else "processing_failed"
        try:
            repository.replace_chunks(document.id, [])
            document.status = DocumentStatus.FAILED
            document.processed_at = None
            document.chunk_count = 0
            document.processing_error_code = str(error_code)[:64]
            document.embedding_status = EmbeddingStatus.PENDING
            document.embedding_error_code = None
            session.commit()
        except SQLAlchemyError:
            session.rollback()
        logger.error(
            "document_processing_failed",
            extra={"document_id": str(document.id), "error_code": error_code},
        )
        raise upload_error("document_processing_failed", "Document processing failed", 422) from exc


@router.get("/{document_id}/chunks", response_model=ChunkListResponse)
def list_document_chunks(
    document_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ChunkListResponse:
    owned_document(document_id, current_user, session)
    chunks, total = DocumentRepository(session).list_chunks(document_id, limit, offset)
    return ChunkListResponse(items=chunks, total=total, limit=limit, offset=offset)


@router.post("/{document_id}/embed", response_model=EmbedResponse)
def embed_document(
    document_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
    embedding_service: EmbeddingServiceDependency,
    vector_store: VectorStoreDependency,
    force: bool = False,
) -> EmbedResponse:
    document = owned_document(document_id, current_user, session)
    if document.status != DocumentStatus.READY:
        raise upload_error("document_not_ready", "Document must be ready before embedding", 409)
    if document.embedding_status == EmbeddingStatus.EMBEDDING:
        raise upload_error("document_already_embedding", "Document is already embedding", 409)

    repository = DocumentRepository(session)
    chunks = repository.all_chunks(document.id)
    if not chunks:
        raise upload_error("document_has_no_chunks", "Document has no chunks to embed", 409)
    settings = get_settings()
    try:
        vector_store.ensure_collection(settings.embedding_dimension)
        vector_records = {
            item.chunk_id: item for item in vector_store.list_vector_metadata(str(document.id))
        }
    except VectorStoreError as exc:
        raise upload_error("vector_store_unavailable", "Vector store is unavailable", 503) from exc
    existing = {item.chunk_id: item for item in repository.embedding_metadata(document.id)}
    targets = [
        chunk
        for chunk in chunks
        if force
        or chunk.id not in existing
        or existing[chunk.id].model_name != embedding_service.model_name
        or str(chunk.id) not in vector_records
        or vector_records[str(chunk.id)].embedding_model != embedding_service.model_name
        or vector_records[str(chunk.id)].embedding_dimension
        != existing[chunk.id].embedding_dimension
    ]
    document.embedding_status = EmbeddingStatus.EMBEDDING
    document.embedding_error_code = None
    session.commit()
    logger.info(
        "document_embedding_started",
        extra={
            "document_id": str(document.id),
            "chunk_count": len(targets),
            "model_name": embedding_service.model_name,
            "force": force,
        },
    )
    milvus_written = False
    try:
        vectors = (
            embedding_service.embed([chunk.content for chunk in targets]) if targets else []
        )
        if vectors and any(len(vector) != settings.embedding_dimension for vector in vectors):
            raise EmbeddingError("embedding_dimension_mismatch")
        vector_store.upsert_embeddings(
            [
                VectorEmbedding(
                    chunk_id=str(chunk.id),
                    document_id=str(document.id),
                    user_id=str(current_user.id),
                    embedding=vector,
                    embedding_model=embedding_service.model_name,
                    created_at=int(datetime.now(UTC).timestamp()),
                )
                for chunk, vector in zip(targets, vectors, strict=True)
            ]
        )
        milvus_written = bool(targets)
        present = vector_store.has_chunk_vectors([str(chunk.id) for chunk in chunks])
        if present != {str(chunk.id) for chunk in chunks}:
            raise VectorStoreError("milvus_vector_verification_failed")
        metadata = [
            ChunkEmbedding(
                chunk_id=chunk.id,
                embedding_dimension=len(vector),
                model_name=embedding_service.model_name,
            )
            for chunk, vector in zip(targets, vectors, strict=True)
        ]
        repository.replace_embedding_metadata([chunk.id for chunk in targets], metadata)
        document.embedding_status = EmbeddingStatus.EMBEDDED
        document.embedding_error_code = None
        session.commit()
        embedded_count = len(chunks)
        logger.info(
            "document_embedding_completed",
            extra={
                "document_id": str(document.id),
                "embedded_chunks": embedded_count,
                "model_name": embedding_service.model_name,
            },
        )
        return EmbedResponse(
            document_id=document.id,
            total_chunks=len(chunks),
            embedded_chunks=embedded_count,
            skipped_chunks=len(chunks) - len(targets),
            embedding_model=embedding_service.model_name,
            status=document.embedding_status,
        )
    except Exception as exc:
        metrics.increment("knowledgehub_embedding_failures_total")
        session.rollback()
        error_code = (
            exc.args[0]
            if isinstance(exc, (EmbeddingError, VectorStoreError))
            else "embedding_failed"
        )
        if milvus_written:
            logger.warning(
                "milvus_compensation_started",
                extra={"document_id": str(document.id), "vector_count": len(targets)},
            )
            try:
                vector_store.delete_by_chunk_ids([str(chunk.id) for chunk in targets])
                logger.info(
                    "milvus_compensation_completed",
                    extra={"document_id": str(document.id), "vector_count": len(targets)},
                )
            except VectorStoreError as cleanup_exc:
                logger.error(
                    "milvus_reconciliation_required",
                    extra={
                        "document_id": str(document.id),
                        "error_code": cleanup_exc.args[0],
                    },
                )
        try:
            document.embedding_status = EmbeddingStatus.EMBEDDING_FAILED
            document.embedding_error_code = str(error_code)[:64]
            session.commit()
        except SQLAlchemyError:
            session.rollback()
        logger.error(
            "document_embedding_failed",
            extra={"document_id": str(document.id), "error_code": error_code},
        )
        raise upload_error("document_embedding_failed", "Document embedding failed", 422) from exc


@router.get("/{document_id}/embedding-status", response_model=EmbeddingStatusResponse)
def document_embedding_status(
    document_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
    vector_store: VectorStoreDependency,
) -> EmbeddingStatusResponse:
    document = owned_document(document_id, current_user, session)
    settings = get_settings()
    repository = DocumentRepository(session)
    chunks = repository.all_chunks(document.id)
    metadata = repository.embedding_metadata(document.id)
    try:
        vector_store.ensure_collection(settings.embedding_dimension)
        vectors = vector_store.list_vector_metadata(str(document.id))
    except VectorStoreError as exc:
        raise upload_error("vector_store_unavailable", "Vector store is unavailable", 503) from exc
    chunk_ids = {str(chunk.id) for chunk in chunks}
    metadata_by_id = {str(item.chunk_id): item for item in metadata}
    vectors_by_id = {item.chunk_id: item for item in vectors}
    embedded = sum(
        chunk_id in chunk_ids
        and item.model_name == settings.embedding_model
        and item.embedding_dimension == settings.embedding_dimension
        for chunk_id, item in metadata_by_id.items()
    )
    valid_vectors = sum(
        chunk_id in chunk_ids
        and item.embedding_model == settings.embedding_model
        and item.embedding_dimension == settings.embedding_dimension
        for chunk_id, item in vectors_by_id.items()
    )
    consistent = (
        embedded == valid_vectors
        and set(metadata_by_id) == set(vectors_by_id)
        and all(
            metadata_by_id[chunk_id].model_name == vectors_by_id[chunk_id].embedding_model
            and metadata_by_id[chunk_id].embedding_dimension
            == vectors_by_id[chunk_id].embedding_dimension
            for chunk_id in set(metadata_by_id) & set(vectors_by_id)
        )
    )
    consistent_pairs = sum(
        chunk_id in metadata_by_id
        and metadata_by_id[chunk_id].model_name == item.embedding_model
        and metadata_by_id[chunk_id].embedding_dimension == item.embedding_dimension
        and item.embedding_model == settings.embedding_model
        and item.embedding_dimension == settings.embedding_dimension
        for chunk_id, item in vectors_by_id.items()
        if chunk_id in chunk_ids
    )
    current_status = document.embedding_status
    if current_status == EmbeddingStatus.EMBEDDED and (
        embedded < len(chunks) or valid_vectors < len(chunks) or not consistent
    ):
        current_status = EmbeddingStatus.PENDING
    return EmbeddingStatusResponse(
        total_chunks=len(chunks),
        embedded_chunks_in_postgres=embedded,
        vectors_in_milvus=valid_vectors,
        remaining_chunks=len(chunks) - consistent_pairs,
        embedding_model=settings.embedding_model,
        embedding_dimension=settings.embedding_dimension,
        status=current_status,
        consistent=consistent,
    )
