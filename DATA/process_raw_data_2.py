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
RAW_DATA_DIR = os.path.join(BASE_DIR, "raw", "Raw_data_2")
if not os.path.exists(RAW_DATA_DIR):
    RAW_DATA_DIR = os.path.join(BASE_DIR, "Raw_data_2")

OUTPUT_DIR = os.path.join(BASE_DIR, "processed", "output_2")
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


def extract_issued_date(text, filename=""):
    # 1. Date explicitly in filename (e.g. 29-01-2026, 14-05-2026)
    m_file = re.search(r'(\d{2})-(\d{2})-(\d{4})', filename)
    if m_file:
        return f"{m_file.group(3)}-{m_file.group(2)}-{m_file.group(1)}"

    # 2. Check header section (first 1000 characters) for official signing date
    header = text[:1000]
    
    # OCR split pattern: "năm 2026_ 16 03" or "năm 2025_ 09 05"
    m_split = re.search(r'năm\s*(\d{4})[_\s]*(\d{1,2})\s+(\d{1,2})', header, re.IGNORECASE)
    if m_split:
        return f"{int(m_split.group(1)):04d}-{int(m_split.group(3)):02d}-{int(m_split.group(2)):02d}"

    # Pattern: "ngày ... tháng_ 16 03 _năm 2026_"
    m_split2 = re.search(r'ngày[_\s]*tháng[_\s]*(\d{1,2})\s+(\d{1,2})[_\s]*năm\s*(\d{4})', header, re.IGNORECASE)
    if m_split2:
        return f"{int(m_split2.group(3)):04d}-{int(m_split2.group(2)):02d}-{int(m_split2.group(1)):02d}"

    # Header signing: "Thành phố Hồ Chí Minh, ngày DD tháng MM năm YYYY"
    m_hcm = re.search(r'Thành phố Hồ Chí Minh,\s*ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})', header, re.IGNORECASE)
    if m_hcm:
        return f"{int(m_hcm.group(3)):04d}-{int(m_hcm.group(2)):02d}-{int(m_hcm.group(1)):02d}"

    # 3. Standard patterns in whole text (avoiding cited decisions if header matched)
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


def is_boilerplate(text):
    s = text.strip()
    if not s:
        return True
    # Isolated page numbers or dividers
    if re.fullmatch(r'\d+|[-*_~=\s]+', s):
        return True
    # Pure institutional headers
    lines = [ln.strip() for ln in s.split('\n') if ln.strip()]
    header_pat = r'^(?:CỘNG HÒA XÃ HỘI|Độc lập\s*[–-]|ĐẠI HỌC QUỐC GIA|TRƯỜNG ĐẠI HỌC BÁCH KHOA|Số:\s*/?QĐ|Thành phố Hồ Chí Minh,\s*ngày|HIỆU TRƯỞNG TRƯỜNG)'
    if lines and all(re.match(header_pat, ln, re.IGNORECASE) for ln in lines):
        return True
    return False


def parse_curriculum_markdown_table(lines_with_idx):
    """
    Parse a block of Markdown table lines with multi-row cell continuation awareness.
    Preserves all courses (including CO3345), conditions (TQ, SH, KN, SHT, HT),
    and sets exact line locators.
    """
    courses = []
    code_pattern = re.compile(r'\b([A-Z]{2}\d{4})\b')
    cond_pattern = re.compile(r'([A-Z]{2}\d{4})\s*\(([A-Za-z]+)\)')

    rows = []
    for line_num, line_str in lines_with_idx:
        s = line_str.strip()
        if not (s.startswith('|') and s.endswith('|')):
            continue
        parts = [p.strip() for p in s.split('|')]
        cells = parts[1:-1] if len(parts) >= 2 else []
        rows.append({'line_num': line_num, 'cells': cells, 'raw': line_str})

    def clean_cell_text(text):
        text = re.sub(r'</?(?:sup|sub|p|span|b|i|x|br\s*/?)[^>]*>', ' ', text, flags=re.I)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    consumed_rows = set()

    for i, row in enumerate(rows):
        cells = row['cells']
        code = None
        code_idx = -1
        for c_idx in range(min(3, len(cells))):
            m = code_pattern.search(cells[c_idx])
            if m:
                code = m.group(1)
                code_idx = c_idx
                break
        if not code:
            continue

        line_num = row['line_num']

        # Credits: look in cells after code
        credits = 0
        for c in cells[code_idx + 1:]:
            m_cr = re.search(r'^\s*(\d+)\s*$', c)
            if m_cr:
                credits = int(m_cr.group(1))
                break

        # Collect names and condition text
        names = []
        cond_text_parts = []

        # Previous row check (if not consumed and has no code)
        prev_row = rows[i - 1] if i > 0 else None
        prev_has_code = False
        if prev_row:
            if prev_row['line_num'] in consumed_rows:
                prev_has_code = True
            else:
                for c in prev_row['cells'][:3]:
                    if code_pattern.search(c):
                        prev_has_code = True
                        break

        # Next row check (if has no code)
        next_row = rows[i + 1] if i + 1 < len(rows) else None
        next_has_code = False
        if next_row:
            for c in next_row['cells'][:3]:
                if code_pattern.search(c):
                    next_has_code = True
                    break

        # Clean current cell name
        raw_name = cells[code_idx + 1] if len(cells) > code_idx + 1 else ""
        if raw_name.isdigit() and len(cells) > code_idx + 2:
            raw_name = cells[code_idx + 2]
        clean_curr_name = clean_cell_text(raw_name)

        # Check if preceding row contains the course name or split conditions
        if prev_row and not prev_has_code:
            prev_has_useful_name = False
            for c in prev_row['cells']:
                cl = clean_cell_text(c)
                if cond_pattern.search(c):
                    cond_text_parts.append(c)
                elif cl and not cl.isdigit() and len(cl) > 2 and not cl.startswith('---'):
                    names.append(cl)
                    prev_has_useful_name = True
            if prev_has_useful_name or cond_pattern.search(' '.join(prev_row['cells'])):
                consumed_rows.add(prev_row['line_num'])

        if clean_curr_name and len(clean_curr_name) > 1 and not clean_curr_name.isdigit():
            names.append(clean_curr_name)

        # Check if succeeding row contains continuation name or split conditions
        if next_row and not next_has_code:
            next_has_useful = False
            for c in next_row['cells']:
                cl = clean_cell_text(c)
                if cond_pattern.search(c):
                    cond_text_parts.append(c)
                    next_has_useful = True
                elif cl and not cl.isdigit() and len(cl) > 2 and not cl.startswith('---'):
                    names.append(cl)
                    next_has_useful = True
            if next_has_useful:
                consumed_rows.add(next_row['line_num'])

        # Build clean course name
        course_name = names[0] if names else clean_curr_name
        course_name = re.sub(r'[,x\s]+$', '', course_name).strip()

        # Combine conditions
        cond_text_parts.append(' '.join(cells))
        all_cond_text = ' '.join(cond_text_parts)
        prereqs = cond_pattern.findall(all_cond_text)

        unique_conds = []
        seen = set()
        for c_code, c_type in prereqs:
            if (c_code, c_type) not in seen:
                seen.add((c_code, c_type))
                unique_conds.append({'code': c_code, 'type': c_type})

        courses.append({
            'code': code,
            'name': course_name,
            'credits': credits,
            'conditions': unique_conds,
            'source_locator': f"line_{line_num}"
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

    full_text = "".join(lines)

    # Document type classification
    document_type = "regulation"
    if "QĐ" in title or "QD" in doc_id or "Quyết định" in title or "QUYẾT ĐỊNH" in full_text[:500]:
        document_type = "decision"
    elif "TB" in title or "Thông báo" in title or "Thong bao" in doc_id or "THÔNG BÁO" in full_text[:500]:
        document_type = "notice"
    elif "Kết luận" in title or "Ket luan" in doc_id:
        document_type = "meeting_minutes"
    elif "MT_KHMT" in title or "MT_KTMT" in title or "CHƯƠNG TRÌNH ĐÀO TẠO" in full_text[:500]:
        document_type = "curriculum"

    issued_date = extract_issued_date(full_text, filename)

    # Scope definition
    scope = {
        "institution": "Trường Đại học Bách khoa - ĐHQG-HCM",
        "program": "Tất cả các ngành",
        "study_mode": "Đại học",
        "cohorts": []
    }
    if "KHMT" in filename:
        scope["program"] = "Khoa học Máy tính"
        scope["study_mode"] = "Đại học chính quy"
        scope["cohorts"] = ["2024"]
    elif "KTMT" in filename:
        scope["program"] = "Kỹ thuật Máy tính"
        scope["study_mode"] = "Đại học chính quy"
        scope["cohorts"] = ["2024"]
    elif "Đại học" in title or "Dai_hoc" in doc_id:
        scope["study_mode"] = "Đại học chính quy"

    document = {
        "doc_id": doc_id,
        "title": title,
        "document_type": document_type,
        "source_url": URL_MAPPING.get(filename),
        "source_file": f"Raw_data_2/{filename}",
        "issued_date": issued_date,
        "effective_date": None,
        "scope": scope
    }

    passages = []
    order = 1
    section_path = []
    current_paragraph_lines = []

    def flush_current_paragraph(start_line_idx):
        nonlocal order, current_paragraph_lines
        if not current_paragraph_lines:
            return

        raw_text_newlines = "\n".join(ln for _, ln in current_paragraph_lines)
        is_table = bool(re.search(r"\|.*\|.*\|", raw_text_newlines))

        if is_table:
            courses = parse_curriculum_markdown_table(current_paragraph_lines)
            if courses:
                for course in courses:
                    loc = course.pop("source_locator", f"line_{start_line_idx + 1}")
                    passages.append({
                        "passage_id": f"{doc_id}_P{order:03d}",
                        "doc_id": doc_id,
                        "order": order,
                        "section_path": list(section_path),
                        "content_type": "course_entity",
                        "text": json.dumps(course, ensure_ascii=False),
                        "source_locator": loc,
                        "review_status": "pending"
                    })
                    order += 1
                current_paragraph_lines = []
                return

        cleaned_text = clean_text(raw_text_newlines)
        if cleaned_text and not is_boilerplate(cleaned_text):
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

    for i, line_raw in enumerate(lines):
        line = line_raw.strip()
        if not line:
            flush_current_paragraph(paragraph_start_idx)
            paragraph_start_idx = i + 1
            continue

        # Check for list items a), b), c) with content (V01)
        letter_match = re.match(r'^([a-z])\)\s+(.*)', line)
        if letter_match and not re.match(r'^[a-z]\)\s+(?:Sửa đổi|Bổ sung|Thay thế)', line, re.IGNORECASE):
            # Flush prior content
            flush_current_paragraph(paragraph_start_idx)
            cleaned_item = clean_text(line)
            if cleaned_item and not is_boilerplate(cleaned_item):
                passages.append({
                    "passage_id": f"{doc_id}_P{order:03d}",
                    "doc_id": doc_id,
                    "order": order,
                    "section_path": list(section_path),
                    "content_type": "list_item",
                    "text": cleaned_item,
                    "source_locator": f"line_{i + 1}",
                    "review_status": "pending"
                })
                order += 1
            paragraph_start_idx = i + 1
            continue

        heading_match = re.match(r'^(#+)\s+(.*)', line)
        numbered_match = re.match(r'^(\d+(?:\.\d+)+)\.?\s+(\S+.*)', line)
        dieu_match = re.match(r'^(Điều\s+\d+[:\.])\s*(.*)', line, re.IGNORECASE)
        chuong_phan_match = re.match(r'^((?:Chương|Phần)\s+[IVX\d]+[:\.])\s*(.*)', line, re.IGNORECASE)
        roman_match = re.match(r'^([IVX]+)[\.\)]\s+([A-ZÀ-Ỹ].*)', line)
        khoan_muc_match = re.match(r'^((?:Khoản|Mục)\s+\d+[:\.])\s*(.*)', line, re.IGNORECASE)
        letter_subhead = re.match(r'^([a-z])\)\s+(?:Sửa đổi|Bổ sung|Thay thế)\s*(.*)', line, re.IGNORECASE)

        if heading_match or numbered_match or dieu_match or chuong_phan_match or roman_match or khoan_muc_match or letter_subhead:
            flush_current_paragraph(paragraph_start_idx)

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
                heading_text = f"{number_str}. {clean_text(numbered_match.group(2))}"
            elif khoan_muc_match:
                level = 3
                heading_text = f"{khoan_muc_match.group(1)} {clean_text(khoan_muc_match.group(2))}".strip()
            elif letter_subhead:
                level = 4
                heading_text = clean_text(line)

            if level <= len(section_path):
                section_path = section_path[:level - 1]
            section_path.append(heading_text)
            paragraph_start_idx = i + 1
        else:
            current_paragraph_lines.append((i, line))

    flush_current_paragraph(paragraph_start_idx)

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
    if not md_files:
        print(f"LỖI: Không tìm thấy tệp .md trong thư mục {RAW_DATA_DIR}")
        sys.exit(1)
    for md_file in md_files:
        parse_markdown(md_file)
    print("Hoàn tất xử lý Raw_data_2!")
