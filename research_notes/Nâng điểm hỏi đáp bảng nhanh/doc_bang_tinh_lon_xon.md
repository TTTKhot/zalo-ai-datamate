# Hiểu cấu trúc bảng tính lộn xộn chưa từng thấy bằng heuristic + LLM ~4B, không huấn luyện (ghi chú nghiên cứu, 16/11/2026)

Ghi chú về độ tin cậy: chỉ dùng được ~14 lượt công cụ; nhiều kết quả chỉ đọc qua tóm tắt/abstract (đánh dấu "chưa đọc bảng gốc"). Phần "Inferences" là suy luận của tôi, KHÔNG có nguồn; phần "Gaps" nêu rõ cái không tìm được. Không dùng truy vấn nào chứa thông tin riêng của dự án.

## 1. Prompt cho schema matching / column type annotation với model nhỏ: một cột hay cả bảng, mẫu giá trị, shortlist, "grain", self-consistency

### Takeaway
Bằng chứng công khai mạnh nhất cho model nhỏ là ArcheType (zero-shot CTA, model mở, 5 mẫu giá trị/cột, ánh xạ lại nhãn lạc ngoài tập cho phép); thêm thống kê/tên bảng/cột khác giúp model fine-tune nhưng LÀM HẠI model zero-shot. Majority vote 3 lần được dùng trong nghiên cứu schema matching nhưng chỉ đo với GPT-4-class; không tìm thấy số đo self-consistency cho model ~4B.

### Cited Findings
- ArcheType (VLDB 2024; arXiv 10/2023): 4 bước = chọn mẫu đại diện của cột, serialize prompt, gọi LLM, remap nhãn ngoài tập về nhãn cho phép; zero-shot, mã nguồn mở. — [ArcheType arXiv 2310.18208](https://arxiv.org/pdf/2310.18208)
- ArcheType: chọn giá trị duy nhất có trọng số theo độ dài chuỗi (chuỗi dài chứa nhiều thông tin hơn); zero-shot dùng 5 mẫu/cột, đưa cả cột một lần; hiệu năng tăng khi mẫu từ 3 lên 10 nhưng prompt dài hơn gây cắt cụt. — [ArcheType html v3](https://arxiv.org/html/2310.18208v3)
- ArcheType: thêm thống kê tóm tắt, tên bảng, các cột khác giúp model fine-tune nhưng gây hại cho model zero-shot. — [ArcheType html v3](https://arxiv.org/html/2310.18208v3)
- ArcheType: remap nhãn: CONTAINS+RESAMPLE (khớp chuỗi con, nếu không thì hỏi lại với siêu tham số khác) tốt nhất ở mọi cỡ mẫu; luật remap tăng trung bình ~1,3% (SOTAB), 7,2% (D4), 3,2% (Amstr), 9,9% (Pubchem). — [ArcheType html v3](https://arxiv.org/html/2310.18208v3)
- ArcheType zero-shot (Micro-F1, T5 / UL2 / GPT): SOTAB-27 62,5/60,9/66,0; D4-20 84,6/82,4/87,3; Amstr-56 29,2/35,8/27,2; Pubchem-20 72,0/70,9/65,9; tức model mở cỡ T5/UL2 xấp xỉ GPT trong bài toán gán nhãn từ tập đóng. Trang cung cấp không nêu rõ tham số (chưa kiểm). — [ArcheType html v3](https://arxiv.org/html/2310.18208v3)
- ArcheType: biến thiên giữa 6 prompt khác nhau trên SOTAB-27 khá rộng (T5 47,1–54,0; UL2 47,2–56,4; GPT 53,2–64,6) => thiết kế prompt đáng kể, nên có cơ sở cho việc chạy nhiều prompt rồi bỏ phiếu. — [ArcheType html v3](https://arxiv.org/html/2310.18208v3)
- Parciak et al. 2024 (thử nghiệm schema matching với LLM): chạy lặp 5 lần để đo độ dao động, kết luận LLM đủ nhất quán để dùng thực tế; dùng majority voting gửi cùng prompt 3 lần để giảm hallucination. Chủ yếu GPT-class; chưa đọc được bảng số (PDF nén). — [Parciak arXiv 2407.11852](https://arxiv.org/pdf/2407.11852) (qua tóm tắt tìm kiếm)
- Prompt-Matcher (2024): dùng LLM xác minh từng cặp tương ứng đơn lẻ rồi cập nhật xác suất tập ghép, dùng entropy Shannon làm thước đo bất định, ngân sách truy vấn cố định; self-consistency nêu là hướng tương lai. Dùng GPT-4. — [Prompt-Matcher arXiv 2408.14507](https://arxiv.org/html/2408.14507v3)
- Magneto (PVLDB 2025): model nhỏ (fine-tune bằng dữ liệu do LLM sinh) lấy ứng viên + LLM rerank; không dùng self-consistency; hướng "ứng viên từ model rẻ, quyết định bằng model mạnh". Có fine-tune nên không training-free. — [Magneto arXiv 2412.08194](https://arxiv.org/pdf/2412.08194)
- Korini & Bizer (2025) so sánh knowledge generation, self-refinement với self-consistency và fine-tuning cho CTA; kết quả tốt nhất là fine-tune + self-refinement với gpt-4o (không phải model nhỏ). — [arXiv 2503.02718](https://arxiv.org/pdf/2503.02718v1)
- StraTyper (2026): LLM có thể gán nhãn khác nhau cho cột tương đương ngữ nghĩa => dư thừa kiểu; cần chuẩn hoá nhãn. — [StraTyper arXiv 2602.04004](https://arxiv.org/html/2602.04004v1)

### Inferences
- Thiết kế prompt nên "đóng": đưa tập vai trò/khái niệm hữu hạn làm menu, yêu cầu trả đúng nhãn trong menu, remap bằng so khớp chuỗi (kiểu CONTAINS) rồi hỏi lại (resample) khi lạc nhãn. Rẻ, không cần model mới.
- Theo ArcheType, khi zero-shot nên đưa ít ngữ cảnh phụ (≈5–10 mẫu giá trị dài/đa dạng) hơn là nhồi thống kê; trong hệ thống này README + thẻ cột có thể là ngoại lệ vì README là mô tả tự nhiên chứ không phải thống kê số. Cần đo, không suy ra từ paper.
- Thêm bước "grain": hỏi riêng một câu (một dòng của bảng này đại diện cho gì: dòng hàng/đơn/phiếu dịch vụ/khoản nợ) dạng chọn nhãn đóng, chạy 3–5 lần với thứ tự cột hoán vị hoặc nhiệt độ >0 rồi bỏ phiếu. Độ bất đồng giữa các lần (entropy kiểu Prompt-Matcher) dùng làm tín hiệu "không chắc" cho cả bảng. Chưa tìm thấy paper đo riêng bước "grain" ở model nhỏ.
- Ba thành phần trên (menu đóng, remap, vote hoán vị) đều rẻ với ngân sách ~10% thời gian đang dùng.

### Gaps
- Không tìm thấy số liệu self-consistency/hoán vị cột cho model 3–8B ở bài toán schema matching hay CTA; mọi số vote đều từ GPT-class.
- Chưa đọc được bảng số của Parciak (PDF nén) nên không có số "có/không mô tả cột" của họ.
- Không tìm thấy nguồn so sánh "một cột một lần" với "cả bảng một lần" cho model nhỏ ngoài lưu ý của ArcheType (cột-một-lúc, 5 mẫu).

## 2. Kiểm tra tất định để xác nhận ánh xạ (khoá duy nhất, phụ thuộc hàm, đẳng thức số học, độ phủ dòng, liên tục ngày)

### Takeaway
Mẫu chung trong tài liệu làm sạch dữ liệu: LLM đề xuất kiểu/ràng buộc, rồi kiểm chứng ràng buộc bằng thống kê trên dữ liệu (phụ thuộc hàm, vi phạm). Không tìm thấy phương pháp công bố "constraint-based schema verification" đã đo trực tiếp để bắt lỗi ánh xạ vai trò bảng; các kiểm tra cụ thể ở mục dưới là thiết kế của tôi dựa trên mẫu đó.

### Cited Findings
- Cocoon: LLM gợi ý kiểu ngữ nghĩa phù hợp cho từng cột; các phụ thuộc hàm mạnh về thống kê được sàng trước, LLM chỉ duyệt xem có ý nghĩa ngữ nghĩa không. — [Data Cleaning Using LLMs arXiv 2410.15547](https://arxiv.org/pdf/2410.15547) (qua tóm tắt tìm kiếm)
- LLMClean: LLM sinh Ontological Functional Dependencies, hệ thống cưỡng chế bằng cách tìm các dòng vi phạm; dùng prompt ensembling với đồng thuận; F1 phát hiện lỗi vượt HoloClean, Raha trên IoT, Hospital, CONTEXT. — [LLMClean review](https://www.themoonlight.io/review/llmclean-context-aware-tabular-data-cleaning-via-llm-generated-ofds)
- Data Quality Rule Generation with LLMs (2026): khám phá CFD cổ điển hợp ràng buộc cấu trúc nhưng yếu với luật ngữ nghĩa cần bối cảnh; lưu ý cách sinh toàn bộ luật một lần dựa trên lỗi "LLM kỳ vọng" thay vì lỗi quan sát được trong dữ liệu. — [arXiv 2609.06053](https://arxiv.org/pdf/2609.06053)
- Prompt-Matcher dùng entropy trên phân phối xác suất của các tập tương ứng làm thước đo bất định để quyết định kiểm chứng gì tiếp. — [arXiv 2408.14507](https://arxiv.org/html/2408.14507v3)

### Inferences
Kiểm tra cấp bảng/cấp shop đề xuất (đều pandas, không model), mỗi kiểm tra cho điểm 0/1 hoặc [0,1]:
- Khoá đơn: tỉ lệ duy nhất của cột "mã đơn" ứng viên; với bảng dòng hàng, mỗi giá trị khoá phải lặp (số dòng/đơn ≥1) và các trường cấp đơn (ngày, khách, tổng đơn) phải hằng trong nhóm khoá: tính độ vi phạm phụ thuộc hàm khoá -> ngày/khách. Cột STT chạy lại theo sheet tháng: khoá thật = (sheet, STT) hoặc STT gắn ngày; kiểm bằng độ duy nhất của cặp.
- Đẳng thức: median |qty×đơn giá − thành tiền| / thành tiền; Σ thành tiền theo đơn ≈ tổng đơn (bắt cả trường hợp dòng voucher/phí ship xen vào); đã trả ≤ tổng; tỉ lệ dòng thoả đẳng thức ≥ ngưỡng đặt từ shop train.
- Phủ dòng: tỉ lệ dòng có ngày hợp lệ, số tiền hợp lệ, khoá không rỗng; sau gộp các file/sheet con, số dòng = tổng.
- Liên tục ngày: các tháng trong khoảng ngày bảng phải phủ đủ, không "lỗ" hoặc chồng giữa các phần (bắt lỗi tách bảng theo tháng chưa gộp).
- Phân biệt sổ dịch vụ với sổ chi: hóa đơn chi thường có cột nhà cung cấp/danh mục chi, số tiền; sổ phiếu dịch vụ có khách + mã phiếu + trạng thái. Nên để LLM/heuristic đề xuất, kiểm tra bằng sự hiện diện cột "khách" ở mức giá trị (tỉ lệ giá trị trùng với bảng khách, nếu có).
- Cấp shop: shop "đạt" nếu mọi bảng chính qua ≥ k/n kiểm tra; thất bại bảng sales/orders (bảng quyết định nhiều câu) thì bỏ trống cả shop thay vì dùng ngưỡng 20% "unanswerable" (quy tắc cũ chỉ phản ứng sau khi hỏi). Ngưỡng cho từng kiểm tra đặt từ phân phối trên shop train (không dùng public), đúng ràng buộc dự án.

### Gaps
- Không tìm thấy nghiên cứu nào báo cáo tỉ lệ bắt lỗi ánh xạ bằng các kiểm tra số học/khoá cho dữ liệu bán hàng; nguồn chỉ cho khung chung (LLM đề xuất, dữ liệu xác nhận).
- Không có số định lượng của Cocoon/LLMClean với model ≤4B (dùng GPT-class).

## 3. Cấu trúc bảng tính: header nhiều hàng, dòng không phải dữ liệu, bảng tách nhiều sheet/file (union)

### Takeaway
Tài liệu SpreadsheetLLM xác nhận dấu hiệu "hàng/cột dị biệt ở biên bảng" (structural anchors) là điểm bám hữu ích; phát hiện unionable tables trong data lake dựa trên so khớp cột (Starmie, dùng embedding đã huấn luyện). Không có nguồn nào so trực tiếp luật thuần tuý với LLM; luật union đơn giản (cùng tập cột, tên file khác token kỳ) là suy luận của tôi.

### Cited Findings
- SpreadsheetLLM (arXiv 07/2024): SheetCompressor gồm structural-anchor compression (giữ hàng/cột dị biệt ở biên bảng, bỏ hàng/cột đồng nhất xa), inverse-index translation, data-format-aware aggregation; nén trung bình ~25 lần; mô hình fine-tune đạt F1 78,9% phát hiện bảng, hơn SOTA 12,3%; trong ICL với GPT-4 hơn cách ngây thơ 25,6%; bộ test 188 bảng tính. Chỉ đọc qua tóm tắt, chưa đọc ablation từng module. — [SpreadsheetLLM HF paper page](https://huggingface.co/papers/2407.09025.md); [bdtechtalks](https://bdtechtalks.com/2024/07/29/microsoft-spreadsheetllm/)
- Starmie (PVLDB 2023): tìm bảng unionable bằng độ tương đồng cosine giữa embedding cột (contrastive pre-training đa cột), điểm cột -> điểm bảng qua đồ thị hai phía có trọng số; benchmark SANTOS, TUS; cần huấn luyện encoder nên không training-free. — [Starmie arXiv 2210.01922](https://arxiv.org/abs/2210.01922v1)
- CHiTab (11/2025) và RealHiTBench (06/2025) nhắm header phân cấp, nhưng trên bảng khoa học/ảnh chứ không phải sổ bán hàng; 78% bảng HiTab có header cột nhiều mức; không có so sánh trực tiếp với luật thuần. — [CHiTab arXiv 2511.08298](https://arxiv.org/pdf/2511.08298); [DeepTable](https://arxiv.org/pdf/2609.07707)

### Inferences
Luật không model, rẻ, nên đưa vào pandas trước khi gọi LLM:
- Union-compatibility: nhóm các bảng/sheet có tập cột chuẩn hoá (bỏ dấu, hạ chữ, bỏ khoảng trắng) giống nhau ≥ 0,9 (Jaccard) và kiểu cột cùng; tên file/sheet sau khi gạt token thời gian (tháng, quý, năm, số) giống nhau -> hợp nhất thành một bảng logic, thêm cột "nguồn" (tên sheet). Ngay sau đó chạy lại kiểm tra khoá (mục 2) vì STT có thể chạy lại theo sheet.
- Header nhiều dòng: hàng đầu có nhiều ô gộp/NaN xen kẽ và hàng kế còn chứa chuỗi chữ trong khi các hàng sau là số/ngày -> coi là header 2 hàng, nối "trên_dưới". Dùng cùng ý tưởng anchor: hàng chuyển từ chuỗi sang kiểu dữ liệu ổn định.
- Dòng không phải dữ liệu: hàng có ngày/mã đơn rỗng nhưng số tiền có (tổng cộng, voucher, điểm, phí ship) -> gắn cờ "dòng phi hàng hoá" theo mẫu: khoá trùng với dòng trên, tên hàng khớp từ vựng (voucher, điểm, vận chuyển), số âm. Kiểm bằng đẳng thức Σ dòng ≈ tổng đơn.
- Các luật này khớp nguyên tắc dự án (không gắn tên file/shop).

### Gaps
- Không tìm thấy nghiên cứu nào đo riêng độ chính xác của luật thuần tuý phát hiện header đa dòng hay union theo tên so với LLM.
- Chưa đọc TableSense, Auto-Tables; không tìm được số liệu của chúng trong lượt này.

## 4. Dùng tài liệu mô tả dữ liệu (README, data dictionary) với model nhỏ; chunking

### Takeaway
Tìm thấy ít bằng chứng trực tiếp: DABStep/KramaBench đều cho thấy tài liệu miền và xử lý dữ liệu là điểm nghẽn, chứ không phải sinh mã. Không tìm thấy nguồn đo hiệu quả BIRD evidence/Spider 2 documentation hay chiến lược chunk cho model 4B trong lượt này.

### Cited Findings
- DABStep (06/2025, hơn 450 tác vụ lấy từ phân tích tài chính thực): mô hình tốt nhất (o4-mini, prompt suy luận) chỉ đạt 14,55% ở tác vụ Hard, 76,39% ở Easy; model nhỏ như Llama 3.2 1B yếu khắp nơi; một số model nhạy cảm cấu trúc prompt. — [DABstep arXiv 2506.23719](https://arxiv.org/pdf/2506.23719)
- Bảng xếp hạng sau đó có hệ thống đạt 90,74% Hard (dùng claude haiku 4.5), theo trang tổng hợp bên thứ ba, chưa kiểm chứng ngày nhập và so sánh không cùng điều kiện. — [DABstep review aggregator](https://www.themoonlight.io/review/dabstep-data-agent-benchmark-for-multi-step-reasoning) (độ tin cậy thấp)
- KramaBench (06/2025): 104 pipeline, 1700 file, 24 nguồn, 6 miền; hệ tốt nhất 55% end-to-end trên data lake đầy đủ, 62% ngay cả khi truy hồi hoàn hảo; model làm tốt code có đặc tả rõ nhưng kém khi cần xử lý dữ liệu nhiều và kiến thức miền. — [KramaBench arXiv 2506.06541](https://arxiv.org/html/2506.06541v1)
- Phê duyệt hạn chế: phát hiện kiểu về "xử lý dữ liệu/miền là nút cổ chai" cho thấy bước hiểu cấu trúc dữ liệu đáng đầu tư (suy luận, xem Inferences).

### Inferences
- Chia README theo thẻ: (a) mô tả từng file, (b) một dòng mỗi cột, (c) mục "quy ước". Khi gọi LLM theo bảng, chỉ đưa mô tả của file đó + các dòng cột của file đó + toàn bộ mục quy ước (thường ngắn) thay vì cả README, để không bị cắt. Chưa có số đo; đây là thiết kế mặc định hợp lý, cần thử nghiệm A/B trên shop train.
- Dùng README làm "kiểm chứng chéo" tất định: tên file/cột trong README so với file/cột thật; lệch lớn (README nói có 6 file, thực có 12 file theo tháng) là tín hiệu tách bảng.

### Gaps
- Không đo được hiệu quả của file mô tả (BIRD evidence, Spider 2) đối với model nhỏ; chưa tìm được số trong các lượt tìm.
- Không có nguồn về chiến lược chunk cụ thể cho tài liệu dài với model 4B.

## 5. Tự kiểm tra bằng model nhỏ (câu hỏi sanity, xác minh vai trò yes/no)

### Takeaway
Mẫu "LLM xác minh từng tương ứng đơn lẻ rồi cập nhật niềm tin" (Prompt-Matcher) và "LLM đề xuất, dữ liệu xác nhận" (Cocoon, LLMClean) là tiền lệ gần nhất; chưa thấy bằng chứng tự kiểm tra bằng câu hỏi sanity ở model ~4B.

### Cited Findings
- Prompt-Matcher: xác minh từng cặp tương ứng đơn bằng LLM, cập nhật phân phối xác suất, chọn cặp để xác minh theo ngân sách truy vấn. (GPT-4) — [arXiv 2408.14507](https://arxiv.org/html/2408.14507v3)
- LLMClean dùng prompt ensembling với đồng thuận. — [review](https://www.themoonlight.io/review/llmclean-context-aware-tabular-data-cleaning-via-llm-generated-ofds)
- SemEval-2025 Task 8 (QA trên bảng): tổng quan ban tổ chức nêu hướng dựa LLM chiếm ưu thế, model lớn hơn rõ rệt model nhỏ; các hệ thống mạnh dùng LLM sinh pandas; không thấy kỹ thuật riêng cho hiểu cấu trúc bảng trong kết quả tìm được. — [SemEval-2025 Task 8 overview](https://aclanthology.org/2025.semeval-1.324/); [sonrobok4](https://preview.aclanthology.org/setup/2025.semeval-1.51)

### Inferences
- Câu hỏi sanity chạy bằng code tất định (không cần LLM trả lời): đếm số đơn tháng cuối > 0, doanh thu = Σ dòng, ngày min/max trong khoảng calendar, mỗi bảng chính cho ≥1 kết quả khác rỗng. Nếu LLM chỉ cần sinh/chấm "có hợp lý không" thì cho xác suất yes/no từ logit của token "có/không", kết hợp với kiểm tra mục 2 bằng quy tắc tối thiểu (ví dụ bỏ trống nếu bất kỳ kiểm tra cứng nào fail).
- Dùng xác suất yes/no: với model 4B nên chuẩn hoá nhãn thành một câu hỏi/một vai trò và lấy P(yes) đủ cao VÀ ổn định giữa 3 lần hoán vị mẫu; không tin lời giải thích. (Suy luận, chưa có bằng chứng ở quy mô nhỏ.)

### Gaps
- Không tìm thấy nghiên cứu đánh giá tự kiểm tra bằng sanity question/yes-no probability cho vai trò bảng ở model ~4B.
- Chưa đọc bài tổng quan SemEval-2025 Task 8 đầy đủ; không có chi tiết bước hiểu dữ liệu của các đội top.

## 6. Danh sách kỹ thuật xếp hạng (tối đa 5) để triển khai < ~3 giờ mỗi cái

### Takeaway
Ưu tiên kỹ thuật tất định, đo được trên 24 shop train (không cần GPU), rồi mới tới bỏ phiếu LLM. Toàn bộ các số "kỳ vọng" dưới đây KHÔNG có nguồn; chỉ nguồn nêu trong ngoặc là tiền lệ.

### Cited Findings (tiền lệ cho từng mục)
- Menu đóng + remap + resample: [ArcheType](https://arxiv.org/html/2310.18208v3).
- Bỏ phiếu 3 lần / ensembling: [Parciak](https://arxiv.org/pdf/2407.11852), [LLMClean](https://www.themoonlight.io/review/llmclean-context-aware-tabular-data-cleaning-via-llm-generated-ofds).
- LLM đề xuất, dữ liệu xác nhận (phụ thuộc hàm): [Cocoon qua 2410.15547](https://arxiv.org/pdf/2410.15547).
- Bất định đo bằng entropy trên các ứng viên: [Prompt-Matcher](https://arxiv.org/html/2408.14507v3).
- Structural anchors cho ranh giới bảng: [SpreadsheetLLM](https://huggingface.co/papers/2407.09025.md).

### Inferences
1. Bộ kiểm tra tất định cấp bảng + cổng bỏ trống cấp shop (mục 2). Cài: hàm `validate_table(role, mapping)` trả list (tên kiểm tra, điểm); cổng: bỏ trống shop nếu bảng quyết định (sales/orders) fail cứng, thay thế quy tắc 20%. Rủi ro: ngưỡng quá chặt bỏ trống shop đúng (mất điểm +1 mỗi câu); đặt ngưỡng từ phân phối train, chạy trên 24 shop (mọi shop đúng phải qua). Thí nghiệm tối thiểu: cố ý gây lỗi ánh xạ (hoán vai trò, tách bảng, lấy sổ dịch vụ làm sổ chi) trên shop train và đo tỉ lệ phát hiện và tỉ lệ báo nhầm; công cụ perturb_shops.py đã có.
2. Hợp nhất bảng tách theo kỳ bằng union-compatibility + khoá phức hợp (sheet, STT) (mục 3, 2). Rủi ro: gộp nhầm hai bảng khác nhau có cột giống (sổ nợ và sổ thu); giảm bằng yêu cầu token kỳ khác nhau và dải ngày không chồng. Thí nghiệm: kiểm tra trên shop train có tách bảng; thêm test fixture; đo điểm 24 shop không tụt.
3. Bỏ phiếu mapping LLM: K=3–5 lần với hoán vị thứ tự cột/bảng, menu đóng, remap bằng so khớp chuỗi (ArcheType); lấy đa số cho từng (cột, khái niệm); độ bất đồng là tín hiệu cho cổng (mục 1). Rủi ro: thời gian (ngân sách chỉ dùng 10%, ~14 shop nên đủ), và model tự tin sai đồng thuận (vote không sửa được thiên lệch hệ thống). Thí nghiệm: so tỉ lệ ánh xạ đúng 1 lần vs vote trên shop train với bản heuristic mapper.
4. Bước "grain" tường minh: hỏi 1 dòng của bảng là gì (nhãn đóng: dòng hàng, đơn, phiếu dịch vụ, khoản nợ, trả góp, bảo hành, thu cũ đổi mới, chi phí…), vote như mục 3, rồi kiểm chéo bằng khoá/độ lặp (mục 2). Giải quyết trực tiếp lớp lỗi (3) và (5). Rủi ro: nhãn "sổ phụ" mới ngoài menu; thêm nhãn "khác" và bỏ trống câu liên quan chứ không đoán. Thí nghiệm: confusion matrix grain trên toàn bảng của 24 shop.
5. Chia README theo bảng + luôn đưa mục quy ước đầy đủ; đối chiếu README với file thực (mục 4). Rủi ro: README sai/lệch so với dữ liệu; chỉ dùng như tín hiệu, không phải sự thật. Thí nghiệm: A/B prompt "cả README" vs "phần của bảng + quy ước" về độ đúng ánh xạ.

### Gaps
- Không có số kỳ vọng cải thiện điểm cho cả 5; chỉ tiền lệ cơ chế. Ưu tiên theo suy luận về chi phí cài đặt và khả năng đo được, không theo số liệu công bố.
- Thiếu nguồn cho top solutions của DA-Code, InfiAgent-DABench, Spider 2-lite trong lượt này.
