"""Usage: python -m src.vector_module --help"""

import argparse
import json
import logging
import sys
from dataclasses import replace
from pathlib import Path

from src.config.settings import VectorModuleSettings

from .chunking import build_chunks, load_chunks, save_chunks
from .data_loader import load_corpus


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
            allow_nan=False
        ) + "\n",
        encoding="utf-8"
    )
    temporary.replace(path)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Vector module: validate, chunk, embed, index and search")
    root.add_argument("--env-file", type=Path, help="Defaults to repository .env")

    commands = root.add_subparsers(dest="command", required=True)
    for name in ("validate", "chunk"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--processed", type=Path)
        cmd.add_argument("--raw", type=Path)
        cmd.add_argument("--report", type=Path)

        if name == "chunk":
            scope = cmd.add_mutually_exclusive_group(required=True)
            scope.add_argument("--all-documents", action="store_true", help="Explicitly include the whole draft corpus")
            scope.add_argument("--doc-id", action="append", help="Repeat to select documents")
            cmd.add_argument("--target-words", type=int)
            cmd.add_argument("--output", type=Path)

    cmd = commands.add_parser("ingest")
    cmd.add_argument("--chunks", type=Path)
    cmd.add_argument("--collection")
    cmd.add_argument("--report", type=Path)

    cmd = commands.add_parser("search")
    cmd.add_argument("question")
    cmd.add_argument("--top-k", type=int, default=5)
    cmd.add_argument("--collection")

    filters = cmd.add_mutually_exclusive_group()
    filters.add_argument("--doc-id", help="Filter by document ID without shell JSON escaping")
    filters.add_argument("--where", help="Chroma JSON filter; use --where-file in Windows PowerShell")
    filters.add_argument("--where-file", type=Path, help="UTF-8 JSON file containing a Chroma filter")

    cmd.add_argument("--no-expand-section", action="store_true")
    cmd.add_argument("--output", type=Path)

    cmd = commands.add_parser("evaluate")
    cmd.add_argument("dataset", type=Path, help="JSONL questions with expected_passage_ids")
    cmd.add_argument("--top-k", type=int, default=5)
    cmd.add_argument("--collection")
    cmd.add_argument("--output", type=Path)

    return root


def run(args) -> int:
    settings = VectorModuleSettings.from_env(args.env_file)

    if args.command in ("validate", "chunk"):
        corpus = load_corpus(args.processed or settings.processed_path, args.raw or settings.raw_path)
        report = corpus.report()
        report_path = args.report or settings.output_path / "validation_report.json"

        write_json(report_path, report)

        summary = {k: v for k, v in report.items() if k != "issues"}
        summary["report"] = str(report_path)

        if args.command == "chunk" and not report["errors"]:
            chunks = build_chunks(
                corpus,
                args.target_words if args.target_words is not None else settings.target_words,
                set(args.doc_id) if args.doc_id else None
            )
            output = args.output or settings.output_path / "chunks.jsonl"
            save_chunks(chunks, output)
            summary.update(
                chunks=len(chunks),
                chunk_file=str(output),
                selected_documents=len({c.doc_id for c in chunks}),
                oversized_passages=sum("oversize_atomic_passage" in c.warnings for c in chunks)
            )

        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 1 if report["errors"] else 0

    # Offline validation/chunking have no Chroma or HTTP dependency.
    from .chroma_manager import ChromaManager
    from .embeddings import BgeM3API
    from .vector_retriever import VectorRetriever

    if args.collection:
        settings = replace(settings, collection_name=args.collection)

    with BgeM3API.from_settings(settings) as embedder:
        manager = ChromaManager(settings.chroma_path, settings.collection_name)

        if args.command == "ingest":
            chunks = load_chunks(args.chunks or settings.output_path / "chunks.jsonl")
            report_path = args.report or settings.output_path / f"{settings.collection_name}_ingest.json"

            try:
                result = manager.ingest(chunks, embedder)
            except Exception as exc:
                write_json(report_path, {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "embedding_stats": embedder.stats
                })
                raise

            write_json(report_path, {"status": "ready", **result})

        elif args.command == "search":
            if args.doc_id:
                where = {"doc_id": args.doc_id}

            elif args.where_file:
                where = json.loads(args.where_file.read_text(encoding="utf-8-sig"))

            else:
                where = json.loads(args.where) if args.where else None

            if where is not None and not isinstance(where, dict):
                raise ValueError("--where must be a JSON object")

            result = VectorRetriever(manager, embedder).search(
                args.question, args.top_k, where, not args.no_expand_section)

            if args.output:
                write_json(args.output, result)
        else:
            from src.evaluation.evaluate_retrieval import (
                evaluate_retrieval,
                load_questions,
            )

            result = evaluate_retrieval(VectorRetriever(manager, embedder), load_questions(args.dataset), args.top_k)
            result["embedding_stats"] = dict(embedder.stats)
            result["collection"] = settings.collection_name

            write_json(args.output or settings.output_path / "retrieval_evaluation.json", result)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    args = parser().parse_args()

    try:
        return run(args)
    except Exception as exc:
        # No traceback / HTTP response body / API key in normal CLI output.
        print(f"Error ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
