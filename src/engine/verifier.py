"""
Verifiable reasoning: atomic claim verification and proof path extraction.
100% LLM-based Claim Extraction (Neuro) kết hợp Symbolic Knowledge Graph Verification.
Đã loại bỏ hoàn toàn cơ chế Rule-based / Regex Fallback.
"""

from __future__ import annotations

import json
import logging
import os
import re
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.config.settings import QueryUnderstandingSettings
from src.engine.prompts import CLAIM_EXTRACTION_PROMPT
from src.engine.schema import ContextResult

log = logging.getLogger(__name__)


class ClaimStatus(str, Enum):
    VERIFIED = "VERIFIED"          # Xác thực đúng với Symbolic KG hoặc Vector
    CONTRADICTED = "CONTRADICTED"  # Mâu thuẫn trực tiếp với chân lý (Ảo giác)
    UNVERIFIED = "UNVERIFIED"      # Không đủ dữ kiện để khẳng định


class AtomicClaim(BaseModel):
    claim_text: str
    claim_type: str = "other"      # prerequisite, course_info, lecturer, regulation,...
    subject: Optional[str] = None
    predicate: Optional[str] = None
    object: Optional[str] = None
    cited_sources: List[str] = Field(default_factory=list)
    status: ClaimStatus = ClaimStatus.UNVERIFIED
    evidence: Optional[str] = None
    proof_path: Optional[str] = None


class VerificationReport(BaseModel):
    total_claims: int = 0
    verified_claims: int = 0
    contradicted_claims: int = 0
    unverified_claims: int = 0
    faithfulness_score: float = 1.0
    claims: List[AtomicClaim] = Field(default_factory=list)
    proof_paths: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class Verifier:
    """Module kiểm chứng suy luận kết hợp Symbolic Ground Truth và Vector Evidence (100% LLM-based Claim Extraction)."""

    def __init__(self, settings: Optional[QueryUnderstandingSettings] = None, client=None):
        self.settings = settings or QueryUnderstandingSettings.from_env()
        self.client = client
        self.provider = "none"

    def _get_llm_client(self):
        """Khởi tạo LLM client linh hoạt theo API key sẵn có trong môi trường."""
        if self.client is not None:
            return self.client

        # 1. Thử OpenAI nếu có OPENAI_API_KEY
        openai_key = os.getenv("OPENAI_API_KEY", "").strip() or self.settings.api_key
        if openai_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=openai_key)
                self.provider = "openai"
                return self.client
            except Exception:
                pass

        # 2. Thử Groq nếu có GROQ_API_KEY
        groq_key = os.getenv("GROQ_API_KEY", "").strip()
        if groq_key:
            try:
                from groq import Groq
                self.client = Groq(api_key=groq_key)
                self.provider = "groq"
                return self.client
            except Exception:
                pass

        # 3. Thử OpenRouter nếu có OPENROUTER_API_KEY
        openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if openrouter_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=openrouter_key)
                self.provider = "openrouter"
                return self.client
            except Exception:
                pass

        return None

    def extract_atomic_claims(self, answer: str) -> List[AtomicClaim]:
        """
        Bóc tách khẳng định nguyên tử 100% bằng LLM (Neuro-Symbolic Pipeline).
        Không sử dụng luật hay regex fallback.
        """
        if not answer or not answer.strip():
            return []

        client = self._get_llm_client()
        if not client:
            raise RuntimeError(
                "Không tìm thấy LLM client để bóc tách Atomic Claims. "
                "Vui lòng cấu hình OPENAI_API_KEY, GROQ_API_KEY hoặc OPENROUTER_API_KEY trong file .env."
            )

        model_name = self.settings.model
        if self.provider == "groq":
            model_name = "qwen/qwen3.8-27b"
        elif self.provider == "openrouter":
            model_name = os.getenv("OPENROUTER_MODEL_NAME", "meta-llama/llama-3.3-70b-instruct:free")

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a precise logic extraction engine that outputs valid JSON only."},
                    {"role": "user", "content": f"{CLAIM_EXTRACTION_PROMPT}\n\nCâu trả lời cần phân rã:\n\"\"\"\n{answer}\n\"\"\""}
                ],
                temperature=0.0,
                response_format={"type": "json_object"} if self.provider in ("openai", "groq") else None,
                timeout=self.settings.timeout,
            )
            content = response.choices[0].message.content or "{}"
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                raw_claims = data.get("claims", [])
                return [AtomicClaim(**c) for c in raw_claims]
            return []
        except Exception as e:
            log.error("Lỗi khi bóc tách Atomic Claims bằng LLM (%s): %s", model_name, e)
            raise RuntimeError(f"LLM Claim Extraction thất bại trên model {model_name}: {e}") from e

    def verify(
        self,
        answer: str,
        fused_context: ContextResult,
    ) -> tuple[str, VerificationReport]:
        """
        Kiểm chứng toàn bộ câu trả lời đối chiếu với dữ liệu thô của Graph và Vector.
        Trả về: (verified_answer_text, verification_report)
        """
        claims = self.extract_atomic_claims(answer)
        raw_data = fused_context.raw_data or {}
        graph_raw = raw_data.get("graph") or {}
        vector_raw = raw_data.get("vector") or {}

        # Dữ liệu đối soát Symbolic từ Knowledge Graph
        courses_dict = {}
        if isinstance(graph_raw, dict):
            courses_dict = graph_raw.get("raw_data", {}).get("courses") or graph_raw.get("courses") or {}

        # Dữ liệu đối soát Textual từ Vector Passages
        vector_results = []
        if isinstance(vector_raw, dict):
            vector_results = vector_raw.get("raw_data", {}).get("results") or vector_raw.get("results") or []
        vector_corpus_text = " ".join([v.get("text", "") for v in vector_results]).lower()

        verified_cnt = 0
        contradicted_cnt = 0
        proof_paths = []

        for claim in claims:
            # 1. Kiểm chứng Symbolic cho quan hệ Môn học & Tiên quyết
            if claim.claim_type == "prerequisite" and claim.subject and claim.object:
                subj = claim.subject.upper().strip()
                obj = claim.object.upper().strip()
                rel_claimed = (claim.predicate or "PREREQUISITE_FOR").upper()

                if obj in courses_dict:
                    details = courses_dict[obj]
                    prereqs = [p["code"].upper() if isinstance(p, dict) else str(p).upper() for p in details.get("prerequisites", [])]
                    recomms = [r["code"].upper() if isinstance(r, dict) else str(r).upper() for r in details.get("recommended", [])]
                    coreqs = [c["code"].upper() if isinstance(c, dict) else str(c).upper() for c in details.get("corequisites", [])]

                    if "PREREQUISITE" in rel_claimed:
                        if subj in prereqs:
                            claim.status = ClaimStatus.VERIFIED
                            claim.evidence = f"KG xác nhận: {subj} là TIÊN QUYẾT BẮT BUỘC của {obj}."
                            claim.proof_path = f"({subj})-[:PREREQUISITE_FOR]->({obj})"
                            proof_paths.append({"type": "edge", "source": subj, "target": obj, "label": "TIÊN QUYẾT"})
                        elif subj in recomms:
                            claim.status = ClaimStatus.CONTRADICTED
                            claim.evidence = f"MÂU THUẪN: KG chỉ ghi nhận {subj} là môn HỌC TRƯỚC/KHUYẾN NGHỊ của {obj}, không phải tiên quyết bắt buộc!"
                        elif subj in coreqs:
                            claim.status = ClaimStatus.CONTRADICTED
                            claim.evidence = f"MÂU THUẪN: KG chỉ ghi nhận {subj} là môn SONG HÀNH của {obj}!"
                        else:
                            claim.status = ClaimStatus.UNVERIFIED
                            claim.evidence = f"KG không ghi nhận quan hệ tiên quyết nào giữa {subj} và {obj}."
                    elif "RECOMMENDED" in rel_claimed or "HỌC TRƯỚC" in rel_claimed:
                        if subj in recomms:
                            claim.status = ClaimStatus.VERIFIED
                            claim.evidence = f"KG xác nhận: {subj} là môn học trước/khuyến nghị của {obj}."
                            claim.proof_path = f"({subj})-[:RECOMMENDED_FOR]->({obj})"
                        else:
                            claim.status = ClaimStatus.UNVERIFIED
                else:
                    claim.status = ClaimStatus.UNVERIFIED

            # 2. Kiểm chứng Thuộc tính môn học (Tín chỉ, Giảng viên)
            elif claim.claim_type == "course_info" and claim.subject:
                subj = claim.subject.upper().strip()
                if subj in courses_dict:
                    details = courses_dict[subj]
                    if claim.predicate == "credits" and claim.object is not None:
                        try:
                            claimed_credits = int(re.search(r"\d+", str(claim.object)).group(0))
                            real_credits = details.get("credits", 0)
                            if claimed_credits == real_credits:
                                claim.status = ClaimStatus.VERIFIED
                                claim.evidence = f"KG xác nhận: Môn {subj} có {real_credits} tín chỉ."
                            else:
                                claim.status = ClaimStatus.CONTRADICTED
                                claim.evidence = f"MÂU THUẪN: {subj} thực tế có {real_credits} tín chỉ, không phải {claimed_credits} tín chỉ."
                        except Exception:
                            claim.status = ClaimStatus.UNVERIFIED
                    else:
                        claim.status = ClaimStatus.VERIFIED
                        claim.evidence = f"KG xác nhận môn {subj} tồn tại trong CTĐT."
                else:
                    claim.status = ClaimStatus.UNVERIFIED

            # 3. Kiểm chứng Giảng viên phụ trách
            elif claim.claim_type == "lecturer" and claim.subject:
                subj = claim.subject.upper().strip()
                if subj in courses_dict:
                    details = courses_dict[subj]
                    lecturers = [l.get("name", "").strip().lower() for l in details.get("lecturers", [])]
                    obj_name = str(claim.object or "").strip().lower()
                    if any((obj_name in lec or lec in obj_name) for lec in lecturers if lec):
                        claim.status = ClaimStatus.VERIFIED
                        claim.evidence = f"KG xác nhận: {claim.object} giảng dạy môn {subj}."
                    else:
                        claim.status = ClaimStatus.UNVERIFIED
                        claim.evidence = f"KG không ghi nhận {claim.object} phụ trách môn {subj}."
                else:
                    claim.status = ClaimStatus.UNVERIFIED

            # 3. Kiểm chứng Quy chế học vụ với Vector Context
            elif claim.claim_type == "regulation":
                keywords = [w for w in re.split(r"\s+", claim.claim_text.lower()) if len(w) > 3]
                match_count = sum(1 for kw in keywords if kw in vector_corpus_text)
                if keywords and (match_count / len(keywords) >= 0.5):
                    claim.status = ClaimStatus.VERIFIED
                    claim.evidence = "Khớp với nội dung điều khoản văn bản quy chế trong [Vector Data]."
                else:
                    claim.status = ClaimStatus.UNVERIFIED

            if claim.status == ClaimStatus.VERIFIED:
                verified_cnt += 1
            elif claim.status == ClaimStatus.CONTRADICTED:
                contradicted_cnt += 1

        total = len(claims)
        unverified_cnt = total - verified_cnt - contradicted_cnt
        faithfulness = (verified_cnt / total) if total > 0 else 1.0

        # Nếu phát hiện mâu thuẫn (ảo giác), bổ sung khối cảnh báo vào cuối câu trả lời
        verified_answer = answer
        warnings = []
        if contradicted_cnt > 0:
            warnings.append(f"Phát hiện {contradicted_cnt} khẳng định mâu thuẫn với cơ sở tri thức.")
            contradiction_notes = "\n\n> ⚠️ **LƯU Ý KIỂM CHỨNG TỪ KNOWLEDGE GRAPH:**\n"
            for c in claims:
                if c.status == ClaimStatus.CONTRADICTED:
                    contradiction_notes += f"> - **Khẳng định:** *\"{c.claim_text}\"*\n>   👉 **Thực tế:** {c.evidence}\n"
            verified_answer += contradiction_notes

        report = VerificationReport(
            total_claims=total,
            verified_claims=verified_cnt,
            contradicted_claims=contradicted_cnt,
            unverified_claims=unverified_cnt,
            faithfulness_score=round(faithfulness, 3),
            claims=claims,
            proof_paths=proof_paths,
            warnings=warnings,
        )

        return verified_answer, report