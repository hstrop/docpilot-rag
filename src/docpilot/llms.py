from __future__ import annotations

from collections.abc import Sequence

from docpilot.domain import SearchHit


class DeterministicAnswerModel:
    """Transparent offline renderer used for repeatable demos, not an LLM."""

    name = "deterministic-demo"

    def answer(self, question: str, hits: Sequence[SearchHit]) -> str:
        if not hits:
            return "当前知识库中没有达到相似度阈值的资料，暂时无法基于文档回答。"
        lines = [f"针对“{question}”，检索到以下资料："]
        for number, hit in enumerate(hits, start=1):
            summary = " ".join(hit.chunk.text.split())[:220]
            lines.append(f"[{number}] {summary}")
        lines.append(
            "以上为离线演示后端返回的检索片段；启用 DashScope 后由 Qwen 基于同一证据生成回答。"
        )
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
