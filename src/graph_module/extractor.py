"""Extract entity-relation triplets from text using LLM."""
import os
import sys
from pathlib import Path

# Đảm bảo thư mục gốc dự án luôn nằm trong sys.path để import được src
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import glob
import json
from pydantic import BaseModel, Field
from typing import List
from langchain_ollama import ChatOllama
from src.config.settings import RAW_DATA_1_DIR, OUTPUT_2_DIR, GRAPH_TRIPLETS_DIR

# --- 1. ĐỊNH NGHĨA SCHEMA CHO ĐỒ THỊ (PYDANTIC) ---
class CourseNode(BaseModel):
    code: str = Field(description="Mã môn học (VD: CO1005)")
    name: str = Field(description="Tên môn học tiếng Việt")
    credits: int = Field(description="Số tín chỉ (VD: 3)")

class RelationEdge(BaseModel):
    source_code: str = Field(description="Mã môn học điều kiện/tiên quyết")
    target_code: str = Field(description="Mã môn học chính")
    relation_type: str = Field(description="Chỉ được chọn 1 trong: PREREQUISITE_FOR (Tiên quyết), RECOMMENDED_FOR (Khuyên nghị/Học trước), CO_REQUISITE_FOR (Song hành)")

class GraphExtraction(BaseModel):
    courses: List[CourseNode]
    relationships: List[RelationEdge]


# --- 2. HÀM GỌI LLM TRÍCH XUẤT ---
def extract_with_llm(text_content: str, llm: ChatOllama) -> GraphExtraction:
    structured_llm = llm.with_structured_output(GraphExtraction)
    
    prompt = f"""
    Bạn là một chuyên gia bóc tách Dữ liệu Đồ thị Tri thức (Knowledge Graph) trong lĩnh vực Giáo dục.
    Hãy đọc đoạn thông tin môn học dưới đây và bóc tách ra danh sách các Môn học (courses) và Mối quan hệ (relationships) giữa chúng.
    
    Quy tắc:
    - Loại bỏ tiền tố mã môn khỏi tên môn học (VD: "CO1003 - Nhập môn" -> "Nhập môn").
    - Số tín chỉ phải là số nguyên (Nếu ghi "4(3.1.4)" thì chỉ lấy 4).
    - Mối quan hệ tiên quyết gán là PREREQUISITE_FOR. 
    - Mối quan hệ học trước/khuyên nghị gán là RECOMMENDED_FOR.
    - Mối quan hệ song hành gán là CO_REQUISITE_FOR.
    
    Văn bản:
    {text_content}
    """
    try:
        return structured_llm.invoke(prompt)
    except Exception as e:
        print(f"[!] Lỗi khi gọi LLM: {e}")
        return GraphExtraction(courses=[], relationships=[])


# --- 3. PIPELINE XỬ LÝ & NẠP METADATA NGUỒN ---
def extract_curriculum_triplets():
    """
    Dùng LLM đọc các text chunk để bóc tách Thực thể và Quan hệ.
    Gắn thêm source_locator vào metadata của từng Node và Edge.
    """
    output_file = GRAPH_TRIPLETS_DIR / "curriculum_graph.json"
    os.makedirs(GRAPH_TRIPLETS_DIR, exist_ok=True)

    llm = ChatOllama(model="llama3.1", temperature=0)

    all_nodes = {}
    all_relationships = []
    seen_rel = set()

    # 3.1 Xử lý Raw_data_1 (Đề cương môn học) - DÙNG RULE-BASED ĐỂ TỐI ƯU TỐC ĐỘ
    json_files = glob.glob(os.path.join(RAW_DATA_1_DIR, "*.json"))
    print(f"[*] Quét {len(json_files)} đề cương môn học bằng Rule-based (Tốc độ siêu tốc)...")

    # Hàm parse tín chỉ
    import re
    def parse_credits(pbsotc_val) -> int:
        if not pbsotc_val: return 0
        match = re.match(r"^(\d+)", str(pbsotc_val).strip())
        return int(match.group(1)) if match else 0
        
    def clean_course_name(name_raw: str, code: str) -> str:
        if not name_raw: return code
        name = str(name_raw).strip()
        if name.startswith(f"{code} - "):
            name = name[len(f"{code} - "):].strip()
        return name

    for file_path in json_files:
        filename = os.path.basename(file_path)
        source_metadata = f"File: {filename}"
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            code = data.get("mamonhoc", "").strip().upper()
            if not code:
                continue

            ten_raw = data.get("ten", {})
            name_vi = ten_raw.get("vi", str(ten_raw)) if isinstance(ten_raw, dict) else str(ten_raw)
            credits = parse_credits(data.get("pbsotc"))

            if code not in all_nodes or all_nodes[code]["credits"] == 0:
                all_nodes[code] = {
                    "code": code,
                    "name": clean_course_name(name_vi, code),
                    "credits": credits,
                    "source_locator": source_metadata
                }

            # Bóc tách quan hệ tiên quyết (TQ, SH, KN)
            for cond in data.get("monhocdieukien", []) or []:
                prereq_code = cond.get("mamonhoc", "").strip().upper()
                if not prereq_code:
                    continue

                loai_dk = cond.get("maloaidieukien", "").strip().upper()
                rel_type = "PREREQUISITE_FOR" if loai_dk == "TQ" else ("CO_REQUISITE_FOR" if loai_dk == "SH" else "RECOMMENDED_FOR")

                rel_key = (prereq_code, rel_type, code)
                if rel_key not in seen_rel:
                    seen_rel.add(rel_key)
                    all_relationships.append({"source": prereq_code, "target": code, "type": rel_type, "source_locator": source_metadata})

                if prereq_code not in all_nodes:
                    p_name = cond.get("tenmonhoc_only", {}).get("vi", prereq_code)
                    all_nodes[prereq_code] = {"code": prereq_code, "name": clean_course_name(p_name, prereq_code), "credits": 0, "source_locator": source_metadata}
        except Exception as e:
            print(f"[!] Bỏ qua file {filename}: {e}")

    # 3.2 Xử lý Khung chương trình đào tạo
    matrix_files = sorted(glob.glob(str(OUTPUT_2_DIR / "passages" / "*_MT_*.json")))
    print(f"\n[*] Quét {len(matrix_files)} khung CTĐT bằng LLM...")

    for m_file in matrix_files:
        filename = os.path.basename(m_file)
        source_metadata = f"File: {filename}"
        
        try:
            with open(m_file, "r", encoding="utf-8") as f:
                passages = json.load(f)
                
            for p in passages:
                if p.get("content_type") == "course_entity":
                    # Giao việc đọc đoạn text cho LLM bóc tách
                    extracted = extract_with_llm(p.get("text", ""), llm)
                    
                    for c in extracted.courses:
                        if c.code not in all_nodes or all_nodes[c.code]["credits"] == 0:
                            all_nodes[c.code] = {
                                "code": c.code, "name": c.name, "credits": c.credits, 
                                "source_locator": source_metadata
                            }
                    
                    for r in extracted.relationships:
                        rel_key = (r.source_code, r.relation_type, r.target_code)
                        if rel_key not in seen_rel:
                            seen_rel.add(rel_key)
                            all_relationships.append({
                                "source": r.source_code, "target": r.target_code, 
                                "type": r.relation_type, "source_locator": source_metadata
                            })
        except Exception as e:
            print(f"[!] Bỏ qua file {filename}: {e}")

    # --- 4. TỔNG HỢP & GHI KẾT QUẢ ---
    result_data = {
        "metadata": {
            "total_courses": len(all_nodes),
            "total_relationships": len(all_relationships),
            "breakdown": {
                "PREREQUISITE_FOR": sum(1 for r in all_relationships if r["type"] == "PREREQUISITE_FOR"),
                "RECOMMENDED_FOR": sum(1 for r in all_relationships if r["type"] == "RECOMMENDED_FOR"),
                "CO_REQUISITE_FOR": sum(1 for r in all_relationships if r["type"] == "CO_REQUISITE_FOR"),
            }
        },
        "nodes": list(all_nodes.values()),
        "relationships": all_relationships
    }
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    print("\n" + "="*50)
    print(" KẾT QUẢ TRÍCH XUẤT ĐỒ THỊ MÔN HỌC (BẰNG LLM):")
    print(f"  • Tổng số Môn học (Nodes): {len(all_nodes)}")
    print(f"  • Tổng số Quan hệ (Edges): {len(all_relationships)}")
    print(f"  • Đã gán thành công `source_locator` cho mọi nút và cạnh.")
    print(f"  • Lưu tại: {output_file}")
    print("="*50 + "\n")
    return result_data

if __name__ == "__main__":
    extract_curriculum_triplets()