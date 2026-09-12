from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence


def _unit_normalize(vector: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(float(value) * float(value) for value in vector))
    if not norm:
        return [0.0 for _ in vector]
    return [float(value) / norm for value in vector]


class DeterministicEmbedding:
    """Offline hashing embedder for tests and demos; it is not a trained model."""

    name = "deterministic-hash-demo"

    def __init__(self, dimension: int = 1536) -> None:
        self.dimension = dimension

    @staticmethod
    def _tokens(text: str) -> list[str]:
        lowered = text.lower()
        words = re.findall(r"[a-z0-9_]+", lowered)
        chinese = re.findall(r"[\u4e00-\u9fff]", lowered)
        chinese_bigrams = ["".join(chinese[index : index + 2]) for index in range(len(chinese) - 1)]
        return words + chinese + chinese_bigrams

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in self._tokens(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign
        return _unit_normalize(vector)

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class DashScopeEmbedding:
    name = "dashscope"

    def __init__(self, api_key: str, model: str, dimension: int = 1536) -> None:
        self.api_key = api_key
        self.model = model
        self.dimension = dimension

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        try:
            import dashscope
        except ImportError as exc:  # pragma: no cover - production adapter
            raise RuntimeError("install requirements-production.txt for DashScope") from exc
        vectors: list[list[float]] = []
        for start in range(0, len(texts), 10):
            response = dashscope.TextEmbedding.call(
                model=self.model,
                input=list(texts[start : start + 10]),
                api_key=self.api_key,
            )
            if getattr(response, "status_code", 500) != 200:
                raise RuntimeError(f"DashScope embedding request failed: {response.code}")
            items = sorted(response.output["embeddings"], key=lambda item: item["text_index"])
            vectors.extend(_unit_normalize(item["embedding"]) for item in items)
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]
