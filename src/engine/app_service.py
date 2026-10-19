"""
Application Service: Cầu nối nghiệp vụ End-to-End giữa UI và hệ thống Neuro-Symbolic RAG.
Hỗ trợ đa provider LLM (Groq, OpenAI, OpenRouter) và cơ chế Fallback an toàn khi offline.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config.settings import QueryUnderstandingSettings, VectorModuleSettings
from src.engine.fusion_chain import fuse_contexts
from src.engine.prompts import GENERATION_SYSTEM_PROMPT
from src.engine.schema import FinalResponse, ContextResult, QueryAnalysis
from src.engine.verifier import Verifier

log = logging.getLogger(__name__)


def _get_generation_client():
    """Khởi tạo LLM client để sinh câu trả lời, ưu tiên theo API key sẵn có."""
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if openai_key:
        try:
            from openai import OpenAI
            return OpenAI(api_key=openai_key), os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")
        except Exception:
            pass

    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if groq_key:
        try:
            from groq import Groq
            return Groq(api_key=groq_key), "qwen/qwen3.8-27b"
        except Exception:
            pass

    openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if openrouter_key:
        try:
            from openai import OpenAI
            model = os.getenv("OPENROUTER_MODEL_NAME", "meta-llama/llama-3.3-70b-instruct:free")
            return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=openrouter_key), model
        except Exception:
            pass

    return None, None


def _retrieve_from_graph_json(query_text: str) -> Optional[ContextResult]:
    """
    Fallback truy xuất tri thức từ Knowledge Graph JSON (curriculum_graph.json)
    khi cơ sở dữ liệu Neo4j offline hoặc chưa được kích hoạt.
    """
    graph_path = Path("DATA/graph_triplets/curriculum_graph.json")
    if not graph_path.is_file():
        return None

    try:
        with open(graph_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        log.warning(f"Không thể đọc curriculum_graph.json: {e}")
        return None

    nodes_by_code: Dict[str, Dict[str, Any]] = {}
    for n in data.get("nodes", []):
        if n.get("code"):
            nodes_by_code[n["code"].upper()] = n

    rels = data.get("relationships", [])

    # Trích xuất mã môn (ví dụ: CO2003, MT1007,...)
    found_codes = re.findall(r"\b[A-Za-z]{2}\d{4}\b", query_text.upper())
    for code, n in nodes_by_code.items():
        if n.get("name") and n["name"].lower() in query_text.lower():
            if code not in found_codes:
                found_codes.append(code)

    if not found_codes:
        return None

    courses_data: Dict[str, Dict[str, Any]] = {}
    formatted_lines = ["[DỮ LIỆU ĐỒ THỊ TRI THỨC (OFFLINE KG JSON)]:\n"]
    citations = set()
    pyvis_nodes = []
    pyvis_edges = []
    seen_nodes = set()

    for code in found_codes:
        node = nodes_by_code.get(code)
        if not node:
            continue
        c_name = node.get("name", code)
        credits = node.get("credits", 0)
        source_loc = node.get("source_locator", "")
        if source_loc:
            citations.add(source_loc)

        prereqs = []
        recomms = []
        coreqs = []
        lecturers = []
        assessments = []

        for r in rels:
            s, t, rel_type = r.get("source"), r.get("target"), r.get("type")
            loc = r.get("source_locator", "")
            if loc:
                citations.add(loc)
            if t == code:
                if rel_type == "PREREQUISITE_FOR":
                    prereqs.append({"code": s, "source_locator": loc})
                elif rel_type == "RECOMMENDED_FOR":
                    recomms.append({"code": s, "source_locator": loc})
                elif rel_type == "CO_REQUISITE_FOR":
                    coreqs.append({"code": s, "source_locator": loc})
            elif s == code:
                if rel_type == "TAUGHT_BY":
                    lecturers.append({"name": t, "source_locator": loc})
                elif rel_type == "EVALUATED_BY":
                    assessments.append({"name": t, "weight": r.get("properties", {}).get("weight", 0)})

        courses_data[code] = {
            "code": code,
            "name": c_name,
            "credits": credits,
            "source_locator": source_loc,
            "prerequisites": prereqs,
            "recommended": recomms,
            "corequisites": coreqs,
            "lecturers": lecturers,
            "assessments": assessments,
        }

        tc_str = f" ({credits} tín chỉ)" if credits > 0 else ""
        formatted_lines.append(f"### Môn học: {code} - {c_name}{tc_str}")
        if prereqs:
            formatted_lines.append(f"  - Tiên quyết bắt buộc: {[p['code'] for p in prereqs]}")
        if recomms:
            formatted_lines.append(f"  - Môn học trước / Khuyến nghị: {[r['code'] for r in recomms]}")
        if coreqs:
            formatted_lines.append(f"  - Môn song hành: {[c['code'] for c in coreqs]}")
        if lecturers:
            formatted_lines.append(f"  - Giảng viên phụ trách: {[l['name'] for l in lecturers]}")

        if code not in seen_nodes:
            seen_nodes.add(code)
            pyvis_nodes.append({"id": code, "label": f"{code}\n{c_name}", "color": "#FF9900"})

        for p in prereqs:
            p_code = p["code"]
            if p_code not in seen_nodes:
                seen_nodes.add(p_code)
                pyvis_nodes.append({"id": p_code, "label": p_code, "color": "#D0021B"})
            pyvis_edges.append({"from": p_code, "to": code, "label": "TIÊN QUYẾT"})

        for r in recomms:
            r_code = r["code"]
            if r_code not in seen_nodes:
                seen_nodes.add(r_code)
                pyvis_nodes.append({"id": r_code, "label": r_code, "color": "#4A90E2"})
            pyvis_edges.append({"from": r_code, "to": code, "label": "HỌC TRƯỚC"})

    return ContextResult(
        branch_name="Graph_Traversal",
        content="\n".join(formatted_lines),
        citations=sorted(list(citations)),
        raw_data={"courses": courses_data, "pyvis": {"nodes": pyvis_nodes, "edges": pyvis_edges}},
    )


def answer_question(
    question: str,
    history: Optional[List[Dict[str, str]]] = None,
    top_k_vector: int = 3,
    max_tokens: int = 4096,
) -> FinalResponse:
    """
    Hàm giao tiếp chuẩn hóa được gọi từ Streamlit Web UI (src/ui/app.py).
    
    Quy trình:
    1. Query Understanding: Phân tích & chuẩn hóa câu hỏi, kiểm tra làm rõ (disambiguation).
    2. Retrieval kép: Gọi đồng thời Vector Retrieval (ChromaDB) và Graph Traversal (Neo4j / KG JSON).
    3. Context Fusion: Ghép ngữ cảnh an toàn, trần 4096 tokens, bảo toàn nguồn [Vn]/[Gn].
    4. Constrained Generation: LLM sinh câu trả lời có kiểm chứng.
    5. Verifier Layer: Bóc tách claims 100% bằng LLM, đối soát với KG, tính Faithfulness.
    6. Trả về FinalResponse với format hiển thị tương thích hoàn toàn với Streamlit.
    """
    settings_qu = QueryUnderstandingSettings.from_env()
    settings_vec = VectorModuleSettings.from_env()

    # -------------------------------------------------------------
    # BƯỚC 1: QUERY UNDERSTANDING
    # -------------------------------------------------------------
    normalized_q = question
    if settings_qu.api_key:
        try:
            from src.engine.query_understanding import QueryUnderstanding
            with QueryUnderstanding(settings_qu) as qu_engine:
                query_analysis = qu_engine.analyze(question, history=history)

            if query_analysis.status == "needs_clarification":
                return FinalResponse(
                    answer=query_analysis.clarification_question or "Bạn có thể nói rõ hơn về môn học hoặc quy chế cần tra cứu không?",
                    references=[],
                    graph_data=None,
                )
            normalized_q = query_analysis.normalized_question or question
        except Exception as e:
            log.info(f"Query Understanding chạy chế độ fallback câu hỏi gốc ({e})")
            normalized_q = question
    else:
        normalized_q = question

    # -------------------------------------------------------------
    # BƯỚC 2: DUAL RETRIEVAL (VECTOR + GRAPH)
    # -------------------------------------------------------------
    vector_context: Optional[ContextResult] = None
    try:
        from src.vector_module.chroma_manager import ChromaManager
        from src.vector_module.embeddings import BgeM3API
        from src.vector_module.vector_retriever import VectorRetriever
        from src.engine.vector_pipeline import vector_context as make_vector_context

        with BgeM3API.from_settings(settings_vec) as embedder:
            manager = ChromaManager(settings_vec.chroma_path, settings_vec.collection_name)
            matches = VectorRetriever(manager, embedder).search(
                normalized_q, top_k=top_k_vector, expand_section=False
            )
            if matches:
                vector_context = make_vector_context(matches)
    except Exception as e:
        log.warning(f"Vector Retrieval gặp sự cố: {e}")
        vector_context = None

    graph_context: Optional[ContextResult] = None
    try:
        from src.graph_module.graph_retriever import GraphRetriever
        with GraphRetriever() as retriever:
            graph_context = retriever.retrieve(query_text=normalized_q)
    except Exception as e:
        log.info(f"Graph Retrieval gặp sự cố kết nối Neo4j ({e}). Chuyển sang đọc từ Knowledge Graph JSON.")
        graph_context = _retrieve_from_graph_json(normalized_q)

    # -------------------------------------------------------------
    # BƯỚC 3: CONTEXT FUSION (HỢP NHẤT NGỮ CẢNH)
    # -------------------------------------------------------------
    fused = fuse_contexts(
        vector_context=vector_context,
        graph_context=graph_context,
        max_tokens=max_tokens,
        graph_ratio=0.5,
    )

    # -------------------------------------------------------------
    # BƯỚC 4: CONSTRAINED GENERATION (LLM SYNTHESIS)
    # -------------------------------------------------------------
    client, model_name = _get_generation_client()
    raw_answer = ""

    if client and model_name:
        try:
            messages = [
                {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
            ]
            if history:
                for msg in history[-4:]:
                    messages.append({"role": msg["role"], "content": msg["content"]})

            user_prompt = f"NGỮ CẢNH ĐƯỢC CẤP:\n\"\"\"\n{fused.content}\n\"\"\"\n\nCÂU HỎI CỦA NGƯỜI DÙNG: {normalized_q}"
            messages.append({"role": "user", "content": user_prompt})

            gen_response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.1,
                timeout=30.0,
            )
            raw_answer = gen_response.choices[0].message.content or ""
        except Exception as e:
            log.warning(f"Lỗi khi sinh câu trả lời bằng LLM ({e}), chuyển sang chế độ tóm tắt ngữ cảnh.")

    if not raw_answer.strip():
        if fused.content.strip():
            raw_answer = (
                f"Dựa trên dữ liệu học vụ được truy xuất cho câu hỏi *\"{normalized_q}\"*:\n\n"
                f"{fused.content[:1500]}\n\n"
                "*(Đang hiển thị tóm lược ngữ cảnh trực tiếp từ hệ thống đối chiếu tri thức)*"
            )
        else:
            raw_answer = f"Hệ thống chưa tìm thấy dữ liệu phù hợp trong cơ sở tri thức cho câu hỏi: *\"{normalized_q}\"*."

    # -------------------------------------------------------------
    # BƯỚC 5: LỚP KIỂM CHỨNG SUY LUẬN (VERIFIER)
    # -------------------------------------------------------------
    verifier = Verifier(settings=settings_qu)
    verified_answer, v_report = verifier.verify(raw_answer, fused_context=fused)

    # -------------------------------------------------------------
    # BƯỚC 6: ĐÓNG GÓI DỮ LIỆU CHO STREAMLIT UI
    # -------------------------------------------------------------
    references_ui = []
    seen_refs = set()

    for cit in fused.citations:
        match = re.match(r"^(\[[VG]\d+\])\s*(.*)$", cit)
        code_label = match.group(1) if match else "[Nguồn]"
        raw_info = match.group(2) if match else cit

        title = "Tài liệu học vụ"
        source = "ĐH Bách Khoa TP.HCM"
        chunk_text = ""

        try:
            parsed = json.loads(raw_info)
            title = parsed.get("source_file") or parsed.get("doc_id") or title
            source = parsed.get("source_locator") or source
            chunk_text = f"Mã đoạn: {parsed.get('passage_id', '')}"
        except Exception:
            title = raw_info[:40]

        ref_key = (code_label, title)
        if ref_key not in seen_refs:
            seen_refs.add(ref_key)
            references_ui.append({
                "code": code_label,
                "title": title,
                "source": str(source),
                "chunk": chunk_text,
            })

    graph_data_ui = None
    if graph_context and graph_context.raw_data:
        graph_data_ui = graph_context.raw_data.get("pyvis")

    if v_report.total_claims > 0:
        verified_answer += f"\n\n---\n*Độ tin cậy kiểm chứng:* **{int(v_report.faithfulness_score * 100)}%** ({v_report.verified_claims}/{v_report.total_claims} khẳng định được xác thực)."

    return FinalResponse(
        answer=verified_answer,
        references=references_ui,
        graph_data=graph_data_ui,
    )
