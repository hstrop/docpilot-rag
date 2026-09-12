from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path

from docpilot.domain import Chunk, IndexResult, LoadedDocument, QueryResult, SearchHit
from docpilot.loaders import DocumentLoader
from docpilot.ports import AnswerModel, EmbeddingProvider, VectorStore
from docpilot.text_splitter import RecursiveTextSplitter


class KnowledgeBaseService:
    def __init__(
        self,
        loader: DocumentLoader,
        splitter: RecursiveTextSplitter,
        embedder: EmbeddingProvider,
        vector_store: VectorStore,
        answer_model: AnswerModel,
        default_top_k: int = 5,
        default_threshold: float = 0.5,
    ) -> None:
        self.loader = loader
        self.splitter = splitter
        self.embedder = embedder
        self.vector_store = vector_store
        self.answer_model = answer_model
        self.default_top_k = default_top_k
        self.default_threshold = default_threshold

    def index_path(self, path: str | Path) -> IndexResult:
        documents = self.loader.load_path(path)
        raw = Path(path).expanduser().resolve().read_bytes()
        return self._index(documents, raw)

    def index_bytes(self, content: bytes, filename: str) -> IndexResult:
        return self._index(self.loader.load_bytes(content, filename), content)

    def _index(self, documents: Sequence[LoadedDocument], raw_content: bytes) -> IndexResult:
        if not documents or not any(document.text.strip() for document in documents):
            raise ValueError("document contains no extractable text")
        document_id = hashlib.sha256(raw_content).hexdigest()[:32]
        source = documents[0].source
        chunks: list[Chunk] = []
        chunk_index = 0
        for document in documents:
            for text in self.splitter.split_text(document.text):
                chunk_id = hashlib.sha256(
                    f"{document_id}:{chunk_index}:{text}".encode()
                ).hexdigest()[:32]
                chunks.append(
                    Chunk(
                        id=chunk_id,
                        document_id=document_id,
                        text=text,
                        source=document.source,
                        chunk_index=chunk_index,
                        metadata=dict(document.metadata),
                    )
                )
                chunk_index += 1
        if not chunks:
            raise ValueError("document contains no extractable text")
        vectors = self.embedder.embed_documents([chunk.text for chunk in chunks])
        self.vector_store.delete_document(document_id)
        self.vector_store.upsert(chunks, vectors)
        return IndexResult(document_id=document_id, source=source, chunks_indexed=len(chunks))

    def search(
        self,
        query: str,
        top_k: int | None = None,
        similarity_threshold: float | None = None,
    ) -> list[SearchHit]:
        if not query.strip():
            raise ValueError("query cannot be empty")
        resolved_top_k = self.default_top_k if top_k is None else top_k
        resolved_threshold = (
            self.default_threshold if similarity_threshold is None else similarity_threshold
        )
        if resolved_top_k <= 0 or resolved_top_k > 50:
            raise ValueError("top_k must be between 1 and 50")
        if not 0 <= resolved_threshold <= 1:
            raise ValueError("similarity_threshold must be between 0 and 1")
        vector = self.embedder.embed_query(query)
        return self.vector_store.search(vector, resolved_top_k, resolved_threshold)

    def query(
        self,
        question: str,
        top_k: int | None = None,
        similarity_threshold: float | None = None,
    ) -> QueryResult:
        hits = self.search(question, top_k, similarity_threshold)
        return QueryResult(
            answer=self.answer_model.answer(question, hits),
            sources=hits,
            provider=self.answer_model.name,
        )

    def clear(self) -> None:
        self.vector_store.clear()

    def info(self) -> dict[str, object]:
        return {
            **self.vector_store.info(),
            "embedding_provider": self.embedder.name,
            "answer_provider": self.answer_model.name,
            "default_top_k": self.default_top_k,
            "default_similarity_threshold": self.default_threshold,
        }
