from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class LoadedDocument:
    text: str
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Chunk:
    id: str
    document_id: str
    text: str
    source: str
    chunk_index: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SearchHit:
    chunk: Chunk
    score: float
    distance: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "chunk": self.chunk.as_dict(),
            "score": round(self.score, 6),
            "distance": round(self.distance, 6),
        }


@dataclass(slots=True)
class IndexResult:
    document_id: str
    source: str
    chunks_indexed: int


@dataclass(slots=True)
class QueryResult:
    answer: str
    sources: list[SearchHit]
    provider: str
