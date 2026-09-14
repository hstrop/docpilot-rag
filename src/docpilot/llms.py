from __future__ import annotations

import re
from collections.abc import Sequence

from docpilot.domain import SearchHit


class DeterministicAnswerModel:
    """Transparent offline renderer used for repeatable demos, not an LLM."""

    name = "deterministic-demo"

    def answer(self, question: str, hits: Sequence[SearchHit]) -> str:
        if not hits:
            return "我暂时没有找到足够相关的文档依据。可以换一种关键词，或先上传相关资料。"

        # The offline backend intentionally stays deterministic, but it still
        # behaves like an assistant: pick the most query-relevant sentences
        # instead of dumping the complete chunk into the chat bubble.
        terms = [term for term in re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_-]+", question.casefold())]
        candidates: list[tuple[int, int, str]] = []
        for hit_index, hit in enumerate(hits):
            sentences = [
                part.strip(" \t\r\n。；;.!！")
                for part in re.split(r"[。；;.!！?？\n]", hit.chunk.text)
                if part.strip() and not part.strip().startswith("#")
            ]
            for sentence_index, sentence in enumerate(sentences):
                score = sum(1 for term in terms if term and term in sentence.casefold())
                candidates.append((score, -hit_index * 10 - sentence_index, sentence))
        selected = [item[2] for item in sorted(candidates, reverse=True)[:3]]
        if not selected:
            selected = [" ".join(hits[0].chunk.text.split())[:220]]
        lines = [f"根据已索引资料，关于“{question}”我找到："]
        lines.extend(f"- {sentence[:220]}" for sentence in selected)
        lines.append("这是离线演示回答，结论来自本地文档检索；下方来源卡片可展开核对原文。")
        return "\n".join(lines)


class DashScopeAnswerModel:
    name = "dashscope-qwen"

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def answer(self, question: str, hits: Sequence[SearchHit]) -> str:
        if not hits:
            return "当前知识库中没有达到相似度阈值的资料，暂时无法基于文档回答。"
        try:
            import dashscope
        except ImportError as exc:  # pragma: no cover - production adapter
            raise RuntimeError("install requirements-production.txt for DashScope") from exc
        context = "\n\n".join(
            f"[{number}] 来源：{hit.chunk.source}\n{hit.chunk.text}"
            for number, hit in enumerate(hits, start=1)
        )
        prompt = (
            "你是本地知识库助手。只能根据给定资料回答；资料不足时明确说明。"
            "引用事实时在句末写来源编号，例如 [1]，不得编造来源。\n\n"
            f"资料：\n{context}\n\n问题：{question}"
        )
        response = dashscope.Generation.call(
            model=self.model,
            api_key=self.api_key,
            messages=[{"role": "user", "content": prompt}],
            result_format="message",
        )
        if getattr(response, "status_code", 500) != 200:
            raise RuntimeError(f"DashScope generation request failed: {response.code}")
        return response.output["choices"][0]["message"]["content"]
