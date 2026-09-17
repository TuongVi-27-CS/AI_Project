import os
import sys
import json
import glob
import shutil

sys.stdout.reconfigure(encoding="utf-8")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DETAILS_DIR = os.path.join(BASE_DIR, "details")
OUTPUT_RAW_DIR = os.path.join(BASE_DIR, "Raw_data")
os.makedirs(OUTPUT_RAW_DIR, exist_ok=True)


def get_lang_text(obj, lang="vi"):
    if isinstance(obj, dict):
        return obj.get(lang, "")
    return obj if obj else ""


def filter_and_copy():
    detail_files = glob.glob(os.path.join(DETAILS_DIR, "*.json"))
    processed_subjects = set()
    copied_count = 0
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
        print(f"Đã duyệt và Copy: {ma_mon_hoc} - {get_lang_text(data.get('ten'))}")
        file_name = os.path.basename(file_path)
        dest_path = os.path.join(OUTPUT_RAW_DIR, file_name)
        shutil.copy2(file_path, dest_path)
        copied_count += 1
    return copied_count


if __name__ == "__main__":
    print("Bắt đầu khởi chạy bộ lọc và copy file gốc...")
    print(f"Thư mục nguồn: {DETAILS_DIR}")
    print(f"Thư mục đích: {OUTPUT_RAW_DIR}")
    print("-" * 50)
    total_copied = filter_and_copy()
    print("-" * 50)
    print(
        f"HOÀN THÀNH! Tổng số file gốc (sạch) đã được copy vào Raw_data: {total_copied}"
    )
