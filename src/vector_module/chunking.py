"""Conservative structural chunking. TV3 passages are never truncated or repaired."""

import hashlib
import json
from dataclasses import asdict, dataclass
from itertools import groupby
from pathlib import Path

from .data_loader import Corpus, canonical

CHUNKER_VERSION = "structural-v1"


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    section_id: str
    text: str
    embedding_text: str
    document: dict
    passages: list[dict]
    warnings: list[str]
    chunker_version: str = CHUNKER_VERSION

    def to_dict(self) -> dict:
        return asdict(self)


def build_chunks(
    corpus: Corpus,
    target_words: int = 500,
    doc_ids: set[str] | None = None
) -> list[Chunk]:

    if target_words < 1:
        raise ValueError("target_words must be positive")

    if corpus.report()["errors"]:
        raise ValueError("Corpus has structural errors; inspect the validation report before chunking.")

    if doc_ids is not None and doc_ids - corpus.documents.keys():
        raise ValueError(f"Unknown doc_ids: {sorted(doc_ids - corpus.documents.keys())}")

    issues: dict[str, set[str]] = {}
    for issue in corpus.issues:
        issues.setdefault(issue["record"], set()).add(issue["code"])

    chunks = []
    for did in sorted(corpus.documents):
        if doc_ids is not None and did not in doc_ids:
            continue

        doc = corpus.documents[did]
        # groupby preserves separate occurrences of a heading rather than merging distant sections.
        for section, iterator in groupby(corpus.passages[did], key=lambda p: p["section_path"]):
            group = list(iterator)
            section_id = digest([did, section, group[0]["passage_id"]])
            batches: list[list[dict]] = []
            current: list[dict] = []
            size = 0

            for p in group:
                words = len(p["text"].split())
                if current and size + words > target_words:
                    batches.append(current)
                    current, size = [], 0
                current.append(p)
                size += words

            if current:
                batches.append(current)

            for batch in batches:
                body = "\n\n".join(p["text"] for p in batch)
                header = f"Tài liệu: {doc['title']}\nMã tài liệu: {did}"

                if section:
                    header += "\nMục: " + " > ".join(section)

                embedding_text = header + "\n\n" + body
                warnings = set(issues.get(did, set()))

                for p in batch:
                    warnings.update(issues.get(p["passage_id"], set()))

                if len(body.split()) > target_words:
                    warnings.add("oversize_atomic_passage")

                if len(batches) > 1:
                    warnings.add("section_spans_multiple_chunks")

                chunk_id = "chunk_" + digest([CHUNKER_VERSION, target_words, doc, batch])
                chunks.append(Chunk(
                    chunk_id, did, section_id,
                    body, embedding_text, doc,
                    batch,
                    sorted(warnings)
                ))
    return chunks


def save_chunks(chunks: list[Chunk], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")

    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        for chunk in chunks:
            stream.write(canonical(chunk.to_dict()) + "\n")

    temporary.replace(path)


def load_chunks(path: Path) -> list[Chunk]:
    chunks = []
    seen: set[str] = set()

    with path.open(encoding="utf-8-sig") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue

            try:
                chunk = Chunk(**json.loads(line))
                if (
                    chunk.chunk_id in seen
                    or not chunk.text.strip()
                    or not chunk.embedding_text.strip()
                    or not chunk.passages
                    or chunk.document["doc_id"] != chunk.doc_id
                    or any(p["doc_id"] != chunk.doc_id for p in chunk.passages)
                ):
                    raise ValueError("Duplicate ID or invalid chunk contents")
            except (ValueError, TypeError, KeyError, AttributeError) as exc:
                raise ValueError(f"Invalid chunk at line {number}") from exc

            seen.add(chunk.chunk_id)
            chunks.append(chunk)

    if not chunks:
        raise ValueError("Chunk file is empty")

    return chunks
