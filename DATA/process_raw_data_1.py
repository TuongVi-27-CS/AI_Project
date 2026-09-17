import os
import sys
import json
import glob
import re
from bs4 import BeautifulSoup
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PAGES_DIR = os.path.join(BASE_DIR, "pages")
DETAILS_DIR = os.path.join(BASE_DIR, "details")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DOCS_OUT_DIR = os.path.join(OUTPUT_DIR, "documents")
PASSAGES_OUT_DIR = os.path.join(OUTPUT_DIR, "passages")
os.makedirs(DOCS_OUT_DIR, exist_ok=True)
os.makedirs(PASSAGES_OUT_DIR, exist_ok=True)


def build_id_mapping():
    """Đọc thư mục pages/ để lấy map từ code sang id"""
    mapping = {}
    page_files = glob.glob(os.path.join(PAGES_DIR, "page-*.json"))
    for file_path in page_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "data" in data and "content" in data["data"]:
                    for item in data["data"]["content"]:
                        code = item.get("code")
                        item_id = item.get("id")
                        if code and item_id:
                            mapping[code] = item_id
        except Exception as e:
            print(f"Lỗi khi đọc file {file_path}: {e}")
    return mapping


def clean_html_text(raw_html):
    if not raw_html:
        return ""
    if isinstance(raw_html, str):
        raw_html = re.sub(r"</p>|<br\s*/?>", ".\n", raw_html, flags=re.IGNORECASE)
        soup = BeautifulSoup(raw_html, "html.parser")
        text = soup.get_text(separator=" ")
        text = re.sub(r"\s+", " ", text)
        text = text.replace(" .", ".")
        text = re.sub(r"\.+", ".", text)
        return text.strip()
    return str(raw_html)


def get_lang_text(obj, lang="vi"):
    if isinstance(obj, dict):
        return obj.get(lang, "")
    return obj if obj else ""


class PassageBuilder:
    def __init__(self, doc_id):
        self.doc_id = doc_id
        self.passages = []
        self.order = 1

    def add_passage(self, section_path, text, source_path, content_type="paragraph"):
        cleaned_text = clean_html_text(text)
        if not cleaned_text:
            return
        passage = {
            "passage_id": f"{self.doc_id}_P{self.order}",
            "doc_id": self.doc_id,
            "order": self.order,
            "section_path": section_path,
            "content_type": content_type,
            "text": cleaned_text,
            "source_locator": {"type": "json_field", "path": source_path},
            "review_status": "pending",
        }
        self.passages.append(passage)
        self.order += 1


def process_details(id_mapping):
    detail_files = glob.glob(os.path.join(DETAILS_DIR, "*.json"))
    processed_subjects = set()
    for file_path in detail_files:
        if file_path.endswith(".raw.json"):
            continue
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                print(f"Lỗi cú pháp JSON tại file: {file_path}")
                continue
        khoa_name = get_lang_text(data.get("khoa"))
        hockyapdung = data.get("hockyapdung", "")
        ma_mon_hoc = data.get("mamonhoc", "")
        doc_id = data.get("ma", "")
        if (
            not khoa_name
            or "Khoa Khoa Học và Kỹ Thuật Máy Tính" not in khoa_name
            and "Khoa Khoa học và Kỹ thuật Máy tính" not in khoa_name
            and "Faculty of Computer Science and Engineering"
            not in get_lang_text(data.get("khoa"), "en")
        ):
            continue
        if hockyapdung not in ["HK261", "HK262"]:
            continue
        if ma_mon_hoc in processed_subjects:
            print(
                f"Bỏ qua (Trùng lặp): {ma_mon_hoc} ở {hockyapdung} (Đã xử lý trước đó)"
            )
            continue
        processed_subjects.add(ma_mon_hoc)
        print(
            f"Đang xử lý: {doc_id} - Môn: {ma_mon_hoc} - {get_lang_text(data.get('ten'))}"
        )
        source_url = None
        if doc_id in id_mapping:
            source_url = f"https://mybk.hcmut.edu.vn/app/he-thong-quan-ly-dao-tao/dcmh-core/{id_mapping[doc_id]}"
        issued_date_str = data.get("capnhat")
        issued_date_formatted = None
        if issued_date_str:
            try:
                dt = datetime.strptime(issued_date_str, "%d/%m/%Y %H:%M")
                issued_date_formatted = dt.strftime("%Y-%m-%d")
            except ValueError:
                pass
        program_name = None
        if data.get("nganh") and len(data["nganh"]) > 0:
            program_name = get_lang_text(data["nganh"][0].get("ten"))
        study_mode = None
        if data.get("thongtinchung") and data["thongtinchung"].get("bacDaoTao"):
            study_mode = get_lang_text(data["thongtinchung"]["bacDaoTao"].get("ten"))
        document = {
            "doc_id": doc_id,
            "title": get_lang_text(data.get("ten")),
            "document_type": "course_syllabus",
            "source_url": source_url,
            "source_file": f"details/{os.path.basename(file_path)}",
            "issued_date": issued_date_formatted,
            "effective_date": None,
            "scope": {
                "institution": "Trường Đại học Bách khoa - ĐHQG-HCM",
                "program": program_name,
                "study_mode": study_mode,
                "cohorts": [hockyapdung],
            },
        }
        pb = PassageBuilder(doc_id)
        mndk = data.get("monhocdieukien")
        if mndk:
            pb.add_passage(["Môn học điều kiện"], mndk, "monhocdieukien")
        ttc = data.get("thongtinchung", {})
        ttc_keys = [
            ("mucTieuMonHoc", "Mục tiêu môn học"),
            ("noiDungTomTatMonHoc", "Nội dung tóm tắt môn học"),
            ("taiLieuHocTap", "Tài liệu học tập"),
            ("huongDanCachHoc", "Hướng dẫn cách học"),
            ("ghiChu", "Ghi chú"),
        ]
        for key, section_name in ttc_keys:
            val = ttc.get(key)
            if val:
                pb.add_passage(
                    ["Thông tin chung", section_name],
                    get_lang_text(val),
                    f"thongtinchung.{key}.vi",
                )
        pbsotc = data.get("pbsotc")
        pbsotiet = data.get("pbsotiet")
        time_text = []
        if pbsotc:
            time_text.append(f"Phân bổ tín chỉ: {pbsotc}")
        if pbsotiet:
            time_text.append(f"Phân bổ tiết: {pbsotiet}")
        if time_text:
            pb.add_passage(
                ["Phân bổ thời gian"], " | ".join(time_text), "pbsotc_pbsotiet"
            )
        cdr_list = data.get("cdr", [])
        for i, cdr in enumerate(cdr_list):
            ma_cdr = cdr.get("ma", f"L.O.{i}")
            ten_cdr = get_lang_text(cdr.get("ten"))
            pb.add_passage(
                ["Chuẩn đầu ra", ma_cdr],
                ten_cdr,
                f"cdr[{i}].ten.vi",
                content_type="list_item",
            )
        hddg = data.get("hddg")
        if isinstance(hddg, dict):
            for hddg_key, hddg_val in hddg.items():
                if hddg_val:
                    pb.add_passage(
                        ["Đánh giá kết quả học tập", hddg_key],
                        str(hddg_val),
                        f"hddg.{hddg_key}",
                    )
        elif isinstance(hddg, list):
            for i, item in enumerate(hddg):
                if isinstance(item, dict):
                    thanh_phan = get_lang_text(item.get("tenThanhPhan")) or item.get(
                        "ma", f"Item_{i}"
                    )
                    pb.add_passage(
                        ["Đánh giá kết quả học tập", thanh_phan],
                        str(item),
                        f"hddg[{i}]",
                    )
                else:
                    pb.add_passage(
                        ["Đánh giá kết quả học tập", f"Mục {i}"],
                        str(item),
                        f"hddg[{i}]",
                    )
        ndct_list = data.get("ndct", [])
        for i, session in enumerate(ndct_list):
            buoi = session.get("buoi", f"Buổi {i+1}")
            noidung = get_lang_text(session.get("noidung"))
            activities = []
            for j, chitiets in enumerate(session.get("chuandaurachitiet", [])):
                gv = get_lang_text(chitiets.get("hoatdonggiangvien"))
                sv = get_lang_text(chitiets.get("hoatdongsinhvien"))
                if gv:
                    activities.append(f"Hoạt động giảng viên: {gv}")
                if sv:
                    activities.append(f"Hoạt động sinh viên: {sv}")
            full_content = noidung + "\n" + "\n".join(activities)
            pb.add_passage(["Nội dung chi tiết", buoi], full_content, f"ndct[{i}]")
        lienhe = data.get("lienhe")
        if lienhe:
            pb.add_passage(["Thông tin liên hệ"], get_lang_text(lienhe), "lienhe")
        doc_out_path = os.path.join(DOCS_OUT_DIR, f"{doc_id}.json")
        passages_out_path = os.path.join(PASSAGES_OUT_DIR, f"{doc_id}.json")
        with open(doc_out_path, "w", encoding="utf-8") as f:
            json.dump(document, f, ensure_ascii=False, indent=2)
        with open(passages_out_path, "w", encoding="utf-8") as f:
            json.dump(pb.passages, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    print("Bắt đầu khởi chạy bộ chuyển đổi dữ liệu...")
    print(f"Thư mục nguồn: {DETAILS_DIR}")
    print(f"Thư mục đích: {OUTPUT_DIR}")
    print("-" * 50)
    mapping = build_id_mapping()
    print(f"Đã nạp {len(mapping)} liên kết ID từ pages.")
    process_details(mapping)
    print("-" * 50)
    print("HOÀN THÀNH!")
