# Báo cáo sai sót trong tiền xử lý dữ liệu

**Người nhận:** Người phụ trách xử lý dữ liệu.  
**Ngày đối chiếu:** 13/10/2026.  
**Phạm vi:** JSON đề cương và Markdown học vụ/chương trình đào tạo (CTĐT), đầu ra tương ứng trong `DATA/processed/`, cùng mã trực tiếp đọc, chuyển đổi và kiểm tra các bản ghi này.

## 1. Nhận định chính

**Đầu ra hiện tại có mất nội dung và sai metadata, cần khắc phục trước khi dùng làm căn cứ đã xác minh để trả lời câu hỏi học vụ.** Đã xác nhận hai điều kiện chuyển ngành a), b) trong quyết định 1259 biến mất; bộ lọc xóa nhầm câu quy định và ngưỡng điểm; parser bảng làm mất CO3345 trong CTĐT KTMT, bỏ điều kiện và tạo tên môn rỗng. Đề cương CO3005 còn thiếu tỷ lệ đánh giá, hình thức và thời lượng kiểm tra/thi trong đầu ra.

Một bất thường khác **đã có trong dữ liệu đầu vào**: cả 129 đề cương chứa cùng bộ tên chuẩn đầu ra về kỹ năng ngôn ngữ. Không đủ căn cứ quy lỗi này cho bước tiền xử lý; trách nhiệm cần bổ sung ở bước này là phát hiện, đánh dấu và chuyển xác minh, thay vì đưa tiếp dữ liệu bất thường mà không có kiểm tra tương ứng.

Số liệu được tính lại từ dữ liệu hiện có:

| Nhóm dữ liệu | Tệp nguồn | Bản ghi tài liệu | Passage |
| --- | ---: | ---: | ---: |
| `DATA/raw/Raw_data_1/` → `DATA/processed/output_1/` | 129 JSON | 129 | 4.214 |
| `DATA/raw/Raw_data_2/` → `DATA/processed/output_2/` | 10 Markdown | 10 | 824 |
| **Tổng** | **139** | **139** | **5.038** |

Trong báo cáo, **passage** là một đoạn/bản ghi nội dung; **entity môn học** là passage có `content_type = "course_entity"`, với thông tin môn được mã hóa thành JSON trong trường `text`. `section_path` là đường dẫn mục; `source_locator` là vị trí nguồn.

**Cách kiểm chứng và giới hạn:** đọc nguồn, đầu ra và mã; kiểm tra cả `text` lẫn `section_path` trước khi kết luận mất nội dung; tính lại các thống kê; tái chạy parser Markdown trong bộ nhớ, chặn tạo thư mục và chuyển thao tác ghi thành bộ đệm. **20/20 JSON** được tái tạo khớp bản lưu (10 metadata và 10 mảng passage). Bộ đọc `load_corpus()` kiểm tra 139 tài liệu/5.038 passage, ghi nhận **0 lỗi cấu trúc** nhưng **5.574 cảnh báo**. Các kết quả này không chứng minh nội dung đúng về ngữ nghĩa. Bộ chuyển đổi đề cương được kiểm tra bằng đối chiếu trường nguồn–đầu ra và đọc mã, chưa tái chạy toàn bộ trong lần này.

Các kết luận chỉ áp dụng cho bản JSON/Markdown đang lưu. Chưa đối chiếu PDF/Word hay bản đề cương phát hành gốc; Markdown đã có hàng bảng bị tách, ô bị dính và ngày tháng sai bố cục. Báo cáo chỉ ghi nhận sai sót và đề xuất khắc phục, không sửa dữ liệu, mã nguồn hoặc báo cáo trước đó. Toàn bộ số liệu cần dùng được trình bày ngay trong báo cáo này.

## 2. Bảng tổng hợp theo mức độ ưu tiên

**P0:** ưu tiên bảo toàn/khôi phục nội dung hoặc xác minh nguồn trước khi dùng làm căn cứ. **P1:** hoàn thiện thuộc tính, truy nguồn và kiểm soát tái chạy trước khi nghiệm thu dữ liệu.

| Mã | Mức | Vấn đề | Tính chất bằng chứng | Kết quả cần đạt |
| --- | --- | --- | --- | --- |
| V01 | P0 | Mục liệt kê bị nhận thành tiêu đề rồi ghi đè | Đã xác nhận mất điều kiện a), b) của khoản 25.3, quyết định 1259 | Giữ đủ từng điều kiện và liên kết với khoản gốc |
| V02 | P0 | Lọc nhầm câu quy định và nội dung ngắn | Đã xác nhận câu trong 1260, HK251 và ngưỡng điểm trong 1259 bị loại | Lọc theo vai trò/bố cục, có nhật ký nội dung bị loại |
| V03 | P0 | Đọc bảng CTĐT thiếu môn, hàng nối, tên và quan hệ | Đã xác nhận CO3345 mất hoàn toàn trong đầu ra CTĐT KTMT; CO3015/CO3135 thiếu thuộc tính | Bảo toàn từng hàng, nối đúng ô và kiểm tra quan hệ |
| V05 | P0 | Bộ tên chuẩn đầu ra giống nhau trên 129 đề cương | Bất thường có sẵn trong nguồn; mã chuyển tiếp mà chưa phát hiện riêng | Đối chiếu đề cương gốc, đánh dấu trạng thái xác minh |
| V04 | P1 | Bỏ sót tỷ lệ đánh giá và hình thức thi | Hai đối tượng nguồn có ở 129/129 đề cương nhưng không được trích trực tiếp; CO3005 xác nhận thiếu thông tin cụ thể | Trích đủ giá trị, đơn vị và locator |
| V06 | P1 | Metadata sai hoặc thiếu | Đã xác nhận sai vai trò ngày, học kỳ/bậc học/ngành và phân loại | Tách đúng các khái niệm, giữ phạm vi nhiều giá trị |
| V07 | P1 | Truy nguồn chưa chính xác | 129 locator không tồn tại, 129 đề cương thiếu URL; locator bảng chỉ tới đầu khối | Truy đúng trường hoặc hàng tạo ra nội dung |
| V08 | P1 | Đường dẫn, lựa chọn phiên bản và duyệt dữ liệu | Đường dẫn sai và trạng thái `pending` đã xác nhận; rủi ro nguồn rỗng/chọn phiên bản suy ra từ mã | Chạy có kiểm soát, báo lỗi rõ, nghiệm thu nội dung trước khi duyệt |

## 3. Phân tích chi tiết

### V01 — Mất điều kiện học vụ do ghi đè tiêu đề

**Yêu cầu cần đáp ứng.** Mỗi điều kiện, ngoại lệ và mục liệt kê phải được giữ như nội dung có thể trích dẫn, gắn đúng điều/khoản. Không để việc phân cấp tiêu đề làm mất câu quy định.

**Hiện trạng và bằng chứng — lỗi đã xác nhận.** Nguồn [quyết định 1259](<../DATA/raw/Raw_data_2/1259 QĐ điều chỉnh_HVu chung_2931_2026.signed.md>), khoản 25.3 về chuyển ngành, có:

```text
Dòng 326: Người học được xem xét chuyển sang học một ngành đào tạo khác khi có đủ các điều kiện sau:
Dòng 328: a) Không đang là sinh viên trình độ năm thứ nhất hoặc năm cuối khóa đối với trình độ đại học, không thuộc diện bị xem xét buộc thôi học và còn đủ thời gian học tập theo quy định;
Dòng 330: b) Đạt điều kiện trúng tuyển của ngành đào tạo trong cùng khóa tuyển sinh;
Dòng 332: c) Ngành chuyển đến có đủ các điều kiện bảo đảm chất lượng, chưa vượt quá năng lực đào tạo của khoá tuyển sinh;
```

Trong [đầu ra 1259](../DATA/processed/output_2/passages/1259_QD_dieu_chinh_HVu_chung_2931_2026_signed.json):

| Passage | Nội dung còn giữ |
| --- | --- |
| `1259_QD_dieu_chinh_HVu_chung_2931_2026_signed_P097` | `text` là câu mở đầu ở dòng 326; locator `line_326` |
| `1259_QD_dieu_chinh_HVu_chung_2931_2026_signed_P098` | `text` là lời khuyến khích tham vấn Khoa ở dòng 334; `section_path` chứa điều kiện **c)**; locator `line_334` |

Đã tìm trong toàn bộ `text` và từng phần tử `section_path` của tài liệu: **không có hai điều kiện a), b)**. Điều kiện c) còn ở đường dẫn mục, vì vậy không kết luận cả ba điều kiện đều biến mất.

**Nguyên nhân.** Trong [parser Markdown](../DATA/process_raw_data_2.py), dòng 208 nhận `a)`, `b)`, `c)` bằng `letter_match`; dòng 234–243 đưa chúng vào `section_path` ở cấp 4 và cắt phần tử cùng cấp trước đó. Nhánh này không tạo passage cho chính câu vừa nhận là tiêu đề. Khi không có đoạn thân xen giữa, a) bị b) thay thế, rồi b) bị c) thay thế trước khi có bản ghi lưu nội dung. Mã nhận số thứ tự ở dòng 203 cũng cần rà soát theo cùng nguyên tắc; báo cáo không suy rộng rằng mọi mục đánh số đều đã mất.

**Tác động.** Đầu ra giữ câu “có đủ các điều kiện sau” nhưng thiếu điều kiện về trình độ năm học, tình trạng học vụ, thời gian học và điều kiện trúng tuyển. Câu trả lời dựa vào đầu ra có thể nêu thiếu yêu cầu chuyển ngành.

**Hướng khắc phục.** Phân biệt tiêu đề tổ chức tài liệu với câu liệt kê mang nội dung. Lưu các mục a), b), c) thành `list_item` hoặc một đoạn đầy đủ, giữ thứ tự, nhãn mục và liên kết khoản 25.3. Rà soát các chuỗi tiêu đề liên tiếp và mục cuối tài liệu chưa có đoạn thân.

**Tiêu chí nghiệm thu.** Ba điều kiện trên đều tìm được trong nội dung passage của 1259, mỗi điều kiện truy đúng dòng 328/330/332 hoặc khoảng dòng bao trùm; không chỉ tồn tại trong `section_path`. Ca kiểm tra gồm các mục liên tiếp, mục có/không có đoạn giải thích và mục cuối tệp; không có mục mang nội dung bị thay thế mà không được lưu.

### V02 — Bộ lọc loại nhầm nội dung quy định

**Yêu cầu cần đáp ứng.** Chỉ loại phần hành chính không cần giữ khi xác định được vai trò của nó; phải bảo toàn câu quy định dù câu có tên trường hoặc rất ngắn.

**Hiện trạng và bằng chứng — lỗi đã xác nhận.** Hai ví dụ bị bộ lọc tên trường loại bỏ:

| Nguồn | Trích đoạn trước xử lý | Sau xử lý |
| --- | --- | --- |
| [Quyết định 1260](<../DATA/raw/Raw_data_2/1260 QĐ điều chỉnh_HVu Đại học_2933_2026.signed.md>), dòng 316 | “Tạm thời cho phép sinh viên sử dụng kết quả các kỳ kiểm tra kỹ năng Nói – Viết do Trung tâm Ngoại ngữ Trường Đại học Bách khoa tổ chức để xét tốt nghiệp.” | Không có câu này trong `text` hoặc `section_path` của đầu ra 1260. `1260_QD_dieu_chinh_HVu_Dai_hoc_2933_2026_signed_P078` giữ dòng 314; `P079` giữ dòng 320. |
| [Kết luận HĐHV HK251](<../DATA/raw/Raw_data_2/Kết luận HĐHV_HK251.signed.md>), dòng 33 | “Người hướng dẫn chính của nghiên cứu sinh bắt buộc phải là giảng viên cơ hữu của Trường Đại học Bách khoa” | Không có câu này trong `text` hoặc `section_path` của `Ket_luan_HDHV_HK251_signed.json`. |

Ngưỡng độ dài cũng **đã gây mất nội dung trong dữ liệu hiện tại**, không chỉ là khả năng lý thuyết. Nguồn 1259 có `P: từ 5,0 trở lên.` ở dòng 210 và `P: từ 7,0 trở lên.”` ở dòng 218. Cả hai câu đều dưới 30 ký tự và bị loại. Các passage `1259_QD_dieu_chinh_HVu_chung_2931_2026_signed_P059`–`P061` còn tên nhóm học phần nhưng không giữ hai ngưỡng này trong nội dung hoặc đường dẫn mục. Việc tái chạy trong bộ nhớ xác nhận các câu nêu trên đi qua nhánh loại của bộ lọc.

**Nguyên nhân.** `BOILERPLATE_PATTERNS` và `is_boilerplate()` trong [parser Markdown](../DATA/process_raw_data_2.py), dòng 65–81, chứa mẫu `TRƯỜNG ĐẠI HỌC BÁCH KHOA` và `ĐẠI HỌC QUỐC GIA`. `re.search(..., re.IGNORECASE)` tìm ở bất kỳ vị trí nào, không giới hạn dòng quốc hiệu/tên cơ quan đầu trang. Hàm còn trả về `True` ngay khi `len(text.strip()) < 30`. `process_current_paragraph()` áp dụng kết quả này cho toàn đoạn.

**Tác động.** Mất ngoại lệ xét tốt nghiệp, yêu cầu đối với người hướng dẫn và ngưỡng đạt; phần còn lại có thể khiến người đọc hiểu sai hoặc thiếu điều kiện. Các câu quy định khác có cấu trúc tương tự tiếp tục có nguy cơ bị loại.

**Hướng khắc phục.** Xét vị trí, mẫu toàn dòng và vai trò của đoạn thay vì chỉ dò tên cơ quan. Loại số trang/dòng trang trí bằng quy tắc riêng. Với đoạn ngắn có điểm số, đơn vị, nhãn điều kiện hoặc ý nghĩa độc lập, giữ nguyên hoặc ghép với câu dẫn. Ghi lại đoạn bị loại, vị trí và lý do để kiểm tra.

**Tiêu chí nghiệm thu.** Khôi phục đủ bốn trích đoạn cụ thể trên, gắn đúng ngữ cảnh. Ca kiểm tra có câu thân bài chứa tên trường, ngưỡng điểm ngắn, số trang và tên cơ quan đầu trang; chỉ những phần thực sự không mang nội dung mới bị loại, có lý do kiểm tra được.

### V03 — Parser bảng CTĐT bỏ hàng nối, mất môn và điều kiện

**Yêu cầu cần đáp ứng.** Giữ đủ mã, tên, tín chỉ và điều kiện của môn trong từng nhóm CTĐT; xử lý hàng nối trước khi tạo entity. Hàng chưa đọc được phải còn ở dạng văn bản có cảnh báo, không bị bỏ im lặng. Các loại quan hệ phải được bảo toàn theo nguồn.

**Hiện trạng và bằng chứng — lỗi chuyển đổi trên nguồn đã có vấn đề bố cục.** Đối chiếu [CTĐT KHMT](../DATA/raw/Raw_data_2/2024_MT_KHMT.md), [CTĐT KTMT](../DATA/raw/Raw_data_2/2024_MT_KTMT.md) và hai tệp passage tương ứng:

| Chỉ tiêu | KHMT 2024 | KTMT 2024 |
| --- | ---: | ---: |
| Mã khác nhau trong ô nguồn khớp `\|\s*([A-Z]{2}\d{4})\s*\|` | 110 | 75 |
| Số bản ghi `course_entity` | 121 | 62 |
| Mã khác nhau trong entity | 81 | 62 |
| Mã thuộc tập ô nguồn chưa thành entity | 29 | 13 |
| Trong số đó, mã vẫn còn trong `text` | 29 | 12 |
| Mã không còn cả trong `text` lẫn `section_path` | 0 | 1: CO3345 |
| Entity có tên rỗng | 3 | 1 |

Đây là thống kê **ô mã nguyên vẹn**, không bao quát mã bị vỡ/dính cột. KHMT có nhiều entity cùng mã do môn xuất hiện ở nhiều nhóm. **Không được gọi 29 và 13 là số môn mất hoàn toàn.** Bốn tên rỗng là `2024_MT_KHMT_P024` (IM1025), `P062` (CO3137), `P071` (CO3135) và `2024_MT_KTMT_P068` (PE1039).

**a. CO3345 và quan hệ SHT trong CTĐT KTMT.** Các hàng nguồn liên tiếp:

```text
171: |||Thực tập Ngoài trường||CO2017(HT),<br>CO2011(HT),<br>CO2007(HT),<br>CO2003(HT)|
172: |1|CO3345||2|,<br>|
173: |||Internship||CO1027(HT),<br>CO1023(HT),<br>CO1007(HT),<br>CO1005(HT)|
174: |2|CO4041|Đồ án môn học Kỹthuật Máytính<br>Computer EngineeringProject|2|CO3345(SHT)<br>x|
175: |3|CO4347|Đồ án Tốt nghiệp (Kỹthuật Máytính)<br>|4|<sup>CO4041(TQ),</sup><br><br>x|
176: |||Capstone Project||CO3345(TQ)|
```

Trong [đầu ra KTMT](../DATA/processed/output_2/passages/2024_MT_KTMT.json):

- CO3345 không có entity và không còn ở bất kỳ `text`/`section_path` nào của tài liệu này. Kết luận chỉ áp dụng cho đầu ra CTĐT KTMT.
- `2024_MT_KTMT_P051` chứa CO4041 nhưng `conditions = []`, làm mất `CO3345(SHT)`.
- `2024_MT_KTMT_P052` chứa CO4347 với duy nhất `{"code":"CO4041","type":"TQ"}`; điều kiện `CO3345(TQ)` ở hàng nối 176 bị bỏ.

**b. CO3015 trong CTĐT KHMT.** Nguồn đã tách tên tiếng Việt và một điều kiện sang hàng trước:

```text
140: |||Kiểm tra Phần mềm||<sup>CO3001(KN),</sup>|
141: |4|CO3015|Software Testing|3|<br>CO1027(TQ)|
```

[Đầu ra KHMT](../DATA/processed/output_2/passages/2024_MT_KHMT.json), passage `2024_MT_KHMT_P066`:

```json
{"code":"CO3015","name":"Software Testing","credits":3,"conditions":[{"code":"CO1027","type":"TQ"}]}
```

Entity thiếu tên “Kiểm tra Phần mềm” và không gắn `CO3001(KN)` với CO3015. Việc ghép hàng phải được kiểm tra theo bảng gốc, không tự gán mọi hàng không mã cho môn trước đó.

**c. CO3135 trong CTĐT KHMT.** Dòng 152 chứa `Lậptrình cho Trí tuệnhân tạo và Khoa học dữ liệu` cùng `CO2003(TQ)` ở hàng không mã. Dòng 153 chứa mã CO3135, ô tên bắt đầu bằng `<br>Programmingfor Artificial Intelligence and Data Science(P4AI-D` và điều kiện `CO1027(TQ)`.

Giá trị `text` được giải mã của `2024_MT_KHMT_P071`:

```json
{"code":"CO3135","name":"","credits":3,"conditions":[{"code":"CO1027","type":"TQ"}]}
```

Cùng mã này, `2024_MT_KHMT_P092` và `2024_MT_KHMT_P118` giữ được tên tiếng Việt và cả CO2003(TQ), CO1027(TQ), tương ứng các hàng nguồn 190 và 245. Đây là sai lệch giữa các lần trích xuất; không phải toàn bộ thông tin CO3135 đã mất khỏi tài liệu.

**Nguyên nhân.** [Parser Markdown](../DATA/process_raw_data_2.py), dòng 83–105, chỉ đọc từng hàng bằng regex: yêu cầu ô tên có ít nhất một ký tự (`[^|]+`), ô tín chỉ nguyên vẹn và đúng số cột. Nó không nối hàng trước/sau. Dòng 93 xóa từ `<br>` trở đi, nên tên bắt đầu bằng `<br>` trở thành rỗng. Dòng 97 chỉ nhận `(TQ|SH|KN)`, không nhận `SHT` và `HT` đang có trong nguồn. Khi đọc được ít nhất một môn trong khối bảng, dòng 161–178 chỉ xuất các môn khớp mẫu rồi `return`, bỏ các hàng còn lại. Nếu cả khối không đọc được môn nào, khối vẫn được giữ dạng paragraph; điều này giải thích các mã chưa có entity nhưng chưa mất văn bản.

**Tác động.** Danh mục và quan hệ điều kiện không đầy đủ; `conditions = []` có thể bị hiểu nhầm là môn không có điều kiện. Tên rỗng và các lần xuất hiện thiếu nhất quán gây khó tra cứu, đối chiếu và xây dựng quan hệ môn học.

**Hướng khắc phục.** Phục hồi ô/hàng logic, giữ số dòng gốc rồi mới trích entity; đối chiếu bản gốc khi hàng nối mơ hồ. Tách tín chỉ khỏi điều kiện khi ô bị dính. Lưu phần chưa đọc được cùng cảnh báo. Bảo toàn ký hiệu quan hệ lạ và xác minh định nghĩa `SHT`, `HT`; không tự đổi `SHT` thành `SH`. Phân biệt “chưa trích đủ điều kiện” với “đã xác minh không có điều kiện”.

**Tiêu chí nghiệm thu.** CO3345 có tên, 2 tín chỉ và đầy đủ điều kiện sau khi kiểm tra hàng 171–173; CO4041 giữ quan hệ CO3345(SHT), CO4347 giữ thêm CO3345(TQ). CO3015 giữ tên và hai điều kiện của hàng 140–141. CO3135 không còn tên rỗng, không bỏ CO2003(TQ) ở lần xuất hiện nêu trên. Không còn bốn entity tên rỗng đã thống kê. Mọi hàng nguồn được ánh xạ tới entity hoặc văn bản còn giữ kèm lý do chưa trích; quan hệ chưa rõ vẫn truy được về nguồn. So sánh các lần xuất hiện cùng mã trong đúng nhóm/chuyên ngành, không gộp mù theo mã môn.

### V04 — Thiếu tỷ lệ đánh giá, hình thức và thời lượng thi trong đề cương

**Yêu cầu cần đáp ứng.** Trích riêng thành phần đánh giá, tỷ trọng, hình thức, thời lượng và đơn vị; không dùng phân bổ tín chỉ/tiết học để thay cho tỷ trọng điểm.

**Hiện trạng và bằng chứng — lỗi bỏ sót trường đã xác nhận.** Cả **129/129 JSON nguồn** có đối tượng `tyledanhgia` và `hinhthucdanhgia` khác rỗng. Đầu ra không có passage với locator bắt đầu bằng hai trường này; mã không đọc chúng. Điều này không đồng nghĩa mọi chi tiết đánh giá đều mất ở mọi đề cương, vì mô tả ở trường khác có thể còn thông tin liên quan.

Ví dụ [nguồn CO3005](../DATA/raw/Raw_data_1/DCMH.CO3005.13.1_42982.json), “Nguyên lý Ngôn ngữ Lập trình”:

| Trường nguồn | Giá trị |
| --- | --- |
| `tyledanhgia.baiTapLon` | 30 (%) |
| `tyledanhgia.kiemTra` | 20 (%) |
| `tyledanhgia.thi` | 40 (%) |
| `tyledanhgia.khac` | 10 (%) |
| `tyledanhgia.tong` | 100 (%) |
| `hinhthucdanhgia.kiemTra.hinhThuc.text.vi` | `Trắc nghiệm (chấm máy)` |
| `hinhthucdanhgia.kiemTra.thoiGian.thoigian` | 60; nhãn nguồn `60 phút` |
| `hinhthucdanhgia.thi.hinhThuc.text.vi` | `Trắc nghiệm (chấm máy)` |
| `hinhthucdanhgia.thi.thoiGian.thoigian` | 90; nhãn nguồn `90 phút` |

Trong [passage CO3005](../DATA/processed/output_1/passages/DCMH.CO3005.13.1.json), các passage `DCMH.CO3005.13.1_P21`–`P28` lấy từ `hddg[0]`–`hddg[7]`. Chẳng hạn P22 chứa tên “Kiểm tra giữa kì”, P24 chứa “Bài tập lớn 1”, nhưng không có tỷ trọng tương ứng. Đã kiểm tra cả nội dung và đường dẫn mục của 38 passage: không có thông tin trắc nghiệm, thời lượng 60/90 phút hoặc bộ tỷ lệ trên. P6 có `baiTapLon` và các con số ở phần tín chỉ/tiết; đó là đại lượng khác, không phải bằng chứng tỷ trọng điểm được giữ.

**Nguyên nhân.** [Script đề cương](../DATA/process_raw_data_1.py), dòng 162–241, chọn các nhóm thông tin chung, thời gian, chuẩn đầu ra, `hddg`, nội dung chi tiết và liên hệ; bỏ hai đối tượng đánh giá nêu trên. Dòng 199–224 chủ yếu chuyển `hddg` bằng `str(dict)`, chưa tạo mô tả đánh giá đầy đủ từ các trường riêng.

**Tác động.** Không đủ căn cứ trả lời tỷ lệ bài tập lớn hoặc hình thức/thời lượng thi của CO3005; dễ nhầm tỷ lệ với số tín chỉ, tiết hoặc giờ tự học.

**Hướng khắc phục.** Bổ sung bản ghi có cấu trúc và câu diễn đạt rõ thành phần–giá trị–đơn vị, kèm locator trường. Giữ phân biệt số 0, `null` và không có trường. Kiểm tra tổng tỷ lệ khi nguồn đủ thông tin, không tự suy tỷ lệ còn thiếu.

**Tiêu chí nghiệm thu.** CO3005 trả được đúng 30/20/40/10%, tổng 100%, trắc nghiệm chấm máy, kiểm tra 60 phút và thi 90 phút, mỗi giá trị truy đúng trường nguồn. Với toàn bộ 129 đề cương, có đối chiếu độ bao phủ từng trường đánh giá; giá trị thiếu/bất nhất được cảnh báo thay vì tự điền.

### V05 — Chuẩn đầu ra bất thường đã có sẵn trong nguồn

**Yêu cầu cần đáp ứng.** Chuẩn đầu ra phải phù hợp môn và phiên bản; phát hiện nội dung lặp bất thường trước khi coi là dữ liệu đã xác minh.

**Hiện trạng và bằng chứng — bất thường từ nguồn.** So sánh dãy `cdr[*].ten` (cả tên tiếng Việt/tiếng Anh hiện có) của **129 JSON** cho kết quả **một dãy duy nhất**, mỗi đề cương có **14 mục**. Trong phần tên tiếng Việt có **7 nội dung khác nhau, mỗi nội dung lặp hai lần**: mục gốc CTĐT 2019, từ vựng, ngữ pháp, nghe, đọc, nói, viết.

Ví dụ nguồn CO3005:

```text
cdr[0].ten.vi = "Chuẩn đầu ra môn học (Root) - Năm CTĐT 2019"
cdr[1].ten.vi = "Từ vựng: Biết được một lượng từ vựng đủ để có thể diễn đạt ý mình về các chủ đề thường nhật như Bạn là ai, Trái tim ở đâu, Sức khỏe và hạnh phúc, Học tập và Gia đình & Bạn bè."
```

Hai nội dung này được chuyển sang `DCMH.CO3005.13.1_P7` và `P8`, rồi lặp ở `P14` và `P15`. Toàn bộ nhóm tạo **1.806 passage**, bằng khoảng **35,8%** của 5.038 passage; mỗi trong bảy nội dung xuất hiện **258 lần**. Kết luận giống nhau ở đây là về **bộ tên chuẩn đầu ra**, không khẳng định toàn bộ đối tượng `cdr` hoặc toàn bộ đề cương giống hệt nhau.

**Nguyên nhân.** Bất thường đã hiện diện ở JSON nguồn; chưa đủ chứng cứ phân biệt lỗi dữ liệu phát hành, bước thu thập/chuyển đổi trước đó hoặc dữ liệu mẫu. [Script đề cương](../DATA/process_raw_data_1.py), dòng 189–198, lặp qua `cdr` và chuyển tên sang passage mà không kiểm tra mức trùng giữa môn hoặc sự phù hợp với nội dung môn. Trạng thái `pending` có tồn tại, nhưng chưa biểu thị riêng bất thường này.

**Tác động.** Các chuẩn đầu ra về ngôn ngữ có thể bị gán cho môn chuyên ngành và lặp với tần suất lớn trong dữ liệu dùng để truy xuất. Chưa đo tác động định lượng đến chất lượng câu trả lời.

**Hướng khắc phục.** Đối chiếu đề cương gốc của từng môn/phiên bản; đánh dấu nhóm `cdr` chưa xác minh và không dùng nhóm này làm căn cứ đã duyệt trước khi xử lý. Bổ sung phát hiện dãy chuẩn đầu ra trùng giữa môn, trùng nội bộ và lệch chủ đề. Không tự viết lại chuẩn đầu ra hoặc xóa trùng toàn corpus khi chưa biết nguồn đúng.

**Tiêu chí nghiệm thu.** Cả 129 bộ chuẩn đầu ra có kết quả kiểm tra nguồn và trạng thái rõ ràng. Mỗi nội dung sửa có căn cứ theo môn/phiên bản; trường hợp dùng chung hợp lệ có giải thích. Ca kiểm tra phải phát hiện được hiện tượng 129 dãy giống nhau và hai lần lặp nội bộ, đồng thời không đánh đồng mọi nội dung dùng chung với lỗi.

### V06 — Metadata sai vai trò ngày, phạm vi và loại tài liệu

**Yêu cầu cần đáp ứng.** Phân biệt ngày ban hành, cập nhật, họp và hiệu lực; học kỳ, khóa tuyển sinh, bậc học và hình thức đào tạo; giữ đủ ngành/chuyên ngành. Phân loại tài liệu theo nội dung nhận diện và quy ước schema rõ ràng.

**Hiện trạng và bằng chứng — lỗi ánh xạ và thiếu metadata đã xác nhận.**

| Thành phần | Nguồn → đầu ra hiện tại | Phạm vi xác nhận |
| --- | --- | --- |
| Ngày cập nhật thành ngày ban hành | CO3005: `capnhat = "27/01/2026 09:18"` → `issued_date = "2026-01-27"` | Cả 129 đề cương được mã ánh xạ từ `capnhat`; chưa có căn cứ coi đây là ngày ban hành |
| Ngày viện dẫn thành ngày ban hành | Nguồn 1259/1260 dòng 11 dẫn quyết định 2931/2933 ký ngày 10/9/2021 → cả hai lưu `issued_date = "2021-09-10"` | Văn bản sửa đổi mang năm 2026; dòng ngày đầu văn bản bị tách bố cục |
| Ngày họp thành ngày ban hành | [Văn bản HK242](<../DATA/raw/Raw_data_2/Ket luan tai Phien hop Hoi dong hoc vu DH _ SDH HK242.signed.md>), dòng 11: cuộc họp 26/03/2025 → `issued_date = "2025-03-26"` | Dòng 5 có ngày của thông báo bị tách vị trí; không đủ cơ sở dùng ngày họp làm ngày ban hành |
| Học kỳ thành khóa | CO3005: `hockyapdung = "HK262"` → `scope.cohorts = ["HK262"]` | 129/129 đề cương: 125 HK261, 4 HK262 |
| Bậc học thành hình thức đào tạo | `thongtinchung.bacDaoTao.ten.vi` → `scope.study_mode` | 129/129: 76 Đại học, 33 Thạc sĩ, 11 Sau đại học, 9 Tiến sĩ; các nhãn này không xác định chính quy/vừa làm vừa học |
| Chỉ giữ ngành đầu tiên | [Nguồn CO1007](../DATA/raw/Raw_data_1/DCMH.CO1007.13.1_42979.json) có `nganh[0] = Ngành Kỹ thuật Máy tính`, `nganh[1] = Ngành Khoa học Máy tính` → [metadata](../DATA/processed/output_1/documents/DCMH.CO1007.13.1.json) chỉ giữ KTMT | 48/129 đề cương có từ hai mục ngành/chuyên ngành; metadata chỉ giữ mục đầu |
| Thiếu phạm vi Markdown | Hai CTĐT ghi rõ cử nhân khóa 2024, ngành KHMT/KTMT trong nguồn → `program = null`, `study_mode = null`, `cohorts = []` | Cả 10 tài liệu Markdown có cùng tình trạng thiếu các trường này; không đồng nghĩa cả 10 đều áp dụng khóa 2024 |
| Phân loại chưa đúng | Hai quyết định 1259/1260, hai CTĐT và HK242 đều đang là `regulation` | 1259/1260 có tiêu đề “QUYẾT ĐỊNH”; HK242 có tiêu đề “THÔNG BÁO”; hai CTĐT chưa được phân biệt theo loại chương trình đào tạo |

Riêng KHMT, dòng 5 nêu “CHƯƠNG TRÌNH ĐÀO TẠO CỬ NHÂN KHÓA 2024”, dòng 9 nêu ngành Khoa học Máy tính. Mất thông tin trong **metadata** không có nghĩa các câu đó đã mất khỏi **văn bản/đường dẫn mục**. Tương tự, số 48 là số đề cương có nhiều mục `nganh`, không phải số ngành bị mất.

Ngoài ra, **139/139 tài liệu có `effective_date = null`**. Đây là thông tin chưa được biểu diễn, không phải bằng chứng mỗi tài liệu đều có ngày hiệu lực tường minh để điền. Với ngày đầu 1259/1260, Markdown thể hiện năm 2026 và các số `16 03` bị tách; cần kiểm tra bản gốc trước khi chuẩn hóa, không lấy ngày viện dẫn thay thế.

**Nguyên nhân.** [Script đề cương](../DATA/process_raw_data_1.py), dòng 121–147, dùng `capnhat`, `nganh[0]`, `bacDaoTao` và `hockyapdung` cho các trường sai/thiếu vai trò. [Parser Markdown](../DATA/process_raw_data_2.py), dòng 50–63, tìm ngày khớp mẫu trong toàn văn, không phân biệt vai trò ngày; dòng 118–124 phân loại từ tên tệp. Tên “QĐ” không khớp “Quyết định”; kiểm tra chuỗi không dấu có khoảng trắng trong khi `doc_id` đã đổi khoảng trắng thành `_`, khiến trường hợp HK242 không được nhận đúng. Metadata Markdown không trích phạm vi mà gán sẵn các giá trị rỗng.

**Tác động.** Lọc sai ngành, khóa hoặc bậc học; chọn nhầm thời điểm áp dụng hay văn bản sửa đổi. Việc trường có giá trị không bảo đảm giá trị đó đúng nghĩa.

**Hướng khắc phục.** Tách `updated_at`, `issued_date`, ngày họp và `effective_date`; lưu vai trò ngày và căn cứ trích. Tách học kỳ áp dụng, khóa tuyển sinh, bậc học, hình thức đào tạo. Giữ danh sách ngành/chuyên ngành cùng mã và quan hệ, không lấy duy nhất phần tử đầu. Đọc tiêu đề nội dung, số/ký hiệu và quy ước loại tài liệu; biểu diễn quan hệ sửa đổi/được viện dẫn. Giữ giá trị chưa biết cùng lý do thay vì tự suy từ tên tệp hoặc loại ngày khác.

**Tiêu chí nghiệm thu.** Không còn HK261/HK262 trong trường khóa tuyển sinh; bậc học không bị coi là hình thức đào tạo. CO1007 giữ cả KTMT và KHMT; đủ mọi mục `nganh` của 48 đề cương nhiều mục. Hai CTĐT có phạm vi cử nhân, ngành tương ứng và khóa 2024. Ngày 2021 của văn bản được viện dẫn không còn làm ngày ban hành 1259/1260; CO3005 giữ ngày cập nhật đúng vai trò. Loại của năm tài liệu nêu trên được rà soát; trường ngày/hiệu lực chưa xác minh có lý do và căn cứ cần bổ sung, không tự điền.

### V07 — Locator không tồn tại, vị trí bảng quá rộng và thiếu URL đề cương

**Yêu cầu cần đáp ứng.** Từ mỗi passage phải truy được các trường/hàng tạo ra nội dung. URL chỉ là một thành phần truy nguồn; cần giữ tệp nguồn, phiên bản và vị trí chính xác.

**Hiện trạng và bằng chứng — lỗi/thiếu đã xác nhận.**

- **129 locator không tồn tại:** nhóm “Phân bổ thời gian” dùng `{"type":"json_field","path":"pbsotc_pbsotiet"}`. Ví dụ `DCMH.CO3005.13.1_P6`; nguồn chỉ có hai trường riêng `pbsotc` và `pbsotiet`, không có khóa ghép. Bộ kiểm tra ghi nhận đúng 129 cảnh báo `unresolved_locator`.
- **Locator entity bảng là đầu khối:** 13 entity `2024_MT_KHMT_P006`–`P018` đều trỏ `line_19`, là dòng tiêu đề bảng. MT1003/P006 thực tế ở dòng 23, MT1005/P007 ở dòng 24. CO3015/P066 trỏ `line_93`, trong khi các hàng cần đối chiếu là 140–141. Vị trí tồn tại nhưng chưa xác định đúng hàng và hàng nối.
- **129/129 đề cương có `source_url = null`**, nhưng vẫn có `source_file` và tệp nguồn cục bộ đọc được. Không kết luận mất toàn bộ truy vết.

**Nguyên nhân.** [Script đề cương](../DATA/process_raw_data_1.py), dòng 185–188, tạo locator ghép tùy ý. URL phụ thuộc `build_id_mapping()` đọc `DATA/pages/page-*.json` (dòng 21–36), trong khi `DATA/pages/` không tồn tại. [Parser Markdown](../DATA/process_raw_data_2.py), dòng 173, gán cùng `start_line_idx` cho mọi môn trong khối, không giữ vị trí từng hàng. Bộ kiểm tra locator Markdown trong [data_loader.py](../src/vector_module/data_loader.py), dòng 177–179, chỉ kiểm tra dòng không vượt phạm vi tệp, chưa chứng minh dòng đó chứa bằng chứng cho passage.

**Tác động.** Người duyệt khó tái kiểm tra số liệu, có thể mở nhầm hàng hoặc không lần ra nguồn phát hành. Một locator hợp lệ về cú pháp/vị trí vẫn có thể không đủ căn cứ cho nội dung.

**Hướng khắc phục.** Cho phép một passage tham chiếu nhiều trường (`pbsotc`, `pbsotiet`) và nhiều khoảng dòng. Entity bảng giữ hàng chính, hàng nối, cột và phiên bản nguồn; bổ sung trang nếu đối chiếu được tài liệu gốc. Khôi phục ánh xạ URL từ nguồn thu thập đáng tin cậy; không mặc nhiên suy URL hợp lệ chỉ từ hậu tố số trong tên tệp.

**Tiêu chí nghiệm thu.** Không còn 129 locator ghép không phân giải; hai trường của passage thời gian đều truy được. Locator CO3015 phủ hàng 140–141; CO3135 phủ hàng cần nối; MT1003/MT1005 trỏ đúng hàng thay vì chỉ đầu bảng. Với 129 đề cương, URL được xác minh hoặc ghi rõ lý do chưa có, đồng thời luôn giữ nguồn cục bộ và định danh phiên bản. Kiểm tra cả việc locator tồn tại và nội dung nguồn có hỗ trợ giá trị được trích.

### V08 — Khả năng tái chạy, lựa chọn phiên bản và kiểm soát chất lượng

**Yêu cầu cần đáp ứng.** Lệnh xử lý mặc định đọc/ghi đúng cây thư mục, báo lỗi khi không có nguồn hoặc không có bản ghi đạt yêu cầu; quy tắc chọn phiên bản minh bạch và tái lập được. Dữ liệu phải được kiểm tra nội dung trước khi chuyển trạng thái duyệt.

**Hiện trạng và bằng chứng.**

| Hạng mục | Kết quả đối chiếu | Loại kết luận |
| --- | --- | --- |
| Đường dẫn đề cương | Script dùng `DATA/Raw_data_1` → `DATA/output_1`; thực tế là `DATA/raw/Raw_data_1` → `DATA/processed/output_1` | Sai cấu hình đã xác nhận |
| Đường dẫn Markdown | Script dùng `DATA/Raw_data_2` → `DATA/output_2`; thực tế là `DATA/raw/Raw_data_2` → `DATA/processed/output_2` | Sai cấu hình đã xác nhận |
| Nguồn rỗng | Hai đường dẫn đầu vào mặc định không tồn tại. Vòng lặp `glob.glob` không kiểm tra danh sách rỗng, cuối chương trình vẫn in hoàn thành | Rủi ro chạy không xử lý gì suy ra từ mã; chưa chạy lệnh mặc định để ghi ra đĩa |
| Chọn phiên bản đề cương | Chỉ nhận HK261/HK262; bỏ các bản cùng `mamonhoc` sau bản gặp đầu tiên, không sắp xếp tệp hay so sánh `phienban`/thời điểm áp dụng | Rủi ro khi có nhiều phiên bản. Hiện có 129 mã khác nhau trong 129 nguồn, chưa chứng minh đã bỏ nhầm phiên bản vì trùng mã |
| Trạng thái duyệt | **5.038/5.038 passage là `pending`**, không có `approved` | Trạng thái hiện có đã xác nhận |

Mã liên quan: [script đề cương](../DATA/process_raw_data_1.py), dòng 11–18, 83–114 và 250–259; [parser Markdown](../DATA/process_raw_data_2.py), dòng 25–32 và 260–265. Các lệnh tạo thư mục đang chạy ngay khi nạp script, trước khi xác nhận có nguồn.

Kết quả chạy `load_corpus()` trong bộ nhớ:

| Cảnh báo | Số lần |
| --- | ---: |
| `unreviewed` | 5.038 |
| `missing_effective_date` | 139 |
| `missing_source_url` | 129 |
| `semester_in_cohorts` | 129 |
| `unresolved_locator` | 129 |
| `incomplete_scope` | 10 |
| **Tổng** | **5.574** |

Một bản ghi có thể sinh nhiều cảnh báo; không diễn giải 5.574 thành số bản ghi lỗi khác nhau. **0 lỗi cấu trúc** vẫn đi cùng các lỗi nội dung V01–V07. Bộ kiểm tra hiện chưa giải mã và kiểm tra sâu tên/điều kiện bên trong chuỗi `text` của entity môn học; bốn tên rỗng vì vậy không trở thành lỗi schema. Việc tái tạo 20/20 JSON Markdown khớp bản lưu chỉ chứng minh lỗi hiện có tái lập được, không chứng minh parser đúng.

**Nguyên nhân.** Đường dẫn cố định chưa theo cấu trúc lưu trữ hiện tại; thiếu kiểm tra số tệp và số đầu ra; lựa chọn phiên bản dựa vào thứ tự gặp; hai bộ tạo passage gán `pending` nhưng trạng thái duyệt chưa được hoàn tất trong dữ liệu. Kiểm tra hiện có chủ yếu bảo vệ cấu trúc/liên kết nguồn, chưa đo đầy đủ mức bảo toàn nội dung và tính đúng của từng thuộc tính.

**Tác động.** Một lần chạy có thể không cập nhật bộ dữ liệu mà người dùng đang đọc; khi bổ sung phiên bản có thể chọn bản không phù hợp. Dữ liệu sai ngữ nghĩa vẫn có thể vượt kiểm tra cấu trúc và tiếp tục được sử dụng.

**Hướng khắc phục.** Cấu hình thống nhất đường dẫn, kiểm tra nguồn trước khi tạo/ghi đầu ra; báo lỗi rõ khi nguồn rỗng hoặc tất cả bản ghi bị loại ngoài dự kiến. Ghi số lượng đầu vào, xử lý, bỏ qua và lý do. Quy định khóa định danh theo môn/phiên bản/phạm vi hoặc quy tắc chọn phiên bản có căn cứ, ghi lại bản được chọn và bản bị loại. Bổ sung kiểm tra ngữ nghĩa gắn với V01–V07; ghi người duyệt, thời điểm và căn cứ cho dữ liệu đủ điều kiện, giữ trạng thái cần xác minh cho phần chưa rõ.

**Tiêu chí nghiệm thu.** Lệnh chuẩn chạy từ thư mục dự án đọc đúng `DATA/raw/` và tạo kết quả tại `DATA/processed/`. Nguồn không tồn tại/rỗng và trường hợp lọc hết đều được báo rõ, không coi là lần chạy thành công bình thường. Chạy hai lần với cùng nguồn/cấu hình cho cùng kết quả; đổi thứ tự tệp không làm đổi quyết định chọn phiên bản. Có tổng kết xử lý và kiểm tra ngữ nghĩa. Chỉ passage đã đối chiếu đạt tiêu chí mới được duyệt; không đổi hàng loạt `pending` thành `approved` để làm hết cảnh báo.

## 4. Kiểm tra sau khắc phục và điều kiện bàn giao

Người phụ trách xử lý dữ liệu cần đối chiếu lại đầu ra với các ví dụ nguồn ở mục 3 và ghi nhận kết quả theo từng mã vấn đề. Không chỉ chạy lại kiểm tra schema.

| Nhóm kiểm tra | Điều kiện đạt |
| --- | --- |
| Bảo toàn điều kiện học vụ — V01, V02 | Đủ a), b), c) khoản 25.3 của 1259; giữ các câu quy định trong 1260/HK251 và các ngưỡng P. Mỗi nội dung tìm được trong passage và đúng ngữ cảnh nguồn. |
| Bảng CTĐT — V03 | CO3345, CO3015, CO3135 và các điều kiện liên quan được khôi phục đúng. Không còn tên rỗng đã nêu; hàng chưa trích vẫn được giữ, có cảnh báo. Không biến lỗi đọc điều kiện thành khẳng định “không có điều kiện”. |
| Đánh giá đề cương — V04 | CO3005 có đủ tỷ trọng, hình thức, thời lượng và đơn vị; có kiểm tra độ bao phủ các trường đánh giá cho 129 đề cương. |
| Chất lượng nguồn — V05 | Mỗi bộ chuẩn đầu ra có kết quả đối chiếu hoặc trạng thái chưa xác minh cụ thể; phát hiện được hiện tượng trùng bất thường. Không quy lỗi nguồn cho parser hoặc tự viết lại nội dung khi thiếu căn cứ. |
| Metadata — V06 | Tách đúng các loại ngày và phạm vi; giữ đủ danh sách ngành; loại tài liệu và giá trị chưa biết có căn cứ rõ ràng. |
| Truy nguồn — V07 | Locator phân giải được và chỉ đúng bằng chứng, bao gồm nhiều trường/hàng nối. URL đề cương có kết quả xác minh hoặc lý do chưa có. |
| Tái chạy và duyệt — V08 | Đường dẫn đúng, trường hợp rỗng được xử lý rõ, lựa chọn phiên bản ổn định, có thống kê bỏ qua và kiểm tra ngữ nghĩa; trạng thái duyệt phản ánh việc đã kiểm tra thực tế. |

Khi đánh giá độ bao phủ, phải tìm cả `text` và `section_path` để phân biệt **mất hoàn toàn**, **chỉ còn trong đường dẫn mục** và **chưa thành entity nhưng còn văn bản**. Với điều kiện nghiệp vụ, việc chỉ còn trong đường dẫn mục vẫn cần cải thiện để nội dung được lưu/trích dẫn đầy đủ. Mọi sai lệch chưa xác minh phải còn dấu vết và lý do; không dùng sự khớp giữa hai lần chạy hay việc schema hợp lệ làm bằng chứng thay thế cho tính đúng của dữ liệu.
