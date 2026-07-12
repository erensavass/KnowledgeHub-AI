import re
from dataclasses import dataclass

from app.application.extraction import ExtractedSection


class TokenCounter:
    """Stable tokenizer abstraction using Unicode word/punctuation tokens."""

    _tokens = re.compile(r"\w+|[^\w\s]", re.UNICODE)

    def count(self, text: str) -> int:
        return len(self._tokens.findall(text))


@dataclass(frozen=True)
class GeneratedChunk:
    content: str
    character_count: int
    token_count: int
    page_number: int | None
    metadata_json: dict | None = None


@dataclass(frozen=True)
class _Paragraph:
    text: str
    page_number: int | None


class DocumentChunker:
    def __init__(self, size: int, overlap: int, token_counter: TokenCounter | None = None) -> None:
        if size <= 0 or overlap < 0 or overlap >= size:
            raise ValueError("chunk size and overlap are invalid")
        self.size = size
        self.overlap = overlap
        self.token_counter = token_counter or TokenCounter()

    def chunk(self, sections: list[ExtractedSection]) -> list[GeneratedChunk]:
        paragraphs: list[_Paragraph] = []
        for section in sections:
            normalized = re.sub(r"[\t\f\v ]+", " ", section.text.replace("\r\n", "\n"))
            for value in re.split(r"\n\s*\n|\n", normalized):
                value = value.strip()
                if value:
                    paragraphs.append(_Paragraph(value, section.page_number))

        units: list[_Paragraph] = []
        for paragraph in paragraphs:
            if len(paragraph.text) <= self.size:
                units.append(paragraph)
                continue
            step = self.size - self.overlap
            for start in range(0, len(paragraph.text), step):
                part = paragraph.text[start : start + self.size].strip()
                if part:
                    units.append(_Paragraph(part, paragraph.page_number))
                if start + self.size >= len(paragraph.text):
                    break

        groups: list[list[_Paragraph]] = []
        current: list[_Paragraph] = []
        for unit in units:
            candidate = "\n\n".join(item.text for item in [*current, unit])
            if current and len(candidate) > self.size:
                groups.append(current)
                current = self._paragraph_overlap(current)
                while (
                    current
                    and len("\n\n".join(item.text for item in [*current, unit])) > self.size
                ):
                    current.pop(0)
            current.append(unit)
        if current:
            groups.append(current)

        result: list[GeneratedChunk] = []
        for group in groups:
            content = "\n\n".join(item.text for item in group).strip()
            pages = {item.page_number for item in group if item.page_number is not None}
            page_number = next(iter(pages)) if len(pages) == 1 else None
            metadata = {"page_numbers": sorted(pages)} if len(pages) > 1 else None
            result.append(
                GeneratedChunk(
                    content, len(content), self.token_counter.count(content), page_number, metadata
                )
            )
        return result

    def _paragraph_overlap(self, group: list[_Paragraph]) -> list[_Paragraph]:
        selected: list[_Paragraph] = []
        length = 0
        for paragraph in reversed(group):
            added = len(paragraph.text) + (2 if selected else 0)
            if length + added > self.overlap:
                break
            selected.insert(0, paragraph)
            length += added
        return selected
