# Ước lượng độ tin cậy và bỏ trống (selective answering) không cần huấn luyện cho LLM ~4B dưới chấm điểm +1/−1/0

Ghi chú: ~11 lượt tìm/đọc. Nhiều trang chỉ đọc qua bản tóm tắt tự động của WebFetch (không đọc toàn văn); số liệu đáng kể đã đánh dấu "cần kiểm lại toàn văn". Các bài ghi ngày arXiv/ACL 2026 là theo kết quả tìm kiếm, chưa tự kiểm chứng độc lập.

## 1. Xác suất token (logprob) của nhãn đã chọn có dự đoán đúng/sai ở mô hình nhỏ không?

### Takeaway
Với mô hình 7–8B, logprob token là tín hiệu zero-shot tốt nhất trong các tín hiệu so sánh, nhưng AUROC chỉ ~0.65–0.71 (trên MMLU-Pro) và ~0.72–0.83 (TriviaQA); nó tương đối bền khi đổi phân phối, tốt hơn bộ định tuyến học có giám sát. Với đầu ra JSON ngắn, nên lấy xác suất của token quyết định (tên metric) chứ không lấy trung bình cả chuỗi.

### Cited Findings
- Qwen-2.5-7B, Llama-3.1-8B, Mistral-7B (2026-05), MMLU-Pro: AUROC token log-prob = 0.714 / 0.650 / 0.678; self-assessment YES/NO = 0.562 / 0.614 / 0.638; self-consistency (Jaccard) = 0.504 / 0.594 / 0.604; log-prob tốt nhất trên cả ba mô hình. — [arXiv 2605.02241](https://arxiv.org/html/2605.02241v1)
- Cùng bài: bộ định tuyến có giám sát huấn luyện trên MMLU-Pro rơi từ 0.662 xuống 0.546 khi test TriviaQA (gần ngẫu nhiên), còn log-prob tăng 0.681 → 0.782. Tác giả giải thích: logprob đo chính quá trình sinh, không học phân phối truy vấn. — [arXiv 2605.02241](https://arxiv.org/html/2605.02241v1)
- Cùng bài: lấy trung bình mọi tín hiệu làm TỆ hơn log-prob đơn (Qwen: 0.523 vs 0.714). Nhãn có ~13% bất đồng giữa giám khảo nên AUROC sai số ~±0.05. — [arXiv 2605.02241](https://arxiv.org/html/2605.02241v1)
- Text-to-SQL (BIRD/Spider, 2026-07): white-box log-prob ~0.67 AUROC, tương đương các tín hiệu black-box (0.61–0.68); LLM judge cao hơn (0.72–0.82) nhưng dùng mô hình đóng lớn. — [arXiv 2607.06799](https://arxiv.org/abs/2607.06799) (qua [tóm tắt](https://www.roboticscenter.ai/research/papers/what-predicts-correctness-in-text-to-sql-a-selective-prediction-study-2607))
- EHRSQL 2024 (ProbGate, hạng 3): ngưỡng log-probability + xử lý lỗi, ngưỡng đặt theo tỉ lệ câu không trả lời được ở tập validation. — [arXiv 2405.06673](https://arxiv.org/html/2405.06673v2)
- Cách tính trong transformers: `generate(..., return_dict_in_generate=True, output_scores=True)`, rồi `model.compute_transition_scores(out.sequences, out.scores, normalize_logits=True)` cho logprob từng token sinh ra (shape batch×độ dài sinh); cắt phần prompt bằng `out.sequences[:, input_len:]`. (Chữ ký/ví dụ lấy từ tóm tắt tự động của trang docs, có ghi chú là kiến thức chung, cần kiểm lại với bản transformers đang dùng.) — [HF docs](https://huggingface.co/docs/transformers/main/en/internal/generation_utils)

### Inferences
- Cài đặt gợi ý (<3h): trong chuỗi JSON sinh greedy, tìm vị trí token(s) của giá trị `metric`; lấy (a) p của nhãn đã chọn, (b) margin top1−top2 tại token đầu phân biệt các tên metric, (c) tổng p cả tên nhãn nhiều token. Tốt hơn: sau khi sinh xong, chạy 1 forward riêng chấm điểm (score) từng ứng viên trong ~40 metric (teacher forcing) để có phân phối đầy đủ trên danh sách đóng, rồi lấy entropy/margin. Thêm cùng cách cho slot thời gian và bộ lọc. Điểm tin cậy = min hoặc tích qua các slot (không trung bình cộng, vì bài trên cho thấy trung bình tín hiệu có thể hại).
- Tên metric nhiều token: token đầu thường quyết định, các token sau gần xác suất 1 (làm phồng trung bình toàn chuỗi); lấy xác suất tại token đầu phân nhánh.
- LoRA ý định đã fine-tune thường quá tự tin (xác suất ~1 gần như mọi câu): nghi ngờ margin kém phân tách; là suy luận, chưa có nguồn đo cho trường hợp fine-tune ngắn.

### Gaps
- Không tìm thấy số ECE/AUROC của logprob riêng cho đầu ra JSON/nhãn đóng của mô hình ~4B sau fine-tune.
- Chưa đọc toàn văn 2605.02241 (chỉ qua tóm tắt); tác vụ là QA trắc nghiệm/trivia, không phải phân loại ý định.

## 2. Self-consistency (lấy mẫu K lần, hoặc K diễn đạt lại/nhiễu đầu vào) so với greedy

### Takeaway
Với mô hình 7–8B, self-consistency lấy mẫu cho AUROC thấp hơn logprob (0.50–0.60 vs 0.65–0.71) trong một bài; trong text-to-SQL, consistency theo thực thi đạt ~0.61–0.68. Có một hướng "paraphrase uncertainty" (biến thiên theo cách diễn đạt) được đề xuất nhưng tôi không tìm được so sánh số định lượng paraphrase vs sampling cho mô hình nhỏ.

### Cited Findings
- Self-consistency (Jaccard) AUROC 0.504–0.604 cho 3 mô hình 7–8B, thấp hơn logprob. — [arXiv 2605.02241](https://arxiv.org/html/2605.02241v1)
- Text-to-SQL: string/structural/execution self-consistency ~0.61–0.68 AUROC; string consistency tốt nhất 0.675 (BIRD, Spider, 2026-07). — [arXiv 2607.06799](https://arxiv.org/abs/2607.06799)
- Đánh giá confidence ở phân loại (2026-08, Findings of ACL 2026): kết quả xếp hạng giữa các phương pháp phụ thuộc cách nội suy khi tính AUARC; consistency sampling từ "tốt nhất" thành "tệ nhất" khi đổi từ stepwise sang linear interpolation. Khuyến nghị dùng stepwise. — [arXiv 2608.04899](https://arxiv.org/abs/2608.04899)
- Cox et al. "Mapping from Meaning: Addressing the Miscalibration of Prompt-Sensitive Language Models" (AAAI 2025): coi biến thiên qua các paraphrase là bất định "epistemic" (nhạy với cách hỏi) và biến thiên khi lấy mẫu tại một prompt là "aleatoric"; lấy mẫu qua paraphrase rồi gộp được báo cáo là cải thiện calibration mà không hại độ chính xác (kết quả theo tóm tắt; chưa có số). — [arXiv 2510.17028](https://arxiv.org/abs/2510.17028)
- Bài báo cùng hướng ghi nhận: phân phối đầu ra tại MỘT prompt có thể không phản ánh bất định của mô hình về NGHĨA của prompt. — [arXiv 2510.17028](https://arxiv.org/abs/2510.17028)
- EHRSQL 2024: KU-DMIS bỏ trống khi các SQL lấy mẫu không nhất quán; PromptMind chỉ trả lời khi cả ba LLM đóng cùng đồng ý (bỏ trống nếu bất đồng). — [arXiv 2405.06673](https://arxiv.org/html/2405.06673v2)

### Inferences
- Với greedy decoding và LoRA đã sắc, lấy mẫu nhiệt độ cao tạo nhiễu ít thông tin; biến thể đầu vào (bỏ dấu, đổi thứ tự cụm, rút gọn) hợp lý hơn vì lỗi thực tế là lỗi hiểu câu hỏi. Cài đặt: K=5–8 biến thể rule-based (không cần LLM), greedy mỗi biến thể, sau đó dùng TỈ LỆ phiếu của đa số làm điểm liên tục, kèm margin logprob, không dùng đồng ý/không đồng ý nhị phân.
- Bài học từ lần thất bại "hai pipeline đồng ý": bất đồng nhị phân vứt đi 61% câu vẫn đúng; PromptMind (EHRSQL) cũng dùng đồng thuận tuyệt đối và vẫn điểm âm. Nên dùng điểm liên tục và ngưỡng theo risk-coverage (mục 4), không dùng quy tắc "đồng ý hoàn toàn".
- Chỉ bỏ phiếu theo metric/slot đã chuẩn hoá (so sánh intent đã canonical hoá, hoặc tốt hơn: so đáp án đã tính), vì nhiều intent khác nhau cho cùng đáp án (chuẩn hoá theo "giá trị đầu ra" giống execution consistency).

### Gaps
- Không tìm thấy so sánh định lượng paraphrase-consistency vs sampling-consistency cho mô hình ~4B (chỉ có định tính ở Cox et al.).
- Không có số cho bỏ phiếu K biến thể làm tăng độ chính xác intent so với greedy ở mô hình nhỏ, đầu ra có cấu trúc.

## 3. P(True), verbalized confidence, tự kiểm chứng

### Takeaway
Ở mô hình nhỏ, bằng chứng nghiêng về: P(True)/self-assessment YES/NO yếu (AUROC 0.56–0.64 ở 7–8B), confidence nói bằng chữ bị dồn vào vài giá trị. Nếu dùng, đọc xác suất token (yes/no hoặc chữ số) chứ không đọc con số model "nói".

### Cited Findings
- Self-assessment YES/NO (gần P(True)) AUROC 0.56–0.64 ở Qwen/Llama/Mistral 7–8B, thấp hơn logprob; cải thiện chút khi gắn với truy xuất mạnh (0.562→0.599 Qwen). — [arXiv 2605.02241](https://arxiv.org/html/2605.02241v1)
- Verbalized confidence rất thưa: Qwen3-32B trên SST-2 chỉ ra 8 giá trị khác nhau, >50% là đúng 95% (4 tập, 2 mô hình). Cách "verbalization logprobs" (trọng số các chữ số theo xác suất token) giảm thưa, cho AUARC tốt nhất, +2.3 điểm so với vanilla, không tốn thêm suy luận. — [arXiv 2608.04899](https://arxiv.org/abs/2608.04899)
- Text-to-SQL: LLM judge zero-shot 0.72 (GPT-4o-mini) – 0.78 (Claude); ensemble 2 hãng đạt 0.82, ECE 0.03 (mô hình đóng). Verifier fine-tune 7B: 0.77–0.79 trong miền nhưng ~0.66 trên schema lạ; tăng quy mô/đa dạng schema/distill không bù được. — [arXiv 2607.06799](https://arxiv.org/abs/2607.06799)
- Tian et al., "Just Ask for Calibration" (EMNLP 2023): verbalized confidence thường calibrate tốt hơn xác suất có điều kiện, giảm ECE tương đối ~50%, nhưng trên mô hình RLHF/chat lớn (gpt-3.5-turbo, v.v.), KHÔNG phải mô hình 4B. — [arXiv 2305.14975](https://arxiv.org/abs/2305.14975v2)
- Một bài 2026 (tóm tắt qua tìm kiếm) nói P(True) vượt confidence tự nói ở 4 mô hình nhỏ, giảm ECE 56–78%, trái chiều với nhận xét "P(True) không thoả đáng" ở bài khác; tôi chưa đọc toàn văn nên không dựa vào. — [alphaxiv 2604.09624](https://www.alphaxiv.org/abs/2604.09624)

### Inferences
- Thử rẻ: 1 prompt kiểm tra ("Câu hỏi: … Intent: … Intent này có đúng không? Có/Không"), lấy p(Có) của token. Kỳ vọng AUROC ≤ logprob; chỉ giữ nếu bổ sung được khi ghép (logistic 2–3 đặc trưng). Có thể thử dạng thay thế: yêu cầu model diễn đạt lại câu hỏi từ intent (back-translation) rồi so với câu gốc bằng embedding/từ khoá, cho tín hiệu ngoài họ P(True).
- Không đáng làm: hỏi "độ tự tin 0–100" rồi đọc số.

### Gaps
- Không có số P(True) riêng cho Qwen-class 4B, hay cho kiểm chứng intent có cấu trúc.
- Không đọc được toàn văn bài "Language Models (Mostly) Know What They Know"; chỉ tóm tắt thứ cấp mâu thuẫn về hiệu quả theo quy mô.

## 4. Chọn ngưỡng bỏ trống với chấm +1/−1/0 và độ bền khi đổi phân phối

### Takeaway
Điều kiện đúng: trả lời khi P(đúng) > 0,5 (độ chính xác nhóm đã trả lời > 50% theo biên). Cách chuẩn: học ngưỡng trên tập calibration có nhãn, chọn ngưỡng cực đại điểm kỳ vọng (hoặc ngưỡng với cận trên Clopper–Pearson); nhưng bảo đảm lý thuyết chỉ đúng khi hiệu chuẩn và triển khai exchangeable.

### Cited Findings
- EHRSQL 2024 dùng điểm phạt RS(N) (sai bị trừ N); không đội nào có RS(N) dương; abstain-all được 20.0; điểm RS(0)/RS(10): LG AI Research & KAIST 88.17/81.32, PromptMind 82.6/74.89, ProbGate 81.92/74.21. Lưu ý: với N lớn (thuộc điểm phạt rất nặng của họ), khác điều kiện +1/−1. — [arXiv 2405.06673](https://arxiv.org/html/2405.06673v2)
- Đội hạng 1 tự huấn luyện (self-training với nhãn giả cho câu không trả lời được); ProbGate đặt ngưỡng logprob theo tỉ lệ câu không trả lời được ở validation (heuristic); LTRC-IIITH (hạng 6) dùng module abstention + ngưỡng tin cậy SQL. — [arXiv 2405.06673](https://arxiv.org/html/2405.06673v2), [ACL Anthology 2024.clinicalnlp-1.66](https://preview.aclanthology.org/new-sigs/2024.clinicalnlp-1.66/) (trang này tôi đọc lỗi 404; chỉ có mô tả từ kết quả tìm kiếm)
- CIC ("Uncertainty-Aware Abstention", 2026): chọn ngưỡng lớn nhất sao cho cận trên Clopper–Pearson một phía của tỉ lệ lỗi trong nhóm được chấp nhận ≤ α; thử trên Qwen2.5-3B/7B/14B, Llama-3.1-8B, v.v.; ở α=0.05 FDR thực ~0.040–0.044 nhưng Vicuna vẫn vượt (0.055–0.057) và nhiều lần chia không khả thi (34–99/100). KHÔNG thử đổi phân phối; chỉ biến thiên kích thước tập calibration. — [alphaxiv 2607.04430](https://www.alphaxiv.org/abs/2607.04430.md)
- SAFER (ICLR 2026): sample-then-filter, conformal risk control, thử trên 5 LLM mã nguồn mở, QA mở. — [ICLR 2026 poster](https://iclr.cc/virtual/2026/poster/10007799)
- Text-to-SQL: nhãn thực thi quyết định rủi ro báo cáo của conformal abstention; đổi nhãn đúng/sai làm rủi ro held-out tăng 2.73–10.23 điểm (Spider-Realistic, 4 checkpoint SQL). — [arXiv 2609.25938](https://arxiv.org/pdf/2609.25938)
- Tín hiệu có giám sát học ở một phân phối có thể sụp khi đổi (router 0.66→0.55; verifier 0.78→0.66 trên schema lạ), còn logprob không học thì giữ. — [2605.02241](https://arxiv.org/html/2605.02241v1), [2607.06799](https://arxiv.org/abs/2607.06799)

### Inferences
- Công thức: với điểm tin cậy s, chọn ngưỡng τ tối đa Σ(+1 nếu đúng, −1 nếu sai) trên các câu s≥τ trong tập train theo từng shop (leave-shop-out); để thận trọng, chọn τ sao cho cận dưới Wilson/Clopper–Pearson của độ chính xác nhóm đã trả lời tại τ lớn hơn ~0.55–0.6 (đệm cho dịch chuyển shop), thay vì đúng 0.5.
- Ngưỡng nên theo hạng/phân vị trong lô test (vd bỏ q% câu thấp nhất theo s) hay theo giá trị tuyệt đối? Giá trị tuyệt đối của logprob dịch khi đổi shop; phân vị ổn định hơn nhưng giả định tỉ lệ câu khó tương tự. Gợi ý: dùng giá trị tuyệt đối đã chuẩn hoá từ train, kiểm chứng bằng leave-shop-out đo lệch giữa shop (độ rộng điểm theo shop là đo độ bền).
- Vì sao ngưỡng "đồng ý hay không" mất điểm: nhóm bất đồng vẫn đúng 61% > 50% → bỏ trống nhóm này lỗ (kỳ vọng +0.22/câu). Chỉ bỏ trống nhóm có P(đúng)<0.5; bài học là hiệu chuẩn P(đúng|điểm) bằng hồi quy logistic/isotonic với 2–3 đặc trưng, rồi chọn P>0.5 (+ đệm).

### Gaps
- Không tìm được nghiên cứu cụ thể về độ bền ngưỡng chọn ở phân phối A khi áp phân phối B cho điểm +1/−1/0 (CIC không thử shift). Chưa tìm thấy kỹ thuật conformal/covariate-shift đơn giản đã được kiểm chứng ở mô hình nhỏ.
- Chưa có mô tả chi tiết của đội hạng 1 EHRSQL về abstention; bản tóm tắt overview không nêu bước dựa tin cậy.

## 5. Không nên làm (tín hiệu trông hữu ích nhưng không)

### Takeaway
Các tín hiệu trung bình/ghép lỏng lẻo, self-consistency lấy mẫu thuần, confidence nói bằng chữ, và bộ phân loại độ tin cậy huấn luyện ở phân phối khác đều dễ yếu hoặc sụp ở mô hình nhỏ khi đổi phân phối.

### Cited Findings
- Trung bình mọi tín hiệu tệ hơn logprob đơn (0.523 vs 0.714, Qwen-7B). — [arXiv 2605.02241](https://arxiv.org/html/2605.02241v1)
- Router/verifier có giám sát mất gần hết lợi thế khi đổi phân phối (0.66→0.55; 0.78→0.66). — [2605.02241](https://arxiv.org/html/2605.02241v1), [2607.06799](https://arxiv.org/abs/2607.06799)
- Confidence nói bằng chữ dồn vào ~8 giá trị (đa số 95%) → không thể đặt ngưỡng tinh. — [arXiv 2608.04899](https://arxiv.org/abs/2608.04899)
- Thứ hạng giữa các phương pháp (đặc biệt consistency sampling) có thể đảo chỉ vì cách tính AUARC (nội suy) — nên đo bằng "điểm +1/−1/0 thực tế tại ngưỡng chọn từ train" thay vì chỉ AUROC/AUARC. — [arXiv 2608.04899](https://arxiv.org/abs/2608.04899)
- Đồng thuận tuyệt đối giữa các mô hình (PromptMind) vẫn cho RS(10) 74.89 < đội hạng 1 81.32 và điểm âm với N lớn. — [arXiv 2405.06673](https://arxiv.org/html/2405.06673v2)

### Inferences
- Không dùng quy tắc đồng ý/không (đã mất điểm); không dùng "nói độ tự tin"; không dùng nhãn thô K phiếu nếu K nhỏ (rời rạc, ít mức).

### Gaps
- Không tìm thấy kết quả "tín hiệu vô dụng" đặc thù cho đầu ra JSON.

## Danh sách xếp hạng (≤5) kỹ thuật đề xuất (tổng hợp, mỗi mục là suy luận từ trên)

1. **Điểm logprob/margin của metric (và slot) từ chính lần greedy** + chấm lại toàn bộ 40 metric bằng teacher forcing để có entropy/margin; ngưỡng bằng cận Wilson/CP trên train leave-shop-out. Bằng chứng: logprob là tín hiệu zero-shot mạnh và bền nhất ở 7–8B (AUROC 0.65–0.83) [2605.02241]. Rủi ro: LoRA quá tự tin → ít phân tách; AUROC chỉ ~0.7. Chi phí: ~1–2h.
2. **Bỏ phiếu K biến thể đầu vào (bỏ dấu, đảo cụm, viết tắt) → tỉ lệ phiếu của intent chuẩn hoá/đáp án**, dùng như điểm liên tục. Bằng chứng gián tiếp: paraphrase-uncertainty [2510.17028], execution-consistency 0.61–0.68 [2607.06799]. Rủi ro: ít bằng chứng định lượng; tương quan lỗi với greedy. Có thể tăng độ chính xác bằng đa số phiếu (chưa có số nguồn).
3. **Logistic 2–3 đặc trưng (margin logprob, tỉ lệ phiếu biến thể, đồng ý SQL/metric dạng liên tục) → P(đúng) → trả lời khi P>0.5+đệm.** Khớp lý do hồi quy nhỏ không hại khi đổi phân phối nếu đặc trưng không học thuộc miền; cảnh báo trung bình thô hại [2605.02241].
4. **P(Có) của prompt kiểm tra intent** làm đặc trưng thứ ba; kỳ vọng yếu (0.56–0.64 ở 7–8B), chỉ giữ nếu bổ sung được trong bước 3.
5. **Chọn ngưỡng bằng cận trên Clopper–Pearson / Wilson trên train, kiểm bằng leave-shop-out** [2607.04430]; chỉ đảm bảo khi exchangeable, nên đệm thêm.
