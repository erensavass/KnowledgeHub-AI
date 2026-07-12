from dataclasses import dataclass


@dataclass(frozen=True)
class HistoryMessage:
    role: str
    content: str
