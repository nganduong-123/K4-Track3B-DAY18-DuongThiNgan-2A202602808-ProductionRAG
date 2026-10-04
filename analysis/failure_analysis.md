# Failure Analysis — Lab 18: Production RAG

**Họ và tên học viên:** Dương Thị Ngân

**MSSV:** 2A202602808

**Khóa:** K4 - Track 3B

## RAGAS Scores

| Metric | Naive Baseline | Production | Δ |
|---|---:|---:|---:|
| Faithfulness | 0.6583 | 0.8271 | +0.1688 |
| Answer Relevancy | 0.1889 | 0.2660 | +0.0771 |
| Context Precision | 0.7958 | 0.9542 | +0.1584 |
| Context Recall | 0.7000 | 0.9250 | +0.2250 |

Pipeline Production tăng rõ ở Faithfulness, Context Precision và Context Recall. Answer Relevancy vẫn thấp dù nhiều câu trả lời đúng ý; em cho rằng một phần do metric đang dùng embedding cục bộ `all-MiniLM-L6-v2` với câu tiếng Việt. Vì vậy em đọc lại từng output và context, không chỉ dựa vào điểm tổng.

## Bottom-5 Failures

### #1 — Tạm ứng 15 triệu, thanh toán sau 20 ngày

- **Expected:** Quá hạn 5 ngày; phí 2%/tháng trên 15 triệu là 300.000 đồng/tháng, tính theo tỷ lệ 5 ngày khoảng 50.000 đồng.
- **Got:** Mô hình nêu đúng hạn 15 ngày và mức 2%, nhưng kết luận “không tính vì chưa đủ một tháng”, sau đó còn thêm “Không tìm thấy”.
- **Worst metric:** `answer_relevancy` (0.0000).
- **Error Tree:** Output sai → context đúng và đủ → query rõ → lỗi ở bước LLM synthesis.
- **Root cause:** Prompt chưa yêu cầu tính pro-rata và chưa chặn câu kết thúc mâu thuẫn với phần tính toán phía trên.
- **Suggested fix:** Yêu cầu trả lời theo công thức `số tiền × 2% × số ngày quá hạn / 30`, chỉ xuất một kết luận cuối cùng.

### #2 — Thiết bị 55 triệu

- **Expected:** Tổng Giám đốc (CEO) phê duyệt vì giá trị trên 50 triệu.
- **Got:** Câu trả lời đúng và context có đúng hàng “Trên 50.000.000 VNĐ → CEO”, nhưng Faithfulness vẫn bị chấm 0.
- **Worst metric:** `faithfulness` (0.0000).
- **Error Tree:** Output đúng → context đúng → query rõ → lỗi false-negative ở evaluator.
- **Root cause:** Câu trả lời quá ngắn và metric/judge có thể không nối được “55 triệu” với điều kiện “trên 50 triệu”.
- **Suggested fix:** Trả lời kèm căn cứ: “55 triệu > 50 triệu, nên CEO phê duyệt”, rồi chạy lại judge tuần tự để kiểm tra độ ổn định.

### #3 — Laptop 30 triệu cho nhân viên mới

- **Expected:** Director phê duyệt, CNTT xác nhận cấu hình và cần ít nhất 3 báo giá.
- **Got:** Trả lời đúng người phê duyệt và yêu cầu CNTT nhưng thiếu điều kiện 3 báo giá. Trong top-3 có hai context không liên quan trước context mua sắm.
- **Worst metric:** `answer_relevancy` (0.1329).
- **Error Tree:** Output thiếu một ý → context đúng có trong top-3 → query rõ → lỗi ở reranking và synthesis.
- **Root cause:** Lexical reranker ưu tiên các đoạn có từ chung “nhân viên/cần”, còn prompt chưa yêu cầu kiểm tra đủ mọi điều kiện trong context.
- **Suggested fix:** Dùng `bge-reranker-v2-m3`, lọc stopword và yêu cầu LLM liệt kê đủ phê duyệt, xác nhận kỹ thuật, báo giá.

### #4 — Senior có 9 năm thâm niên

- **Expected:** 18 ngày phép; lương Senior P3–P4 từ 20–35 triệu đồng/tháng.
- **Got:** Tính đúng 18 ngày nhưng hiểu nhầm câu hỏi về khoảng lương thành “được hưởng lương đầy đủ khi nghỉ phép”. Context top-3 không có bảng lương.
- **Worst metric:** `answer_relevancy` (0.1334).
- **Error Tree:** Output thiếu nửa sau → context thiếu bảng lương → query rõ → lỗi ở retrieval đa tài liệu.
- **Root cause:** Query có hai ý thuộc hai tài liệu khác nhau, nhưng reranker chọn ba đoạn đều nghiêng về chính sách nghỉ.
- **Suggested fix:** Tách query thành hai sub-query “ngày phép” và “khung lương Senior”, tìm riêng rồi hợp nhất context trước khi sinh câu trả lời.

### #5 — Hoàn chi khóa học 25 triệu

- **Expected:** Nghỉ sau 8 tháng là trước cam kết 1 năm nên hoàn trả 100%, tức 25 triệu đồng.
- **Got:** Câu trả lời đúng và context hỗ trợ đầy đủ, nhưng Answer Relevancy chỉ 0.0078.
- **Worst metric:** `answer_relevancy` (0.0078).
- **Error Tree:** Output đúng → context đúng → query rõ → metric tiếng Việt cho false-negative.
- **Root cause:** Embedding cục bộ dùng cho Answer Relevancy chưa phù hợp tiếng Việt, trong khi các metric còn lại và kiểm tra thủ công đều xác nhận câu trả lời.
- **Suggested fix:** Dùng embedding đa ngôn ngữ như `BAAI/bge-m3` cho evaluator hoặc thêm phép kiểm tra số/điều kiện dạng rule-based.

## Case Study cho presentation

**Câu chọn phân tích:** Một nhân viên Senior có 9 năm thâm niên được nghỉ bao nhiêu ngày phép năm và lương trong khoảng nào?

**Error Tree walkthrough:**

1. Output đúng? → Đúng phần ngày phép, sai phần khoảng lương.
2. Context đúng? → Có context phép năm nhưng thiếu bảng lương Senior.
3. Query rewrite OK? → Query rõ nhưng chứa hai yêu cầu thuộc hai tài liệu.
4. Fix ở bước nào? → Tách query, retrieval riêng từng ý, sau đó hợp nhất context và trả lời đủ hai phần.

**Nếu có thêm 1 giờ, em sẽ tối ưu:** tải đầy đủ cross-encoder thật, thêm query decomposition cho câu nhiều ý, dùng embedding đa ngôn ngữ khi tính Answer Relevancy và kiểm thử lại các câu có số tiền/khoảng số.
