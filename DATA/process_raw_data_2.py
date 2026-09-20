import os
import sys
import json
import glob
import re
import unicodedata

sys.stdout.reconfigure(encoding="utf-8")

URL_MAPPING = {
    "1259 QĐ điều chỉnh_HVu chung_2931_2026.signed.md": "https://drive.google.com/file/d/1B6_nkyM4jrXfPGgm2rYatxispHvOj8CI/view?pli=1",
    "1260 QĐ điều chỉnh_HVu Đại học_2933_2026.signed.md": "https://drive.google.com/file/d/1Qingbecnl6u4cGmayPmrELFkBIdYvVlr/view",
    "2024_MT_KHMT.md": "https://drive.google.com/file/d/1H5xt_kvNvykE2kRbvEzP9zqsi0Qq8Pyu/view",
    "2024_MT_KTMT.md": "https://drive.google.com/file/d/1NUbFT0jku_f95uRMir3T6POyV5c1NSE1/view",
    "474_TB Kết luận tại phiên họp Hội đồng học vụ ĐH  SĐH - HK241.md": "https://drive.google.com/file/d/1_WbN70-LwSEi_t5F_qjhZ56XcQ7Z7pN1/view",
    "Ket luan tai Phien hop Hoi dong hoc vu DH _ SDH HK242.signed.md": "https://drive.google.com/file/d/1KJ4RkhZQoh89-jA4Di3Sxl7o4Ex_qln1/view",
    "Kết luận HĐHV_HK251.signed.md": "https://drive.google.com/file/d/1ML1cRH8w8nSwKurWd5ZJ4zHPlwEfBUv9/view",
    "Kết luận HĐHV_HK251_bổ sung_29-01-2026.signed.md": "https://drive.google.com/file/d/1zM208Xqjvmxh1HF_l30YhmnQKxhuGkoI/view",
    "Kết luận HĐHV_HK252.signed.md": "https://drive.google.com/file/d/16I0a0bsIEzhgyjR1i516UoMceMaKIsOt/view",
    "Kết luận HĐHV_HK252_14-05-2026_ bổ sung.signed (1).md": "https://drive.google.com/file/d/1KJgCQHwYDz_JRb6mjQdhzRZZJ5j7dDjh/view",
    "2931_Quyết định ban hành Quy định chung về học vụ và đào tạo.md": "https://drive.google.com/file/d/13wBdNxD2PxO_Dwq4S5sbvfE10zwNKCjK/view",
    "2933_Quyết định ban hành Quy định học vụ và đào tạo bậc Đại học.md": "https://drive.google.com/file/d/1k68Nvfm8QUjC6Dry84PlE_ZzIeXtXmvN/view"
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DATA_DIR = os.path.join(BASE_DIR, "Raw_data_2")
OUTPUT_DIR = os.path.join(BASE_DIR, "output_2")
DOCS_OUT_DIR = os.path.join(OUTPUT_DIR, "documents")
PASSAGES_OUT_DIR = os.path.join(OUTPUT_DIR, "passages")

os.makedirs(DOCS_OUT_DIR, exist_ok=True)
os.makedirs(PASSAGES_OUT_DIR, exist_ok=True)

def remove_accents(input_str):
    input_str = input_str.replace("đ", "d").replace("Đ", "D")
    s1 = unicodedata.normalize('NFD', input_str)
    s2 = s1.encode('ascii', 'ignore').decode('utf-8')
    return s2

def clean_text(text, keep_newlines=False):
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    if keep_newlines:
        text = re.sub(r'[ \t]+', ' ', text)
    else:
        text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_issued_date(text):
    match1 = re.search(r'ngày\s+(\d{1,2})\s*(?:tháng|/)\s*(\d{1,2})\s*(?:năm|/|,)\s*(\d{4})', text, re.IGNORECASE)
    if match1:
        return f"{int(match1.group(3)):04d}-{int(match1.group(2)):02d}-{int(match1.group(1)):02d}"
    
    match2 = re.search(r'(\d{1,2})\s+tháng\s+(\d{1,2})\s*(?:năm|,)?\s*(\d{4})', text, re.IGNORECASE)
    if match2:
        return f"{int(match2.group(3)):04d}-{int(match2.group(2)):02d}-{int(match2.group(1)):02d}"
    
    match3 = re.search(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b', text)
    if match3:
        return f"{int(match3.group(3)):04d}-{int(match3.group(2)):02d}-{int(match3.group(1)):02d}"
        
    return None

BOILERPLATE_PATTERNS = [
    r"CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM",
    r"Độc lập\s*[–-]\s*Tự do\s*[–-]\s*Hạnh phúc",
    r"ĐẠI HỌC QUỐC GIA",
    r"TRƯỜNG ĐẠI HỌC BÁCH KHOA",
    r"^Số:\s*/?QĐ",
    r"^Thành phố Hồ Chí Minh,\s*ngày",
    r"^HIỆU TRƯỞNG TRƯỜNG ĐẠI HỌC BÁCH KHOA$",
]

def is_boilerplate(text):
    if len(text.strip()) < 30:
        return True
    for pat in BOILERPLATE_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False

def parse_curriculum_markdown_table(table_text):
    courses = []
    lines = table_text.split("\n")
    
    pattern = r"\|?\s*\d*\s*\|\s*([A-Z]{2}\d{4})\s*\|\s*([^|]+)\|\s*(\d+)\s*\|\s*([^|]*)\|"
    
    for line in lines:
        match = re.search(pattern, line)
        if match:
            course_code = match.group(1).strip()
            course_name = re.sub(r"<br>.*", "", match.group(2)).strip()
            credits = int(match.group(3).strip())
            prereq_raw = match.group(4).strip()
            
            prereqs = re.findall(r"([A-Z]{2}\d{4})\s*\((TQ|SH|KN)\)", prereq_raw)
            
            courses.append({
                "code": course_code,
                "name": course_name,
                "credits": credits,
                "conditions": [{"code": code, "type": rel_type} for code, rel_type in prereqs]
            })
    return courses

def parse_markdown(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    filename = os.path.basename(file_path)
    title = os.path.splitext(filename)[0]
    
    doc_id = remove_accents(title)
    doc_id = re.sub(r'[^a-zA-Z0-9]', '_', doc_id)
    doc_id = re.sub(r'_+', '_', doc_id).strip('_')
    
    document_type = "regulation"
    if "Quyết định" in title or "Quyet dinh" in doc_id:
        document_type = "decision"
    elif "Thông báo" in title or "Thong bao" in doc_id or "TB" in title:
        document_type = "notice"
    elif "Kết luận" in title or "Ket luan" in doc_id:
        document_type = "meeting_minutes"

    full_text = "".join(lines)
    issued_date = extract_issued_date(full_text)

    document = {
        "doc_id": doc_id,
        "title": title,
        "document_type": document_type,
        "source_url": URL_MAPPING.get(filename),
        "source_file": f"Raw_data_2/{filename}",
        "issued_date": issued_date,
        "effective_date": None,
        "scope": {
            "institution": "Trường Đại học Bách khoa - ĐHQG-HCM",
            "program": None,
            "study_mode": None,
            "cohorts": []
        }
    }

    passages = []
    order = 1
    section_path = []
    current_paragraph_lines = []
    
    def process_current_paragraph(start_line_idx):
        nonlocal order, current_paragraph_lines
        if not current_paragraph_lines:
            return
        
        raw_text_newlines = "\n".join(current_paragraph_lines)
        is_table = bool(re.search(r"\|.*\|.*\|", raw_text_newlines))
        
        raw_text = raw_text_newlines if is_table else " ".join(current_paragraph_lines)
        cleaned_text = clean_text(raw_text, keep_newlines=is_table)
        
        if cleaned_text and not is_boilerplate(cleaned_text):
            if is_table:
                courses = parse_curriculum_markdown_table(raw_text_newlines)
                if courses:
                    for course in courses:
                        passages.append({
                            "passage_id": f"{doc_id}_P{order:03d}",
                            "doc_id": doc_id,
                            "order": order,
                            "section_path": list(section_path),
                            "content_type": "course_entity",
                            "text": json.dumps(course, ensure_ascii=False),
                            "source_locator": f"line_{start_line_idx + 1}",
                            "review_status": "pending"
                        })
                        order += 1
                    current_paragraph_lines = []
                    return

            passages.append({
                "passage_id": f"{doc_id}_P{order:03d}",
                "doc_id": doc_id,
                "order": order,
                "section_path": list(section_path),
                "content_type": "paragraph",
                "text": cleaned_text,
                "source_locator": f"line_{start_line_idx + 1}",
                "review_status": "pending"
            })
            order += 1
        current_paragraph_lines = []

    paragraph_start_idx = 0
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            process_current_paragraph(paragraph_start_idx)
            paragraph_start_idx = i + 1
            continue
            
        heading_match = re.match(r'^(#+)\s+(.*)', line)
        numbered_match = re.match(r'^(\d+(\.\d+)*)\.?\s+(.*)', line)
        dieu_match = re.match(r'^(Điều\s+\d+[:\.])\s*(.*)', line, re.IGNORECASE)
        chuong_phan_match = re.match(r'^((?:Chương|Phần)\s+[IVX\d]+[:\.])\s*(.*)', line, re.IGNORECASE)
        roman_match = re.match(r'^([IVX]+)[\.\)]\s+(.*)', line)
        khoan_muc_match = re.match(r'^((?:Khoản|Mục)\s+\d+[:\.])\s*(.*)', line, re.IGNORECASE)
        letter_match = re.match(r'^([a-z])\)\s+(.*)', line)
        
        if heading_match or numbered_match or dieu_match or chuong_phan_match or roman_match or khoan_muc_match or letter_match:
            process_current_paragraph(paragraph_start_idx)
            
            level = 1
            heading_text = ""
            if heading_match:
                level = len(heading_match.group(1))
                heading_text = clean_text(heading_match.group(2))
            elif chuong_phan_match:
                level = 1
                heading_text = f"{chuong_phan_match.group(1)} {clean_text(chuong_phan_match.group(2))}".strip()
            elif roman_match:
                level = 1
                heading_text = f"{roman_match.group(1)}. {clean_text(roman_match.group(2))}".strip()
            elif dieu_match:
                level = 2
                heading_text = f"{dieu_match.group(1)} {clean_text(dieu_match.group(2))}".strip()
            elif numbered_match:
                number_str = numbered_match.group(1)
                level = len(number_str.split('.')) + 1
                heading_text = f"{number_str}. {clean_text(numbered_match.group(3))}"
            elif khoan_muc_match:
                level = 3
                heading_text = f"{khoan_muc_match.group(1)} {clean_text(khoan_muc_match.group(2))}".strip()
            elif letter_match:
                level = 4
                heading_text = f"{letter_match.group(1)}) {clean_text(letter_match.group(2))}".strip()
                
            if level <= len(section_path):
                section_path = section_path[:level-1]
            elif level > len(section_path) + 1:
                pass
                
            section_path.append(heading_text)
            paragraph_start_idx = i + 1
        else:
            current_paragraph_lines.append(line)
            
    process_current_paragraph(paragraph_start_idx)

    doc_out_path = os.path.join(DOCS_OUT_DIR, f"{doc_id}.json")
    passages_out_path = os.path.join(PASSAGES_OUT_DIR, f"{doc_id}.json")
    
    with open(doc_out_path, "w", encoding="utf-8") as f:
        json.dump(document, f, ensure_ascii=False, indent=2)
    with open(passages_out_path, "w", encoding="utf-8") as f:
        json.dump(passages, f, ensure_ascii=False, indent=2)
        
    print(f"Hoàn thành xử lý: {filename} -> {len(passages)} passages")

if __name__ == "__main__":
    print("Bắt đầu xử lý dữ liệu Raw_data_2...")
    md_files = glob.glob(os.path.join(RAW_DATA_DIR, "*.md"))
    for md_file in md_files:
        parse_markdown(md_file)
    print("Hoàn tất!")
