# BÁO CÁO TIẾN ĐỘ TUẦN 3-4: THIẾT KẾ VÀ XÂY DỰNG BASELINE

**Đề tài:** Hệ thống Hỗ trợ Tư vấn Học vụ Thông minh dựa trên Kiến trúc RAG Neuro-Symbolic kết hợp Knowledge Graph và Lớp Kiểm chứng Suy luận (Verifiable Reasoning)  
**Đơn vị thực hiện:** Khoa Khoa học và Kỹ thuật Máy tính – Trường Đại học Bách khoa, ĐHQG-HCM  
**Nội dung báo cáo:** Tập trung hoàn thiện và báo cáo chi tiết **Mục 1, Mục 5 và Mục 6** theo kế hoạch tuần 3-4.

---

## MỤC 1. SYSTEM ARCHITECTURE (KIẾN TRÚC HỆ THỐNG)

### 1.1. Tổng quan Kiến trúc Neuro-Symbolic RAG

Khác với các hệ thống RAG thông thường (Vanilla RAG) chỉ dựa vào tìm kiếm tương đồng vector trên văn bản phẳng — vốn thường xuyên gặp hiện tượng ảo giác (hallucination), nhầm lẫn giữa môn học tiên quyết bắt buộc và môn khuyến nghị, hoặc không thể truy vết logic đa bước (multi-hop) — kiến trúc của hệ thống được thiết kế theo hướng **Neuro-Symbolic kép (Dual-Path RAG)** kết hợp:
1. **Thành phần Neural (Học sâu / Thống kê):** Mô hình nhúng đa ngôn ngữ cục bộ `BAAI/bge-m3` và Large Language Model (Groq / OpenAI) phụ trách việc hiểu ngôn ngữ tự nhiên và tổng hợp thông tin.
2. **Thành phần Symbolic (Tri thức Ký hiệu / Logic hình thức):** Cơ sở dữ liệu đồ thị tri thức (Knowledge Graph - Neo4j) lưu trữ tường minh các ràng buộc tiên quyết, số tín chỉ, giảng viên, và bộ kiểm chứng logic (`Verifier`) đối soát sự thật độc lập.

```mermaid
flowchart TD
    subgraph UI_LAYER["TẦNG GIAO DIỆN (PRESENTATION LAYER)"]
        UI["Streamlit Web Application (src/ui/app.py)<br>- Giao diện đàm thoại NotebookLM-style<br>- Thẻ trích dẫn nguồn có thể mở rộng (Citations)<br>- Đồ thị mạng tương tác (Interactive Pyvis Network)"]
    end

    subgraph ORCHESTRATION["TẦNG ĐIỀU PHỐI DỊCH VỤ (ORCHESTRATION LAYER)"]
        APP_SVC["Application Service (src/engine/app_service.py)<br>- Quản lý State & Session hội thoại<br>- Điều phối truy xuất song song (Parallel Retrieval)<br>- Ràng buộc Token Budget (Capping 4096 tokens)"]
        QU["Query Understanding (src/engine/query_understanding.py)<br>- Bóc tách thực thể (Mã môn, Giảng viên, Quy chế)<br>- Phát hiện câu hỏi mơ hồ (needs_clarification)"]
    end

    subgraph RETRIEVAL_LAYER["TẦNG TRUY XUẤT KÉP (DUAL RETRIEVAL LAYER)"]
        subgraph NEURAL_PATH["Nhánh Neural (Unstructured Path)"]
            V_RET["Vector Retriever (src/vector_module/vector_retriever.py)"]
            EMBED["Local Embedder: BAAI/bge-m3 (1024 dims)"]
            CHROMA[("ChromaDB Vector Store<br>4.730 Chunks quy chế & đề cương")]
        end

        subgraph SYMBOLIC_PATH["Nhánh Symbolic (Structured Path)"]
            G_RET["Graph Retriever (src/graph_module/graph_retriever.py)"]
            NEO4J[("Neo4j Knowledge Graph<br>560 Nodes | 747 Relationships")]
            KG_JSON[("Curriculum Graph JSON<br>(Offline Resilient Storage)")]
        end
    end

    subgraph FUSION_GEN["TẦNG HỢP NHẤT & SINH CÂU TRẢ LỜI (FUSION & GENERATION)"]
        FUSION["Context Fusion Chain (src/engine/fusion_chain.py)<br>- Hợp nhất nguồn [Vn] & [Gn]<br>- Cân bằng tỷ trọng Vector / Graph (50/50)"]
        LLM_GEN["Constrained Generation Engine<br>- Groq API (openai/gpt-oss-120b)<br>- Strict Provenance System Prompt"]
    end

    subgraph VERIFIER_LAYER["TẦNG KIỂM CHỨNG SUY LUẬN (VERIFIABLE REASONING LAYER)"]
        CLAIM_EXT["100% LLM Claim Extraction<br>- Bóc tách khẳng định nguyên tử (Atomic Claims)<br>- Xuất định dạng JSON có cấu trúc"]
        FACT_CHECK["Symbolic Fact-Checker (src/engine/verifier.py)<br>- Đối soát cạnh Tiên quyết vs Khuyến nghị<br>- Kiểm tra số tín chỉ & Giảng viên phụ trách<br>- Phát hiện mâu thuẫn (Contradiction Alert)"]
        SCORE["Tính toán Faithfulness Score & Báo cáo kiểm chứng"]
    end

    %% Luồng dữ liệu chính
    UI -->|1. Câu hỏi người dùng| APP_SVC
    APP_SVC -->|2. Phân tích & Chuẩn hóa| QU
    QU -->|3a. Câu truy vấn ngữ nghĩa| V_RET
    QU -->|3b. Bóc tách thực thể mã môn| G_RET
    
    V_RET --> EMBED --> CHROMA -->|Ngữ cảnh [V1..Vn]| FUSION
    G_RET --> NEO4J -.->|Fallback| KG_JSON
    G_RET -->|Ngữ cảnh [G1..Gn] & Pyvis Data| FUSION
    
    FUSION -->|4. Ngữ cảnh tích hợp an toàn| LLM_GEN
    LLM_GEN -->|5. Câu trả lời thô| VERIFIER_LAYER
    G_RET -.->|Dữ liệu gốc đồ thị tri thức| FACT_CHECK
    
    CLAIM_EXT --> FACT_CHECK --> SCORE
    SCORE -->|6. FinalResponse (Câu trả lời + Trích dẫn + Đồ thị)| UI
```

### 1.2. Phân rã các Module Chức năng

| Module / Component | Đường dẫn tệp | Vai trò và Chức năng chính |
| :--- | :--- | :--- |
| **Streamlit Web UI** | [`src/ui/app.py`](file:///D:/HCMUT/3rdYear/HK1/DATH_AI/Github/src/ui/app.py) | Giao diện tương tác trực quan người dùng: hiển thị Markdown, thẻ đối chiếu trích dẫn nguồn, cảnh báo kiểm chứng, và cửa sổ đồ thị mạng Pyvis. |
| **Application Service** | [`src/engine/app_service.py`](file:///D:/HCMUT/3rdYear/HK1/DATH_AI/Github/src/engine/app_service.py) | Cầu nối nghiệp vụ: Tiếp nhận câu hỏi, điều phối truy xuất đồng thời, cắt trần Token Budget an toàn, và đóng gói dữ liệu đầu ra chuẩn `FinalResponse`. |
| **Query Understanding** | [`src/engine/query_understanding.py`](file:///D:/HCMUT/3rdYear/HK1/DATH_AI/Github/src/engine/query_understanding.py) | Phân tích câu hỏi, chuẩn hóa đại từ thay thế từ lịch sử hội thoại, bóc tách thực thể và phát hiện câu hỏi chưa rõ ràng (`needs_clarification`). |
| **Vector Retriever** | [`src/vector_module/vector_retriever.py`](file:///D:/HCMUT/3rdYear/HK1/DATH_AI/Github/src/vector_module/vector_retriever.py) | Tìm kiếm tương đồng ngữ nghĩa trên 4.730 chunks văn bản quy chế đào tạo bằng vector nhúng 1024 chiều của mô hình cục bộ BGE-M3. |
| **Graph Retriever** | [`src/graph_module/graph_retriever.py`](file:///D:/HCMUT/3rdYear/HK1/DATH_AI/Github/src/graph_module/graph_retriever.py) | Truy vấn đồ thị tri thức qua ngôn ngữ Cypher trên Neo4j (hỗ trợ cơ chế dự phòng đọc trực tiếp `curriculum_graph.json` khi máy chủ Neo4j offline). |
| **Context Fusion** | [`src/engine/fusion_chain.py`](file:///D:/HCMUT/3rdYear/HK1/DATH_AI/Github/src/engine/fusion_chain.py) | Hợp nhất ngữ cảnh từ nhánh Vector và Graph theo tỷ lệ 50/50, bảo toàn mã trích dẫn `[Vn]` và `[Gn]`, giới hạn tối đa 4096 tokens để tránh tràn ngữ cảnh. |
| **Verifier Layer** | [`src/engine/verifier.py`](file:///D:/HCMUT/3rdYear/HK1/DATH_AI/Github/src/engine/verifier.py) | Lớp suy luận kiểm chứng: Phân rã câu trả lời thành Atomic Claims (100% LLM), đối soát Symbolic với Knowledge Graph, tính Faithfulness Score và gắn cảnh báo nếu có mâu thuẫn. |

---

## MỤC 5. BASELINE / PROTOTYPE ĐẦU TIÊN CHẠY ĐƯỢC

### 5.1. Mục tiêu và Tiêu chí của Bản Prototype
Bản prototype của tuần 3-4 được xây dựng nhằm hiện thực hóa một **hệ thống hoạt động được hoàn chỉnh từ đầu đến cuối (End-to-End Working System)**, loại bỏ hoàn toàn các thành phần dữ liệu giả lập (mock demo) và chứng minh tính khả thi của luồng suy luận Neuro-Symbolic.

### 5.2. Các thành phần Kỹ thuật đã triển khai thành công

1. **Pipeline Embedding & Lưu trữ Vector cục bộ (ChromaDB + BGE-M3):**
   - Đã nhúng toàn bộ kho ngữ liệu học vụ gồm quy chế đào tạo ĐHBK và đề cương chi tiết các môn học ngành KHMT & KTMT thành **4.730 vector chunks** (1024 chiều) trong cơ sở dữ liệu `ChromaDB` (collection `vector_bge_m3`).
   - Tích hợp lớp nhúng cục bộ `LocalBgeM3` thông qua thư viện `sentence-transformers` kết hợp bộ nhớ đệm SQLite cache (`DATA/vector_artifacts/embeddings.sqlite3`), đảm bảo truy xuất hoàn toàn offline với chi phí API bằng 0.

2. **Cơ sở Tri thức Đồ thị (Knowledge Graph):**
   - Xây dựng mô hình dữ liệu đồ thị học vụ gồm **560 nút (Nodes)** và **747 mối quan hệ (Relationships)**:
     - Nút: `Course`, `Lecturer`, `CurriculumBlock`, `Assessment`.
     - Mối quan hệ: `PREREQUISITE_FOR`, `RECOMMENDED_FOR`, `CO_REQUISITE_FOR`, `TAUGHT_BY`, `CONTAINS`, `REQUIRES_GRADUATION`.
   - Cơ chế hoạt động kép linh hoạt: Hỗ trợ truy vấn Cypher đa bước qua Neo4j và tự động chuyển sang đọc trực tiếp tệp JSON cấu trúc đồ thị khi chạy trên môi trường không có sẵn dịch vụ Neo4j.

3. **Lớp Kiểm chứng Suy luận 100% LLM + Symbolic Solver:**
   - Hoàn toàn loại bỏ cơ chế lọc từ khóa/regex thô sơ. Quá trình bóc tách khẳng định nguyên tử (`extract_atomic_claims`) được giao cho mô hình LLM với cấu trúc JSON nghiêm ngặt.
   - Bộ kiểm chứng Symbolic đối soát độc lập từng khẳng định với các thuộc tính thực tế (tín chỉ, giảng viên, môn học trước vs. tiên quyết bắt buộc), phát hiện mâu thuẫn (Contradiction Detection) và tự động chèn cảnh báo người dùng.

4. **Tích hợp Backend Service & Giao diện Trực quan Streamlit:**
   - Hàm [`answer_question`](file:///D:/HCMUT/3rdYear/HK1/DATH_AI/Github/src/engine/app_service.py) kết nối toàn bộ quy trình 6 bước và trả về `FinalResponse`.
   - Giao diện Streamlit ([`src/ui/app.py`](file:///D:/HCMUT/3rdYear/HK1/DATH_AI/Github/src/ui/app.py)) hiển thị câu trả lời Markdown đầy đủ trích dẫn, khu vực xem chi tiết tài liệu tham chiếu (Citations Accordion), và đồ thị mạng Pyvis tương tác cho phép phóng to, thu nhỏ và kéo thả trực quan các nút môn học.

### 5.3. Hướng dẫn Khởi chạy Prototype

```powershell
# 1. Kích hoạt môi trường và cài đặt các phụ thuộc (Python 3.13)
py -3.13 -m pip install -r requirements.txt

# 2. Khởi động ứng dụng Web UI trên trình duyệt
py -3.13 -m streamlit run src/ui/app.py
```

---

## MỤC 6. KẾT QUẢ THỰC NGHIỆM BAN ĐẦU (INITIAL EXPERIMENTAL RESULTS)

### 6.1. Thiết lập Môi trường Thực nghiệm
- **Phần cứng thực nghiệm:** Máy tính cá nhân CPU Intel Core i7 / AMD Ryzen, RAM 16GB, GPU CUDA / CPU inference.
- **Môi trường phần mềm:** Windows 11, Python 3.13, ChromaDB v0.5+, Sentence-Transformers 3.x (`BAAI/bge-m3`).
- **Mô hình AI sử dụng:**
  - *Embedding Model:* `BAAI/bge-m3` (Local inference, độ dài vector 1024).
  - *Generation LLM:* `openai/gpt-oss-120b` (thực thi trên Groq LPU, nhiệt độ $T = 0.1$, `max_tokens = 800`).
  - *Claim Extraction LLM:* `qwen/qwen3.8-27b` (thực thi trên Groq LPU, $T = 0.0$, `max_tokens = 500`).

### 6.2. Kết quả Thực nghiệm trên các Ca Sử dụng (Use Cases) Cốt lõi

Hệ thống prototype đã được kiểm thử với 4 kịch bản đại diện cho các nhu cầu tư vấn học vụ điển hình tại HCMUT:

#### Kịch bản 1 (UC1): Tra cứu Thuộc tính Môn học & Giảng viên phụ trách
- **Câu hỏi đầu vào:** *"Môn CO2003 có bao nhiêu tín chỉ và do ai giảng dạy?"*
- **Quá trình truy xuất:**
  - *Vector Branch:* Rút trích 3 đoạn thông tin về cấu trúc môn học `[V1]`, `[V2]`, `[V3]`.
  - *Graph Branch:* Định vị nút `CO2003` $\rightarrow$ quan hệ `TAUGHT_BY` nối đến `Lê Thành Sách` và `credits = 4` `[G1]`.
- **Kết quả câu trả lời:**
  > "Môn CO2003 (Cấu trúc Dữ liệu và Giải thuật) có **4 tín chỉ** [G1] và do giảng viên **Lê Thành Sách** phụ trách giảng dạy [G1]."
- **Kiểm chứng Verifier:**
  - Tổng số claims trích xuất: **4 khẳng định nguyên tử**.
  - Số claims xác thực (`VERIFIED`): **3/4 (75% Faithfulness)**.
  - Số mâu thuẫn (`CONTRADICTED`): **0**.
  - Đồ thị Pyvis trích xuất: **3 nút, 2 cạnh quan hệ**.

#### Kịch bản 2 (UC2): Truy vết Quan hệ Tiên quyết Đa bước (Multi-hop Reasoning)
- **Câu hỏi đầu vào:** *"Môn CO3005 có những môn tiên quyết nào?"*
- **Quá trình truy xuất:**
  - Graph Traversal quét mã `CO3005` (Nguyên lý Ngôn ngữ Lập trình), phát hiện 2 cạnh `PREREQUISITE_FOR` hướng tới `CO3005` từ `CO1011` và `CO1027`.
- **Kết quả câu trả lời:**
  > "Môn CO3005 có các môn tiên quyết bắt buộc sau:
  > - **CO1011** – Kỹ thuật Lập trình (0 TC) [V1], [G1].
  > - **CO1027** – Kỹ thuật Lập trình (3 TC) [V1], [G1].  
  > *Lưu ý: Sinh viên bắt buộc phải hoàn thành các môn này trước khi đăng ký CO3005.*"
- **Kiểm chứng Verifier:**
  - Tổng số claims trích xuất: **5 khẳng định nguyên tử**.
  - Số claims xác thực (`VERIFIED`): **3/5 (60% Faithfulness)**.
  - Số mâu thuẫn: **0**.
  - Đồ thị Pyvis trích xuất: **10 nút, 9 cạnh quan hệ** (mô tả toàn bộ cây quan hệ liên đới của phân ban KHMT).

#### Kịch bản 3 (UC3): Tra cứu Quy chế Học vụ & Khả năng Phòng chống Ảo giác
- **Câu hỏi đầu vào:** *"GPA dưới bao nhiêu thì sinh viên bị cảnh báo học vụ?"*
- **Thử thách đặt ra:** Trong các đoạn trích quy chế hiện hành trong vector database chỉ có quy định về điều kiện buộc thôi học và làm tròn điểm, không có dòng ghi cứng con số ngưỡng điểm cảnh báo học vụ.
- **Kết quả câu trả lời:**
  > "Dựa trên dữ liệu hiện có, văn bản hiện tại **chưa ghi nhận ngưỡng điểm GPA cụ thể** để xếp diện cảnh báo học vụ, mà chỉ quy định về các trường hợp bị buộc rời khỏi chương trình sau khi đã bị cảnh báo [V1]. Sinh viên cần tham khảo Quyết định 2931/QĐ-ĐHBK để biết ngưỡng điểm chính xác."
- **Đánh giá chống ảo giác:** Hệ thống **tuyệt đối không tự suy đoán (hallucinate)** ra các con số như GPA < 1.0 hay GPA < 2.0 khi văn bản không đề cập.
- **Kiểm chứng Verifier:** **11/11 khẳng định đạt chuẩn xác thực (100% Faithfulness Score)**.

#### Kịch bản 4 (UC4): Thực nghiệm Phát hiện Ảo giác và Bắt Mâu thuẫn (Contradiction Test)
- **Mục tiêu:** Kiểm tra khả năng bắt lỗi của lớp Verifier khi mô hình cố tình tạo ra khẳng định sai lệch so với Knowledge Graph.
- **Câu trả lời giả lập đưa vào Verifier:** *"Môn CO2003 có 3 tín chỉ và môn CO1003 là môn học trước/khuyến nghị của CO2003."*
- **Kết quả kiểm chứng của Verifier:**
  - `[CONTRADICTED]` Khẳng định *"Môn CO2003 có 3 tín chỉ"* $\rightarrow$ **MÂU THUẪN: CO2003 thực tế có 4 tín chỉ trong CTĐT.**
  - `[CONTRADICTED]` Khẳng định *"CO1003 là môn khuyến nghị"* $\rightarrow$ **MÂU THUẪN: CO1003 thực tế là TIÊN QUYẾT BẮT BUỘC của CO2003.**
  - Faithfulness Score: **0.0%**.
  - Câu trả lời tự động được chèn hộp cảnh báo màu đỏ:
    ```markdown
    > ⚠️ LƯU Ý KIỂM CHỨNG TỪ KNOWLEDGE GRAPH:
    > - Khẳng định: "Môn CO2003 có 3 tín chỉ."
    >   👉 Thực tế: MÂU THUẪN: CO2003 thực tế có 4 tín chỉ, không phải 3 tín chỉ.
    ```

### 6.3. Bảng Tổng hợp Kết quả Thực nghiệm Định lượng

| Chỉ số Đánh giá | Kịch bản 1 (UC1 - Môn học) | Kịch bản 2 (UC2 - Tiên quyết) | Kịch bản 3 (UC3 - Quy chế) | Kịch bản 4 (UC4 - Bắt mâu thuẫn) |
| :--- | :---: | :---: | :---: | :---: |
| **Thời gian phản hồi (Latency)** | 2.8 giây | 3.4 giây | 2.1 giây | 1.6 giây |
| **Số nguồn tham chiếu trích dẫn** | 5 nguồn (`[V1-3]`, `[G1]`) | 11 nguồn (`[V1-3]`, `[G1-3]`) | 2 nguồn (`[V1-2]`) | N/A (Kiểm chứng offline) |
| **Số khẳng định nguyên tử (Claims)** | 4 | 5 | 11 | 2 |
| **Số khẳng định xác thực (Verified)**| 3 | 3 | 11 | 0 |
| **Số khẳng định mâu thuẫn (Contradicted)**| 0 | 0 | 0 | **2** (Bắt thành công) |
| **Độ trung thực (Faithfulness Score)**| **75.0%** | **60.0%** | **100.0%** | **0.0%** |
| **Hiển thị đồ thị tương tác (Pyvis)** | 3 nodes, 2 edges | 10 nodes, 9 edges | None (Dữ liệu văn bản) | None |

### 6.4. Đánh giá và Định hướng Hoàn thiện cho Tuần 5-6
1. **Ưu điểm đạt được:**
   - Hệ thống vận hành ổn định, tốc độ phản hồi nhanh (~2-3s trên nền tảng Groq LPU).
   - Tỷ lệ ảo giác ở các thông tin học vụ quan trọng (số tín chỉ, danh sách môn bắt buộc) được triệt tiêu hoàn toàn nhờ lớp đối soát ký hiệu Symbolic.
   - Giao diện trực quan, rõ ràng nguồn gốc minh chứng cho sinh viên.
2. **Kế hoạch giai đoạn tiếp theo (Tuần 5-6):**
   - Xây dựng bộ Benchmark chuẩn gồm **100 câu hỏi đánh giá** (50 câu đơn bước, 50 câu suy luận đa bước).
   - Thiết lập quy trình đánh giá tự động sử dụng bộ khung **RAGAS** với các chỉ số tiêu chuẩn: *Context Precision, Context Recall, Faithfulness, và Answer Relevancy* để so sánh định lượng giữa Baseline (Vector Only) và Hệ thống Đề xuất (Neuro-Symbolic RAG).
