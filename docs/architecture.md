# 架构说明

DocPilot 只有两条核心流水线，并通过端口/适配器隔离外部依赖。

```text
索引：PDF/TXT/DOCX/CSV -> DocumentLoader -> RecursiveTextSplitter
      -> EmbeddingProvider -> VectorStore

检索：Question -> EmbeddingProvider -> L2 Top-K Search
      -> Similarity Filter -> AnswerModel -> Answer + Sources
```

## 模块职责

| 模块 | 职责 |
| --- | --- |
| `loaders.py` | 将四类文件转换为带来源、页码或行号的文本单元 |
| `text_splitter.py` | 默认按 500 字、50 字重叠递归寻找中文标点边界 |
| `embeddings.py` | 可替换的离线哈希演示实现与 DashScope Embedding 适配器 |
| `vectorstores.py` | 线程安全内存实现与 Milvus L2 索引适配器 |
| `service.py` | 文档幂等入库、检索、问答和清理用例 |
| `langchain_compat.py` | Embeddings 接口、Document 转换和 `invoke` 检索兼容层 |
| `api.py` / `cli.py` | HTTP 与命令行入口 |

## 分数约定

Milvus 的 L2 距离越小越接近。DocPilot 在入库和查询前对向量做单位归一化；Milvus 返回平方 L2
距离后，服务用 `similarity = clamp(1 - distance / 4, 0, 1)` 转成 0 到 1 的分数。这个公式等价于
把余弦相似度从 `[-1, 1]` 平移到 `[0, 1]`。接口同时返回原始 `distance` 和转换后的 `score`，
便于调试阈值；内存后端使用相同公式，保证本地测试与生产接口语义一致。

## 演示与生产边界

- `deterministic + memory`：无网络、无密钥，可验证解析、切分、入库、检索、引用和 API 合约；哈希向量不是语义模型，固定模板也不是 LLM。
- `dashscope + milvus`：调用 `text-embedding-v1` 和 `qwen-plus`，向 Milvus 持久化 1536 维向量。需要外部服务与密钥，因此不纳入离线 CI。
