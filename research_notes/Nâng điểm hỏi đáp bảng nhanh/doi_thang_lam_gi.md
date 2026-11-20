# Đội thắng làm gì trong các cuộc thi hỏi đáp bảng / text-to-SQL có phạt sai (nghiên cứu ngày 2026-11-16)

Ghi chú phạm vi: đã đọc được trọn nội dung của 5 nguồn (overview EHRSQL, ProbGate, ITUNLP, Anotheroption, MRT, Agentic LLMs, DABStep). Nhiều PDF ACL Anthology không trích được chữ (TabaQA, sonrobok4, LTRC-IIITH, overview SemEval Task 8) và tôi không cài được công cụ đọc PDF, nên các mục đó ghi vào Gaps. Không tìm được nguồn về BIRD, Spider 2.0-lite, KramaBench, DA-Code, InfiAgent-DABench, các cuộc thi Kaggle/AIcrowd/quốc gia có chấm âm: ghi rõ ở Gaps, không suy đoán.

## 1. SemEval-2025 Task 8 (DataBench): đội dùng mô hình mở/nhỏ làm gì, bước nào tăng nhiều nhất

### Takeaway
Các hệ thống tốt đều sinh code Pandas/SQL rồi chạy (không để LLM đọc bảng trực tiếp). Lợi ích đo được rõ nhất, không cần train: chạy song song nhiều đường (Pandas + SQL) rồi chọn đáp án; ép kiểu đầu ra (bool/số/chuỗi/list) trong prompt; schema kèm giá trị mẫu. Bước "retry khi lỗi chạy" giảm nửa số lỗi thực thi nhưng ít đổi điểm cuối khi đã có nhiều đường song song. Bước định dạng bằng heuristic cuối cùng có thể TỤT điểm.

### Cited Findings
- Overview: hệ dùng LLM áp đảo, mô hình lớn hơn rõ rệt so với nhỏ; test 522 câu / 15 bộ dữ liệu. Bản overview không đọc được, đây là câu trích từ kết quả tìm kiếm — [SemEval-2025 Task 8 overview (ACL Anthology 2025.semeval-1.324)](https://aclanthology.org/2025.semeval-1.324/) (2025)
- ITUNLP (zero-shot, KHÔNG fine-tune, mô hình mở 32B–671B: DeepSeek-R1/V3, Qwen2.5-Coder-32B, Llama-3.3-70B): tiền xử lý tên cột (thay ký tự lạ bằng `_`, hạ chữ thường, đổi tên cột trùng); schema gồm tên cột, kiểu dữ liệu, 5 giá trị duy nhất mẫu (cắt 100 ký tự) và số giá trị duy nhất; prompt buộc một khối code, in đáp án trên một dòng, kiểu Python gốc (Boolean/Category/Number/List), tránh `unique()`/`drop_duplicates()` nếu câu hỏi không đòi, câu yes/no trả boolean. Điểm test 83,1–84,7% (Subtask I), hạng 8/I và 6/II trong nhóm mở. — [ITUNLP, arXiv 2508.00762](https://arxiv.org/html/2508.00762v1) (2025)
- ITUNLP retry khi lỗi (gửi lại code lỗi + thông báo lỗi, tối đa 2 vòng): số lỗi thực thi giảm dev 9→6, 35→11, 11→9, 16→5 và test 15→7, 18→9, 25→8, 16→10 (R1, V3, Qwen-Coder-32B, Llama-70B). Lỗi chủ yếu là runtime (KeyError, ValueError, NameError…); vòng lặp suy biến và lỗi cú pháp chỉ ở họ DeepSeek. — [ITUNLP](https://arxiv.org/html/2508.00762v1)
- Anotheroption (toàn mô hình mở: Codestral và Qwen2.5-Coder-32B sinh code, Llama-3.3-70B làm orchestrator, Llama-3.2-3B truy hồi): dev: Codestral Python 68% → Python + SQL 84% → hai mô hình code + orchestrator 88%; test chính thức 80,08% (hạng 13/38 nhóm mở). Chọn cột bằng LLM trước khi sinh SQL, thêm 3 hàng gần nhất (embedding) vào prompt, checklist ép kiểu/kiểm cột trong prompt. — [Anotheroption, arXiv 2506.09657](https://arxiv.org/html/2506.09657v2) (2025)
- Anotheroption: viết lại câu hỏi (reformulation) LÀM GIẢM độ chính xác (Codestral Python + reformulation chỉ 68%, E2E 52%); self-correction "gần như vô dụng" vì luôn có ít nhất một agent Python/SQL chạy được; few-shot động bị coi là quá tốn công. — [Anotheroption](https://arxiv.org/html/2506.09657v2)
- Anotheroption, orchestrator trên 41 câu dev: 63,4% là đồng thuận khi đáp án giống nhau, 14,6% lọc đáp án sai logic, 12,2% loại đáp án sai định dạng, 9,8% xử lý mâu thuẫn. Quy ước định dạng: yes/no → True/False; đếm dùng COALESCE để trả 0 khi không có hàng; Pandas nhiều giá trị dùng `.tolist()`; số cắt 2 chữ số thập phân; thứ tự list bị bỏ qua. — [Anotheroption](https://arxiv.org/html/2506.09657v2)
- MRT (đều mô hình mở 7–14B, chạy trên 1 GPU A6000 48GB): pipeline Column Descriptor (Qwen2.5-7B, thống kê + mô tả từng cột, cache theo bảng) → Explainer (viết các bước bằng lời) → Coder (Qwen2.5-Coder-14B, tối đa 4 lần sửa cú pháp, 3 lần regenerate khi runtime lỗi) → Interpreter (chọn kiểu đáp án) → Formatter (luật cast, làm tròn). Điểm chính thức 70,50% (subtask 1); validation: Qwen2.5-14B 0,759, Phi-4 14B 0,75, Llama-3-8B 0,606, majority vote ba mô hình 0,766. — [MRT, arXiv 2505.22264](https://arxiv.org/html/2505.22264) (2025)
- MRT, ablation theo giai đoạn (val): Interpreter tăng Llama-3-8B 0,563→0,613 và Qwen 0,762→0,766; bước Formatter (heuristic) làm GIẢM điểm ở mọi hàng ("heuristics to format… sometimes introduce additional errors"); ensemble majority vote cao nhất ở mọi giai đoạn, hòa thì ưu tiên Qwen. — [MRT](https://arxiv.org/html/2505.22264)
- Agentic LLMs (dùng GPT-4o; thử DeepSeek-V2 16B): pipeline 5 bước (chọn ví dụ: 25 cặp câu-SQL, lấy 2 giống nhất bằng embedding; sinh SQL với schema + hàng mẫu; trích đáp án bằng CoT; kiểm tra bằng GPT-4o; sinh lại câu bị đánh dấu). DataBench: GPT-4o 70,50, GPT-4o-mini 60,34, DeepSeek-V2-16B 39,68, baseline 26,00. Không có ablation từng thành phần. LƯU Ý: hạng này là bảng "proprietary", không phải nhóm mở. — [Agentic LLMs, arXiv 2509.09234](https://arxiv.org/html/2509.09234) (2025)
- Một số bài khác nêu trong kết quả tìm kiếm nhưng không đọc được toàn văn: TabaQA "column augmented generation" (hạng 7 ở DataBench Lite), sonrobok4 (Pandas + LLM, 89,46% Subtask 1 theo bài tự báo). — [TabaQA](https://airi.net/articles/tabaqa-at-semeval-2025-task-8-column-augmented-generation-for-question-answering-over-tabular-data), [sonrobok4](https://preview.aclanthology.org/setup/2025.semeval-1.51)

### Inferences
- (Suy luận) Hệ của bạn khác kiến trúc (LLM chỉ ra intent JSON, code cố định tính), nên "sinh code + retry" không áp trực tiếp. Phần chuyển được là: (a) kiểm tra đồng thuận giữa hai đường độc lập (bạn đã có đường SQL đối chiếu); (b) ép kiểu đầu ra trong prompt; (c) schema kèm giá trị mẫu/số giá trị duy nhất; (d) KHÔNG thêm bước viết lại câu hỏi; (e) cẩn thận với bước "format" cuối: đo trước khi bật vì có bằng chứng nó làm tụt.
- (Suy luận) Số liệu nhóm mở tốt nhất đều ≥ 32B hoặc ensemble ≥ 3 mô hình 14B+; đội 14B đơn lẻ ~70%. Với 4B, không nên kỳ vọng ngang các số này.

### Gaps
- Bảng xếp hạng chính thức và kết luận "mô hình nhỏ vs lớn" chi tiết của overview paper: PDF không trích được chữ. Trang benchmarklist.com có số mâu thuẫn (52,87% vs 95,02%), không dùng.
- TabaQA, sonrobok4: không đọc được toàn văn, không có số ablation.

## 2. EHRSQL 2024 (text-to-SQL, phạt khi sai): phương pháp bỏ trống của top đội và điểm

### Takeaway
Cả 3 đội đứng đầu dùng mô hình ChatGPT/GPT-4 đã fine-tune, nhưng cơ chế bỏ trống của họ đều là tín hiệu rẻ, không train thêm: ngưỡng log-prob/entropy của token SQL, đồng thuận nhiều mô hình/nhiều mẫu, và lọc SQL chạy lỗi. Ablation của ProbGate cho thấy ngưỡng bỏ trống là thành phần tăng lớn nhất; bộ phân loại "trả lời được hay không" riêng làm tệ hơn nhiều.

### Cited Findings
- Bảng kết quả chính thức (RS(0)/RS(10)/RS(N)): 1) LG AI Research & KAIST 88,17/81,32/−711,83 (ChatGPT fine-tune, unified); 2) PromptMind 82,6/74,89/−817,4 (ensemble GPT-4, ChatGPT, Claude Opus, fine-tune); 3) ProbGate 81,92/74,21/−818,08 (ChatGPT fine-tune); 4) KU-DMIS 72,07/59,21/−1427,93; 5) AIRI NLP 68,89/44,04 (T5-3B + logistic regression, pipeline); 6) LTRC-IIITH 66,84/43,7 (SQLCoder-7b-2); 7) Saama 53,21/36,08; 8) PRIMUS 14,14/−713,37 (SQLCoder-7b-2 in-context, không fine-tune). Baseline "bỏ trống hết" = 20,0 ở mọi thang. Không đội nào có RS(N) dương. — [Overview EHRSQL 2024, arXiv 2405.06673](https://arxiv.org/html/2405.06673v2) (2024)
- PromptMind: trả SQL chỉ khi cả 3 mô hình thống nhất, nếu không thì bỏ trống; có truy hồi 2 bộ cặp câu-SQL giống nhất làm ví dụ in-context. — [Overview EHRSQL](https://arxiv.org/html/2405.06673v2)
- KU-DMIS: sinh nhiều SQL cho mỗi câu, bỏ trống khi không nhất quán. — [Overview EHRSQL](https://arxiv.org/html/2405.06673v2)
- ProbGate (gpt-3.5-turbo fine-tune trên 4.674 cặp trả lời được): bỏ các từ khoá SQL, lấy trung bình t=10 log-prob thấp nhất của token còn lại, xếp hạng, đánh dấu k câu thấp nhất là không trả lời (k chọn từ tỉ lệ ~19,97% câu không trả lời; k=425/1167). Thêm GEF: SQL chạy lỗi → bỏ trống. Ablation test RS(10): chỉ fine-tune −191,25 → +ProbGate 66,58 (+257,83) → +GEF 72,06 (+5,48) → k=425: 74,21 (+2,15). Bộ phân loại T5 hoặc gpt-3.5 làm bộ lọc cho RS(10) chỉ 12,89 và 27,86. — [ProbGate, arXiv 2404.16659](https://arxiv.org/html/2404.16659v1) (2024)
- LG AI/KAIST (hạng 1): blog của họ nói lọc 2 tầng: entropy cấp token của SQL sinh ra, rồi lọc theo thực thi; bài tóm tắt thứ cấp nói ngưỡng đặt theo tỉ lệ câu không trả lời mong muốn. Tôi chỉ có blog + tóm tắt thứ cấp, không đọc được bài gốc. — [LG blog](https://www.lgresearch.ai/blog/view?seq=430) (2024-05); [tóm tắt thứ cấp](https://themoonlight.io/review/lg-ai-research-kaist-at-ehrsql-2024-self-training-large-language-models-with-pseudo-labeled-unanswerable-questions-for-a-reliable-text-to-sql-system-on-ehrs)
- LTRC-IIITH (hạng 6, SQLCoder-7b-2, mô hình nhỏ nhất ở nhóm giữa): ngưỡng độ tin cậy + lọc lỗi thực thi, theo tóm tắt kết quả tìm kiếm. Không đọc được bài. — [LTRC-IIITH](https://preview.aclanthology.org/new-sigs/2024.clinicalnlp-1.66/)

### Inferences
- (Suy luận) Với thang +1/−1 (tương ứng RS(1)), mỗi câu sai tốn 2 điểm so với câu đúng; ngưỡng bỏ trống nên đặt để độ chính xác trên phần được trả lời > ~50% (hoà vốn tại 50%). ProbGate đặt ngưỡng bằng đếm tỉ lệ từ dev, giống việc bạn hiệu chỉnh trên shop train.
- (Suy luận) Tín hiệu rẻ tương ứng ở hệ bạn: độ tin của LLM trên token intent JSON (log-prob), đồng thuận giữa đường metric và đường SQL (bạn có `agree`), lỗi thực thi/slot rỗng. Bằng chứng ProbGate nói log-prob + lỗi thực thi hiệu quả hơn bộ phân loại học riêng; hệ bạn đã có XLM-R "trả lời được", nên so sánh trên shop giữ kín trước khi bỏ/giữ.
- (Suy luận) Chỉ đội không fine-tune và dùng 7B in-context (PRIMUS) kém hơn bỏ trống hết: nhắc rằng không có cơ chế bỏ trống thì mô hình nhỏ có thể tệ hơn bỏ trống toàn bộ.

### Gaps
- Chi tiết bài gốc của LG/KAIST, KU-DMIS, LTRC-IIITH, PromptMind, AIRI: không đọc được (PDF không trích được). Không có số ablation của họ.
- Không có đội nào dùng mô hình nhỏ + chỉ training-free đạt hạng cao để làm đối chứng, ngoài PRIMUS (hạng cuối).

## 3. DABStep, DA-Code, KramaBench, InfiAgent-DABench, Spider 2.0-lite, BIRD: bước hiểu dữ liệu và định dạng đáp án

### Takeaway
Chỉ DABStep có bằng chứng tìm được. Các lỗi chính của agent: không đọc/áp dụng đúng manual quy tắc nghiệp vụ (đặc biệt quy tắc ngầm/ghép), kế hoạch thiếu bước, và định dạng sai (làm tròn, dấu phân cách, thứ tự). Bộ chấm của DABStep chuẩn hoá nhẹ, nên định dạng vẫn là nguồn mất điểm.

### Cited Findings
- DABStep (450+ tác vụ từ khối lượng công việc thật của Adyen; Hard = 84%): baseline ReAct + Python tốt nhất ở bản ra mắt: o4-mini 14,55% Hard / 76,39% Easy; Claude 3.7 Sonnet 13,76 / 75,00; GPT-4.1 12,43 / 80,56; Llama 3.2 1B 0,00 / 1,39; tối đa 10 bước. Đây là mô hình lớn/đóng, không phải mô hình nhỏ. — [DABStep, arXiv 2506.23719](https://arxiv.org/html/2506.23719v1) (2025)
- Phân loại lỗi của DABStep (định tính, không có phần trăm): (1) lập kế hoạch/theo chỉ dẫn kém (tính trước khi đọc tài liệu; làm theo luật tường minh tốt hơn luật ngầm); (2) code kém hiệu quả; (3) lỗi chỉ dẫn nhiều bước: thêm chữ hội thoại, làm tròn sai, sai dấu phân cách/thứ tự; (4) nhạy prompt (R1, o1 gần 0% với prompt ReAct chuẩn cho đến khi đổi prompt cho mô hình suy luận). Có ví dụ agent đã nạp tài liệu nhưng vẫn trả dư vì bỏ sót điều kiện áp dụng phí. — [DABStep](https://arxiv.org/html/2506.23719v1)
- `manual.md` của DABStep là bản "tinh gọn" khái niệm nghiệp vụ, tác giả gọi là thiết yếu cho nhiều tác vụ Hard; mỗi tác vụ có hướng dẫn định dạng cụ thể (vd "scheme:fee, fee làm tròn 2 chữ số"). — [DABStep](https://arxiv.org/html/2506.23719v1)
- Bộ chấm DABStep: hạ chữ thường + cắt khoảng trắng; số: bỏ ký hiệu tiền/dấu phân cách rồi so với dung sai (văn bản nói 1e-4, mã giả dùng 1e-2: mâu thuẫn); list: tách, chuẩn hoá, bỏ qua thứ tự trừ khi yêu cầu; chuỗi: khớp chính xác hoặc mờ > 0,95. — [DABStep](https://arxiv.org/html/2506.23719v1)
- Bảng xếp hạng/top hiện tại của DABStep: một whitepaper Adyen nêu agent Claude 3.5 Sonnet nhiều sub-agent đạt 80,56%; đây là kết quả thứ cấp qua trang tóm tắt và là mô hình đóng. Trang leaderboard nói đã ngừng nhận validation mới chờ DABStep-v2. — [leaderboard](https://adyen-dabstep.hf.space/)

### Inferences
- (Suy luận) "Mô hình lỗi vì không áp đúng luật ngầm/ghép trong manual" khớp với việc bạn đã xây `rulebook.py` và Gate cho luật mới; hướng đúng là biến mỗi mục manual thành code tường minh, thay vì để LLM tự đọc.

### Gaps
- DA-Code, KramaBench, InfiAgent-DABench, Spider 2.0-lite, BIRD/mini-dev: không tìm được nguồn đọc được trong ngân sách tìm kiếm; không có số liệu phân tích lỗi (hiểu dữ liệu vs suy luận vs định dạng) cho chúng.
- Không tìm được mục nhập nào của DABStep dùng mô hình mở/nhỏ với mô tả kỹ thuật.

## 4. Cuộc thi Kaggle/AIcrowd/quốc gia 2024–2026 có chấm âm, LLM nhỏ offline

### Takeaway
Không tìm được bài tổng kết nào trong ngân sách tìm kiếm (không có kết quả nào cho truy vấn tương ứng).

### Cited Findings
- Không có nguồn đọc được.

### Gaps
- Chưa thử các truy vấn cụ thể cho Kaggle/AIcrowd/cuộc thi quốc gia; cần tìm riêng nếu còn thời gian.

## 5. Định dạng đáp án: mất bao nhiêu điểm, luật chuẩn hoá của đội thắng

### Takeaway
Bằng chứng định lượng duy nhất tìm được: ở pipeline Qwen2.5-14B (MRT), lỗi định dạng ≈ 10% số lỗi còn lại (6,49% biến đổi + 3,90% kiểu đáp án), tức chỉ vài điểm phần trăm tổng. Lỗi lớn nhất vẫn là hiểu câu hỏi/chỉ dẫn (37,66%) và lọc giá trị ô sai (14,29%). Bước chuẩn hoá bằng heuristic có thể gây thêm lỗi, nên cần kiểm tra bằng đo.

### Cited Findings
- MRT, phân tích lỗi thủ công (Qwen2.5-14B, validation): wrong instructions 37,66%; others (nhãn mơ hồ/sai) 23,38%; wrong cell value filtering 14,29%; wrong code 14,29%; formatting (transformations) 6,49%; formatting (answer type) 3,90%. Tác giả nhận xét xử lý các lỗi này phụ thuộc vào cách cài đặt metric (làm tròn, khớp một phần, thứ tự list). — [MRT](https://arxiv.org/html/2505.22264)
- TABVERSE (2026): với exact match nghiêm ngặt, lỗi "lệch khuôn đáp án" (thêm chữ, nhiều dòng, khác dấu phân cách, đáp án đúng nhưng không ở token đầu) phổ biến, nặng nhất với mô hình nhỏ; không có tỉ lệ rõ cho làm tròn/đơn vị. Chỉ có kết quả tìm kiếm tóm tắt, chưa đọc toàn văn. — [TABVERSE, arXiv 2606.09578](https://arxiv.org/pdf/2606.09578)
- Quy tắc chuẩn hoá thực dụng của các đội: yes/no → True/False; list → `.tolist()`, bỏ qua thứ tự; số cắt 2 chữ số; đếm rỗng → 0 (COALESCE); chỉ in giá trị, không câu văn. — [Anotheroption](https://arxiv.org/html/2506.09657v2), [ITUNLP](https://arxiv.org/html/2508.00762v1)

### Inferences
- (Suy luận) Vì hệ bạn tính bằng code cố định, định dạng đã thuộc quyền kiểm soát: mất điểm do định dạng sẽ do luật làm tròn/đơn vị/ngày của rulebook, không phải do LLM. Kiểm tra bằng bộ answers train (so từng loại đáp án) rẻ hơn mọi thay đổi khác.

### Gaps
- Không tìm được nguồn đo "bao nhiêu điểm mất do làm tròn/đơn vị" riêng; không có số cho các cuộc thi khác.

## Tách theo điều kiện áp dụng

- Training-free, áp được trong vài giờ (ý tưởng): ngưỡng log-prob trên token intent + lọc theo lỗi thực thi (ProbGate); đồng thuận hai đường độc lập để quyết định bỏ trống (PromptMind, KU-DMIS, Anotheroption orchestrator); schema kèm giá trị mẫu/số giá trị duy nhất (ITUNLP); ép kiểu đầu ra trong prompt (ITUNLP, Anotheroption); KHÔNG viết lại câu hỏi (Anotheroption).
- Cần fine-tune hoặc mô hình lớn: các số điểm cao nhất của EHRSQL (ChatGPT fine-tune), DataBench nhóm mở ≥ 32B, DABStep ~80% (mô hình đóng). Đừng so điểm tuyệt đối của chúng với hệ 4B.
