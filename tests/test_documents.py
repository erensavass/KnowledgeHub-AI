from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings

PDF_CONTENT = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"
TXT_CONTENT = b"KnowledgeHub document text\n"


def make_docx() -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types></Types>")
        archive.writestr("word/document.xml", "<document></document>")
    return output.getvalue()


def create_user(client: TestClient, email: str) -> str:
    credentials = {"email": email, "password": "StrongPass123!"}
    assert client.post("/auth/register", json=credentials).status_code == 201
    response = client.post("/auth/login", json=credentials)
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def upload(
    client: TestClient, token: str, filename: str, content: bytes, mime_type: str
):
    return client.post(
        "/documents/upload", headers=auth(token), files={"file": (filename, content, mime_type)}
    )


@pytest.mark.parametrize(
    ("filename", "content", "mime_type"),
    [
        ("report.pdf", PDF_CONTENT, "application/pdf"),
        (
            "report.docx",
            make_docx(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        ("notes.txt", TXT_CONTENT, "text/plain"),
    ],
)
def test_successful_supported_uploads(
    client: TestClient, filename: str, content: bytes, mime_type: str
) -> None:
    token = create_user(client, "uploader@example.com")
    response = upload(client, token, f"../../{filename}", content, mime_type)

    assert response.status_code == 201
    body = response.json()
    assert body["original_filename"] == filename
    assert body["mime_type"] == mime_type
    assert body["size_bytes"] == len(content)
    assert body["status"] == "uploaded"
    assert "storage_path" not in body
    assert body["stored_filename"] != filename
    assert Path(get_settings().document_storage_path, body["stored_filename"]).is_file()


def test_unsupported_file_type(client: TestClient) -> None:
    token = create_user(client, "unsupported@example.com")
    response = upload(client, token, "malware.exe", b"not executable", "application/octet-stream")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_file_type"


def test_oversized_file(client: TestClient) -> None:
    token = create_user(client, "large@example.com")
    response = upload(client, token, "large.txt", b"a" * (1024 * 1024 + 1), "text/plain")

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


def test_empty_file(client: TestClient) -> None:
    token = create_user(client, "empty@example.com")
    response = upload(client, token, "empty.txt", b"", "text/plain")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "empty_file"


def test_unauthenticated_upload(client: TestClient) -> None:
    response = client.post(
        "/documents/upload", files={"file": ("notes.txt", TXT_CONTENT, "text/plain")}
    )

    assert response.status_code == 401


def test_listing_only_current_users_documents(client: TestClient) -> None:
    first = create_user(client, "first@example.com")
    second = create_user(client, "second@example.com")
    own_document = upload(client, first, "own.txt", TXT_CONTENT, "text/plain").json()
    upload(client, second, "other.txt", TXT_CONTENT, "text/plain")

    response = client.get("/documents", headers=auth(first))

    assert response.status_code == 200
    assert [document["id"] for document in response.json()] == [own_document["id"]]


def test_cross_user_access_is_not_found(client: TestClient) -> None:
    owner = create_user(client, "owner@example.com")
    other = create_user(client, "other@example.com")
    document = upload(client, owner, "private.txt", TXT_CONTENT, "text/plain").json()

    response = client.get(f"/documents/{document['id']}", headers=auth(other))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"


def test_cross_user_deletion_is_not_found(client: TestClient) -> None:
    owner = create_user(client, "delete-owner@example.com")
    other = create_user(client, "delete-other@example.com")
    document = upload(client, owner, "private.txt", TXT_CONTENT, "text/plain").json()

    response = client.delete(f"/documents/{document['id']}", headers=auth(other))

    assert response.status_code == 404
    assert client.get(f"/documents/{document['id']}", headers=auth(owner)).status_code == 200


def test_successful_deletion_removes_metadata_and_file(client: TestClient) -> None:
    token = create_user(client, "delete@example.com")
    document = upload(client, token, "delete.txt", TXT_CONTENT, "text/plain").json()
    stored_file = Path(get_settings().document_storage_path, document["stored_filename"])

    response = client.delete(f"/documents/{document['id']}", headers=auth(token))

    assert response.status_code == 204
    assert not stored_file.exists()
    assert client.get(f"/documents/{document['id']}", headers=auth(token)).status_code == 404
