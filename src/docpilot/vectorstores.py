from __future__ import annotations

import json
import threading
from collections.abc import Sequence

from docpilot.domain import Chunk, SearchHit


def _squared_l2(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("vector dimensions do not match")
    return sum((a - b) ** 2 for a, b in zip(left, right))


def _distance_to_score(distance: float) -> float:
    """Map squared L2 distance between unit vectors to shifted cosine similarity."""
    return max(0.0, min(1.0, 1.0 - max(0.0, distance) / 4.0))


class InMemoryVectorStore:
    name = "memory"

    def __init__(self, dimension: int, collection_name: str = "docpilot_chunks") -> None:
        self.dimension = dimension
        self.collection_name = collection_name
        self._items: dict[str, tuple[Chunk, list[float]]] = {}
        self._lock = threading.RLock()

    def upsert(self, chunks: Sequence[Chunk], vectors: Sequence[Sequence[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        with self._lock:
            for chunk, vector in zip(chunks, vectors):
                if len(vector) != self.dimension:
                    raise ValueError("unexpected embedding dimension")
                self._items[chunk.id] = (chunk, list(vector))

    def search(
        self, vector: Sequence[float], top_k: int, similarity_threshold: float
    ) -> list[SearchHit]:
        with self._lock:
            ranked = []
            for chunk, candidate in self._items.values():
                distance = _squared_l2(vector, candidate)
                score = _distance_to_score(distance)
                if score >= similarity_threshold:
                    ranked.append(SearchHit(chunk, score, distance))
        return sorted(ranked, key=lambda hit: (hit.distance, hit.chunk.id))[:top_k]

    def delete_document(self, document_id: str) -> int:
        with self._lock:
            targets = [
                key for key, (chunk, _) in self._items.items() if chunk.document_id == document_id
            ]
            for key in targets:
                del self._items[key]
            return len(targets)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def info(self) -> dict[str, object]:
        with self._lock:
            count = len(self._items)
        return {
            "collection_name": self.collection_name,
            "entity_count": count,
            "backend": self.name,
            "metric_type": "L2",
            "dimension": self.dimension,
        }


class MilvusVectorStore:
    """Production Milvus adapter using an explicit schema and L2 index."""

    name = "milvus"

    def __init__(self, uri: str, token: str, collection_name: str, dimension: int) -> None:
        try:
            from pymilvus import DataType, MilvusClient
        except ImportError as exc:  # pragma: no cover - production adapter
            raise RuntimeError("install requirements-production.txt for Milvus") from exc
        self._DataType = DataType
        self.client = MilvusClient(uri=uri, token=token or None)
        self.collection_name = collection_name
        self.dimension = dimension
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        if self.client.has_collection(self.collection_name):
            return
        schema = self.client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("id", self._DataType.VARCHAR, is_primary=True, max_length=64)
        schema.add_field("document_id", self._DataType.VARCHAR, max_length=64)
        schema.add_field("text", self._DataType.VARCHAR, max_length=65535)
        schema.add_field("source", self._DataType.VARCHAR, max_length=1024)
        schema.add_field("chunk_index", self._DataType.INT64)
        schema.add_field("metadata", self._DataType.JSON)
        schema.add_field("embedding", self._DataType.FLOAT_VECTOR, dim=self.dimension)
        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="AUTOINDEX",
            metric_type="L2",
        )
        self.client.create_collection(
            collection_name=self.collection_name,
            schema=schema,
            index_params=index_params,
            consistency_level="Bounded",
        )

    def upsert(self, chunks: Sequence[Chunk], vectors: Sequence[Sequence[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        rows = []
        for chunk, vector in zip(chunks, vectors):
            rows.append(
                {
                    **chunk.as_dict(),
                    "metadata": chunk.metadata,
                    "embedding": list(vector),
                }
            )
        if rows:
            self.client.upsert(collection_name=self.collection_name, data=rows)

    def search(
        self, vector: Sequence[float], top_k: int, similarity_threshold: float
    ) -> list[SearchHit]:
        results = self.client.search(
            collection_name=self.collection_name,
            data=[list(vector)],
            anns_field="embedding",
            limit=top_k,
            output_fields=["document_id", "text", "source", "chunk_index", "metadata"],
            search_params={"metric_type": "L2", "params": {}},
        )
        hits: list[SearchHit] = []
        for item in results[0] if results else []:
            entity = item.get("entity", item)
            distance = float(item.get("distance", 0.0))
            score = _distance_to_score(distance)
            if score < similarity_threshold:
                continue
            metadata = entity.get("metadata", {})
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
            chunk = Chunk(
                id=str(item.get("id", entity.get("id"))),
                document_id=entity["document_id"],
                text=entity["text"],
                source=entity["source"],
                chunk_index=int(entity["chunk_index"]),
                metadata=metadata,
            )
            hits.append(SearchHit(chunk, score, distance))
        return hits

    def delete_document(self, document_id: str) -> int:
        safe_id = document_id.replace('"', '\\"')
        result = self.client.delete(
            collection_name=self.collection_name,
            filter=f'document_id == "{safe_id}"',
        )
        return int(result.get("delete_count", 0))

    def clear(self) -> None:
        if self.client.has_collection(self.collection_name):
            self.client.drop_collection(self.collection_name)
        self._ensure_collection()

    def info(self) -> dict[str, object]:
        stats = self.client.get_collection_stats(self.collection_name)
        return {
            "collection_name": self.collection_name,
            "entity_count": int(stats.get("row_count", 0)),
            "backend": self.name,
            "metric_type": "L2",
            "dimension": self.dimension,
        }
