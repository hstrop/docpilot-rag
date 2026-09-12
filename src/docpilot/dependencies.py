from __future__ import annotations

from dataclasses import dataclass

from docpilot.config import Settings
from docpilot.embeddings import DashScopeEmbedding, DeterministicEmbedding
from docpilot.llms import DashScopeAnswerModel, DeterministicAnswerModel
from docpilot.loaders import DocumentLoader
from docpilot.service import KnowledgeBaseService
from docpilot.text_splitter import RecursiveTextSplitter
from docpilot.vectorstores import InMemoryVectorStore, MilvusVectorStore


@dataclass(slots=True)
class Container:
    settings: Settings
    service: KnowledgeBaseService


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or Settings.from_env()
    settings.validate()
    if settings.ai_backend == "dashscope":
        embedder = DashScopeEmbedding(
            settings.dashscope_api_key,
            settings.embedding_model,
            settings.embedding_dimension,
        )
        answer_model = DashScopeAnswerModel(settings.dashscope_api_key, settings.chat_model)
    else:
        embedder = DeterministicEmbedding(settings.embedding_dimension)
        answer_model = DeterministicAnswerModel()

    if settings.vector_backend == "milvus":
        vector_store = MilvusVectorStore(
            settings.milvus_uri,
            settings.milvus_token,
            settings.collection_name,
            settings.embedding_dimension,
        )
    else:
        vector_store = InMemoryVectorStore(
            settings.embedding_dimension,
            settings.collection_name,
        )

    service = KnowledgeBaseService(
        loader=DocumentLoader(),
        splitter=RecursiveTextSplitter(settings.chunk_size, settings.chunk_overlap),
        embedder=embedder,
        vector_store=vector_store,
        answer_model=answer_model,
        default_top_k=settings.top_k,
        default_threshold=settings.similarity_threshold,
    )
    return Container(settings, service)
