from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from docpilot import __version__
from docpilot.dependencies import Container, build_container
from docpilot.loaders import UnsupportedDocumentError


class PathUploadRequest(BaseModel):
    path: str = Field(description="Local document path; disabled when local paths are not allowed")


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=50)
    similarity_threshold: float | None = Field(default=None, ge=0, le=1)


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=50)
    similarity_threshold: float | None = Field(default=None, ge=0, le=1)


class ClearRequest(BaseModel):
    confirm: bool = Field(
        default=False, description="Must be true because this clears the collection"
    )


DEMO_DOCUMENT = """# DocPilot 产品与研发手册

## 代码评审
研发团队每周三下午进行代码评审。提交评审前，开发者需要补充单元测试，并在合并请求中说明改动范围与验证方式。

## 入职学习
新员工入职第一个月需要完成信息安全、开发规范和产品基础三门课程。课程完成情况由直属导师在月底确认。

## 文档规范
内部技术文档应标注维护人和最后更新时间。涉及接口变更时，需要同步更新 API 示例和兼容性说明。

## 会议与协作
跨团队需求先在项目看板登记，明确负责人、优先级和验收标准，再进入开发排期。
"""


def _container(request: Request) -> Container:
    return request.app.state.container


def create_app(container: Container | None = None) -> FastAPI:
    app = FastAPI(
        title="DocPilot 本地知识库助手",
        version=__version__,
        description="PDF/TXT/DOCX/CSV indexing and retrieval API",
    )
    selected_container = container or build_container()
    app.state.container = selected_container
    # A fresh demo process should be useful immediately, even before the
    # browser bundle has made its first request. Custom containers used by
    # tests and production deployments are never mutated here.
    if container is None and selected_container.settings.mode == "demo":
        selected_container.service.index_bytes(
            DEMO_DOCUMENT.encode("utf-8"), "docpilot-demo-handbook.txt"
        )

    static_dir = Path(__file__).parent / "static"
    assets_dir = static_dir / "assets"
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/", include_in_schema=False)
    def frontend() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/meta", tags=["system"])
    def meta(request: Request) -> dict[str, object]:
        settings = _container(request).settings
        return {
            "name": "DocPilot",
            "description": "可解释的本地文档问答助手",
            "mode": settings.mode,
            "answer_provider": _container(request).service.answer_model.name,
            "features": ["文档上传", "中文切分", "相似度检索", "来源回传"],
        }

    @app.post("/demo/seed", tags=["system"])
    def seed_demo(request: Request) -> dict[str, object]:
        """写入一份可立即提问的本地示例文档；重复调用是幂等的。"""
        result = _container(request).service.index_bytes(
            DEMO_DOCUMENT.encode("utf-8"), "docpilot-demo-handbook.txt"
        )
        return {
            "seeded": True,
            "document_id": result.document_id,
            "source": result.source,
            "chunks_indexed": result.chunks_indexed,
        }

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.post("/upload_document", tags=["documents"])
    def upload_document(payload: PathUploadRequest, request: Request) -> dict[str, object]:
        current = _container(request)
        if not current.settings.allow_local_paths:
            raise HTTPException(status_code=403, detail="local path import is disabled")
        try:
            result = current.service.index_path(payload.path)
            return (
                result.__dict__
                if hasattr(result, "__dict__")
                else {
                    "document_id": result.document_id,
                    "source": result.source,
                    "chunks_indexed": result.chunks_indexed,
                }
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="document path was not found") from exc
        except (UnsupportedDocumentError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/upload_file", tags=["documents"])
    async def upload_file(
        request: Request,
        file: Annotated[UploadFile, File(description="PDF, TXT, DOCX or CSV")],
    ) -> dict[str, object]:
        current = _container(request)
        content = await file.read(current.settings.max_upload_bytes + 1)
        if len(content) > current.settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="uploaded file is too large")
        try:
            result = current.service.index_bytes(content, file.filename or "upload.txt")
        except UnsupportedDocumentError as exc:
            raise HTTPException(status_code=415, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "document_id": result.document_id,
            "source": result.source,
            "chunks_indexed": result.chunks_indexed,
        }

    @app.post("/search", tags=["retrieval"])
    def search(payload: SearchRequest, request: Request) -> dict[str, object]:
        try:
            hits = _container(request).service.search(
                payload.query,
                payload.top_k,
                payload.similarity_threshold,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"query": payload.query, "results": [hit.as_dict() for hit in hits]}

    @app.post("/query", tags=["retrieval"])
    def query(payload: QueryRequest, request: Request) -> dict[str, object]:
        try:
            result = _container(request).service.query(
                payload.question,
                payload.top_k,
                payload.similarity_threshold,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "question": payload.question,
            "answer": result.answer,
            "provider": result.provider,
            "sources": [hit.as_dict() for hit in result.sources],
        }

    @app.get("/collection_info", tags=["collection"])
    def collection_info(request: Request) -> dict[str, object]:
        return _container(request).service.info()

    @app.post("/clear_collection", tags=["collection"])
    def clear_collection(payload: ClearRequest, request: Request) -> dict[str, object]:
        if not payload.confirm:
            raise HTTPException(status_code=400, detail="set confirm=true to clear the collection")
        _container(request).service.clear()
        return {"cleared": True}

    return app


app = create_app()
