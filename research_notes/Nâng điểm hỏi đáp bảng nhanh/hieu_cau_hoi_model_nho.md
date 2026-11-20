# Kỹ thuật không huấn luyện (prompt/decoding) để nâng độ chính xác semantic parsing câu hỏi → JSON intent cho LLM ~4B

Ghi chú: ~14 lệnh tìm/đọc. Nhiều con số lấy từ snippet tìm kiếm hoặc trang tóm tắt, không kiểm lại bảng gốc; chỗ nào chưa kiểm ghi rõ. Hầu hết bằng chứng text-to-SQL của DAIL-SQL là GPT-4 (không phải model nhỏ).

## 1. Retrieval-based dynamic few-shot (DAIL-SQL, BM25, masking)

### Takeaway
Chọn ví dụ theo độ giống câu hỏi (có che entity) cho tăng lớn so với chọn ngẫu nhiên, nhưng bằng chứng định lượng mạnh nhất là trên GPT-4; với model nhỏ và dữ liệu lệch phân phối chưa có số trực tiếp. BM25 thường ngang hoặc hơn retriever dense (BERT) trong semantic parsing, nên BM25 thuần là lựa chọn hợp lý; nhưng "giống bề mặt" là proxy yếu khi cấu trúc đầu ra khác, nên cần thêm đa dạng/phủ nhãn.

### Cited Findings
- DAIL-SQL (GPT-4, Spider dev, EM, 5-shot, theo bảng README; ánh xạ cột là suy luận của công cụ tìm kiếm, chưa đối chiếu bài báo): random ~51.6, question-similarity ~58.2, masked-question-similarity ~66.8, DAIL selection (masked question + độ giống skeleton SQL) ~71.9. 3-shot: masked ~58.2 vs plain ~53.3. Chỉ đã chứng minh trên GPT-4-class. — [DAIL-SQL README](https://raw.githubusercontent.com/BeachWang/DAIL-SQL/main/README.md), [arXiv 2308.15363, 2023](https://arxiv.org/pdf/2308.15363v3) (tôi không đọc được bảng PDF)
- Một luận văn MSc (Edinburgh) báo đổi embedding model ít ảnh hưởng execution accuracy; cách chọn ví dụ quan trọng hơn. Nguồn phụ. — [msc_proj](https://project-archive.inf.ed.ac.uk/msc/20247134/msc_proj.pdf)
- BM25 vượt retriever dựa BERT trong chọn ví dụ cho semantic parsing; ví dụ giống nhất theo bề mặt có thể kém hữu ích hơn ví dụ ít giống nhưng cùng cấu trúc đích. — [Evaluating the Impact of Model Scale for Compositional Generalization in Semantic Parsing, 2022](https://arxiv.org/pdf/2205.12253)
- Cosine và BM25 đều dưới tối ưu (một embedding / unigram overlap); chọn tập ví dụ phủ các cấu trúc con (SET-BSR) tăng thêm trong semantic parsing, nhất là compositional, gain lớn dần theo cỡ LLM. — [Coverage-based Example Selection, 2023](https://arxiv.org/pdf/2305.14907)
- Trong compositional generalization, chỉ chọn ví dụ giống là chưa đủ; kết hợp ví dụ đa dạng cho gain trên 3 bộ semantic parsing. — [diverse-demonstrations](https://github.com/itayle/diverse-demonstrations)
- Nhiều nhãn: dùng retriever chọn ví dụ + chỉ các nhãn liên quan, không cần fine-tune; model lớn tận dụng nhiều ví dụ tốt hơn model nhỏ. Kiểm tra trên OPT/LLaMA, BANKING77/HWU64/CLINC150. Ablation: độ giống ví dụ, nghĩa tên nhãn, đúng cặp ví dụ-nhãn đều quan trọng tuỳ domain. — [In-Context Learning for Text Classification with Many Labels, 2023](https://arxiv.org/pdf/2309.10954)
- Fine-tune vs ICL dưới domain shift: fine-tune tốt trong-domain, few-shot LLM thường vượt khi khác domain; nhưng bài so sánh công bằng cho rằng khoảng cách có thể do cách thiết lập. — kết quả tìm kiếm tổng hợp, [Fine-tuning vs ICL (2026)](https://www.alphaxiv.org/abs/2604.23267.md); [few-shot FT vs ICL fair comparison](https://astro.paperswithcode.com/paper/few-shot-fine-tuning-vs-in-context-learning-a)
- Retrieval theo độ giống gặp khó khi shift phân phối (bằng chứng ở thị giác-ngôn ngữ, không phải intent/slot). — [arXiv 2405.12217](https://arxiv.org/pdf/2405.12217)

### Inferences
- Câu hỏi test khác cách diễn đạt so với train (LoRA overfit phrasing): few-shot động không thay trọng số nên ít overfit hơn, nhưng nếu câu test nằm xa mọi ví dụ train thì ví dụ lấy về có thể gây hại (nhãn "gần nhất" kéo model sang sai). Cần cơ chế: chỉ dùng ví dụ khi điểm BM25 vượt ngưỡng, ngưỡng đặt từ train.
- Che entity (số, tên sản phẩm, ngày tháng → placeholder) trước BM25 là rẻ và khớp với phát hiện masked > plain; áp dụng được cho tiếng Việt (che số, ngày, tên riêng bằng regex). Chuẩn hoá bỏ dấu tăng khả năng khớp giữa cách viết khác nhau.
- k nên 4–8 (ngân sách thời gian dư); sắp xếp ví dụ giống nhất ở CUỐI (gần câu hỏi). Chưa có nguồn đã kiểm cho khuyến nghị k/thứ tự; đây là suy đoán thực hành.
- Chọn ví dụ đảm bảo phủ nhãn gần nhau (cặp dễ nhầm) thay vì top-k thuần BM25 (theo ý coverage/diverse).

### Gaps
- Không tìm được số đo dynamic few-shot vs zero-shot cho model ≤8B trong text-to-SQL/intent parsing, và không có so sánh trực tiếp với fine-tune dưới distribution shift cho intent/slot. Số k tối ưu, thứ tự ví dụ: không có nguồn đáng tin tìm được.
- Chưa kiểm bảng gốc DAIL-SQL (PDF nhị phân, không đọc được), kể cả kết quả với model mã nguồn mở.

## 2. Constrained / grammar-guided decoding tới JSON schema

### Takeaway
Constrained decoding gần như chắc chắn loại bỏ lỗi định dạng (validity 78.6–92.9% → 100% ở model 0.6B–4B), nhưng KHÔNG cải thiện đáng tin cậy độ đúng ngữ nghĩa và có thể hại model nhỏ khi grammar phức tạp hoặc khi buộc trả lời trước lý do. Với tác vụ giống phân loại, ràng buộc enum thường trung tính hoặc tốt.

### Cited Findings
- Format restriction (JSON-mode, schema) làm hỏng reasoning nhưng giữ/tăng độ chính xác phân loại: Gemini 1.5 Flash trên DDXPlus ~41.6% (text) → 60.3% (JSON); các bộ phân loại khác (Sports, Task 280, MultiFin) JSON-mode ngang hoặc hơn; giả thuyết: thu hẹp không gian đáp án giảm lỗi chọn đáp án. — [Let Me Speak Freely?, Tam et al., 2024](https://arxiv.org/html/2408.02442v3)
- Cùng bài: GSM8K zero-shot text vs JSON: LLaMA-3-8B-Instruct 75.13 → 64.67; Gemma-2-9B 86.5 → 84.2; thêm schema constraint làm tụt thêm ở một số model (Claude 3 Haiku JSON 23.44, GPT-3.5 49.25). Last Letter: LLaMA-3-8B 70.1 → 28.0. — cùng nguồn
- Cùng bài: GPT-3.5 ở JSON-mode đặt khoá "answer" trước "reason" 100% số lần, nên bỏ qua suy luận. (Blog khuyến nghị đặt khoá reasoning trước là ý kiến thực hành, không phải kết luận bài.) — cùng nguồn; [blog](https://tianpan.co/blog/2026-04-23-markdown-beats-json-output-format-tax)
- StructureBench (IJCAI 2026): constrained decoding đảm bảo hợp lệ cú pháp nhưng không cải thiện ngữ nghĩa đáng tin cậy, có thể giảm với model nhỏ hoặc grammar phức tạp. Nghiên cứu 0.6B–4B trên 14 tác vụ (Outlines, XGrammar): validity lên 100%, vẫn còn khoảng cách ngữ nghĩa phụ thuộc cỡ model. Chỉ đọc snippet, chưa đọc bài. — [IJCAI 2026](https://www.ijcai.org/proceedings/2026/0267.pdf)
- JSONSchemaBench: benchmark 10K schema, so 6 framework (Guidance, Outlines, llama.cpp, XGrammar, OpenAI, Gemini); độ phủ/độ nhạy phụ thuộc engine và độ phức tạp schema. — [arXiv 2501.10868, 2025](https://arxiv.org/pdf/2501.10868)

### Inferences
- Cách rẻ nhất trong transformers thuần: không cần thư viện. (a) Với nhãn operation: chấm điểm log-prob của từng nhãn (~40) sau prefix `"operation": "` rồi lấy argmax (hoặc top-3 làm shortlist) — tương đương enum-constrained, không lo grammar, cho ra phân phối để đo độ chắc chắn và bỏ trống. (b) Phần còn lại: sinh tự do + `json.loads` + kiểm khoá hợp lệ, thử lại 1 lần. Cũng có thể dùng `prefix_allowed_tokens_fn`/logits processor trong `generate` (có sẵn trong transformers) cho enum.
- Thứ tự khoá: đặt trường "ghi chú ngắn/restate" trước "operation" nếu dùng CoT ngắn; còn không thì để operation trước.
- Rủi ro chính: ép tokenizer tiếng Việt/enum bằng grammar có thể làm model chọn nhãn có prefix token giống; scoring log-prob toàn nhãn tránh vấn đề này.

### Gaps
- Không có số đo riêng cho 3–4B Qwen trên tác vụ parse → JSON với enum; chỉ có suy luận từ các nghiên cứu khác. Chưa đọc số liệu bài 0.6B–4B.

## 3. Reasoning trước JSON (thinking mode / CoT ngắn)

### Takeaway
Bằng chứng nghiêng về CoT/thinking KHÔNG giúp (có khi hại) các tác vụ giống phân loại ở model nhỏ; rủi ro: overthinking, không đóng khối thinking, vỡ format. CoT rất ngắn có cấu trúc (restate cái đang được đếm) là hướng nhẹ hơn nhưng chưa có nguồn định lượng trực tiếp.

### Cited Findings
- Qwen3 thinking vs non-thinking trên sentiment: reasoning thường làm giảm hiệu năng, nhất là phân loại nhị phân đơn giản. Chỉ biết từ snippet. — [arXiv 2602.24060](https://arxiv.org/pdf/2602.24060)
- IFEval, Qwen3 1.7B–32B, cùng trọng số bật/tắt thinking: thinking giảm strict accuracy ở mọi cỡ; tụt lớn nhất ở 1.7B (~3.5 điểm mức prompt), giảm dần tới 14B. — [arXiv 2606.09662](https://arxiv.org/pdf/2606.09662)
- Biến thể thinking nhỏ của Qwen3/Qwen3.5 khó triển khai nếu không giới hạn: có lần không bao giờ đóng khối thinking. — [Mellum2 Technical Report, 2026](https://arxiv.org/pdf/2605.31268)
- Reasoning tăng accuracy nhưng giảm recall ở điểm vận hành quan trọng (phát hiện an toàn/hallucination). — [EACL 2026](https://preview.aclanthology.org/ingest-eacl/2026.eacl-long.190.pdf)
- Trong text-to-SQL/table QA cuộc thi (SemEval-2025 Task 8), đa số hệ thống top dùng sinh code + tự sửa lỗi; mô hình lớn vượt rõ mô hình nhỏ; tổ chức nhận xét prompting thông minh quan trọng không kém cỡ model. — [Task 8 overview/system papers](https://preview.aclanthology.org/setup/2025.semeval-1.324)

### Inferences
- Thinking mode mặc định bật cho 4B chỉ nên thử như A/B nhỏ có giới hạn token, không phải hướng ưu tiên. CoT ngắn có kiểm soát (1–2 câu "đối tượng được đếm/tính: …", rồi JSON) rẻ hơn và dễ cắt; cần đo trên cặp đơn hàng vs doanh thu, số lượng vs hiệu ứng đổi giá.
- Phương án thay thế mạnh hơn CoT: self-consistency/ensemble prompt (vài prompt khác nhau, bỏ phiếu nhãn), vì ngân sách thời gian dư. Đây là suy luận, không có nguồn trong ghi chú này.

### Gaps
- Không tìm được nghiên cứu đo CoT vs trực tiếp cho model 3–8B trên semantic parsing/intent parsing đa nhãn; không có số cụ thể cho Qwen 4B parse JSON.

## 4. Hai giai đoạn: shortlist nhãn + định nghĩa tương phản, sau đó điền slot

### Takeaway
Thu hẹp không gian nhãn trước khi cho LLM chọn có bằng chứng cải thiện chọn nhãn và OOS (kể cả LLM lớn), và rút gọn prompt; bằng chứng đến từ các pipeline có bộ phân loại nhỏ đứng trước. Định nghĩa tương phản cho cặp dễ nhầm chưa có số đo chuyên biệt tìm được.

### Cited Findings
- Label Space Reduction: chọn tập nhỏ nhất các intent có tổng xác suất tích luỹ ≥ 0.85 từ BERT rồi chỉ đưa tập này vào prompt LLM; hit rate >90%, giảm không gian nhãn ~50–80%; DeepSeek-R1 70B trên MPGT: F1-OOS 35.90 → 45.00, ACC 81.88; Llama-3 70B vẫn kém OOS. Cải thiện không đồng đều (MIntRec2.0 không vượt BERT đơn). — [Intent Recognition and OOS Detection using LLMs, 2025](https://arxiv.org/html/2507.22289v1)
- Pipeline ICL thích nghi (BGE retriever + mô tả intent do LLM sinh): Claude 3 Haiku avg F1 0.736, Mistral Large 0.735, SetFit 0.600; định tuyến sang LLM chỉ khi SetFit không chắc: trong ~2% F1 của LLM thuần, giảm ~50% latency. OOS recall thấp ở mọi model và giảm khi nhãn rộng, số nhãn lớn. — [Intent Detection in the Age of LLMs, 2024](https://arxiv.org/html/2410.01627v1)
- ICL nhiều nhãn: chỉ đưa các nhãn liên quan do retriever chọn. — [Milios et al., 2023](https://arxiv.org/pdf/2309.10954)

### Inferences
- ~40 nhãn của bạn nhỏ so với CLINC150 (150); lợi ích shortlist ít hơn, nhưng lỗi của bạn là giữa các nhãn lân cận, nên shortlist K=5–8 theo BM25/từ khoá/điểm log-prob của lượt 1 rồi cho định nghĩa tương phản chỉ cho cặp nằm trong shortlist là khả thi (tăng mật độ thông tin mà prompt không dài).
- Rủi ro: lượt 1 loại nhầm nhãn đúng khỏi shortlist (cần recall@K đo trên train, ≥ 98% mới dùng).

### Gaps
- Không có số đo cho hierarchical/shortlist classification ở ~40 nhãn với model ≤8B không huấn luyện; số liệu trên dùng bộ phân loại có huấn luyện (BERT/SetFit) đứng trước, không phải training-free.

## 5. Nhãn "không hỗ trợ / none of the above" cho model nhỏ không huấn luyện

### Takeaway
LLM nhìn chung yếu ở OOS (recall thấp), kém hơn khi nhiều nhãn; cách có bằng chứng: thu hẹp nhãn, mô tả nhãn rõ, nhãn UNK được định nghĩa tường minh, và kiểm tra bổ sung sau khi chọn nhãn (khoảng cách tới ví dụ của nhãn đó). Gate dựa trên độ chắc chắn là hướng khả thi ở bạn vì điểm bỏ trống = 0 rẻ hơn sai = −1.

### Cited Findings
- Tất cả model (kể cả LLM) có OOS recall kém (trung bình bảng 3: Mistral Large 0.641, Haiku 0.601, SetFit+NegAug 0.489); OOS tệ đi khi phạm vi nhãn rộng và nhiều nhãn. — [Intent Detection in the Age of LLMs, 2024](https://arxiv.org/html/2410.01627v1)
- Phương pháp hai bước (Mistral-7B): LLM chọn nhãn in-scope, rồi so biểu diễn nội bộ câu hỏi với ví dụ của nhãn đó; F1 0.699 → 0.751, 0.615 → 0.766, 0.384 → 0.739 trên 3 bộ; OOS recall 0.205 → 0.950 trên PowerPlay11; thêm ~300 ms trên V100. Cần ví dụ có nhãn (có sẵn ở bạn), không cần huấn luyện LLM. — cùng nguồn
- Prompt zero-shot có nhãn "UNK" định nghĩa tường minh cho OOS, đầu ra JSON, nhãn lấy từ danh sách động; Llama-3 70B vẫn rất kém OOS (F1-OOS 6.25 zero-shot trên MPGT), model suy luận mạnh hơn khá hơn. — [arXiv 2507.22289](https://arxiv.org/html/2507.22289v1)
- Template trắc nghiệm có lựa chọn "none of the above" cải thiện OOS cho Flan-T5-base (model nhỏ). — [ICL Markup, 2023](https://export.arxiv.org/pdf/2312.07405)
- Luận văn Llama-3.2-3B trên CLINC150: hỏi LLM thẳng nhãn luôn tệ nhất; embedding trích từ LLM cho accuracy và OOS tốt nhất. Nguồn luận văn, chưa kiểm tra sâu. — [Dimins thesis](https://theses.liacs.nl/pdf/2024-2025-DiminsMMatiss.pdf)

### Inferences
- Kết hợp: (1) thêm nhãn UNSUPPORTED có định nghĩa + vài ví dụ phản mẫu (sửa chữa, trả góp điện thoại → unsupported); (2) lấy log-prob nhãn đã chọn và khoảng cách BM25 tới ví dụ gần nhất của nhãn đó; nếu cả hai thấp → bỏ trống hoặc unsupported. Ngưỡng đặt từ train bằng leave-one-shop-out (để không học từ test).
- Ví dụ phản mẫu unsupported cần nằm trong kho ví dụ retrieval; câu loại này không có trong train nên cần tự viết, chú ý không hard-code theo shop.

### Gaps
- Không tìm được số CLINC150-OOS cho model 3–4B bằng prompt thuần có nhãn OOS; các số trên là model khác (Mistral-7B có thêm bước biểu diễn nội bộ, Flan-T5-base, LLM 70B).

## 6. Grounding filter bằng giá trị thật trong dữ liệu (value retrieval)

### Takeaway
Value retrieval/schema linking được báo là có ích trong text-to-SQL (CHESS ~5% cho cả module entity+context retrieval; schema linking tốt tiến gần schema vàng cho CodeS-15B), nhưng tôi không tìm được ablation tách riêng giá trị cho model nhỏ.

### Cited Findings
- CHESS: module entity and context retrieval (LSH tìm giá trị DB liên quan) đóng góp ~5% accuracy (cả module, không riêng value); schema selection ~2% và giảm token. Theo tóm tắt phụ. — [CHESS review](https://www.themoonlight.io/en/review/chess-contextual-harnessing-for-efficient-sql-synthesis), [arXiv 2405.16755](https://arxiv.org/pdf/2405.16755v1)
- CodeS-15B trên BIRD: schema gốc 58.47%, schema RTS 65.19%, schema vàng 66.27% (bảng chưa kiểm). — [LitE-SQL, 2025](https://arxiv.org/pdf/2510.09014)
- Trong LitE-SQL (model nhỏ), lợi ích chính đến từ SFT; schema retrieval thu hẹp không gian tìm kiếm sau khi đã huấn luyện. — cùng nguồn

### Inferences
- Với bài của bạn: model chỉ sinh JSON bộ lọc, nên lỗi "bịa filter" giảm nếu liệt kê giá trị thật (vd danh sách kênh bán, phương thức thanh toán, danh mục) của cột liên quan, và quy tắc "chỉ dùng filter khi câu hỏi nhắc đến một giá trị trong danh sách; nếu không, để null". Hậu kiểm bằng code (loại filter có giá trị không xuất hiện trong câu hỏi hoặc không có trong cột) rẻ hơn và an toàn hơn thêm prompt.
- Lỗi "đặt giá trị sai khoá": hậu xử lý bằng cách tra giá trị trong từ điển cột → gán khoá đúng (value→column map) thay vì tin model.

### Gaps
- Không có số tách riêng value retrieval cho model ≤8B; CHESS dùng LLM lớn.

## 7. Danh sách xếp hạng kỹ thuật (≤5), mỗi cái kèm thực nghiệm tối thiểu

### Takeaway
Ưu tiên theo (bằng chứng × độ phù hợp × độ rẻ): 1) retrieval few-shot BM25 có che entity + ngưỡng, 2) chấm log-prob nhãn (enum constrained) + gate bỏ trống, 3) hậu kiểm filter bằng giá trị thật, 4) shortlist hai lượt với định nghĩa tương phản, 5) CoT ngắn A/B. Toàn bộ chưa được kiểm trên đúng bài toán; đây là kết hợp bằng chứng + suy luận.

### Cited Findings
Xem các phần 1–6 cho bằng chứng; tóm tắt cho từng kỹ thuật:
1. **BM25 dynamic few-shot, che entity** (bằng chứng: DAIL-SQL masked > plain, GPT-4; BM25 ≥ BERT ở semantic parsing). Cài: tokenizer đơn giản (bỏ dấu + lower), che số/ngày/tên riêng bằng regex, BM25 (rank_bm25 hoặc tự cài ~30 dòng) trên ~3000 câu train, lấy k=6, kèm ví dụ phản mẫu unsupported; ngưỡng điểm. Thực nghiệm: train-leave-shop-out, so zero-shot vs k=0/4/8, đo accuracy từng nhãn + số câu sai→đúng/đúng→sai. Rủi ro: ví dụ gần nhưng nhãn khác kéo lệch; câu test xa phân phối. Giảm bằng ngưỡng, đa dạng nhãn.
2. **Log-prob scoring cho operation + gate**: lấy phân phối 40 nhãn, bỏ trống khi p(top1) − p(top2) nhỏ hoặc p thấp (ngưỡng từ train). Bằng chứng gián tiếp: constrained decode hữu ích cho phân loại (Tam et al., 2024); OOS recall thấp ở LLM nên cần gate. Thực nghiệm: đường cong coverage–accuracy trên shop giữ kín; mục tiêu: điểm = đúng − sai tối đa.
3. **Hậu kiểm filter bằng giá trị cột thật** (value→column map; xoá filter không có dấu vết trong câu hỏi). Bằng chứng gián tiếp (CHESS). Thực nghiệm: đo tỉ lệ filter bịa trước/sau.
4. **Shortlist 2 lượt + định nghĩa tương phản cặp lân cận** (bằng chứng: LSR 2025 với LLM 70B/BERT; chưa có số training-free ở 4B). Thực nghiệm: recall@K trước, rồi A/B.
5. **CoT ngắn/thinking A/B có giới hạn token** (bằng chứng nghiêng chống: Qwen3 sentiment, IFEval). Chỉ thử sau 1–4, đặt khoá lý do trước nhãn nếu dùng JSON.

### Inferences
- Ví dụ 1 và 2 dùng chung hạ tầng (logit scoring + retrieval) nên có thể gộp vào ~1 lần chạy GPU 2–3 cấu hình.
- Tránh nhồi cả 5 vào một lần: khó quy lỗi; nhưng ngân sách chạy ít, nên gộp 1+2 làm lần chạy 1, 3 là code thuần (không cần GPU), 4+5 lần chạy 2.

### Gaps
- Không có số đo nào trên đúng bài toán (4B Qwen, ~40 nhãn, tiếng Việt, shift phân phối); mọi gain định lượng là từ model/miền khác. Không tìm được bài viết của đội hàng đầu cho DABStep hoặc kỹ thuật đội mở trong SemEval-2025 Task 8 vượt quá mức mô tả tổng quan (chủ yếu sinh code + tự sửa).
