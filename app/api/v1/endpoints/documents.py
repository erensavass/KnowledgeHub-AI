import codecs
import re
import zipfile
from pathlib import Path
from typing import Annotated, BinaryIO
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.endpoints.auth import DatabaseSession, get_current_user
from app.api.v1.schemas.documents import DocumentResponse
from app.core.config import get_settings
from app.infrastructure.database.models import Document, User
from app.infrastructure.repositories.documents import DocumentRepository

router = APIRouter(prefix="/documents", tags=["documents"])
CurrentUser = Annotated[User, Depends(get_current_user)]

ALLOWED_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}
CHUNK_SIZE = 1024 * 1024


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
            return DocumentRepository(session).create(document)
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
def delete_document(document_id: UUID, current_user: CurrentUser, session: DatabaseSession) -> None:
    document = owned_document(document_id, current_user, session)
    Path(document.storage_path).unlink(missing_ok=True)
    DocumentRepository(session).delete(document)
