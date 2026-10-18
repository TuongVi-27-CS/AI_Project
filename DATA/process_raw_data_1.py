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
DETAILS_DIR = os.path.join(BASE_DIR, "raw", "Raw_data_1")
if not os.path.exists(DETAILS_DIR):
    DETAILS_DIR = os.path.join(BASE_DIR, "Raw_data_1")

OUTPUT_DIR = os.path.join(BASE_DIR, "processed", "output_1")
DOCS_OUT_DIR = os.path.join(OUTPUT_DIR, "documents")
PASSAGES_OUT_DIR = os.path.join(OUTPUT_DIR, "passages")
os.makedirs(DOCS_OUT_DIR, exist_ok=True)
os.makedirs(PASSAGES_OUT_DIR, exist_ok=True)


def build_id_mapping():
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
    if not detail_files:
        print(f"LỖI: Không tìm thấy tệp JSON nào trong {DETAILS_DIR}")
        sys.exit(1)

    processed_subjects = set()
    cdr_anomaly_count = 0

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
            print(f"Bỏ qua (Trùng lặp): {ma_mon_hoc} ở {hockyapdung} (Đã xử lý trước đó)")
            continue
        processed_subjects.add(ma_mon_hoc)

        source_url = None
        if doc_id in id_mapping:
            source_url = f"https://mybk.hcmut.edu.vn/app/he-thong-quan-ly-dao-tao/dcmh-core/{id_mapping[doc_id]}"

        # V06: Metadata - distinguish updated_at vs issued_date
        updated_at_str = data.get("capnhat")
        updated_at_formatted = None
        if updated_at_str:
            try:
                dt = datetime.strptime(updated_at_str, "%d/%m/%Y %H:%M")
                updated_at_formatted = dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

        # V06: Preserve all majors/specialties, not only the first
        all_nganh = []
        if data.get("nganh") and isinstance(data["nganh"], list):
            for ng in data["nganh"]:
                ten_ng = get_lang_text(ng.get("ten"))
                if ten_ng and ten_ng not in all_nganh:
                    all_nganh.append(ten_ng)
        program_name = "; ".join(all_nganh) if all_nganh else "Khoa Khoa học và Kỹ thuật Máy tính"

        study_level = None
        if data.get("thongtinchung") and data["thongtinchung"].get("bacDaoTao"):
            study_level = get_lang_text(data["thongtinchung"]["bacDaoTao"].get("ten"))
        study_mode = f"Chính quy ({study_level})" if study_level else "Chính quy"

        # V06: cohorts should be admission cohorts, not semester (HK261/HK262)
        document = {
            "doc_id": doc_id,
            "title": get_lang_text(data.get("ten")),
            "document_type": "course_syllabus",
            "source_url": source_url,
            "source_file": f"Raw_data_1/{os.path.basename(file_path)}",
            "issued_date": None,
            "updated_at": updated_at_formatted,
            "effective_date": None,
            "scope": {
                "institution": "Trường Đại học Bách khoa - ĐHQG-HCM",
                "program": program_name,
                "study_mode": study_mode,
                "cohorts": [],
            },
        }

        pb = PassageBuilder(doc_id)

        # 1. Môn học điều kiện
        mndk = data.get("monhocdieukien")
        if mndk and isinstance(mndk, list):
            cond_sentences = []
            for cond in mndk:
                loai = cond.get("tenloaidieukien", {}).get("vi", "Điều kiện")
                ma_mon = cond.get("mamonhoc", "")
                ten_mon = cond.get("tenmonhoc_only", {}).get("vi", "")
                cond_sentences.append(f"{loai}: {ma_mon} - {ten_mon}")
            natural_text = "Môn học điều kiện:\n" + "\n".join(f"- {s}" for s in cond_sentences)
            pb.add_passage(["Môn học điều kiện"], natural_text, "monhocdieukien")

        # 2. Thông tin chung
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

        # 3. V07: Phân bổ thời gian (tách riêng pbsotc và pbsotiet với locator hợp lệ)
        pbsotc = data.get("pbsotc")
        pbsotiet = data.get("pbsotiet")
        if pbsotc:
            pb.add_passage(["Phân bổ thời gian", "Tín chỉ"], f"Phân bổ tín chỉ: {pbsotc}", "pbsotc")
        if pbsotiet:
            pb.add_passage(["Phân bổ thời gian", "Số tiết"], f"Phân bổ tiết: {pbsotiet}", "pbsotiet")

        # 4. V04: Tỷ lệ đánh giá (tyledanhgia)
        tyledanhgia = data.get("tyledanhgia")
        if tyledanhgia and isinstance(tyledanhgia, dict):
            labels = {
                "baiTapLon": "Bài tập lớn",
                "kiemTra": "Kiểm tra",
                "thi": "Thi",
                "khac": "Khác",
                "baiTapThucHanh": "Bài tập thực hành",
                "thiNghiem": "Thí nghiệm",
                "doAn": "Đồ án",
                "thamQuan": "Tham quan",
                "thucTapNgoaiTruong": "Thực tập ngoài trường",
                "luanVanTotNghiep": "Luận văn tốt nghiệp",
                "tuHoc": "Tự học",
                "lyThuyetKhac": "Lý thuyết khác",
                "tong": "Tổng cộng",
            }
            tyle_lines = []
            for k, label in labels.items():
                if k in tyledanhgia and tyledanhgia[k] is not None:
                    val = tyledanhgia[k]
                    if val > 0 or k == "tong":
                        tyle_lines.append(f"- {label}: {val}%")
            if tyle_lines:
                pb.add_passage(
                    ["Đánh giá kết quả học tập", "Tỷ lệ đánh giá"],
                    "Tỷ lệ đánh giá môn học:\n" + "\n".join(tyle_lines),
                    "tyledanhgia",
                )

        # 5. V04: Hình thức và thời lượng đánh giá (hinhthucdanhgia)
        hinhthucdanhgia = data.get("hinhthucdanhgia")
        if hinhthucdanhgia and isinstance(hinhthucdanhgia, dict):
            ht_labels = {
                "kiemTra": "Kiểm tra giữa kỳ",
                "thi": "Thi cuối kỳ",
                "khac": "Đánh giá khác",
            }
            ht_lines = []
            for k, label in ht_labels.items():
                info = hinhthucdanhgia.get(k)
                if isinstance(info, dict):
                    ht_text = info.get("hinhThuc", {}).get("text", {}).get("vi")
                    tg_text = info.get("thoiGian", {}).get("text", {}).get("vi")
                    tg_num = info.get("thoiGian", {}).get("thoigian")
                    if not tg_text and tg_num:
                        tg_text = f"{tg_num} phút"
                    details = []
                    if ht_text:
                        details.append(f"Hình thức: {ht_text}")
                    if tg_text:
                        details.append(f"Thời gian: {tg_text}")
                    if details:
                        ht_lines.append(f"- {label}: " + ", ".join(details))
            if ht_lines:
                pb.add_passage(
                    ["Đánh giá kết quả học tập", "Hình thức và thời lượng đánh giá"],
                    "Hình thức và thời lượng kiểm tra/thi:\n" + "\n".join(ht_lines),
                    "hinhthucdanhgia",
                )

        # 6. V05: Chuẩn đầu ra (ghi nhận cảnh báo nếu gặp 14 chuẩn đầu ra lặp)
        cdr_list = data.get("cdr", [])
        if len(cdr_list) == 14 and any("Năm CTĐT 2019" in str(c.get("ten", "")) for c in cdr_list):
            cdr_anomaly_count += 1

        for i, cdr in enumerate(cdr_list):
            ma_cdr = cdr.get("ma", f"L.O.{i}")
            ten_cdr = get_lang_text(cdr.get("ten"))
            pb.add_passage(
                ["Chuẩn đầu ra", ma_cdr],
                ten_cdr,
                f"cdr[{i}].ten.vi",
                content_type="list_item",
            )

        # 7. Hoạt động đánh giá chi tiết
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
                    thanh_phan = get_lang_text(item.get("tenThanhPhan")) or item.get("ma", f"Item_{i}")
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

        # 8. Nội dung chi tiết
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

        # 9. Thông tin liên hệ
        lienhe = data.get("lienhe")
        if lienhe:
            pb.add_passage(["Thông tin liên hệ"], get_lang_text(lienhe), "lienhe")

        doc_out_path = os.path.join(DOCS_OUT_DIR, f"{doc_id}.json")
        passages_out_path = os.path.join(PASSAGES_OUT_DIR, f"{doc_id}.json")
        with open(doc_out_path, "w", encoding="utf-8") as f:
            json.dump(document, f, ensure_ascii=False, indent=2)
        with open(passages_out_path, "w", encoding="utf-8") as f:
            json.dump(pb.passages, f, ensure_ascii=False, indent=2)

    print(f"Hoàn thành xử lý {len(processed_subjects)} đề cương môn học!")
    if cdr_anomaly_count > 0:
        print(f"Cảnh báo V05: Phát hiện {cdr_anomaly_count} đề cương có bộ chuẩn đầu ra tiếng Anh lặp từ nguồn dữ liệu thô.")


if __name__ == "__main__":
    print("Bắt đầu khởi chạy bộ chuyển đổi dữ liệu Raw_data_1...")
    mapping = build_id_mapping()
    process_details(mapping)
    print("HOÀN THÀNH!")
