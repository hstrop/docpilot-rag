from __future__ import annotations

from fastapi.testclient import TestClient

from docpilot.api import create_app
from docpilot.config import Settings
from docpilot.dependencies import build_container


def client() -> TestClient:
    return TestClient(create_app(build_container()))


def test_six_api_capabilities() -> None:
    api = client()
    assert api.get("/").status_code == 200
    assert api.get("/meta").json()["name"] == "DocPilot"
    demo = api.post("/demo/seed")
    assert demo.status_code == 200
    assert demo.json()["chunks_indexed"] >= 1
    upload = api.post(
        "/upload_file",
        files={"file": ("manual.txt", "RAG 通过检索资料辅助回答。".encode(), "text/plain")},
    )
    assert upload.status_code == 200
    assert upload.json()["chunks_indexed"] == 1

    search = api.post(
        "/search",
        json={"query": "RAG 检索", "similarity_threshold": 0, "top_k": 5},
    )
    assert search.status_code == 200
    assert search.json()["results"]

    query = api.post(
        "/query",
        json={"question": "RAG 是什么？", "similarity_threshold": 0},
    )
    assert query.status_code == 200
    assert query.json()["provider"] == "deterministic-demo"
    assert query.json()["sources"]

    info = api.get("/collection_info")
    assert info.status_code == 200
    assert info.json()["metric_type"] == "L2"

    rejected = api.post("/clear_collection", json={"confirm": False})
    assert rejected.status_code == 400
    cleared = api.post("/clear_collection", json={"confirm": True})
    assert cleared.json() == {"cleared": True}


def test_local_path_upload_and_input_errors(tmp_path) -> None:
    path = tmp_path / "local.txt"
    path.write_text("本地文档导入", encoding="utf-8")
    api = client()
    response = api.post("/upload_document", json={"path": str(path)})
    assert response.status_code == 200
    assert response.json()["source"] == "local.txt"
    unsupported = api.post(
        "/upload_file",
        files={"file": ("payload.exe", b"MZ", "application/octet-stream")},
    )
    assert unsupported.status_code == 415


def test_local_path_import_can_be_disabled(tmp_path) -> None:
    path = tmp_path / "local.txt"
    path.write_text("不会读取的内容", encoding="utf-8")
    settings = Settings(allow_local_paths=False)
    api = TestClient(create_app(build_container(settings)))
    response = api.post("/upload_document", json={"path": str(path)})
    assert response.status_code == 403
