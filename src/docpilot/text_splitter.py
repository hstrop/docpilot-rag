from __future__ import annotations


class RecursiveTextSplitter:
    """Small dependency-free equivalent for the project's recursive chunking policy."""

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        separators: tuple[str, ...] = ("\n\n", "\n", "。", "！", "？", ";", "；", "，", " "),
    ) -> None:
        if chunk_size <= 0 or not 0 <= chunk_overlap < chunk_size:
            raise ValueError("chunk_overlap must satisfy 0 <= overlap < chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators

    def split_text(self, text: str) -> list[str]:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            return []

        chunks: list[str] = []
        start = 0
        text_length = len(normalized)
        while start < text_length:
            hard_end = min(start + self.chunk_size, text_length)
            end = hard_end
            if hard_end < text_length:
                lower_bound = start + max(1, self.chunk_size // 2)
                candidates: list[int] = []
                for separator in self.separators:
                    position = normalized.rfind(separator, lower_bound, hard_end)
                    if position >= 0:
                        candidates.append(position + len(separator))
                if candidates:
                    end = max(candidates)

            piece = normalized[start:end].strip()
            if piece:
                chunks.append(piece)
            if end >= text_length:
                break
            start = max(start + 1, end - self.chunk_overlap)
        return chunks
