from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from docpilot.domain import Chunk
from docpilot.ports import EmbeddingProvider
from docpilot.service import KnowledgeBaseService

try:  # Optional integration: core app does not require LangChain at runtime.
    from langchain_core.documents import Document as LangChainDocument
    from langchain_core.embeddings import Embeddings as LangChainEmbeddings
except ImportError:  # pragma: no cover - exercised when optional extra is absent

    @dataclass
    class LangChainDocument:  # type: ignore[no-redef]
        page_content: str
        metadata: dict[str, Any]

    class LangChainEmbeddings:  # type: ignore[no-redef]
        pass


class EmbeddingsAdapter(LangChainEmbeddings):
    """Expose a DocPilot embedding provider through LangChain's Embeddings interface."""

    def __init__(self, provider: EmbeddingProvider) -> None:
        self.provider = provider

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.provider.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self.provider.embed_query(text)


def chunks_to_documents(chunks: Sequence[Chunk]) -> list[LangChainDocument]:
    return [
        LangChainDocument(
            page_content=chunk.text,
            metadata={
                **chunk.metadata,
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "source": chunk.source,
                "chunk_index": chunk.chunk_index,
            },
        )
        for chunk in chunks
    ]


class RetrieverAdapter:
    """Minimal invoke-compatible retriever for LCEL/tool integration."""

    def __init__(
        self,
        service: KnowledgeBaseService,
        top_k: int | None = None,
        similarity_threshold: float | None = None,
    ) -> None:
        self.service = service
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold

    def invoke(self, query: str, config: dict[str, Any] | None = None) -> list[LangChainDocument]:
        del config
        hits = self.service.search(query, self.top_k, self.similarity_threshold)
        documents = chunks_to_documents([hit.chunk for hit in hits])
        for document, hit in zip(documents, hits):
            document.metadata["score"] = hit.score
            document.metadata["distance"] = hit.distance
        return documents
