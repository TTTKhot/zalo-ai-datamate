# Thiết kế prompt cho LLM nhỏ (3–8B, Qwen-class) trích xuất/phân loại từ văn bản tiếng Việt không chuẩn

Ghi chú về mức đọc: "ĐỌC" = đã mở trang và đọc nội dung; "SNIPPET" = chỉ đọc đoạn tóm tắt do công cụ tìm kiếm trả về (chưa mở bài đầy đủ). Hầu hết bài chỉ ở mức SNIPPET vì giới hạn số lượt tra cứu. Không tìm thấy nghiên cứu nào đo đúng bối cảnh (~4B, JSON ra nhỏ, tiếng Việt không dấu); mọi chỗ ngoại suy đều ghi là Suy luận.

## 1. Ngôn ngữ của hướng dẫn / định nghĩa nhãn (Anh, Việt, song ngữ)

### Takeaway
Không có bằng chứng nhất quán cho thấy viết hướng dẫn bằng tiếng Việt thắng tiếng Anh ở mô hình nhỏ; bằng chứng cho tác vụ NLP chuẩn nghiêng về hướng dẫn tiếng Anh (hoặc dịch-rồi-xử lý), còn tiếng bản địa chỉ thắng nhẹ ở tác vụ nặng văn hoá hoặc ở mô hình đa ngữ mạnh. Không có số liệu cho prompt song ngữ/trộn trên Qwen 3–8B với tiếng Việt.

### Cited Findings
- "Is Translation All You Need?" (arXiv 2403.10258 v3, ĐỌC phần đầu): ChatGPT (gpt-3.5) và Llama-2-70B-Chat trên 24 ngôn ngữ; điểm TB (ngôn ngữ giàu / nghèo tài nguyên) Native-Basic 50.8/40.8 (ChatGPT), 42.5/29.5 (Llama-2-70B); EN-Basic (hướng dẫn tiếng Anh, input gốc) 56.4/46.0 và 47.3/35.2; dịch input sang Anh bằng Google 61.4/59.0 và 56.4/54.4. Tức hướng dẫn tiếng Anh +4,8 đến +5,7 điểm so với hướng dẫn bản địa, dịch toàn bộ còn hơn. Với Qwen1.5-72B và Yi-34B (chỉ tiếng Trung) khoảng cách dịch–bản địa nhỏ hơn (2.8 và 8 điểm trên MGSM) và dịch làm hại M3Exam; tác giả kết luận "dịch không tối ưu phổ quát", tác vụ văn hoá hoặc mô hình mạnh bản ngữ thì prompt bản địa tốt hơn. Mô hình đều ≥ 34B hoặc không rõ cỡ, tiếng Việt không phải ngôn ngữ trọng tâm — [arXiv](https://arxiv.org/html/2403.10258v3) (2024)
- Cùng bài: với Llama-2-70B-Chat truy vấn người dùng thật dịch sang Anh được ưa hơn ở mọi ngôn ngữ; ChatGPT thì ưa bản gốc ở ngôn ngữ giàu tài nguyên — [arXiv](https://arxiv.org/html/2403.10258v3)
- "Cross-Lingual Prompt Steerability" (arXiv 2512.02841, 12/2025, SNIPPET): system prompt tiếng Anh kém hơn nhẹ (marginal) so với system prompt cùng ngôn ngữ câu hỏi trên cả 4 chỉ số — [arXiv](https://arxiv.org/pdf/2512.02841)
- CulturALL (arXiv 2604.19262, 2026, SNIPPET): prompt tiếng Anh thấp hơn prompt bản địa ~8 điểm trên tác vụ gắn văn hoá; tác giả đoán do dịch làm mất ngữ cảnh văn hoá — [arXiv](https://arxiv.org/pdf/2604.19262)
- Native vs Non-Native Language Prompting (arXiv 2409.07054, 2024, SNIPPET qua tóm tắt): trên 11 tác vụ NLP tiếng Ả Rập, prompt không bản địa (Anh) tốt nhất, rồi trộn, rồi bản địa; lợi ích rõ ở few-shot — [bản tóm tắt](https://www.themoonlight.io/review/native-vs-non-native-language-prompting-a-comparative-analysis)
- ViExam (arXiv 2508.13680, 2025, SNIPPET): đổi hướng dẫn sang tiếng Anh trong khi nội dung đề thi giữ tiếng Việt không cải thiện; hiệu ứng lẫn lộn (nhỉnh với VLM mã nguồn mở, hại model đóng mạnh). Tác vụ là đề thi thị giác, không phải trích xuất — [arXiv](https://arxiv.org/pdf/2508.13680v1)
- Phân loại cảm xúc tiếng Việt (PACLIC 2024) thử 3 mẫu prompt song ngữ Anh/Việt, zero/few-shot trên GPT và mô hình mở; snippet không có kết quả so sánh ngôn ngữ — [ACL Anthology](https://preview.aclanthology.org/moar-dois/2024.paclic-1.17.pdf)

### Inferences
- Suy luận: với model 4B đa ngữ kiểu Qwen, hướng dẫn và định nghĩa nhãn tiếng Anh là mặc định an toàn (lệch về ≤ vài điểm nếu sai); lợi thế nếu có sẽ nằm ở TỪ KHOÁ miền tiếng Việt (tên nhãn đồng nghĩa, cách người dùng nói) chứ không phải câu hướng dẫn. Cách dung hoà rẻ nhất: hướng dẫn tiếng Anh + mỗi định nghĩa nhãn kèm 2–4 cụm từ khoá tiếng Việt (có dấu và không dấu). Đây là suy luận, không có thí nghiệm công bố cho đúng thiết kế này.
- Prompt hiện tại (hướng dẫn Anh + ví dụ Việt) đã gần với "mixed" nằm giữa; không có căn cứ để đổi toàn bộ sang tiếng Việt.

### Gaps
- Không tìm thấy so sánh có số liệu Anh/Việt/song ngữ cho mô hình 3–8B trên trích xuất hoặc phân loại ý định tiếng Việt. Chưa mở được PACLIC 2024 và ViExam bản đầy đủ. "Cross-lingual-thought" prompting (XLT) không được tra trực tiếp trong lượt này.

## 2. Chuẩn hoá đầu vào trước LLM (khôi phục dấu, mở rộng viết tắt, dịch sang Anh)

### Takeaway
Không tìm thấy bằng chứng trực tiếp về LLM đa ngữ trên tiếng Việt không dấu; bằng chứng gián tiếp: mô hình ít thấy văn bản có dấu bị bóc dấu, và dịch toàn bộ sang Anh có lợi ở mô hình yếu, nhưng với câu hỏi ngắn dạng ý định tác động nhiễu (typo) nhỏ. Thêm bước khôi phục dấu bằng chính LLM nhỏ có rủi ro chưa được đo.

### Cited Findings
- "Don't Touch My Diacritics" (arXiv 2410.24140, 10/2024, SNIPPET): lập luận rằng LLM kém xử lý văn bản bị bóc dấu một phần vì tiền xử lý chuẩn loại dấu khỏi dữ liệu huấn luyện; nêu WER khôi phục dấu tiếng Việt > 40% trong một nghiên cứu 2018 (nguồn cũ) — [arXiv](https://arxiv.org/pdf/2410.24140)
- Thẻ mô hình vn-diacritic-vit5-base (tự báo cáo, 1 loại văn bản): gpt-4o-mini đạt 95.37 độ chính xác từ khi khôi phục dấu; chỉ là số của tác giả mô hình, và là mô hình lớn đóng — [Hugging Face](https://huggingface.co/nrl-ai/vn-diacritic-vit5-base)
- "Exploring Robustness of Multilingual LLMs on Real-World Noisy Data" (arXiv 2501.08322, 1/2025, SNIPPET): 9 mô hình 0.2–13B được fine-tune, nhiễu là typo mined từ Wikipedia (Anh, Đức, Tây Ban Nha, Pháp, Hindi, Thổ); chênh sạch→nhiễu 2.3–4.3 điểm tuyệt đối; phân loại ý định (SNIPPETS) là tác vụ có chênh nhỏ nhất, NLI lớn nhất. Không có tiếng Việt, không có bóc dấu, các mô hình được fine-tune (không phải prompting) — [arXiv](https://arxiv.org/pdf/2501.08322)
- "Is Translation All You Need?": dịch sang Anh chất lượng cao (Google) tốt nhất trung bình, dịch bằng NLLB kém hơn rõ (57.3/54.2 so với 61.4/59.0 ở ChatGPT), tức chất lượng dịch quyết định — [arXiv](https://arxiv.org/html/2403.10258v3). Lưu ý bản dịch này được tạo bằng máy dịch chuyên dụng, không phải LLM 4B.

### Inferences
- Suy luận: bóc dấu trong tiếng Việt gây nhập nhằng thật (nhiều từ khác nghĩa trùng dạng không dấu), nên LLM nhỏ phải dùng ngữ cảnh; ép nó khôi phục dấu trước rồi mới phân loại là thêm một bước có thể sai (WER cao trong nghiên cứu cũ) và tốn thời gian suy luận; nguy cơ lan truyền lỗi lớn hơn lợi ích khi chỉ cần chọn 1 trong ~40 thao tác. Chưa được thực nghiệm.
- Suy luận: phương án rủi ro thấp hơn là bổ sung vào prompt (không dịch câu hỏi) bảng "cách người dùng viết tắt/không dấu → khái niệm" và ví dụ không dấu; hoặc đưa vào prompt đồng thời bản gốc và bản chuẩn hoá bằng luật (rule-based, không dùng LLM), để model thấy cả hai.

### Gaps
- Không tìm thấy so sánh LLM 3–8B đọc tiếng Việt không dấu vs có dấu trên tác vụ hiểu; không có số liệu cho unaccented Spanish/French hay romanised Hindi/Arabic (chưa tra riêng). Không có dữ liệu "restore-diacritics-then-classify" đo end-to-end.

## 3. Định dạng few-shot cho chat model (lượt user/assistant xen kẽ vs nhúng system, số ví dụ, thứ tự, cân bằng nhãn, ví dụ phủ định)

### Takeaway
Thiên lệch recency và majority-label là bằng chứng vững (từ 2021, nhiều mô hình); nhưng KHÔNG có nghiên cứu nào tôi tìm được so sánh trực tiếp "ví dụ dạng lượt chat" và "ví dụ nhúng system prompt" ở mô hình nhỏ. Về ví dụ phủ định chỉ có bằng chứng ở sinh văn bản, không phải phân loại.

### Cited Findings
- Majority label bias, recency bias, common-token bias được xác lập ở Zhao et al. 2021 (đọc qua trích dẫn, mô hình GPT-3/2): dự đoán bị kéo về nhãn xuất hiện nhiều nhất và nhãn ở cuối chuỗi ví dụ; đổi thứ tự ví dụ thay đổi dự đoán rất nhiều (Lu et al. 2021). Cả hai chỉ đọc qua bài trích dẫn — [Batch Calibration, arXiv 2309.17249](https://arxiv.org/pdf/2309.17249) (2023), [Prototypical Calibration, arXiv 2205.10183](https://arxiv.org/pdf/2205.10183)
- Cơ chế: bỏ ảnh hưởng của positional embedding trong "in-context heads" giảm recency bias 17%; tăng attention của nhãn thiểu số giảm majority bias 22% (số của chính tác giả, SNIPPET) — [arXiv 2402.02872](https://arxiv.org/pdf/2402.02872) (2024)
- In-Context Calibration (NAACL 2024, SNIPPET): LLM hay dựa vào tiên nghiệm ngữ nghĩa của ví dụ thay vì ánh xạ vào-nhãn ("Demonstration Shortcut") — [arXiv 2403.09488](https://arxiv.org/html/2403.09488v1)
- Vị trí khối demo trong prompt (EMNLP 2025 main.1503, SNIPPET): dời một khối demo cố định (giữ nguyên thứ tự) đổi dự đoán và độ chính xác ("DPP bias") — [ACL Anthology](https://aclanthology.org/anthology-files/pdf/emnlp/2025.emnlp-main.1503.pdf)
- "Mitigating Boundary Ambiguity and Inherent Bias for Text Classification" (arXiv 2406.07001, 2024, SNIPPET): đưa vài demo giảm thiên lệch vị trí đáp án ở mô hình lớn hơn, hiệu quả yếu hơn ở mô hình nhỏ — [arXiv](https://arxiv.org/pdf/2406.07001)
- Nghiên cứu cảm xúc tiếng Bồ Đào Nha trên mô hình ~9B (SNIPPET qua trang tổng hợp): chỉ dẫn rõ ràng mang phần lớn lợi ích ICL (gần tối đa ngay cả zero-shot), chỉ demo có thể làm giảm — [SBC STIL](https://sol.sbc.org.br/index.php/stil/article/download/44627/44390/)
- Đa lượt hội thoại: "LLMs Get Lost in Multi-Turn" — chia nhỏ yêu cầu qua nhiều lượt làm giảm TB 39%, gộp lại (CONCAT) hồi phục ~95%; RMTBench: lịch sử đóng vai ví dụ trong ngữ cảnh gây thiên lệch rõ ở Llama-3.1-8B và Qwen2.5-7B (đều qua trang tổng hợp; đây không phải thí nghiệm few-shot-dạng-lượt, chỉ cảnh báo gián tiếp) — [PromptHub](https://prompthub.substack.com/p/llms-get-lost-in-multi-turn-conversations), [RMTBench](https://arxiv.org/pdf/2507.20352)
- Ví dụ phủ định: Contrastive In-Context Learning (Gao & Das, AAAI 2024, SNIPPET) — cặp ví dụ đúng/sai kèm yêu cầu tự phân tích cải thiện "đáng kể" so với few-shot chuẩn, nhưng cho sinh/tuỳ biến phản hồi, không phải phân loại ý định — [AAAI](https://ojs.aaai.org/index.php/AAAI/article/view/29760)

### Inferences
- Suy luận: vì ví dụ giống nhất đặt cuối được hưởng recency (kéo dự đoán về nhãn của nó), nếu ví dụ lấy từ truy xuất tương đồng thì hợp lý đặt ví dụ giống nhất ở cuối; rủi ro là kéo sai nhãn nếu ví dụ cuối là "gần giống nhưng khác nhãn". Đây là suy luận từ bằng chứng recency bias, chưa có thí nghiệm riêng cho 4B.
- Suy luận: không có bằng chứng cho lợi thế của lượt user/assistant ở mô hình nhỏ; chat template Qwen được huấn luyện với lượt, nên cũng không có bằng chứng bất lợi — cần A/B thực nghiệm.
- Suy luận: cân bằng nhãn trong ví dụ quan trọng hơn số ví dụ; với 40 nhãn thì ví dụ trải đều các nhãn dễ nhầm có giá trị hơn nhồi thêm ví dụ của nhãn phổ biến.

### Gaps
- Không có nghiên cứu so sánh trực tiếp chat-turn vs system-inline cho ≤8B; không có số liệu về số ví dụ tối ưu cho 40 nhãn; không có bằng chứng đo hard-negative cho phân loại ý định.

## 4. Trình bày danh mục nhãn (thứ tự, nhóm, định nghĩa ngắn/dài, trước/sau câu hỏi)

### Takeaway
Thiên lệch vị trí nhãn tăng theo số nhãn và có bằng chứng ở mô hình mở cỡ Qwen/LLaMA; thứ tự "nhãn đầu và cuối được ưa" khá nhất quán. Về vị trí danh mục so với câu hỏi, bằng chứng nghiêng về "đặt câu hỏi/chỉ thị cuối" nhưng thay đổi theo mô hình và tác vụ.

### Cited Findings
- "Serial Position Effects of LLMs" (arXiv 2406.15981, 2024, SNIPPET): với 42 nhãn, mô hình ưa nhãn ở đầu và cuối danh sách; hiệu quả giảm khi số nhãn tăng — [arXiv](https://arxiv.org/html/2406.15981v1). Mô hình nêu trong snippet: SOLAR-0-70b (lớn).
- arXiv 2406.07001 (SNIPPET): dời vị trí của đáp án đúng giữa các lựa chọn làm thay đổi hơn 50% ở mô hình mở như LLaMA và Qwen (cỡ không rõ trong snippet) — [arXiv](https://arxiv.org/pdf/2406.07001)
- Lost in the Middle (Liu et al. 2023, đọc qua tổng hợp): độ chính xác cao nhất khi thông tin ở đầu hoặc cuối ngữ cảnh, thấp ở giữa — [tổng hợp](https://ai-papers.aktagon.com/papers/lost-middle/). Thí nghiệm ở ngữ cảnh dài hơn 2–4k token đáng kể; nên hiệu ứng ở prompt 2–4k token có thể nhỏ hơn (suy luận).
- BAMBOO (arXiv 2309.13345, SNIPPET): vị trí chỉ dẫn tối ưu thay đổi theo bộ dữ liệu và mô hình; đặt chỉ dẫn cuối thường giúp, đặt đầu có nguy cơ "quên chỉ dẫn" ở đầu vào dài — [arXiv](https://arxiv.org/pdf/2309.13345)
- "Lost in the Prompt Order" (arXiv 2601.14152, 1/2026, SNIPPET): với trắc nghiệm, ngữ cảnh trước rồi câu hỏi và lựa chọn (CQO) hơn thứ tự ngược (QOC) hơn 14 điểm phần trăm — [arXiv](https://arxiv.org/html/2601.14152v1)
- Giảm thiên lệch: hoán vị/trộn thứ tự nhãn rồi trung bình, hiệu chuẩn (contextual, batch, domain-context calibration) — [Batch Calibration](https://arxiv.org/pdf/2309.17249), [Domain-context calibration, ETH](https://research-collection.ethz.ch/handle/20.500.11850/669685)

### Inferences
- Suy luận: với danh mục ~40 thao tác trong system prompt và câu hỏi ở lượt user (cuối), cấu hình hiện tại đã "danh mục trước, câu hỏi sau" — khớp CQO và "câu hỏi cuối"; không nên đảo.
- Suy luận: nên đặt các nhãn hay nhầm/phổ biến ở đầu hoặc cuối danh mục, nhóm nhãn gần nghĩa cạnh nhau với dòng phân biệt; nhưng bằng chứng về nhóm nhãn và độ dài định nghĩa (ngắn vs dài) cho mô hình nhỏ tôi KHÔNG tìm thấy.

### Gaps
- Không tìm thấy nghiên cứu về định nghĩa nhãn dài vs ngắn, hay gom nhóm nhãn, ở mô hình ≤8B. Số liệu thiên lệch vị trí chủ yếu từ mô hình lớn hơn hoặc không nêu cỡ.

## 5. Nhạy cảm với prompt và giảm phương sai rẻ (gộp 2–3 mẫu prompt)

### Takeaway
Bỏ phiếu đa số qua vài biến thể prompt giảm phương sai rõ (phần lớn lợi ích đến từ k=1→3) nhưng không đảm bảo tăng độ đúng; hiệu quả chỉ khi các biến thể có chất lượng ngang nhau và đủ khác nhau. Không có số liệu độ chính xác cho phân loại nhỏ-4B tiếng Việt.

### Cited Findings
- Nghiên cứu độ tin cậy giữa các prompt (arXiv 2604.16413, 4/2026, SNIPPET): đa số phiếu qua k prompt tương đương về nghĩa nhưng khác diễn đạt làm "đệm" tin cậy; mức giảm phương sai lớn nhất ở k=1→3; không nhất thiết tăng độ đúng — [arXiv](https://arxiv.org/pdf/2604.16413)
- Nghiên cứu mô hình mã nguồn mở nhỏ trong y tế (nêu trong cùng kết quả tìm kiếm): nhất quán cao không đồng nghĩa đúng — dẫn qua tổng hợp tìm kiếm, nguồn gốc chưa mở
- "Flaw or Artifact? Rethinking Prompt Sensitivity" (arXiv 2509.01790, 2025, SNIPPET): cho rằng độ nhạy prompt phần lớn là hiện tượng của cách chấm (so khớp heuristic) — [arXiv](https://arxiv.org/html/2509.01790v1). Điều này nghĩa là với đầu ra JSON có thể kiểm tra đúng-sai chặt, độ nhạy thật có thể nhỏ hơn.
- Phát hiện URL lừa đảo (arXiv 2603.00917 / catalogue "To ensemble or not", SNIPPET): ensemble chỉ hợp khi các thành phần có hiệu năng tương đương; nếu lệch nhiều có thể không hơn prompt tốt nhất — [arXiv](https://arxiv.org/pdf/2603.00917)

### Inferences
- Suy luận: 2–3 lần chạy với danh mục đảo thứ tự (cùng chỉ dẫn) là biến thể rẻ nhất vừa khử thiên lệch vị trí vừa lấy phiếu; với greedy và chỉ ~10% ngân sách thời gian đã dùng, ngân sách cho phép (suy luận từ mô tả hệ thống). Khi 2 biến thể bất đồng, dùng tín hiệu bất đồng đó làm cờ "không chắc → bỏ trống" có thể có giá trị hơn là cố chọn đa số.
- 2 phiếu không có đa số: cần phiếu thứ 3 hoặc quy tắc phân xử.

### Gaps
- Không có số tăng độ chính xác (điểm %) cho ensemble prompt trên phân loại ý định ≤8B. Chưa mở bài nào đầy đủ trong nhóm này.

## 6. Định dạng đầu ra (khoá JSON tiếng Anh vs bản ngữ, thứ tự trường)

### Takeaway
Bằng chứng mới và mạnh nhất: đặt lập luận/trường "phụ thuộc" trước câu trả lời cuối thì bằng hoặc hơn tự do, đặt đáp án trước gây tụt mạnh ở mô hình nhỏ. Khoá JSON tiếng Anh: chỉ có báo cáo kỹ thuật về lỗi dịch khoá, chưa có đo độ chính xác.

### Cited Findings
- "Structure Tax: How Structured Output affects LLMs Performance" (Kumar et al., AACL-IJCNLP 2026, ĐỌC trang tóm tắt ACL Anthology): reasoning-first bằng hoặc hơn free-form; answer-first "giảm dốc", đặc biệt ở mô hình nhỏ; reasoning-first còn cải thiện calibration. Không có số cụ thể hay tên mô hình trong abstract — [ACL Anthology](https://aclanthology.org/2026.aacl-long.209/)
- Thí nghiệm pydantic-evals trên mô hình GPT (blog CO/AI, SNIPPET): chênh lệch tối thiểu giữa hai thứ tự — mâu thuẫn một phần với bài trên; chỉ là blog — [CO/AI](https://getcoai.com/news/why-field-order-may-not-improve-model-reasoning)
- Báo cáo kỹ thuật (arXiv 2604.24636, 2026, SNIPPET): model nhỏ trên thiết bị dịch khoá JSON sang ngôn ngữ đầu ra của prompt (vd "palabra" thay "word") — lỗi nhất quán, không phải đo độ đúng — [arXiv](https://arxiv.org/pdf/2604.24636)
- Đặt tên thuộc JSON tường minh cải thiện nhất quán định dạng (arXiv 2504.02052, SNIPPET, không thử khoá phi-Anh) — [arXiv](https://arxiv.org/pdf/2504.02052)
- Format Matters (LREC 2026, SNIPPET): hiệu năng và độ tin cậy phụ thuộc định dạng yêu cầu (JSON, XML, key-value) cho SLU và NER — [ACL Anthology](https://preview.aclanthology.org/ingest-lrec/2026.lrec-main.593/)
- Lưu ý: bằng chứng "reasoning-first" là về trường lập luận (CoT) đứng trước đáp án; thinking đã tắt ở hệ thống này nên không áp thẳng được.

### Inferences
- Suy luận: JSON gồm {operation, time period, filters} không có trường lập luận; điều gần nhất là thêm một trường ngắn kiểu "key_phrases" hoặc "interpretation" (câu diễn giải ngắn tiếng Việt/Anh) đặt TRƯỚC "operation". Có thể nâng độ đúng nhờ cơ chế "sinh nội dung trước nhãn", nhưng thinking đã tắt vì lý do nào đó (đã ngoài phạm vi), nên rủi ro làm chậm/lệch; chưa có bằng chứng trực tiếp.
- Suy luận: giữ khoá tiếng Anh, giá trị tiếng Việt khi cần, nói rõ trong prompt "keys in English, values copy the user's words" để tránh dịch khoá.
- Đặt "operation" trước các trường khác (thời gian, bộ lọc) thì các trường sau được điều kiện hoá theo nhãn đã chọn — hợp lý nhưng chưa có bằng chứng; ngược lại, nếu nhãn sai thì lỗi lan sang trường sau.

### Gaps
- Chưa thấy số liệu thứ tự trường cho trích xuất (không CoT) ở ≤8B; chưa có số cụ thể từ Structure Tax (chỉ đọc abstract). Không có đo khoá bản ngữ vs Anh.

## Xếp hạng thay đổi prompt rủi ro thấp (tối đa 5)

Tất cả là dự đoán dựa trên bằng chứng gián tiếp; thiết kế A/B chạy trên cùng tập câu của 24 shop (hoặc 24 shop train, không đụng 6 shop giữ kín) với cùng cấu hình greedy; đo trước/sau và theo từng lớp lỗi.

1. Đảo thứ tự danh mục nhãn, chạy 2 phiên bản (xuôi và đảo) rồi chỉ trả lời khi hai bản trùng operation (bất đồng → bỏ trống hoặc phiên bản thứ 3 phân xử).
   - Cơ sở: thiên lệch vị trí nhãn đầu/cuối (arXiv 2406.15981, 2406.07001), bỏ phiếu giảm phương sai (arXiv 2604.16413).
   - A/B: A = 1 lần chạy hiện tại; B = 2 lần chạy danh mục xuôi/đảo + quy tắc bất đồng. Đo: điểm (+1/−1/0) và số câu bất đồng nhưng sai. Hướng kỳ vọng: số câu sai giảm, một phần câu chuyển thành bỏ trống; tăng thời gian ~2x (vẫn còn dư theo mô tả). Hiệu ứng điểm: không có số công bố cho ≤8B.
2. Thêm cụm từ khoá tiếng Việt (có dấu và không dấu, viết tắt thường gặp) vào định nghĩa nhãn, giữ hướng dẫn tiếng Anh.
   - Cơ sở: hướng dẫn tiếng Anh an toàn (arXiv 2403.10258); ví dụ/tiền xử lý không đủ cho tiếng Việt không dấu (arXiv 2410.24140, gián tiếp).
   - A/B: A = định nghĩa hiện tại; B = cùng định nghĩa + 3 cụm từ khoá Việt mỗi nhãn, rút từ rulebook/từ vựng chung (không từ lỗi 24 shop). Hướng: tăng nhẹ ở câu không dấu/viết tắt; rủi ro: nhiều token hơn (+~500–1000).
3. Đảo/chọn thứ tự ví dụ few-shot: ví dụ giống nhất đặt cuối, và cân bằng nhãn (không để một nhãn chiếm đa số ví dụ).
   - Cơ sở: recency + majority label bias (Zhao et al. 2021 qua arXiv 2309.17249, 2402.02872).
   - A/B: A = thứ tự hiện tại; B = giống nhất cuối + giới hạn mỗi nhãn ≤ 2 ví dụ. Hướng: giảm lỗi "kéo về nhãn phổ biến"; dễ sai nếu ví dụ cuối khác nhãn, nên đo riêng nhóm câu nhầm giữa các nhãn gần nghĩa.
4. Giữ khoá JSON tiếng Anh, thêm câu "keys in English, copy user's words in values", đặt `operation` trước các trường phụ thuộc (đang giữ nguyên nếu đã vậy); nếu có thể thử thêm trường ngắn `interpretation` trước `operation`.
   - Cơ sở: arXiv 2604.24636 (dịch khoá), Structure Tax (field order; chỉ áp cho trường lập luận).
   - A/B: chỉ làm A/B cho `interpretation` (thay đổi duy nhất); A = hiện tại, B = thêm trường. Hướng: có thể tăng (dựa trên Structure Tax) nhưng thinking đang tắt nên bằng chứng yếu; ít token đầu ra nên rủi ro thời gian thấp.
5. Gom nhóm và thêm một dòng phân biệt cho các cặp nhãn hay nhầm trong danh mục; đặt chúng ở đầu hoặc cuối.
   - Cơ sở: gián tiếp (serial position, contrastive ICL ở sinh văn bản). Bằng chứng yếu nhất.
   - A/B: A = danh mục hiện tại; B = nhóm lại + dòng "X vs Y: dùng X khi…". Hướng: giảm nhầm trong cặp đó; rủi ro: viết dòng phân biệt từ lỗi của 24 shop nên số đo là lạc quan.

Không xếp hạng (bằng chứng ngược hoặc thiếu): dịch câu hỏi sang tiếng Anh bằng LLM 4B; khôi phục dấu bằng LLM trước phân loại; đổi toàn bộ hướng dẫn sang tiếng Việt; chuyển ví dụ sang lượt chat (không có bằng chứng, nên chỉ thử nếu còn lượt chạy).
