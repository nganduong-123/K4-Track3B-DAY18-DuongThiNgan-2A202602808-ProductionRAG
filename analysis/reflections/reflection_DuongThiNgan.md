# Individual Reflection — Lab 18: Production RAG

**Họ và tên:** Dương Thị Ngân  
**MSSV:** 2A202602808  
**Khóa:** K4 - Track 3B  
**Ngày hoàn thành:** 04/10/2026  

## Phần 1: Mapping bài giảng

| Lecture Concept | Module | Hàm cụ thể | Observation và phân tích |
|---|---|---|---|
| Semantic chunking | M1 | `chunk_semantic()` | Hàm tách câu, tính cosine giữa hai câu liên tiếp và ngắt khi dưới threshold. Ở lần chạy nhẹ, semantic tạo 102 chunk, còn basic tạo 51 chunk; điều này cho thấy threshold cần được hiệu chỉnh theo embedding thật thay vì dùng một giá trị cố định cho mọi tài liệu. |
| Parent–Child và structure-aware | M1 | `chunk_hierarchical()`, `chunk_structure_aware()` | Hierarchical tạo child nhỏ để tìm chính xác; pipeline lưu `parent_text` và trả lại parent sau rerank để giữ đủ bối cảnh. Structure-aware giữ tiêu đề trong metadata và phù hợp hơn với bảng Markdown. |
| BM25 + Dense fusion | M2 | `BM25Search`, `DenseSearch`, `reciprocal_rank_fusion()` | BM25 bắt tốt số tiền, mốc ngày và từ khóa; Dense hỗ trợ câu hỏi diễn đạt khác tài liệu. RRF gộp theo thứ hạng nên không cần chuẩn hóa hai thang điểm khác nhau. |
| Cross-encoder reranking | M3 | `CrossEncoderReranker.rerank()` | Reranker nhận trực tiếp cặp query–document rồi chọn top-3. Chế độ nhẹ có latency trung bình khoảng 0,03 ms nhưng chỉ dựa trên lexical overlap, nên vẫn xếp sai các đoạn có nhiều từ chung. Bản production mặc định dùng `BAAI/bge-reranker-v2-m3`. |
| RAGAS 4 metrics | M4 | `evaluate_ragas()`, `failure_analysis()` | Lần chạy thật trên 20 câu đạt Faithfulness 0,8271; Context Precision 0,9542; Context Recall 0,9250; Answer Relevancy 0,2660. Metric cuối còn thấp nên em kiểm tra thủ công để nhận diện false-negative với tiếng Việt. |
| Contextual enrichment và HyQA | M5 | `_enrich_single_call()` | Một lần gọi trả về summary, câu hỏi giả định, context và metadata. Em đã kiểm tra combined mode đủ 100/100 chunk; khi API giới hạn, fallback vẫn giữ pipeline chạy và không làm mất văn bản gốc. |

## Phần 2: Khó khăn và cách giải quyết

- **Lỗi kỹ thuật gặp phải:** Ban đầu thiếu `openai`, `ragas` và `sentence-transformers`; khi RAGAS chạy 16 worker, OpenRouter trả `402 in_flight_budget_exhausted`.
- **Cách debug:** Em cài đủ `requirements.txt`, kiểm tra từng module bằng pytest, sau đó giảm `RAGAS_MAX_WORKERS=1` để judge chạy tuần tự. Kết quả cuối đạt 37/37 unit tests và 3/4 metric RAGAS trên 0,70.
- **Vấn đề môi trường:** Docker/Qdrant server không chạy nên client cảnh báo không lấy được phiên bản server. Code đã tự chuyển sang Qdrant in-memory để vẫn kiểm thử end-to-end được.
- **Vấn đề dữ liệu:** Hai PDF là bản scan nên `pypdf` không lấy được text. Pipeline bỏ qua có cảnh báo thay vì đưa chunk rỗng vào index. Nếu triển khai thật, em sẽ thêm OCR trước bước chunking.
- **Điều em hiểu thêm:** Chỉ retrieval đúng tài liệu là chưa đủ; ranh giới chunk và thứ tự rerank quyết định context có chứa trọn đáp án hay không.

## Phần 3: Action Plan cho project cá nhân

### Project: Trợ lý tra cứu quy trình Account Management

#### 1. Hiện trạng

- **Pipeline hiện tại:** Tài liệu được đọc và tìm kiếm chủ yếu theo từ khóa, chưa có đánh giá định lượng cố định.
- **Vấn đề:** Dễ bỏ sót thông tin trong bảng, gặp xung đột giữa phiên bản cũ và mới, và chưa kiểm soát được chất lượng top context.

#### 2. Kế hoạch cải tiến

1. **Chunking:** Dùng structure-aware cho tài liệu Markdown/bảng; dùng parent–child cho tài liệu dài để tìm bằng child nhưng trả về parent.
2. **Search:** Kết hợp BM25 và `bge-m3`, sau đó RRF top-20; thêm filter theo phiên bản/ngày hiệu lực.
3. **Reranking:** Dùng `BAAI/bge-reranker-v2-m3` để lọc top-20 xuống top-3.
4. **Evaluation:** Duy trì bộ câu hỏi chuẩn và chạy bốn metric RAGAS sau mỗi thay đổi; theo dõi riêng câu hỏi số liệu và xung đột phiên bản.
5. **Enrichment:** Dùng contextual prepend và metadata nguồn/phiên bản; chỉ dùng HyQA cho các chunk có nội dung quy định rõ ràng để tránh tăng noise.

#### 3. Timeline triển khai

- **Tuần 1:** Chuẩn hóa tài liệu, OCR file scan, thêm metadata phiên bản và thử hai chiến lược chunking.
- **Tuần 2:** Tích hợp Hybrid Search, cross-encoder, chạy benchmark latency và RAGAS; sửa lần lượt các câu Bottom-5.
