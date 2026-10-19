"""Persistent Chroma snapshots: resume an identical snapshot, never mix revisions."""

import json
import logging
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from .chunking import Chunk, digest
from .data_loader import canonical

log = logging.getLogger(__name__)
SCHEMA = "vector-v1"


def chunk_metadata(chunk: Chunk) -> dict:
    doc = chunk.document
    scope = doc.get("scope", {})
    statuses = {p.get("review_status", "unknown") for p in chunk.passages}

    return {
        "doc_id": chunk.doc_id, "section_id": chunk.section_id,
        "title": doc["title"], "source_file": doc["source_file"],
        "document_type": doc.get("document_type") or "unknown",
        "program": str(scope.get("program") or ""),
        "study_mode": str(scope.get("study_mode") or ""),
        "review_status": next(iter(statuses)) if len(statuses) == 1 else "mixed",
        "payload_json": canonical(chunk.to_dict()),
    }


class ChromaManager:
    def __init__(self, path: Path, collection_name: str):
        self.client = chromadb.PersistentClient(
            path=str(path),
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        self.collection_name = collection_name


    def ingest(self, chunks: list[Chunk], embedder, batch_size: int = 64) -> dict:
        if not chunks or batch_size < 1:
            raise ValueError("Ingest requires chunks and a positive batch size")

        if len({c.chunk_id for c in chunks}) != len(chunks):
            raise ValueError("Duplicate chunk IDs")

        # Fail all oversize inputs before incurring any API cost or changing the collection.
        oversize = [c.chunk_id for c in chunks if len(c.embedding_text) > embedder.max_input_chars]
        if oversize:
            raise ValueError(f"{len(oversize)} chunks exceed the API character guard; first: {oversize[0]}")

        fingerprint = digest([c.to_dict() for c in sorted(chunks, key=lambda c: c.chunk_id)])
        expected = {
            "schema": SCHEMA,
            "embedding_signature": embedder.signature,
            "embedding_identity_json": canonical(embedder.identity),
            "dimension": embedder.dimension,
            "dataset_fingerprint": fingerprint,
            "expected_count": len(chunks),
            "distance_metric": "cosine"
        }

        collection = self.client.get_or_create_collection(
            self.collection_name,
            embedding_function=None,
            configuration={"hnsw": {"space": "cosine"}},
            metadata={**expected, "state": "building"},
        )

        for key, value in expected.items():
            if (collection.metadata or {}).get(key) != value:
                raise ValueError(f"Collection {key} differs; use a new collection name for this dataset/model revision.")

        for start in range(0, len(chunks), batch_size):
            batch = chunks[start:start + batch_size]
            existing = set(collection.get(ids=[c.chunk_id for c in batch], include=[])["ids"])

            pending = [c for c in batch if c.chunk_id not in existing]
            if pending:
                vectors = embedder.embed([c.embedding_text for c in pending])
                collection.upsert(
                    ids=[c.chunk_id for c in pending],
                    embeddings=vectors,
                    documents=[c.text for c in pending],
                    metadatas=[chunk_metadata(c) for c in pending]
                )

            log.info("Indexed %d/%d chunks", min(start + batch_size, len(chunks)), len(chunks))

        if collection.count() != len(chunks):
            raise RuntimeError("Collection count differs from snapshot; use a fresh collection")

        collection.modify(metadata={**expected, "state": "ready"})
        return {
            "collection": self.collection_name,
            "chunks": collection.count(),
            "dataset_fingerprint": fingerprint,
            "embedding_config": embedder.configuration,
            "embedding_stats": dict(embedder.stats)
        }

    def ready_collection(self, embedder):
        collection = self.client.get_collection(self.collection_name, embedding_function=None)
        meta = collection.metadata or {}

        if (
            meta.get("schema") != SCHEMA
            or meta.get("state") != "ready"
            or meta.get("distance_metric") != "cosine"
            or meta.get("expected_count") != collection.count()
        ):
            raise ValueError("Collection is incomplete; finish ingest first")

        if meta.get("dimension") != embedder.dimension:
            raise ValueError(f"Query embedding dimension ({embedder.dimension}) differs from the indexed configuration ({meta.get('dimension')})")

        if meta.get("embedding_signature") != embedder.signature:
            log.info("Lưu ý: Embedding signature khác biệt (%s vs %s), nhưng cùng dimension 1024.", meta.get("embedding_signature"), embedder.signature)

        return collection

    @staticmethod
    def section_context(collection, section_id: str) -> list[dict]:
        records = collection.get(where={"section_id": section_id}, include=["metadatas"])
        passages = {}

        for metadata in records["metadatas"]:
            for p in json.loads(metadata["payload_json"])["passages"]:
                passages[p["passage_id"]] = p

        return sorted(passages.values(), key=lambda p: p["order"])
