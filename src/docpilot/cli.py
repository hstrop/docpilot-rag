from __future__ import annotations

import argparse
import json

from docpilot.dependencies import build_container


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="docpilot", description="DocPilot local RAG assistant")
    subparsers = parser.add_subparsers(dest="command", required=True)

    index = subparsers.add_parser("index", help="index a local PDF/TXT/DOCX/CSV file")
    index.add_argument("path")

    for name in ("search", "query"):
        command = subparsers.add_parser(name)
        command.add_argument("text")
        command.add_argument("--top-k", type=int)
        command.add_argument("--threshold", type=float)

    demo = subparsers.add_parser(
        "demo", help="index one document and ask one question in the same process"
    )
    demo.add_argument("path")
    demo.add_argument("question")
    demo.add_argument("--top-k", type=int)
    demo.add_argument("--threshold", type=float)

    subparsers.add_parser("info")
    clear = subparsers.add_parser("clear")
    clear.add_argument("--yes", action="store_true")
    return parser


def main() -> None:
    args = _parser().parse_args()
    service = build_container().service
    if args.command == "index":
        result = service.index_path(args.path)
        payload = {
            "document_id": result.document_id,
            "source": result.source,
            "chunks_indexed": result.chunks_indexed,
        }
    elif args.command == "search":
        payload = {
            "results": [
                hit.as_dict() for hit in service.search(args.text, args.top_k, args.threshold)
            ]
        }
    elif args.command == "query":
        result = service.query(args.text, args.top_k, args.threshold)
        payload = {
            "answer": result.answer,
            "provider": result.provider,
            "sources": [hit.as_dict() for hit in result.sources],
        }
    elif args.command == "demo":
        indexed = service.index_path(args.path)
        result = service.query(args.question, args.top_k, args.threshold)
        payload = {
            "indexed": {
                "document_id": indexed.document_id,
                "source": indexed.source,
                "chunks_indexed": indexed.chunks_indexed,
            },
            "answer": result.answer,
            "provider": result.provider,
            "sources": [hit.as_dict() for hit in result.sources],
        }
    elif args.command == "info":
        payload = service.info()
    else:
        if not args.yes:
            raise SystemExit("clear requires --yes")
        service.clear()
        payload = {"cleared": True}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
