"""Evaluate positive retrieval questions against independently reviewed passage IDs."""

import json
from pathlib import Path
from time import perf_counter


def load_questions(path: Path) -> list[dict]:
    questions = []
    seen = set()

    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue

        q = json.loads(line)
        if (
            not isinstance(q, dict)
            or not isinstance(q.get("id"), str)
            or not q["id"].strip()
            or q["id"] in seen
            or not isinstance(q.get("question"), str)
            or not q["question"].strip()
            or not isinstance(q.get("expected_passage_ids"), list)
            or not q["expected_passage_ids"]
            or not all(isinstance(p, str) and p.strip() for p in q["expected_passage_ids"])
            or (q.get("where") is not None and not isinstance(q["where"], dict))
        ):
            raise ValueError(f"Invalid question at line {number}; require unique id, question, nonempty expected_passage_ids")

        seen.add(q["id"])
        questions.append(q)

    if not questions:
        raise ValueError("Evaluation dataset is empty")

    return questions


def evaluate_retrieval(retriever, questions: list[dict], top_k: int = 5) -> dict:
    if not questions or top_k < 1:
        raise ValueError("Evaluation requires questions and positive top_k")

    # Verify labels belong to the indexed corpus before spending tokens on queries.
    collection = retriever.manager.ready_collection(retriever.embedder)
    indexed = set()
    for offset in range(0, collection.count(), 500):
        records = collection.get(limit=500, offset=offset, include=["metadatas"])

        for metadata in records["metadatas"]:
            indexed.update(p["passage_id"] for p in json.loads(metadata["payload_json"])["passages"])

    missing = {pid for q in questions for pid in q["expected_passage_ids"]} - indexed
    if missing:
        raise ValueError(f"Gold passage IDs are absent from the collection: {sorted(missing)[:10]}")

    rows = []
    for question in questions:
        started = perf_counter()
        results = retriever.search(question["question"], top_k, question.get("where"), expand_section=False)
        retrieved = {p["passage_id"] for hit in results for p in hit["passages"]}
        gold = set(question["expected_passage_ids"])
        overlap = retrieved & gold
        rows.append({
            "id": question["id"],
            "question": question["question"],
            "hit": int(bool(overlap)),
            "recall": len(overlap) / len(gold),
            "expected_passage_ids": sorted(gold),
            "retrieved_passage_ids": sorted(retrieved),
            "chunk_ids": [h["chunk_id"] for h in results],
            "seconds": perf_counter() - started
        })

    return {
        "questions": len(rows),
        "top_k": top_k,
        "hit_at_k": sum(r["hit"] for r in rows) / len(rows),
        "mean_passage_recall_at_k": sum(r["recall"] for r in rows) / len(rows),
        "context_expansion_scored": False,
        "results": rows
    }
