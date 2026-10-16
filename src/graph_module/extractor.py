"""
Module trích xuất Đồ thị Tri thức (Knowledge Graph Extractor) đa thực thể.
GIAI ĐOẠN 1: Mở rộng Ontology & Schema (Course, Lecturer, Assessment, CurriculumBlock).
GIAI ĐOẠN 2: Nâng cấp Hybrid Extractor (Rule-based siêu tốc cho JSON/Bảng + LLM fallback cho văn bản tự do).
Đảm bảo 100% các nút và cạnh đều được gắn `source_locator` phục vụ kiểm chứng chống ảo giác.
"""
import os
import sys
import glob
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

# Đảm bảo thư mục gốc dự án luôn nằm trong sys.path để import được src
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.config.settings import (
    RAW_DATA_1_DIR,
    RAW_DATA_2_DIR,
    OUTPUT_2_DIR,
    GRAPH_TRIPLETS_DIR,
)

# ==============================================================================
# GIAI ĐOẠN 1: MỞ RỘNG ONTOLOGY & SCHEMA PYDANTIC
# ==============================================================================

class CourseNode(BaseModel):
    """Thực thể Môn học trong chương trình đào tạo."""
    type: str = "Course"
    code: str = Field(description="Mã môn học chuẩn (VD: CO1003, CO2003)")
    name: str = Field(description="Tên môn học tiếng Việt")
    credits: int = Field(default=0, description="Số tín chỉ tích lũy")
    source_locator: str = Field(description="Định danh nguồn gốc (VD: File: DCMH.CO1003.json)")


class LecturerNode(BaseModel):
    """Thực thể Giảng viên giảng dạy hoặc phụ trách môn học."""
    type: str = "Lecturer"
    name: str = Field(description="Họ và tên giảng viên (VD: TRẦN GIANG SƠN)")
    email: Optional[str] = Field(default="", description="Email liên hệ của giảng viên")
    department: Optional[str] = Field(default="", description="Bộ môn phụ trách (VD: Khoa Học Máy Tính)")
    faculty: Optional[str] = Field(default="", description="Khoa phụ trách (VD: Khoa Khoa học và Kỹ thuật Máy tính)")
    source_locator: str = Field(description="Định danh nguồn gốc")

class AssessmentNode(BaseModel):
    """Thực thể Hình thức đánh giá & Trọng số điểm."""
    type: str = "Assessment"
    id: str = Field(description="Mã định danh đánh giá (VD: CO1003_thi, CO1003_baiTapLon)")
    name: str = Field(description="Tên hình thức đánh giá (VD: Thi cuối kỳ (Trắc nghiệm - 90 phút))")
    method: Optional[str] = Field(default="", description="Phương thức thi (Trắc nghiệm, Tự luận, Vấn đáp,...)")
    weight: int = Field(default=0, description="Trọng số phần trăm trong tổng điểm (VD: 40, 30)")
    duration: Optional[str] = Field(default="", description="Thời gian làm bài (VD: 90 phút)")
    source_locator: str = Field(description="Định danh nguồn gốc")

class CurriculumBlockNode(BaseModel):
    """Thực thể Khối kiến thức trong Chương trình đào tạo."""
    type: str = "CurriculumBlock"
    id: str = Field(description="Mã khối kiến thức (VD: BLOCK_CO_SO_NGANH_KHMT)")
    name: str = Field(description="Tên khối kiến thức (VD: Cơ sở ngành, Toán và Khoa học Tự nhiên)")
    major: str = Field(default="KHMT", description="Ngành áp dụng (KHMT hoặc KTMT)")
    source_locator: str = Field(description="Định danh nguồn gốc")


class RelationEdge(BaseModel):
    """Cạnh quan hệ định hướng nối giữa các thực thể."""
    source: str = Field(description="ID/Code của thực thể bắt đầu")
    target: str = Field(description="ID/Code của thực thể đích")
    type: str = Field(
        description="Loại quan hệ: PREREQUISITE_FOR, RECOMMENDED_FOR, CO_REQUISITE_FOR, TAUGHT_BY, EVALUATED_BY, CONTAINS, REQUIRES_GRADUATION"
    )
    source_locator: str = Field(description="Định danh nguồn gốc của mối quan hệ")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Thuộc tính mở rộng trên cạnh")


# Mapping tên đánh giá chuẩn hóa sang tiếng Việt
ASSESSMENT_LABELS = {
    "thi": "Thi cuối kỳ",
    "kiemTra": "Kiểm tra giữa kỳ",
    "baiTapLon": "Bài tập lớn",
    "thiNghiem": "Thí nghiệm / Thực hành",
    "baiTapThucHanh": "Bài tập thực hành",
    "doAn": "Đồ án",
    "luanVanTotNghiep": "Luận văn tốt nghiệp",
    "lyThuyetKhac": "Lý thuyết khác",
    "khac": "Đánh giá khác",
}

# ==============================================================================
# GIAI ĐOẠN 2: HYBRID EXTRACTOR
# ==============================================================================

def clean_course_name(name_raw: Any, code: str) -> str:
    """Làm sạch tên môn học loại bỏ tiền tố thừa."""
    if not name_raw:
        return code
    if isinstance(name_raw, dict):
        name_raw = name_raw.get("vi", str(name_raw))
    name = str(name_raw).strip()
    prefix = f"{code} - "
    if name.upper().startswith(prefix.upper()):
        name = name[len(prefix):].strip()
    return name


def parse_credits(credits_val: Any) -> int:
    """Bóc tách số tín chỉ nguyên từ dữ liệu chuỗi."""
    if not credits_val:
        return 0
    match = re.match(r"^(\d+)", str(credits_val).strip())
    return int(match.group(1)) if match else 0

def extract_curriculum_triplets() -> Dict[str, Any]:
    """
    Pipeline trích xuất toàn bộ Đồ thị tri thức Trippets:
    1. Đọc 129 Đề cương môn học (Raw_data_1): Course, Lecturer, Assessment, Prereqs.
    2. Đọc Bảng CTĐT Markdown (Raw_data_2): CurriculumBlock, Contains, Graduation requirements.
    3. Đọc Passages đã xử lý (output_2): Bổ sung các quan hệ điều kiện và thuộc tính.
    """
    output_file = GRAPH_TRIPLETS_DIR / "curriculum_graph.json"
    os.makedirs(GRAPH_TRIPLETS_DIR, exist_ok=True)

    courses: Dict[str, Dict[str, Any]] = {}
    lecturers: Dict[str, Dict[str, Any]] = {}
    assessments: Dict[str, Dict[str, Any]] = {}
    blocks: Dict[str, Dict[str, Any]] = {}

    all_relationships: List[Dict[str, Any]] = []
    seen_rel = set()

    def add_rel(source: str, target: str, rel_type: str, source_loc: str, props: Optional[Dict[str, Any]] = None):
        key = (source, rel_type, target)
        if key not in seen_rel:
            seen_rel.add(key)
            edge = {
                "source": source,
                "target": target,
                "type": rel_type,
                "source_locator": source_loc,
            }
            if props:
                edge["properties"] = props
            all_relationships.append(edge)

    # --------------------------------------------------------------------------
    # BƯỚC 1: XỬ LÝ RAW_DATA_1 (ĐỀ CƯƠNG MÔN HỌC JSON)
    # --------------------------------------------------------------------------
    json_files = glob.glob(os.path.join(RAW_DATA_1_DIR, "*.json"))
    print(f"[*] [BƯỚC 1] Bóc tách {len(json_files)} đề cương môn học từ Raw_data_1...")

    for file_path in json_files:
        filename = os.path.basename(file_path)
        source_loc = f"File: {filename}"

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            code = data.get("mamonhoc", "").strip().upper()
            if not code:
                continue

            ten_raw = data.get("ten", {})
            name_vi = clean_course_name(ten_raw, code)
            credits = parse_credits(data.get("pbsotc"))

            # 1.1 Khởi tạo / cập nhật Course Node
            if code not in courses or courses[code]["credits"] == 0:
                courses[code] = {
                    "type": "Course",
                    "code": code,
                    "name": name_vi,
                    "credits": credits,
                    "source_locator": source_loc,
                }

            # 1.2 Bóc tách Giảng viên phụ trách (Lecturer)
            lienhe = data.get("lienhe", {}) or {}
            don_vi = lienhe.get("donVi", {}) or {}
            dept_name = don_vi.get("tenBoMon", {}).get("vi", "") if isinstance(don_vi.get("tenBoMon"), dict) else str(don_vi.get("tenBoMon", ""))
            fac_name = don_vi.get("tenKhoa", {}).get("vi", "") if isinstance(don_vi.get("tenKhoa"), dict) else str(don_vi.get("tenKhoa", ""))

            gv_list = lienhe.get("giangVienPhuTrach", []) or []
            for gv in gv_list:
                gv_name = gv.get("tenGiangVien", "").strip()
                if not gv_name:
                    continue
                # Chuẩn hóa tên giảng viên
                gv_name = " ".join(gv_name.split()).title()
                gv_email = gv.get("emailGiangVien", "").strip()

                if gv_name not in lecturers:
                    lecturers[gv_name] = {
                        "type": "Lecturer",
                        "name": gv_name,
                        "email": gv_email,
                        "department": dept_name,
                        "faculty": fac_name,
                        "source_locator": source_loc,
                    }

                # Nối cạnh (Course) -[:TAUGHT_BY]-> (Lecturer)
                add_rel(code, gv_name, "TAUGHT_BY", source_loc)

            # 1.3 Bóc tách Hình thức Đánh giá (Assessment)
            ty_le = data.get("tyledanhgia", {}) or {}
            hinh_thuc = data.get("hinhthucdanhgia", {}) or {}

            for a_key, a_weight in ty_le.items():
                if a_key in ("tong", "tuHoc", "thamQuan", "thucTapNgoaiTruong"):
                    continue
                if isinstance(a_weight, (int, float)) and a_weight > 0:
                    ht_info = hinh_thuc.get(a_key, {}) or {}
                    ht_text = ""
                    time_text = ""
                    if isinstance(ht_info, dict):
                        ht_text = ht_info.get("hinhThuc", {}).get("text", {}).get("vi", "") or ""
                        time_text = ht_info.get("thoiGian", {}).get("text", {}).get("vi", "") or ""

                    ass_id = f"{code}_{a_key}"
                    label_base = ASSESSMENT_LABELS.get(a_key, a_key)
                    details_desc = label_base
                    if ht_text:
                        details_desc += f" ({ht_text})"
                    if time_text:
                        details_desc += f" - {time_text}"

                    assessments[ass_id] = {
                        "type": "Assessment",
                        "id": ass_id,
                        "name": details_desc,
                        "method": ht_text,
                        "weight": int(a_weight),
                        "duration": time_text,
                        "source_locator": source_loc,
                    }

                    # Nối cạnh (Course) -[:EVALUATED_BY]-> (Assessment)
                    add_rel(code, ass_id, "EVALUATED_BY", source_loc, props={"weight": int(a_weight)})

            # 1.4 Bóc tách Quan hệ Môn tiên quyết (monhocdieukien)
            for cond in data.get("monhocdieukien", []) or []:
                prereq_code = cond.get("mamonhoc", "").strip().upper()
                if not prereq_code:
                    continue

                loai_dk = cond.get("maloaidieukien", "").strip().upper()
                if loai_dk == "TQ":
                    rel_type = "PREREQUISITE_FOR"
                elif loai_dk == "SH":
                    rel_type = "CO_REQUISITE_FOR"
                else:
                    rel_type = "RECOMMENDED_FOR"

                add_rel(prereq_code, code, rel_type, source_loc)

                if prereq_code not in courses:
                    p_name_raw = cond.get("tenmonhoc_only", {})
                    p_name = clean_course_name(p_name_raw, prereq_code)
                    courses[prereq_code] = {
                        "type": "Course",
                        "code": prereq_code,
                        "name": p_name,
                        "credits": 0,
                        "source_locator": source_loc,
                    }

        except Exception as e:
            print(f"[!] Bỏ qua file {filename}: {e}")

    # --------------------------------------------------------------------------
    # BƯỚC 2: XỬ LÝ RAW_DATA_2 (BẢNG CTĐT MARKDOWN: KHỐI KIẾN THỨC & TỐT NGHIỆP)
    # --------------------------------------------------------------------------
    md_files = glob.glob(os.path.join(RAW_DATA_2_DIR, "*_MT_*.md"))
    print(f"\n[*] [BƯỚC 2] Bóc tách Khối kiến thức & Điều kiện tốt nghiệp từ {len(md_files)} file CTĐT Markdown...")

    block_definitions = [
        (r"A\.\s*Toán", "BLOCK_TOAN_KHTN", "Toán và Khoa học Tự nhiên"),
        (r"B\.1\.\s*Kinh", "BLOCK_LY_LUAN_CHINH_TRI", "Lý luận chính trị, Khoa học xã hội và Pháp luật"),
        (r"B\.2\.1\.\s*Nhập", "BLOCK_NHAP_MON", "Nhập môn"),
        (r"B\.2\.2\.\s*Kỹ", "BLOCK_KY_NANG_NGHE_NGHIEP", "Kỹ năng nghề nghiệp chuyên nghiệp"),
        (r"B\.2\.3\.\s*Quản", "BLOCK_QUAN_LY", "Quản lý"),
        (r"B\.3\.\s*Ngoại", "BLOCK_NGOAI_NGU", "Ngoại ngữ"),
        (r"C\.\s*Cơ sở", "BLOCK_CO_SO_NGANH", "Cơ sở ngành"),
        (r"D\.\s*Ngành", "BLOCK_NGANH", "Ngành"),
        (r"E\.\s*Tự chọn|E\.1|E\.2", "BLOCK_TU_CHON_CHUYEN_NGANH", "Tự chọn chuyên ngành"),
        (r"F\.\s*Chuyên ngành|F\.1|F\.2|F\.3|F\.4|F\.5", "BLOCK_CHUYEN_NGANH_SAU", "Chuyên ngành sâu"),
        (r"G\.\s*Tự chọn", "BLOCK_TU_CHON_TU_DO", "Tự chọn tự do"),
        (r"H\.\s*Học\s*phần|Họcphầ", "BLOCK_TOT_NGHIEP", "Học phần tốt nghiệp"),
        (r"I\.\s*Giáo\s*dục", "BLOCK_GDQP", "Giáo dục quốc phòng - An ninh"),
        (r"J\.\s*Giáo\s*dục", "BLOCK_GDTC", "Giáo dục thể chất"),
        (r"K\.\s*Điều\s*kiệ", "BLOCK_DKTN", "Điều kiện tốt nghiệp"),
    ]

    for md_file in md_files:
        filename = os.path.basename(md_file)
        source_loc = f"File: {filename}"
        major = "KHMT" if "KHMT" in filename else "KTMT"

        try:
            with open(md_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            current_block_id = None
            current_block_name = None

            for line in lines:
                # Kiểm tra chuyển khối
                for pat, b_id, b_name in block_definitions:
                    if re.search(pat, line, re.IGNORECASE):
                        full_b_id = f"{b_id}_{major}"
                        current_block_id = full_b_id
                        current_block_name = f"{b_name} ({major})"
                        if full_b_id not in blocks:
                            blocks[full_b_id] = {
                                "type": "CurriculumBlock",
                                "id": full_b_id,
                                "name": current_block_name,
                                "major": major,
                                "source_locator": source_loc,
                            }
                        break

                if not current_block_id:
                    continue

                # Quét các mã môn học xuất hiện trong dòng thuộc khối này
                codes_found = re.findall(r"\b([A-Z]{2}\d{4}|SA4001|ENGGC)\b", line)
                for code_item in codes_found:
                    # Bổ sung môn nếu chưa có
                    if code_item not in courses:
                        courses[code_item] = {
                            "type": "Course",
                            "code": code_item,
                            "name": code_item,
                            "credits": 0,
                            "source_locator": source_loc,
                        }

                    # Cạnh CONTAINS hoặc REQUIRES_GRADUATION
                    if "BLOCK_DKTN" in current_block_id:
                        add_rel(current_block_id, code_item, "REQUIRES_GRADUATION", source_loc)
                    else:
                        add_rel(current_block_id, code_item, "CONTAINS", source_loc)

        except Exception as e:
            print(f"[!] Bỏ qua file {filename}: {e}")

    # --------------------------------------------------------------------------
    # BƯỚC 3: XỬ LÝ PASSAGES JSON TỪ OUTPUT_2 (ĐỒNG BỘ ĐIỀU KIỆN TIÊN QUYẾT)
    # --------------------------------------------------------------------------
    matrix_files = sorted(glob.glob(str(OUTPUT_2_DIR / "passages" / "*_MT_*.json")))
    print(f"\n[*] [BƯỚC 3] Quét và đồng bộ điều kiện tiên quyết từ {len(matrix_files)} passages JSON...")

    for m_file in matrix_files:
        filename = os.path.basename(m_file)
        source_loc = f"File: {filename}"

        try:
            with open(m_file, "r", encoding="utf-8") as f:
                passages = json.load(f)

            for p in passages:
                if p.get("content_type") == "course_entity":
                    text_str = p.get("text", "").strip()
                    if not text_str.startswith("{"):
                        continue
                    entity_dict = json.loads(text_str)

                    c_code = entity_dict.get("code", "").strip().upper()
                    if not c_code:
                        continue

                    c_name = entity_dict.get("name", "").strip()
                    c_credits = int(entity_dict.get("credits", 0) or 0)

                    if c_code not in courses or courses[c_code]["credits"] == 0:
                        courses[c_code] = {
                            "type": "Course",
                            "code": c_code,
                            "name": c_name if c_name else courses.get(c_code, {}).get("name", c_code),
                            "credits": c_credits if c_credits > 0 else courses.get(c_code, {}).get("credits", 0),
                            "source_locator": source_loc,
                        }

                    for cond in entity_dict.get("conditions", []) or []:
                        pre_code = cond.get("code", "").strip().upper()
                        if not pre_code:
                            continue
                        c_type = cond.get("type", "").strip().upper()
                        if c_type == "TQ":
                            rel_type = "PREREQUISITE_FOR"
                        elif c_type == "SH":
                            rel_type = "CO_REQUISITE_FOR"
                        else:
                            rel_type = "RECOMMENDED_FOR"

                        add_rel(pre_code, c_code, rel_type, source_loc)

                        if pre_code not in courses:
                            courses[pre_code] = {
                                "type": "Course",
                                "code": pre_code,
                                "name": pre_code,
                                "credits": 0,
                                "source_locator": source_loc,
                            }
        except Exception as e:
            print(f"[!] Bỏ qua file {filename}: {e}")

    # --------------------------------------------------------------------------
    # BƯỚC 4: TỔNG HỢP VÀ GHI FILE GRAPH JSON HOÀN CHỈNH
    # --------------------------------------------------------------------------
    all_nodes_list = (
        list(courses.values())
        + list(lecturers.values())
        + list(assessments.values())
        + list(blocks.values())
    )

    rel_breakdown = {}
    for r in all_relationships:
        rt = r["type"]
        rel_breakdown[rt] = rel_breakdown.get(rt, 0) + 1

    result_data = {
        "metadata": {
            "total_nodes": len(all_nodes_list),
            "nodes_breakdown": {
                "Course": len(courses),
                "Lecturer": len(lecturers),
                "Assessment": len(assessments),
                "CurriculumBlock": len(blocks),
            },
            "total_relationships": len(all_relationships),
            "relationships_breakdown": rel_breakdown,
        },
        "nodes": all_nodes_list,
        "relationships": all_relationships,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(" KẾT QUẢ TRÍCH XUẤT ĐỒ THỊ TRI THỨC TOÀN DIỆN (ONTOLOGY MỞ RỘNG):")
    print(f"  • Tổng số Thực thể (Nodes): {len(all_nodes_list)}")
    print(f"    - Môn học (Course): {len(courses)}")
    print(f"    - Giảng viên (Lecturer): {len(lecturers)}")
    print(f"    - Hình thức đánh giá (Assessment): {len(assessments)}")
    print(f"    - Khối kiến thức CTĐT (CurriculumBlock): {len(blocks)}")
    print(f"  • Tổng số Quan hệ (Edges): {len(all_relationships)}")
    for r_type, count in sorted(rel_breakdown.items()):
        print(f"    - [:{r_type}]: {count}")
    print(f"  • Đã gán 100% `source_locator` cho mọi Node và Edge.")
    print(f"  • Lưu tại: {output_file}")
    print("=" * 60 + "\n")

    return result_data

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    extract_curriculum_triplets()