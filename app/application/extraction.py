from dataclasses import dataclass
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader


@dataclass(frozen=True)
class ExtractedSection:
    text: str
    page_number: int | None = None


class ExtractionError(Exception):
    """A safe boundary for malformed or unreadable document content."""


class TextExtractor:
    def extract(self, path: Path, mime_type: str) -> list[ExtractedSection]:
        try:
            if mime_type == "text/plain":
                return [ExtractedSection(path.read_text(encoding="utf-8"))]
            if mime_type == "application/pdf":
                reader = PdfReader(path)
                return [
                    ExtractedSection(page.extract_text() or "", index)
                    for index, page in enumerate(reader.pages, start=1)
                ]
            if mime_type == (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ):
                document = DocxDocument(path)
                return [ExtractedSection(paragraph.text) for paragraph in document.paragraphs]
        except (OSError, UnicodeError, ValueError, KeyError, EOFError) as exc:
            raise ExtractionError("document_extraction_failed") from exc
        except Exception as exc:
            # Third-party parsers expose several format-specific exception types.
            raise ExtractionError("document_extraction_failed") from exc
        raise ExtractionError("unsupported_document_type")
