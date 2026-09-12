from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from docpilot.domain import Chunk, SearchHit


class EmbeddingProvider(Protocol):
    dimension: int
    name: str

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class VectorStore(Protocol):
    name: str

    def upsert(self, chunks: Sequence[Chunk], vectors: Sequence[Sequence[float]]) -> None: ...

    def search(
        self, vector: Sequence[float], top_k: int, similarity_threshold: float
    ) -> list[SearchHit]: ...

    def delete_document(self, document_id: str) -> int: ...

    def clear(self) -> None: ...

    def info(self) -> dict[str, object]: ...


class AnswerModel(Protocol):
    name: str

    def answer(self, question: str, hits: Sequence[SearchHit]) -> str: ...
