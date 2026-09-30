"""Dense vector search with explicit cosine scores and source provenance."""

import json

from .chroma_manager import ChromaManager


class VectorRetriever:
    def __init__(self, manager: ChromaManager, embedder):
        self.manager, self.embedder = manager, embedder

    def search(
        self,
        question: str,
        top_k: int = 5,
        where: dict | None = None,
        expand_section: bool = True
    ) -> list[dict]:
        if not question.strip() or top_k < 1:
            raise ValueError("Provide a non-empty question and positive top_k")

        collection = self.manager.ready_collection(self.embedder)

        # Avoid a paid query embedding when a filter cannot match any document.
        if where and not collection.get(where=where, limit=1, include=[])["ids"]:
            return []

        vector = self.embedder.embed([question])[0]
        result = collection.query(
            query_embeddings=[vector],
            n_results=min(top_k, collection.count()),
            where=where, include=["distances", "metadatas"]
        )
        matches = []

        for cid, distance, metadata in zip(result["ids"][0], result["distances"][0], result["metadatas"][0]):
            chunk = json.loads(metadata["payload_json"])
            passages = chunk["passages"]

            if expand_section:
                passages = self.manager.section_context(collection, chunk["section_id"])

            matches.append({
                "chunk_id": cid, "doc_id": chunk["doc_id"], "text": chunk["text"],
                "distance": distance, "score": 1.0 - distance, "score_type": "cosine_similarity",
                "document": chunk["document"], "passages": chunk["passages"],
                "warnings": chunk["warnings"],
                "section_context": passages,
                "verification_status": "not_verified",
            })

        return matches
