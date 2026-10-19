"""
Data Contracts (Hợp đồng dữ liệu) cho toàn bộ Luồng 2 (Online Pipeline).
Sử dụng Pydantic để đảm bảo tính nhất quán giữa các module (Retrievers, Solver, UI).
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


# ==========================================
# 1. SCHEMAS CHO HỘI THOẠI & PHÂN TÍCH CÂU HỎI
# ==========================================
class ConversationMessage(BaseModel):
    """Caller-owned conversation history; system/tool messages are not accepted."""
    model_config = ConfigDict(extra="forbid", strict=True)
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class QueryAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    original_question: str
    normalized_question: str | None = None
    status: Literal["ready", "needs_clarification"]
    clarification_question: str | None = None
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_status(self):
        if self.status == "ready":
            if not self.normalized_question or not self.normalized_question.strip():
                raise ValueError("A ready query requires a normalized question")
            if self.clarification_question is not None:
                raise ValueError("A ready query cannot request clarification")
        elif (
            self.normalized_question is not None
            or not self.clarification_question
            or not self.clarification_question.strip()
        ):
            raise ValueError("An ambiguous query requires clarification and no normalized question")
        return self


# ==========================================
# 2. SCHEMAS CHO CÁC NHÁNH TRUY XUẤT (RETRIEVAL)
# ==========================================
class ContextResult(BaseModel):
    """Kết quả trả về chuẩn hóa từ bất kỳ nhánh nào (Vector, Graph, Symbolic)."""
    branch_name: str = Field(description="Tên nhánh xử lý (VD: 'Vector_Retrieval', 'Graph_Traversal', 'Symbolic_Solver')")
    content: str = Field(description="Nội dung văn bản (Context) để nhồi vào Prompt cho LLM sinh câu trả lời.")
    citations: list[str] = Field(
        default_factory=list,
        description="Danh sách các nguồn trích dẫn. (VD: ['File: QC.json', 'File: DCMH.CO1003.json'])"
    )
    raw_data: dict[str, Any] | None = Field(
        default=None,
        description="Dữ liệu thô (như JSON đồ thị) dùng để vẽ UI (nếu cần)."
    )


class VectorResult(BaseModel):
    query: QueryAnalysis
    vector_context: ContextResult | None = None


# ==========================================
# 3. SCHEMAS CHO KẾT QUẢ CUỐI CÙNG (UI DISPLAY)
# ==========================================
class FinalResponse(BaseModel):
    """Đầu ra cuối cùng để hiển thị lên Streamlit Web UI."""
    answer: str = Field(description="Câu trả lời ngôn ngữ tự nhiên đã được kiểm chứng (Verifiable Generation).")
    references: list[str | dict[str, Any]] = Field(
        default_factory=list,
        description="Danh sách nguồn tham khảo (chuỗi hoặc object thẻ trích dẫn) để hiển thị ở mục Citations."
    )
    graph_data: dict[str, Any] | None = Field(
        default=None,
        description="Dữ liệu Graph (Nodes, Edges) để thư viện Pyvis vẽ đồ thị trực quan trên giao diện."
    )