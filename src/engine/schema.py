"""
Data Contracts (Hợp đồng dữ liệu) cho toàn bộ Luồng 2 (Online Pipeline).
Sử dụng Pydantic để đảm bảo tính nhất quán giữa các module (Retrievers, Solver, UI).
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# ==========================================
# 2. SCHEMAS CHO CÁC NHÁNH TRUY XUẤT (RETRIEVAL)
# ==========================================
class ContextResult(BaseModel):
    """Kết quả trả về chuẩn hóa từ bất kỳ nhánh nào (Vector, Graph, Symbolic)."""
    branch_name: str = Field(description="Tên nhánh xử lý (VD: 'Vector_Retrieval', 'Graph_Traversal', 'Symbolic_Solver')")
    content: str = Field(description="Nội dung văn bản (Context) để nhồi vào Prompt cho LLM sinh câu trả lời.")
    citations: List[str] = Field(
        default_factory=list, 
        description="Danh sách các nguồn trích dẫn. (VD: ['File: QC.json', 'File: DCMH.CO1003.json'])"
    )
    raw_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Dữ liệu thô (như JSON đồ thị) dùng để vẽ UI (nếu cần)."
    )

# ==========================================
# 3. SCHEMAS CHO KẾT QUẢ CUỐI CÙNG (UI DISPLAY)
# ==========================================
class FinalResponse(BaseModel):
    """Đầu ra cuối cùng để hiển thị lên Streamlit Web UI."""
    answer: str = Field(description="Câu trả lời ngôn ngữ tự nhiên đã được kiểm chứng (Verifiable Generation).")
    references: List[str] = Field(
        default_factory=list,
        description="Danh sách nguồn tham khảo đã được lọc trùng lặp để hiển thị ở mục Citations."
    )
    graph_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Dữ liệu Graph (Nodes, Edges) để thư viện Pyvis vẽ đồ thị trực quan trên giao diện."
    )
