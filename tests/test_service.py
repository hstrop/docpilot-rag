from __future__ import annotations

from docpilot.dependencies import build_container
from docpilot.langchain_compat import EmbeddingsAdapter, RetrieverAdapter


def test_index_search_query_and_clear() -> None:
    service = build_container().service
    first = service.index_bytes("Milvus 用于向量检索。FastAPI 提供接口。".encode(), "guide.txt")
    second = service.index_bytes("Milvus 用于向量检索。FastAPI 提供接口。".encode(), "guide.txt")
    assert first.document_id == second.document_id
    assert service.info()["entity_count"] == first.chunks_indexed

    hits = service.search("Milvus 向量检索", similarity_threshold=0)
    assert hits
    assert hits[0].chunk.source == "guide.txt"
    result = service.query("Milvus 有什么作用？", similarity_threshold=0)
    assert result.sources
    assert result.provider == "deterministic-demo"
    assert "离线演示" in result.answer

    service.clear()
    assert service.info()["entity_count"] == 0


def test_langchain_compatible_adapters() -> None:
    service = build_container().service
    service.index_bytes("知识库支持可追溯回答。".encode(), "kb.txt")
    embedding = EmbeddingsAdapter(service.embedder)
    assert len(embedding.embed_query("知识库")) == service.embedder.dimension
    documents = RetrieverAdapter(service, similarity_threshold=0).invoke("可追溯")
    assert documents[0].metadata["source"] == "kb.txt"
    assert "score" in documents[0].metadata
