from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
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


def _container(request: Request) -> Container:
    return request.app.state.container


def create_app(container: Container | None = None) -> FastAPI:
    app = FastAPI(
        title="DocPilot 本地知识库助手",
        version=__version__,
        description="PDF/TXT/DOCX/CSV indexing and retrieval API",
    )
    app.state.container = container or build_container()

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
