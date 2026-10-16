# Đề tài 3: RAG Neuro-Symbolic kết hợp Knowledge Graph và Suy luận có kiểm chứng

> **Đồ án Tổng hợp - Hướng Trí tuệ Nhân tạo (AI Project)**  
> **Trường Đại học Bách Khoa - ĐHQG-HCM (HCMUT)**

---

## 📌 Giới thiệu & Đặt vấn đề

Hệ thống **RAG (Retrieval-Augmented Generation)** truyền thống sử dụng Vector Search (Dense Retrieval) để tìm kiếm các đoạn văn bản có độ tương đồng ngữ nghĩa cao nhằm hỗ trợ Mô hình Ngôn ngữ Lớn (LLM) trả lời câu hỏi. Tuy nhiên, phương pháp này tồn tại các nhược điểm cố hữu:
1. **Thiếu khả năng suy luận logic nhiều bước (Multi-hop reasoning):** Khi câu trả lời đòi hỏi liên kết thông tin qua nhiều thực thể phân mảnh trong nhiều tài liệu.
2. **Nguy cơ ảo giác (Hallucination):** Mô hình vẫn có thể bịa đặt thông tin hoặc tổng hợp sai ngữ cảnh.
3. **Thiếu khả năng kiểm chứng (Lack of Verifiability):** Khó truy vết chính xác chuỗi lập luận dẫn đến câu trả lời.

### Mục tiêu đề tài
Dự án nghiên cứu và hiện thực hóa hướng tiếp cận **Neuro-Symbolic RAG** trên miền **Quy chế học vụ & Đề cương môn học**:
* **Neuro (LLM):** Đảm nhiệm việc hiểu ngôn ngữ tự nhiên linh hoạt, phân rã câu hỏi và tổng hợp câu trả lời tự nhiên.
* **Symbolic (Knowledge Graph):** Đóng vai trò cơ sở chân lý (Ground Truth) có cấu trúc, cho phép thực hiện suy diễn logic và cung cấp đường đi lập luận rõ ràng qua đồ thị.
* **Suy luận có kiểm chứng (Verifiable Reasoning):** Xây dựng module đối chiếu (Verification Layer) nhằm xác minh từng khẳng định trong câu trả lời với các bộ ba tri thức (Triples) trong KG, cung cấp bằng chứng minh bạch và giảm thiểu thông tin thiếu cơ sở.
* **Thực nghiệm đối sánh:** Đánh giá định lượng có hệ thống giữa **Baseline RAG (Vector-based)** và **Neuro-Symbolic RAG (Graph-enhanced)** trên bộ 100 câu hỏi test.

---

## 🏗️ Sơ đồ Kiến trúc Hệ thống

```text
                             ┌─────────────────────────────────┐
                             │       User Question (NL)        │
                             └────────────────┬────────────────┘
                                              │
                    ┌─────────────────────────┴─────────────────────────┐
                    ▼                                                   ▼
      ┌───────────────────────────┐                       ┌───────────────────────────┐
      │     Baseline Pipeline     │                       │  Neuro-Symbolic Pipeline  │
      │    (Standard Vector RAG)  │                       │     (KG-Enhanced RAG)     │
      ├───────────────────────────┤                       ├───────────────────────────┤
      │ 1. Vector Search          │                       │ 1. Triplet/Entity Extract │
      │    (Dense Retrieval)      │                       │ 2. Subgraph / Path Search │
      │ 2. Top-k Semantic Chunks  │                       │ 3. Triples + Chunks Pack  │
      │ 3. Prompting LLM          │                       │ 4. Constrained Generation │
      └─────────────┬─────────────┘                       └─────────────┬─────────────┘
                    │                                                   │
                    │ Raw Answer                                        ▼
                    │                                     ┌───────────────────────────┐
                    │                                     │    Verification Layer     │
                    │                                     ├───────────────────────────┤
                    │                                     │ - Atomic Claim Extraction │
                    │                                     │ - Fact Checking vs KG     │
                    │                                     │ - Proof Path Extraction   │
                    │                                     └─────────────┬─────────────┘
                    │                                                   │
                    ▼                                                   ▼
            Unverified Answer                             Verified Answer + Proof Path
                    │                                                   │
                    └─────────────────────────┬─────────────────────────┘
                                              ▼
                             ┌─────────────────────────────────┐
                             │ Comparative Benchmark Framework │
                             │  (Faithfulness, Accuracy, etc.) │
                             └─────────────────────────────────┘
```

---

## 📂 Cấu trúc Dự án

```text
RAG-NeuroSymbolic-Project/
│
├── data/                       # Dữ liệu cục bộ (Thư mục này được đưa vào .gitignore)
│   ├── raw/                    # File PDF/Word gốc 
│   ├── processed/              # File Text đã làm sạch, cắt chunk (JSON/TXT)
│   ├── graph_triplets/         # Dữ liệu Triplets do LLM trích xuất để import Neo4j
│   ├── chromadb_store/         # Nơi lưu trữ local của Vector DB
│   └── test_datasets/          # File chứa 100 câu hỏi test và Ground Truth
│
├── notebooks/                  # Thử nghiệm nháp và trực quan hóa (Jupyter Notebook)
│   ├── graph_tests.ipynb       # Thử nghiệm Cypher query và trích xuất Triplet
│   ├── rag_tests.ipynb         # Thử nghiệm LangChain và ChromaDB
│   └── ragas_tests.ipynb       # Thử nghiệm các hàm đánh giá và độ đo Ragas
│
├── src/                        # Thư mục mã nguồn chính
│   ├── config/                 # Cấu hình chung
│   │   ├── __init__.py
│   │   └── settings.py         # Load biến môi trường, setup đường dẫn thư mục
│   │
│   ├── graph_module/           # Xử lý Knowledge Graph
│   │   ├── __init__.py
│   │   ├── extractor.py        # Trích xuất Triplets từ văn bản bằng LLM
│   │   ├── neo4j_manager.py    # Kết nối Neo4j, hàm import dữ liệu
│   │   └── graph_retriever.py  # Chạy Cypher và lấy Graph Context / Path
│   │
│   ├── vector_module/          # Xử lý Vector RAG
│   │   ├── __init__.py
│   │   ├── chunking.py         # Cắt text thành các chunk có cấu trúc
│   │   ├── chroma_manager.py   # Kết nối ChromaDB, embedding văn bản
│   │   └── vector_retriever.py # Tìm kiếm tương đồng ngữ nghĩa trong ChromaDB
│   │
│   ├── engine/                 # Bộ não tích hợp và suy luận
│   │   ├── __init__.py
│   │   ├── prompts.py          # Lưu trữ các System Prompts
│   │   ├── fusion_chain.py     # Tích hợp Graph Context + Vector Context để trả lời
│   │   └── verifier.py         # Kiểm chứng khẳng định (Claims) và sinh đường dẫn chứng minh
│   │
│   ├── evaluation/             # Kịch bản đánh giá và đo lường
│   │   ├── __init__.py
│   │   ├── run_baseline.py     # Chạy 100 câu test với Naive RAG
│   │   ├── run_kgrag.py        # Chạy 100 câu test với KG-RAG + Verifier
│   │   └── ragas_metrics.py    # Chấm điểm tự động và xuất file kết quả 
│   │
│   └── ui/                     # Giao diện người dùng
│       ├── __init__.py
│       └── app.py              # Streamlit Web App hiển thị trả lời kèm bằng chứng đồ thị
│
├── .env                        # Lưu API Keys, mật khẩu Neo4j (Không commit lên Git)
├── .env.example                # File mẫu cấu hình biến môi trường
├── .gitignore                  # Bỏ qua data/, .env, cache khỏi Git
├── requirements.txt            # Danh sách thư viện Python cần cài đặt
└── README.md                   # Tài liệu hướng dẫn dự án
```

---

## 🗄️ Chi tiết Thư mục Dữ liệu (Data Pipeline & Storage)

Thư mục `data/` quản lý toàn bộ vòng đời dữ liệu của hệ thống, phục vụ hai miền tri thức chính: **Đề cương môn học** và **Quy chế học vụ** (Khoa Khoa học & Kỹ thuật Máy tính - HCMUT).

### 1. Dữ liệu thô (`data/raw/`)
* **`Raw_data_1/`**: Chứa **129 tệp JSON** thu thập từ hệ thống quản lý đào tạo (MyBK / DCMH Core). Mỗi tệp tương ứng với một đề cương môn học (ĐCMH), bao gồm: thông tin chung, mục tiêu môn học, chuẩn đầu ra (L.O), điều kiện tiên quyết/song hành, tài liệu tham khảo, tiêu chuẩn đánh giá và kế hoạch giảng dạy chi tiết theo tuần.
* **`Raw_data_2/`**: Chứa **10 tệp Markdown (`.md`)** về các văn bản quy chế và kế hoạch đào tạo:
  * Các Quyết định điều chỉnh học vụ chung và bậc Đại học (QĐ 1259, 1260, 2931, 2933,...).
  * Khung chương trình đào tạo và cây môn học tiên quyết ngành Khoa học Máy tính (`2024_MT_KHMT.md`) và Kỹ thuật Máy tính (`2024_MT_KTMT.md`).
  * Thông báo Kết luận các phiên họp Hội đồng học vụ qua các học kỳ (HK241, HK242, HK251, HK252,...).

### 2. Dữ liệu đã xử lý & chuẩn hóa (`data/processed/`)
Dữ liệu sau khi qua các pipeline làm sạch được tổ chức thống nhất thành 2 cấp: `documents` (metadata định danh tài liệu) và `passages` (các đoạn trích/chunk văn bản có cấu trúc phục vụ RAG):
* **`output_1/`** *(Tiền xử lý từ `Raw_data_1` qua script `process_raw_data_1.py`)*:
  * `documents/`: 129 tệp JSON lưu metadata từng môn học (`doc_id`, `title`, `scope`, `cohorts`, ngày ban hành, nguồn gốc).
  * `passages/`: 129 tệp JSON chứa các đoạn trích (`passage_id`, `section_path`, `content_type`, `text`, `source_locator`) được phân loại theo từng phần nội dung đề cương.
* **`output_2/`** *(Tiền xử lý từ `Raw_data_2` qua script `process_raw_data_2.py`)*:
  * `documents/`: 10 tệp JSON lưu metadata văn bản quy chế, quyết định và khung đào tạo.
  * `passages/`: 10 tệp JSON chứa các điều khoản, quy định và bảng môn học tiên quyết đã được bóc tách và phân đoạn có thứ tự.

### 3. Lưu trữ Vector & Knowledge Graph
* **`graph_triplets/`**: Lưu trữ các bộ ba tri thức (Triplets: `Subject - Predicate - Object`) trích xuất từ dữ liệu bằng LLM hoặc luật (rule-based), sẵn sàng nạp vào **Neo4j** phục vụ suy luận đồ thị và kiểm chứng câu trả lời.
* **`chromadb_store/`**: Thư mục lưu trữ cục bộ (local persistence) của Vector Database **ChromaDB**, chứa các vector embeddings của các đoạn `passages` phục vụ tìm kiếm ngữ nghĩa (Dense Retrieval).
* **`test_datasets/`**: Bộ dữ liệu chuẩn gồm **100 câu hỏi kiểm thử** (kèm Ground Truth và chuỗi lập luận mẫu) dùng để đánh giá định lượng và đối sánh (benchmark) hai pipeline bằng thư viện Ragas.

### 4. Scripts tiền xử lý (`data/*.py`)
* **`process_raw_data_1.py`**: Tự động lọc các môn học thuộc Khoa Máy tính áp dụng cho HK261/HK262, làm sạch mã HTML, trích xuất cấu trúc văn bản và xuất sang `output_1/`.
* **`process_raw_data_2.py`**: Tự động loại bỏ boilerplate hành chính, phân tách điều khoản văn bản quy chế, trích xuất bảng môn học tiên quyết và xuất sang `output_2/`.

---

## ⚙️ Cài đặt & Khởi chạy

### 1. Yêu cầu hệ thống
* Python `>= 3.10`
* Neo4j Database (Cài cục bộ hoặc chạy Docker: `docker run -p 7687:7687 -p 7474:7474 -e NEO4J_AUTH=neo4j/password neo4j:latest`)

### 2. Thiết lập môi trường ảo
```bash
# Tạo môi trường ảo
python -m venv venv

# Kích hoạt trên Windows PowerShell
.\venv\Scripts\Activate.ps1

# Kích hoạt trên Linux/macOS
source venv/bin/activate

# Cài đặt thư viện
pip install -r requirements.txt
```

### 3. Cấu hình biến môi trường
Sao chép `.env.example` thành `.env` và cập nhật thông tin:
```bash
cp .env.example .env
```

---

## 📊 Phương pháp Thực nghiệm & Tiêu chí Đánh giá

Hệ thống được đánh giá đối sánh trên bộ **100 câu hỏi trắc nghiệm & tự luận** (chia theo câu hỏi tra cứu trực tiếp và câu hỏi suy luận multi-hop):

| Tiêu chí | Mô tả |
|---|---|
| **Faithfulness** | Mức độ trung thực của câu trả lời dựa trên context được cung cấp. |
| **Multi-hop Accuracy** | Độ chính xác trên các câu hỏi đòi hỏi liên kết $\ge 2$ thực thể (điều kiện tiên quyết, ràng buộc học vụ). |
| **Hallucination Rate** | Tỷ lệ thông tin sinh ra không có cơ sở trong cơ sở dữ liệu. |
| **Verifiability** | Khả năng truy vết và xuất đường dẫn chứng minh (Reasoning Path / Triples). |

---

## 🚀 Hướng dẫn Chạy các Module

1. **Chuẩn bị dữ liệu & Ingest:**
   * Nạp văn bản quy chế vào `data/raw/`.
   * Chạy trích xuất Triplet vào `data/graph_triplets/` và nạp vào Neo4j.
   * Chạy chunking và nạp embedding vào ChromaDB.

2. **Chạy giao diện Web App (Demo):**
   ```bash
   streamlit run src/ui/app.py
   ```

3. **Chạy Benchmark đánh giá:**
   ```bash
   python src/evaluation/run_baseline.py
   python src/evaluation/run_kgrag.py
   python src/evaluation/ragas_metrics.py
   ```
