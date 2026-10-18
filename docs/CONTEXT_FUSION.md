# Context Fusion

Module TV2 ghép kết quả Vector và Graph thành một chuỗi ngữ cảnh có nguồn,
loại trùng và giới hạn token. Đây là bước bàn giao cho Verifiable Generation
của TV1; dữ liệu vẫn có trạng thái `not_verified`.

## Setup and demo

Chạy từ gốc repo. `tiktoken>=0.7.0` và `pydantic>=2.7.0` đã có trong
`requirements.txt`. Nếu chỉ chạy Fusion, không cần cài ChromaDB, Neo4j hay SDK LLM:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install "pydantic>=2.7,<3" "tiktoken>=0.7.0"
$env:TIKTOKEN_CACHE_DIR = Join-Path (Get-Location) '.venv/tiktoken-cache'
.\.venv\Scripts\python.exe -c "import tiktoken; tiktoken.get_encoding('o200k_base')"
.\.venv\Scripts\python.exe -m examples.context_fusion
.\.venv\Scripts\python.exe -m examples.context_fusion --max-tokens 400
.\.venv\Scripts\python.exe -m examples.context_fusion --vector-only
```

Tokenizer cần tải bảng mã một lần; sau khi cache sẵn, demo và tests chạy offline.
Giữ cùng `TIKTOKEN_CACHE_DIR` ở các phiên sau nếu muốn dùng lại cache này.
Không có lời gọi LLM/embedding, truy cập cơ sở dữ liệu hay sinh câu trả lời trong
demo. Các môn `DEMO...` và điều kiện trong ví dụ là **dữ liệu giả để minh họa**.
Demo in toàn bộ kết quả JSON, gồm ngữ cảnh, nguồn và nhật ký chọn lọc.

## Python API

```python
from src.engine.fusion_chain import fuse_contexts

fused = fuse_contexts(
    vector_context,                 # ContextResult | None
    graph_context,                  # ContextResult | None
    max_tokens=4096,
    graph_ratio=0.5,
    encoding_name="o200k_base",
)
context_for_generation = fused.content
citations_for_generation = fused.citations
audit = fused.raw_data["fusion"]
```

Hàm không nhận câu hỏi và không tự gọi retriever. Bên gọi chịu trách nhiệm cung cấp
hai kết quả cho **cùng câu hỏi đã chuẩn hóa và phạm vi dữ liệu**. Ví dụ tích hợp
với API hiện có (đoạn này cần cấu hình và dịch vụ thật):

```python
from src.engine.query_understanding import QueryUnderstanding
from src.engine.vector_pipeline import VectorPipeline
from src.graph_module.graph_retriever import GraphRetriever
from src.engine.fusion_chain import fuse_contexts

with QueryUnderstanding() as understanding:
    vector_result = VectorPipeline(understanding).run(question, history, top_k=3)

if vector_result.query.status == "needs_clarification":
    clarification = vector_result.query.clarification_question
    # Bàn giao clarification cho UI; chưa gọi Graph hoặc Fusion.
else:
    with GraphRetriever() as retriever:
        graph_context = retriever.retrieve(
            query_text=vector_result.query.normalized_question,
        )
    fused = fuse_contexts(vector_result.vector_context, graph_context)
    # TV1 đưa fused.content vào prompt sinh câu trả lời.
```

Không coi lỗi truy xuất là kết quả rỗng: bên gọi xử lý lỗi dịch vụ trước Fusion.
`None` có nghĩa nhánh không được cung cấp; `results=[]` là nhánh Vector không có
kết quả. Chỉ số token áp dụng cho `fused.content`; nếu bên gọi nối thêm câu hỏi,
system prompt, lịch sử hoặc nguồn lần nữa thì phải tính riêng phần đó.

## Evidence and citations

Đầu ra vẫn dùng `ContextResult`, không thêm schema chung mới:

| Trường | Nội dung |
| --- | --- |
| `branch_name` | `Context_Fusion` |
| `content` | Chuỗi ngữ cảnh với `[Vector Data]`, `[Graph Data]`, nhãn và nguồn; rỗng nếu không chọn được bằng chứng |
| `citations` | Nguồn của các khối được chọn, kèm nhãn `[Vn]` hoặc `[Gn]` |
| `raw_data.vector` | Bản sao đầy đủ `vector_context.model_dump()`, hoặc `None` |
| `raw_data.graph` | Bản sao đầy đủ `graph_context.model_dump()`, hoặc `None` |
| `raw_data.fusion` | Cấu hình và nhật ký chọn lọc bên dưới |

Vector dùng `raw_data.results`, mỗi chunk là một khối chứa nguyên văn `text`,
metadata `document` và nguồn từng passage. Nhãn theo vị trí gốc: nếu bỏ V2 thì
V3 vẫn mang `[V3]`. Nguồn có cùng dạng `[Vn] {JSON}` như VectorPipeline,
gồm `chunk_id`, `doc_id`, `passage_id`, `source_file`, `source_locator`.

Graph có `courses`/`chains` được định dạng từ dữ liệu cấu trúc:

- Các bản ghi môn học theo thứ tự đầu vào, sau đó các đường đi theo thứ tự đầu vào;
  nhãn `[Gn]` được gán trước khi loại trùng/chọn lọc.
- Một bản ghi môn học giữ toàn bộ nhóm điều kiện và metadata; một đường đi giữ
  toàn bộ nút, cạnh, chiều và loại quan hệ, ví dụ `A -[PREREQUISITE_FOR]-> B`.
- Chi tiết đường đi giữ `source_locator` tại từng nút/cạnh. Nguồn `[Gn]` chỉ lấy
  từ khối tương ứng, không lấy toàn bộ danh sách citations chung của Graph để
  gắn vào mọi khẳng định.
- Thuộc tính `prerequisites`/`recommended`/`corequisites` được giữ nguyên, không
  đổi loại quan hệ hay diễn giải danh sách thành biểu thức AND/OR.

Khi không có cấu trúc trên, toàn bộ `content` và `citations` của nhánh là một khối.
Điều này áp dụng cho Graph tra cứu giảng viên/khối kiến thức hiện tại và đầu vào
chỉ có văn bản. Một khối như vậy hoặc được giữ nguyên, hoặc bị bỏ toàn bộ nếu
không vừa ngân sách; nguồn chỉ hỗ trợ truy vết ở mức khối, không có ánh xạ tự tạo
đến từng câu. Fusion không dựng thêm tri thức từ các nút/cạnh Pyvis.

Các dạng không có kết quả rõ ràng của GraphRetriever (courses/chains rỗng,
không nhận diện thực thể, hoặc lookup giảng viên/khối không có node) không được
đóng gói thành bằng chứng chỉ vì `content` chứa thông báo trạng thái.

Loại trùng bảo thủ trong từng nhánh: Vector so sánh chunk/document IDs, text,
metadata tài liệu và passages; Graph so sánh bản ghi/đường đi đầy đủ, gồm nguồn.
Giữ bản đầu tiên, không dùng score/distance để phân biệt bản sao của cùng bằng
chứng. Văn bản giống nhau nhưng khác nguồn, khóa, phiên bản hoặc metadata vẫn
được giữ. Không gộp bằng chứng giữa Vector và Graph bằng độ tương đồng ngữ nghĩa.
Citation trùng hoàn toàn trong cùng nhãn bị loại; cùng nguồn hỗ trợ nhiều nhãn
vẫn xuất hiện ở từng nhãn để giữ liên kết.

## Token allocation and audit

Mặc định trần 4.096 token, encoding `o200k_base`. Sử dụng tokenizer thật,
không ước lượng từ ký tự hoặc số từ. Các chuỗi như `<|endoftext|>` trong tài liệu
được đếm như văn bản thường. Đổi `encoding_name` nếu model sinh yêu cầu tokenizer
khác; không tự suy ra model từ `.env`.

Hai lượt chọn khối:

1. Dành ngân sách cho phần định dạng chung, chia phần còn lại theo `graph_ratio`
   (mặc định 50% Graph, 50% Vector). Xét khối theo thứ tự đầu vào; bỏ qua khối
   chưa vừa phần phân bổ để xét khối tiếp theo. Đây là mục tiêu mềm do kích thước
   các khối không bằng nhau.
2. Dùng phần dư cho các khối còn lại, xét Vector trước Graph. Mỗi lần thêm đều
   đếm lại toàn bộ chuỗi gồm tiêu đề, nhãn và nguồn. Nhánh duy nhất được dùng
   toàn bộ ngân sách. `graph_ratio=0` hoặc `1` không tắt nhánh còn lại.

Không cắt chuỗi theo token hoặc tóm tắt bằng LLM. Khối không vừa bị bỏ nguyên
vẹn; khối sau nhỏ hơn vẫn có thể được chọn. Thứ tự hiển thị luôn theo thứ tự
đầu vào trong từng nhánh. Không chọn được khối nào thì trả `content=""`,
`citations=[]` và cảnh báo; trường hợp ngân sách quá nhỏ cũng xử lý như vậy.

`raw_data.fusion` có các trường:

| Trường | Ý nghĩa |
| --- | --- |
| `max_tokens`, `graph_ratio`, `encoding_name` | Cấu hình của lần gọi |
| `token_count` | Token chính xác của chuỗi `content` trả về |
| `selected_ids` | Nhãn bằng chứng được chọn theo thứ tự hiển thị |
| `dropped` | `{id, reason}` với `reason=token_budget` hoặc `duplicate`; duplicate có thêm `duplicate_of` |
| `warnings` | Cảnh báo thiếu nguồn, đầu vào chỉ có văn bản, nhánh rỗng, bỏ khối và cảnh báo từ Vector |
| `verification_status` | Luôn `not_verified` |

`raw_data.vector`/`graph` chứa **toàn bộ dữ liệu truy xuất**, kể cả khối không
được chọn. Dữ liệu Pyvis gốc ở `raw_data.graph.raw_data.pyvis` dùng để kiểm tra
đồ thị đã truy xuất, không phải bằng chứng rằng toàn bộ đồ thị đã có trong prompt.
Chỉ đưa `content` vào prompt; không nối thêm snapshot này vì sẽ vượt ngân sách và
đưa lại bằng chứng đã bị bỏ. Kết quả là bản sao độc lập, không sửa đầu vào.

Thiếu nguồn được ghi nhận, không tạo locator giả. Thiếu nguồn cạnh được cảnh báo
riêng dù đường đi có nguồn nút. Fusion không xác minh học vụ, xử lý mâu thuẫn,
chọn phiên bản quy định đúng hay chứng minh đồ thị đã truy xuất đầy đủ. Bên gọi
cần giữ kết quả/cảnh báo để TV1 và lớp kiểm chứng xử lý tiếp.

Cấu hình sai, input không phải `ContextResult`/`None`, cấu trúc đã nhận diện bị
lỗi hoặc path không khớp số cạnh/nút/đích gây `ValueError`. Thiếu `tiktoken`
hoặc không tải được tokenizer gây `RuntimeError` có hướng dẫn; không chuyển
sang một cách đếm gần đúng.

## Tests and B1/B2 comparison

```powershell
$env:TIKTOKEN_CACHE_DIR = Join-Path (Get-Location) '.venv/tiktoken-cache'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_context_fusion.py -v
```

Tests dùng tokenizer thật, dữ liệu giả đúng hợp đồng và không cần API key.
Bao phủ nguồn/nhãn, loại trùng, khác phiên bản/phạm vi, đường đi nhiều bước,
nhánh rỗng, các dạng Graph, khối vượt trần, cấp lại ngân sách, sát ranh giới token,
Unicode, dữ liệu lỗi, tokenizer lỗi và tính độc lập của snapshot.

Để kiểm tra B1/B2 với cùng trần:

```python
b1 = fuse_contexts(vector_context, None, max_tokens=4096)
b2 = fuse_contexts(vector_context, graph_context, max_tokens=4096)
```

Giữ cùng kết quả Vector, câu hỏi, phạm vi dữ liệu, model sinh và cấu hình giải mã;
lưu `raw_data.fusion` cho mỗi cấu hình. B1/B2 cùng trần nhưng không nhất thiết dùng
bằng nhau số token vì chọn nguyên khối. B2/S có thể dùng lại cùng kết quả Fusion.
4.096 token và tỷ lệ 50/50 là mặc định kỹ thuật ban đầu, chưa được tối ưu hóa hoặc
đánh giá chất lượng trên bộ câu hỏi thật.
