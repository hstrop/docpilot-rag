from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - package dependency in normal installs
    load_dotenv = None


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    mode: str = "demo"
    vector_backend: str = "memory"
    ai_backend: str = "deterministic"
    collection_name: str = "docpilot_chunks"
    chunk_size: int = 500
    chunk_overlap: int = 50
    top_k: int = 5
    similarity_threshold: float = 0.5
    embedding_dimension: int = 1536
    milvus_uri: str = "http://localhost:19530"
    milvus_token: str = ""
    dashscope_api_key: str = ""
    embedding_model: str = "text-embedding-v1"
    chat_model: str = "qwen-plus"
    allow_local_paths: bool = True
    max_upload_bytes: int = 20 * 1024 * 1024

    @classmethod
    def from_env(cls) -> Settings:
        if load_dotenv is not None:
            load_dotenv()
        env = os.environ
        settings = cls(
            mode=env.get("DOCPILOT_MODE", "demo"),
            vector_backend=env.get("DOCPILOT_VECTOR_BACKEND", "memory"),
            ai_backend=env.get("DOCPILOT_AI_BACKEND", "deterministic"),
            collection_name=env.get("DOCPILOT_COLLECTION_NAME", "docpilot_chunks"),
            chunk_size=int(env.get("DOCPILOT_CHUNK_SIZE", "500")),
            chunk_overlap=int(env.get("DOCPILOT_CHUNK_OVERLAP", "50")),
            top_k=int(env.get("DOCPILOT_TOP_K", "5")),
            similarity_threshold=float(env.get("DOCPILOT_SIMILARITY_THRESHOLD", "0.5")),
            embedding_dimension=int(env.get("DOCPILOT_EMBEDDING_DIMENSION", "1536")),
            milvus_uri=env.get("DOCPILOT_MILVUS_URI", "http://localhost:19530"),
            milvus_token=env.get("DOCPILOT_MILVUS_TOKEN", ""),
            dashscope_api_key=env.get("DOCPILOT_DASHSCOPE_API_KEY", ""),
            embedding_model=env.get("DOCPILOT_EMBEDDING_MODEL", "text-embedding-v1"),
            chat_model=env.get("DOCPILOT_CHAT_MODEL", "qwen-plus"),
            allow_local_paths=_as_bool(env.get("DOCPILOT_ALLOW_LOCAL_PATHS", "true")),
            max_upload_bytes=int(env.get("DOCPILOT_MAX_UPLOAD_BYTES", str(20 * 1024 * 1024))),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.mode not in {"demo", "production"}:
            raise ValueError("DOCPILOT_MODE must be demo or production")
        if self.vector_backend not in {"memory", "milvus"}:
            raise ValueError("DOCPILOT_VECTOR_BACKEND must be memory or milvus")
        if self.ai_backend not in {"deterministic", "dashscope"}:
            raise ValueError("DOCPILOT_AI_BACKEND must be deterministic or dashscope")
        if self.chunk_size <= 0 or not 0 <= self.chunk_overlap < self.chunk_size:
            raise ValueError("chunk_overlap must satisfy 0 <= overlap < chunk_size")
        if self.top_k <= 0:
            raise ValueError("top_k must be positive")
        if not 0 <= self.similarity_threshold <= 1:
            raise ValueError("similarity_threshold must be between 0 and 1")
        if self.embedding_dimension <= 0:
            raise ValueError("embedding_dimension must be positive")
        if self.ai_backend == "dashscope" and not self.dashscope_api_key:
            raise ValueError("DOCPILOT_DASHSCOPE_API_KEY is required for dashscope backend")
