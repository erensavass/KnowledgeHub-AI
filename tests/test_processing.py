from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from docx import Document as DocxDocument
from fastapi.testclient import TestClient

from app.application.chunking import DocumentChunker
from app.application.extraction import ExtractedSection
from app.core.config import get_settings
from tests.test_documents import auth, create_user, upload


def docx_bytes(*paragraphs: str) -> bytes:
    output = BytesIO()
    document = DocxDocument()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    document.save(output)
    return output.getvalue()


def pdf_bytes(*pages: str) -> bytes:
    objects = ["<< /Type /Catalog /Pages 2 0 R >>"]
    page_ids = [3 + index * 2 for index in range(len(pages))]
    children = " ".join(f"{item} 0 R" for item in page_ids)
    objects.append(f"<< /Type /Pages /Kids [{children}] /Count {len(pages)} >>")
    for index, text in enumerate(pages):
        page_id = page_ids[index]
        content_id = page_id + 1
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 << /Type /Font /Subtype /Type1 "
            f"/BaseFont /Helvetica >> >> >> /Contents {content_id} 0 R >>"
        )
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, value in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n{value}\nendobj\n".encode())
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    output.extend(b"".join(f"{item:010} 00000 n \n".encode() for item in offsets[1:]))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    )
    return bytes(output)


def test_txt_processing_and_listing(client: TestClient) -> None:
    token = create_user(client, "process-txt@example.com")
    uploaded = upload(
        client, token, "notes.txt", b"First paragraph.\n\nSecond paragraph.", "text/plain"
    ).json()

    response = client.post(f"/documents/{uploaded['id']}/process", headers=auth(token))

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["chunk_count"] == 1
    chunks = client.get(f"/documents/{uploaded['id']}/chunks", headers=auth(token)).json()
    assert chunks["total"] == 1
    assert chunks["items"][0]["content"] == "First paragraph.\n\nSecond paragraph."
    assert chunks["items"][0]["character_count"] == len(chunks["items"][0]["content"])
    assert "storage_path" not in chunks["items"][0]


def test_docx_processing_preserves_paragraph_order(client: TestClient) -> None:
    token = create_user(client, "process-docx@example.com")
    uploaded = upload(
        client,
        token,
        "ordered.docx",
        docx_bytes("Alpha", "Beta", "Gamma"),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ).json()

    response = client.post(f"/documents/{uploaded['id']}/process", headers=auth(token))
    assert response.status_code == 200
    chunks = client.get(f"/documents/{uploaded['id']}/chunks", headers=auth(token)).json()
    assert chunks["items"][0]["content"] == "Alpha\n\nBeta\n\nGamma"


def test_pdf_processing_preserves_page_numbers(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("CHUNK_SIZE", "10")
    monkeypatch.setenv("CHUNK_OVERLAP", "0")
    get_settings.cache_clear()
    token = create_user(client, "process-pdf@example.com")
    uploaded = upload(
        client, token, "pages.pdf", pdf_bytes("Page one", "Page two"), "application/pdf"
    ).json()

    response = client.post(f"/documents/{uploaded['id']}/process", headers=auth(token))
    chunks = client.get(f"/documents/{uploaded['id']}/chunks", headers=auth(token)).json()

    assert response.status_code == 200
    assert [item["page_number"] for item in chunks["items"]] == [1, 2]
    assert [item["content"] for item in chunks["items"]] == ["Page one", "Page two"]
    get_settings.cache_clear()


def test_corrupted_pdf_and_docx_fail_safely(client: TestClient) -> None:
    token = create_user(client, "corrupt@example.com")
    corrupt_pdf = upload(client, token, "broken.pdf", b"%PDF-not-really", "application/pdf").json()
    docx = BytesIO()
    with ZipFile(docx, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types></Types>")
        archive.writestr("word/document.xml", "not XML")
    corrupt_docx = upload(
        client,
        token,
        "broken.docx",
        docx.getvalue(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ).json()

    for document_id in (corrupt_pdf["id"], corrupt_docx["id"]):
        response = client.post(f"/documents/{document_id}/process", headers=auth(token))
        assert response.status_code == 422
        stored = client.get(f"/documents/{document_id}", headers=auth(token)).json()
        assert stored["status"] == "failed"
        assert stored["chunk_count"] == 0
        assert stored["processing_error_code"] == "document_extraction_failed"


def test_empty_content_fails_without_chunks(client: TestClient) -> None:
    token = create_user(client, "empty-process@example.com")
    uploaded = upload(client, token, "blank.txt", b" \n\n ", "text/plain").json()

    response = client.post(f"/documents/{uploaded['id']}/process", headers=auth(token))

    assert response.status_code == 422
    document = client.get(f"/documents/{uploaded['id']}", headers=auth(token)).json()
    assert document["status"] == "failed"
    assert document["processing_error_code"] == "empty_extracted_content"
    assert document["chunk_count"] == 0


def test_processing_and_chunks_are_owner_scoped(client: TestClient) -> None:
    owner = create_user(client, "process-owner@example.com")
    other = create_user(client, "process-other@example.com")
    uploaded = upload(client, owner, "private.txt", b"private text", "text/plain").json()

    denied = client.post(f"/documents/{uploaded['id']}/process", headers=auth(other))
    assert denied.status_code == 404
    assert client.post(f"/documents/{uploaded['id']}/process").status_code == 401
    processed = client.post(f"/documents/{uploaded['id']}/process", headers=auth(owner))
    assert processed.status_code == 200
    assert client.get(f"/documents/{uploaded['id']}/chunks", headers=auth(other)).status_code == 404


def test_reprocessing_replaces_chunks_without_duplicates(client: TestClient) -> None:
    token = create_user(client, "reprocess@example.com")
    uploaded = upload(
        client, token, "again.txt", b"same deterministic content", "text/plain"
    ).json()
    url = f"/documents/{uploaded['id']}"

    assert client.post(f"{url}/process", headers=auth(token)).status_code == 200
    first = client.get(f"{url}/chunks", headers=auth(token)).json()
    assert client.post(f"{url}/process", headers=auth(token)).status_code == 200
    second = client.get(f"{url}/chunks", headers=auth(token)).json()

    assert first["total"] == second["total"] == 1
    assert first["items"][0]["content"] == second["items"][0]["content"]
    assert second["items"][0]["chunk_index"] == 0


def test_chunk_pagination(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("CHUNK_SIZE", "10")
    monkeypatch.setenv("CHUNK_OVERLAP", "0")
    get_settings.cache_clear()
    token = create_user(client, "pagination@example.com")
    uploaded = upload(
        client,
        token,
        "pages.txt",
        b"aaaaaaaaaa\n\nbbbbbbbbbb\n\ncccccccccc",
        "text/plain",
    ).json()
    url = f"/documents/{uploaded['id']}"
    assert client.post(f"{url}/process", headers=auth(token)).status_code == 200

    page = client.get(f"{url}/chunks?limit=1&offset=1", headers=auth(token)).json()
    assert page["total"] == 3
    assert page["limit"] == 1
    assert page["offset"] == 1
    assert page["items"][0]["chunk_index"] == 1
    get_settings.cache_clear()


def test_chunking_is_deterministic_and_paragraph_aware() -> None:
    sections = [ExtractedSection("one one\n\ntwo two\n\nthree three")]
    chunker = DocumentChunker(size=20, overlap=8)
    first = chunker.chunk(sections)
    second = chunker.chunk(sections)

    assert first == second
    assert all(chunk.content in {"one one\n\ntwo two", "two two\n\nthree three"} for chunk in first)


def test_oversized_paragraph_uses_overlap() -> None:
    chunks = DocumentChunker(size=10, overlap=3).chunk([ExtractedSection("abcdefghijklmnop")])

    assert [chunk.content for chunk in chunks] == ["abcdefghij", "hijklmnop"]


def test_pdf_page_number_is_preserved_by_chunker() -> None:
    chunks = DocumentChunker(size=100, overlap=0).chunk(
        [ExtractedSection("page one", 1), ExtractedSection("page two", 2)]
    )

    assert chunks[0].page_number is None
    assert chunks[0].metadata_json == {"page_numbers": [1, 2]}


def test_invalid_chunk_configuration_fails(monkeypatch) -> None:
    monkeypatch.setenv("CHUNK_SIZE", "100")
    monkeypatch.setenv("CHUNK_OVERLAP", "100")
    get_settings.cache_clear()
    try:
        try:
            get_settings()
        except ValueError as exc:
            assert "CHUNK_OVERLAP" in str(exc)
        else:
            raise AssertionError("invalid settings were accepted")
    finally:
        get_settings.cache_clear()
