"""Understand a question, then retrieve only matching chunks."""

import json

from src.config.settings import VectorModuleSettings
from .query_understanding import QueryUnderstanding
from .schema import ContextResult, VectorResult


def vector_context(matches: list[dict]) -> ContextResult:
    blocks, citations = [], []
    for index, match in enumerate(matches, 1):
        label = f"[V{index}]"
        blocks.append(f"{label} {match['text']}")
        for passage in match["passages"]:
            source = {
                "chunk_id": match["chunk_id"], "doc_id": match["doc_id"],
                "passage_id": passage["passage_id"],
                "source_file": match["document"].get("source_file"),
                "source_locator": passage.get("source_locator"),
            }
            citations.append(f"{label} " + json.dumps(source, ensure_ascii=False, sort_keys=True))
    return ContextResult(
        branch_name="Vector_Retrieval", content="\n\n".join(blocks),
        citations=citations, raw_data={"results": matches},
    )


class VectorPipeline:
    def __init__(self, query_understanding: QueryUnderstanding, retriever=None, *, settings=None):
        self.query_understanding = query_understanding
        self.retriever = retriever
        self.settings = settings

    def run(self, question: str, history=None, top_k: int = 3, where: dict | None = None) -> VectorResult:
        if type(top_k) is not int or top_k < 1:
            raise ValueError("top_k must be a positive integer")
        if where is not None and not isinstance(where, dict):
            raise ValueError("where must be a metadata filter object")
        query = self.query_understanding.analyze(question, history)
        if query.status == "needs_clarification":
            return VectorResult(query=query)
        if self.retriever is not None:
            matches = self.retriever.search(query.normalized_question, top_k, where, expand_section=False)
        else:
            # No vector client, cache or database is opened before the query is ready.
            from src.vector_module.chroma_manager import ChromaManager
            from src.vector_module.embeddings import BgeM3API
            from src.vector_module.vector_retriever import VectorRetriever

            settings = self.settings or VectorModuleSettings.from_env()
            with BgeM3API.from_settings(settings) as embedder:
                manager = ChromaManager(settings.chroma_path, settings.collection_name)
                matches = VectorRetriever(manager, embedder).search(
                    query.normalized_question, top_k, where, expand_section=False,
                )
        return VectorResult(query=query, vector_context=vector_context(matches))
