"""Offline demo: python -m examples.context_fusion --max-tokens 4096.

All courses and requirements below are fictitious, not HCMUT regulations.
Only Pydantic and tiktoken are needed; no retrieval or generation APIs are called.
"""

import argparse
import json

from src.engine.fusion_chain import fuse_contexts
from src.engine.schema import ContextResult


def build_demo_contexts() -> tuple[ContextResult, ContextResult]:
    """Produce the shapes returned by VectorPipeline and GraphRetriever."""
    text = "DỮ LIỆU MINH HỌA: Môn chuyên đề C yêu cầu hoàn thành môn nền tảng B."
    source_file = "demo/course_c.json"
    match = {
        "chunk_id": "demo_chunk_1", "doc_id": "demo_doc_c", "text": text,
        "distance": 0.2, "score": 0.8, "score_type": "cosine_similarity",
        "document": {
            "doc_id": "demo_doc_c", "title": "Đề cương minh họa C",
            "source_file": source_file, "version": "demo-v1",
            "scope": {"program": "DEMO", "cohorts": ["2024"]},
        },
        "passages": [{
            "passage_id": "demo_passage_1", "doc_id": "demo_doc_c", "text": text,
            "source_locator": {"section": "Điều kiện học phần", "pointer": "/requirements"},
        }],
        "warnings": ["demo_data_only"], "verification_status": "not_verified",
    }
    match["section_context"] = list(match["passages"])
    citation = {
        "chunk_id": match["chunk_id"], "doc_id": match["doc_id"],
        "passage_id": match["passages"][0]["passage_id"], "source_file": source_file,
        "source_locator": match["passages"][0]["source_locator"],
    }
    vector = ContextResult(
        branch_name="Vector_Retrieval", content=f"[V1] {text}",
        citations=["[V1] " + json.dumps(citation, ensure_ascii=False, sort_keys=True)],
        raw_data={"results": [match]},
    )

    nodes = [
        {"code": "DEMO1001", "name": "Môn nền tảng A", "credits": 3,
         "source_locator": "demo/course_a.json"},
        {"code": "DEMO1002", "name": "Môn nền tảng B", "credits": 3,
         "source_locator": "demo/course_b.json"},
        {"code": "DEMO3001", "name": "Môn chuyên đề C", "credits": 3,
         "source_locator": source_file},
    ]
    course = dict(nodes[-1], prerequisites=[nodes[1]], recommended=[], corequisites=[],
                  prerequisite_for=[], lecturers=[], assessments=[], blocks=[], graduation_reqs=[])
    graph = ContextResult(
        branch_name="Graph_Traversal",
        content="DỮ LIỆU MINH HỌA: DEMO1001 -> DEMO1002 -> DEMO3001",
        citations=["demo/course_a.json", "demo/course_b.json", source_file,
                   "demo/requirements.json#/A_to_B", "demo/requirements.json#/B_to_C"],
        raw_data={
            "target_entities": ["DEMO3001"], "courses": {"DEMO3001": course},
            "chains": {"DEMO3001": [{
                "depth": 2, "nodes": nodes,
                "relationships": [
                    {"type": "PREREQUISITE_FOR", "source_locator": "demo/requirements.json#/A_to_B"},
                    {"type": "PREREQUISITE_FOR", "source_locator": "demo/requirements.json#/B_to_C"},
                ],
            }]},
            "pyvis": {
                "target_entities": ["DEMO3001"],
                "nodes": [{"id": node["code"], "label": node["name"]} for node in nodes],
                "edges": [
                    {"from": "DEMO1001", "to": "DEMO1002", "label": "TIÊN QUYẾT", "arrows": "to"},
                    {"from": "DEMO1002", "to": "DEMO3001", "label": "TIÊN QUYẾT", "arrows": "to"},
                ],
            },
        },
    )
    return vector, graph


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--vector-only", action="store_true", help="B1: use only Vector evidence")
    args = parser.parse_args()
    vector, graph = build_demo_contexts()
    result = fuse_contexts(vector, None if args.vector_only else graph, max_tokens=args.max_tokens)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
