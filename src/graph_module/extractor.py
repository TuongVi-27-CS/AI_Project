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
import re
from src.config.settings import RAW_DATA_1_DIR, OUTPUT_2_DIR, GRAPH_TRIPLETS_DIR

def clean_course_name(name_raw: str, code: str) -> str:
    '''
    Remove Course ID to avoid duplicate
    Ex: CO1005 - Nhập môn Điện toán -> Nhập môn Điện toán
    '''
    if not name_raw:
        return code
    name = str(name_raw).strip()
    if name.startswith(f"{code} - "):
        name = name[len(f"{code} - "):].strip()
    return name

def parse_credits(pbsotc_val) -> int:
    "Parse credits from pbsotc string."
    "4(3.1.4) → Trả về số nguyên 4."
    if not pbsotc_val:
        return 0
    match = re.match(r"^(\d+)", str(pbsotc_val).strip())
    return int(match.group(1)) if match else 0

def extract_curriculum_triplets():
    """
    Trích xuất toàn bộ dữ liệu về Môn học (Đỉnh - Nodes) và Mối quan hệ tiên quyết/song hành (Cạnh - Edges / Triplets) từ hai nguồn:
        Raw_data_1: 129 đề cương môn học chi tiết.
        output_2 (2024_MT_KHMT.json): hung chương trình đào tạo để nạp bổ sung các môn đại cương (Toán, Lý...) không nằm trong 129 đề cương trên.
    Return: Tạo ra file curriculum_graph.json chứa cấu trúc đồ thị
    """
    output_file = GRAPH_TRIPLETS_DIR / "curriculum_graph.json"
    os.makedirs(GRAPH_TRIPLETS_DIR, exist_ok=True)

    courses = {} #Dictionary (Key = course id) -> No dup
    relationships = [] #List of edges btw courses
    seen_rel = set() #set of relationship (source, type, target) -> No dup relationship (edge)

    #Process Raw_data_1 (129 de cuong)
    json_files = glob.glob(os.path.join(RAW_DATA_1_DIR, "*.json"))
    print(f"[*] Quét {len(json_files)} đề cương môn học từ: {RAW_DATA_1_DIR}")

    for file_path in json_files: # Đọc từng file đề cương
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        code = data.get("mamonhoc", "").strip().upper()
        if not code:
            continue

        ten_raw = data.get("ten", {})
        name_vi = ten_raw.get("vi", str(ten_raw)) if isinstance(ten_raw, dict) else str(ten_raw)
        credits = parse_credits(data.get("pbsotc"))

        if code not in courses or courses[code]["credits"] == 0:
            courses[code] = {
                "code": code,
                "name": clean_course_name(name_vi, code),
                "credits": credits
            }

        # Bóc tách quan hệ tiên quyết (TQ, SH, KN)
        for cond in data.get("monhocdieukien", []) or []:
            prereq_code = cond.get("mamonhoc", "").strip().upper()
            if not prereq_code:
                continue

            loai_dk = cond.get("maloaidieukien", "").strip().upper()
            rel_type = "PREREQUISITE_FOR" if loai_dk == "TQ" else ("CO_REQUISITE_FOR" if loai_dk == "SH" else "RECOMMENDED_FOR")

            rel_key = (prereq_code, rel_type, code)
            if rel_key not in seen_rel: # Nếu MQH chưa tồn tại
                seen_rel.add(rel_key)
                relationships.append({"source": prereq_code, "target": code, "type": rel_type})

            if prereq_code not in courses: #Nếu chưa có môn này trong đồ thị thì thêm vào
                p_name = cond.get("tenmonhoc_only", {}).get("vi", prereq_code)
                courses[prereq_code] = {"code": prereq_code, "name": clean_course_name(p_name, prereq_code), "credits": 0}

    # Process Raw_data_2 (CTDT 2024 - KHMT & KTMT)
    matrix_files = sorted(glob.glob(str(OUTPUT_2_DIR / "passages" / "*_MT_*.json")))
    print(f"[*] Quét {len(matrix_files)} khung chương trình đào tạo từ: {OUTPUT_2_DIR / 'passages'}")

    for m_file in matrix_files:
        print(f"  -> Nạp bổ sung từ: {os.path.basename(m_file)}")
        try:
            with open(m_file, "r", encoding="utf-8") as f:
                passages = json.load(f)
        except Exception as e:
            print(f"     [!] Lỗi khi đọc file {m_file}: {e}")
            continue

        for p in passages:
            if p.get("content_type") == "course_entity":
                try:
                    c_data = json.loads(p.get("text", "{}"))
                    c_code = c_data.get("code", "").strip().upper()
                    if not c_code:
                        continue

                    # Thêm hoặc cập nhật môn học
                    if c_code not in courses or courses[c_code]["credits"] == 0:
                        courses[c_code] = {
                            "code": c_code,
                            "name": clean_course_name(c_data.get("name", c_code), c_code),
                            "credits": c_data.get("credits", 0)
                        }
                    for cond in c_data.get("conditions", []):
                        p_code = cond.get("code", "").strip().upper()
                        rel_type = "PREREQUISITE_FOR" if cond.get("type") == "TQ" else "RECOMMENDED_FOR"
                        rel_key = (p_code, rel_type, c_code)
                        if rel_key not in seen_rel:
                            seen_rel.add(rel_key)
                            relationships.append({"source": p_code, "target": c_code, "type": rel_type})
                except Exception:
                    pass
    # 3. Ghi ra file JSON trung gian
    result_data = {
        "metadata": {
            "total_courses": len(courses),
            "total_relationships": len(relationships),
            "breakdown": {
                "PREREQUISITE_FOR": sum(1 for r in relationships if r["type"] == "PREREQUISITE_FOR"),
                "RECOMMENDED_FOR": sum(1 for r in relationships if r["type"] == "RECOMMENDED_FOR"),
                "CO_REQUISITE_FOR": sum(1 for r in relationships if r["type"] == "CO_REQUISITE_FOR"),
            }
        },
        "nodes": list(courses.values()),
        "relationships": relationships
    }
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)
    print("\n" + "="*50)
    print(" KẾT QUẢ TRÍCH XUẤT ĐỒ THỊ MÔN HỌC:")
    print(f"  • Tổng số Môn học (Nodes): {len(courses)}")
    print(f"  • Tổng số Quan hệ (Edges): {len(relationships)}")
    print(f"    - Tiên quyết (PREREQUISITE_FOR): {result_data['metadata']['breakdown']['PREREQUISITE_FOR']}")
    print(f"    - Khuyến nghị (RECOMMENDED_FOR): {result_data['metadata']['breakdown']['RECOMMENDED_FOR']}")
    print(f"    - Song hành (CO_REQUISITE_FOR):  {result_data['metadata']['breakdown']['CO_REQUISITE_FOR']}")
    print(f"  • Lưu tại: {output_file}")
    print("="*50 + "\n")
    return result_data

if __name__ == "__main__":
    extract_curriculum_triplets()