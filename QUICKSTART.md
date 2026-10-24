# 🚀 HƯỚNG DẪN CÀI ĐẶT & CHẠY DỰ ÁN BK-SCHOLAR (DÀNH CHO THÀNH VIÊN NHÓM)

Tài liệu này hướng dẫn từng bước để cài đặt môi trường và khởi chạy toàn bộ hệ thống **BK-Scholar (Neuro-Symbolic RAG for Academic Advising)** trên máy cá nhân.

---

## 📌 Yêu cầu Tiên quyết (Prerequisites)

1. **Python**: Phiên bản `3.10` đến `3.13` (Khuyên dùng `3.11` hoặc `3.13`).
2. **Docker Desktop**: Dùng để chạy Neo4j nhanh nhất qua 1 lệnh (*Nếu không có Docker, có thể cài Neo4j Desktop thủ công*).
3. **Git**: Đã cài đặt trên máy.

---

## ⚡ Quy trình 5 Bước Cài đặt

### Bước 1: Clone Repository & Chuyển Branch
Mở Terminal / PowerShell và thực hiện:
```bash
git clone <URL_REPO_GITHUB>
cd <TEN_THU_MUC_REPO>
git checkout feat/verifier-and-backend
```

---

### Bước 2: Tải & Giải nén Dữ liệu Vector (ChromaDB)
Vì cơ sở dữ liệu Vector (`chromadb_store`) và embeddings cache nặng khoảng ~160MB nên không đưa lên Git.
1. Tải file **`DATA_VECTOR_BUNDLE.zip`** từ Google Drive của nhóm *(nhóm trưởng gửi link)*.
2. Giải nén file zip trực tiếp vào thư mục gốc của dự án.
3. **Kiểm tra cấu trúc thư mục:** Đảm bảo xuất hiện các file sau:
   ```text
   DATA/
   ├── chromadb_store/
   │   └── chroma.sqlite3
   ├── vector_artifacts/
   │   ├── chunks.json
   │   └── embeddings.sqlite3
   └── graph_triplets/
       └── curriculum_graph.json
   ```

---

### Bước 3: Tạo Môi trường ảo & Cài đặt Dependencies

**Trên Windows (PowerShell / Command Prompt):**
```powershell
# Tạo môi trường ảo
python -m venv .venv

# Kích hoạt môi trường ảo
.venv\Scripts\activate

# Cài đặt toàn bộ thư viện cần thiết
pip install -r requirements.txt
```

**Trên macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

### Bước 4: Khởi động Neo4j & Nạp Dữ liệu Đồ thị

1. **Khởi động Neo4j bằng Docker (Khuyên dùng):**
   ```bash
   docker compose up -d
   ```
   *(Docker sẽ tự động tải image `neo4j:5.20.0` và khởi chạy với mật khẩu mặc định là `password123` tại cổng `7687`).*

   > 💡 *Nếu bạn dùng Neo4j Desktop thay vì Docker:* Hãy tạo Database với username `neo4j` và password `password123`.

2. **Nạp dữ liệu môn học vào Neo4j:**
   Chạy script sau để tự động tạo ràng buộc và nạp 560 nodes, 747 edges từ `curriculum_graph.json`:
   ```bash
   python -m src.graph_module.neo4j_manager
   ```
   *(Khi màn hình hiển thị: `[+] THỐNG KÊ KNOWLEDGE GRAPH TRONG NEO4J: 560 Nodes, 747 Relationships` là thành công!)*

---

### Bước 5: Cấu hình Biến môi trường (`.env`)

1. Copy file mẫu `.env.example` thành `.env`:
   * **Windows:** `copy .env.example .env`
   * **macOS/Linux:** `cp .env.example .env`
2. Mở file `.env` và điền API Key:
   ```ini
   GROQ_API_KEY=gsk_your_groq_api_key_here
   ```
   *(Nếu chưa có Groq API Key, bạn vào https://console.groq.com tạo tài khoản miễn phí và tạo key trong 1 phút).*

---

## 🎯 Khởi chạy Ứng dụng Web (Streamlit UI)

Sau khi hoàn tất 5 bước trên, bạn có thể chạy ứng dụng như sau:
```bash
streamlit run src/ui/app.py
```

Trình duyệt sẽ tự động mở giao diện tại: **`http://localhost:8501`**.

---

## 🛠️ Một số Lỗi thường gặp (Troubleshooting)

1. **Lỗi `ConnectionRefusedError: bolt://localhost:7687`:**
   * **Nguyên nhân:** Container Neo4j chưa chạy.
   * **Khắc phục:** Chạy `docker compose up -d` hoặc kiểm tra Docker Desktop xem container `neo4j-dath` đã bật màu xanh chưa.

2. **Lỗi `RateLimitError / OTPM Limit (429)` từ Groq:**
   * **Nguyên nhân:** Groq Free Tier giới hạn token/phút.
   * **Khắc phục:** Dự án đã được tối ưu tham số `max_tokens=500`. Nếu gặp lỗi, hãy đợi khoảng 10 giây và gửi lại câu hỏi hoặc đổi sang Groq API Key cá nhân.

3. **Giao diện không hiển thị đồ thị Pyvis:**
   * Hãy mở thanh kiểm tra nguồn trích dẫn hoặc đợi vài giây để vis.js tải CDN mạng trực quan.
