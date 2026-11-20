# Tái lập (reproducibility) của greedy LLM inference giữa các GPU / cấu hình phần mềm, và cách giảm lệch (tra cứu 16/11/2026)

Ghi chú chung: ngày của nguồn ghi bên cạnh từng link. Số liệu của các paper dưới đây đều là cho **sinh văn bản dài** (reasoning 2k–32k token, hoặc 1000 token), KHÔNG phải JSON 50–150 token; phần suy ra cho JSON ngắn nằm ở mục "Inferences" và được đánh dấu là suy luận. Một số paper 2026 chỉ đọc được abstract (PDF không trích được nội dung) — ghi rõ ở từng chỗ.

## 1. Mức lệch đo được của greedy decoding giữa GPU / precision / batch; tăng theo độ dài output thế nào; output ngắn có ổn định hơn không?

### Takeaway
Greedy (temperature 0) KHÔNG đảm bảo cùng output giữa GPU khác loại, batch khác, hay dtype khác; trên chuỗi dài (reasoning) gần như 100% mẫu lệch ở bf16, ít hơn ở fp16, và gần 0–7% ở fp32. Không tìm thấy paper nào đo trực tiếp tỉ lệ lật đáp án cho output JSON ngắn 50–150 token; phải ước lượng gián tiếp (xem Inferences).

### Cited Findings
- Yuan et al., "Understanding and Mitigating Numerical Sources of Nondeterminism in LLM Inference" (arXiv 2506.09501, v2 24/10/2025, NeurIPS 2025; tên cũ "Give Me FP32 or Give Me Death?"): đo bằng vLLM trên 4 model (DeepSeek-R1-Distill-Qwen-7B, Distill-Llama-8B, Qwen2.5-7B-Instruct, Llama-3.1-8B-Instruct), 12 cấu hình/cặp model-task (2 loại GPU × 2 số GPU × 3 batch size), max output 32.768 token (reasoning) hoặc 2.048 (non-reasoning). — [arXiv HTML v2](https://arxiv.org/html/2506.09501v2)
- Cùng paper, Table 9, tỉ lệ ví dụ greedy có output khác nhau giữa 12 cấu hình (bf16 / fp16 / fp32): AIME'24 DS-Qwen-7B 100 / 100 / 0 %; Qwen2.5-7B (non-reasoning) 100 / 73,33 / 6,67 %; Llama-3.1-8B 53,33 / 23,33 / 16,67 %; MATH500 DS-Qwen-7B 99,6 / 86,0 / 5,8 %; LiveCodeBench-Hard Llama-3.1-8B 100 / 58,54 / 7,32 %. Văn bản chính nói 2,2% cho MATH500 fp32 nhưng bảng ghi 5,80% (paper không giải thích mâu thuẫn). — [arXiv HTML v2](https://arxiv.org/html/2506.09501v2)
- Cùng paper: độ lệch accuracy (Std@Acc) trên AIME'24 DS-Qwen-7B: 9,15% (bf16), 5,74% (fp16), 0 (fp32); lệch độ dài output tới ~9.000 token giữa cấu hình. Trong backend HF Transformers (AIME'24): Qwen2.5-7B Std@Acc 2,23% (bf16) so với 0 (fp32). — [arXiv HTML v2](https://arxiv.org/html/2506.09501v2)
- Cùng paper: fp32 "gấp đôi bộ nhớ và thời gian so với bf16"; LayerCast (lưu weight 16-bit, tính toán fp32) giảm ~34% bộ nhớ so với fp32 đầy đủ và cho divergence < 3,4%, Std@Acc 0 trên AIME'24 DS-Qwen-7B; thời gian chạy LayerCast không được định lượng trong phần đọc được. — [arXiv HTML v2](https://arxiv.org/html/2506.09501v2)
- Thinking Machines (He, 10/09/2025): Qwen3-235B-A22B, temp 0, 1.000 lần sinh × 1.000 token cùng một prompt → 80 output khác nhau; **100 token đầu giống hệt nhau**, lệch đầu tiên ở token 103 (992 lần "Queens, New York" vs 8 lần "New York City"). Với kernel batch-invariant, cả 1.000 đầu ra giống hệt. — [Thinking Machines](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/)
- Cùng bài: với cùng batch/cấu hình, forward pass gần như không có atomic add nên chạy lại cho kết quả bitwise giống hệt; nguồn bất định là batch size thay đổi theo tải. Đo trên Qwen-3-8B, 1 GPU, 1.000 chuỗi, 90–110 token output: vLLM mặc định 26 s; deterministic chưa tối ưu 55 s; có kernel attention cải tiến 42 s (≈1,6× chậm hơn). — [Thinking Machines](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/)
- Du et al., "Greedy Decoding Is Not Precision-Invariant" (arXiv 2609.26621, 22/09/2026, TMLR 2026; chỉ đọc được abstract): 6 model 1,1B–7B, 3 benchmark; chỉ đổi bf16 ↔ fp16 trên cùng phần cứng đã làm 49–100% prompt diverge, một lần lật token thường kéo lệch cả quỹ đạo. — [arXiv abs](https://arxiv.org/abs/2609.26621)
- Cooper et al., "Accelerating the Mitigation of LLM Inference Nondeterminism Across GPU Architectures" (arXiv 2609.25624, 22/09/2026; chỉ đọc được abstract): cùng model/prompt/stack vẫn cho kết quả khác giữa GPU vì kernel GEMM chọn khác (thứ tự reduction, tensor-core khác nhau). Đề xuất fused-upcast GEMM (weight 16-bit, nâng lên fp32 trong register, thứ tự cộng cố định theo shape) → output linear layer giống bitwise giữa Ampere/Ada/Hopper (chưa nói Blackwell), nhanh hơn giải pháp SOTA 1,17–3,1×. — [arXiv abs](https://arxiv.org/abs/2609.25624)
- Báo cáo từ cộng đồng: batch=1 vs batch lớn (có left padding) cho kết quả khác trong HF generate (Llama-2, Mistral, BLIP2…); bug masking với hàng bị pad (NaN do hàng bị mask hoàn toàn, Gemma). Đây là các issue/thread lẻ, không phải đo hệ thống. — [HF forum](https://discuss.huggingface.co/t/results-of-model-generate-are-different-for-different-batch-sizes-of-the-decode-only-model/34878), [HF discussion Gemma](https://huggingface.co/google/gemma-4-12B-it/discussions/50)

### Inferences
- (Suy luận) Vì lệch đầu tiên thường xuất hiện sau vài chục–hàng trăm token (ví dụ token 103 ở Thinking Machines) và xác suất lật tích luỹ theo số vị trí, JSON 50–150 token ít cơ hội lệch hơn nhiều so với reasoning hàng nghìn token. Hơn nữa JSON có cấu trúc (khoá, dấu ngoặc) chiếm phần lớn token với margin rất lớn; chỉ vài token "nội dung" (con số, nhãn, lựa chọn) là có thể lật. Nhưng một lần lật ở token nội dung đổi đáp án luôn, nên lệch không "nhẹ" như văn bản tự do.
- (Suy luận) Quan sát của đội: 3/1000 khác giữa hai lần chạy cùng T4 (nhiều khả năng do batch/padding khác nhau hoặc kernel autotune chứ không phải nhiễu ngẫu nhiên thuần, vì cùng cấu hình thì bitwise giống hệt theo Thinking Machines) cho thấy mức nền ~0,3%. Đổi sang kiến trúc GPU khác (T4 sm_75 → 5090 sm_120, kernel/tensor-core hoàn toàn khác) hợp lý sẽ cao hơn mức nền này; ngân sách 0,03 (15 câu đổi đúng/sai ròng = 30 lần lật nếu lật 1 chiều, chỉ cần ròng 15) là rộng so với 0,3% nhưng chưa thể khẳng định không đo trên 5090. Lưu ý chỉ lật giữa đúng/sai mới tính, và lật hai chiều bù trừ nhau.

### Gaps
- Không tìm thấy số đo trực tiếp "tỉ lệ đáp án lật cho output ≤150 token, cross-GPU, model 4B fp16". Cần tự đo (mục 5).
- Hai paper tháng 9/2026 chỉ có abstract; chưa kiểm được số liệu chi tiết (Div_Index theo độ dài, margin) của chúng.
- Chưa có dữ liệu cross-GPU giữa Turing (T4) và Blackwell trong tài liệu tìm được (paper 2609.25624 nói Ampere/Ada/Hopper).

## 2. Nguyên nhân và biện pháp trong PyTorch/transformers (batch/padding, cudnn/deterministic, TF32, SDPA vs eager, fp16/bf16/fp32, KV-cache, torch.compile, device_map)

### Takeaway
Nguồn lệch chính là thứ tự cộng (reduction order) và lựa chọn kernel phụ thuộc shape/GPU; các cờ `cudnn.deterministic`/`use_deterministic_algorithms` chủ yếu xử lý atomic/run-to-run chứ không làm kernel giống nhau giữa các kiến trúc GPU. Biện pháp có bằng chứng mạnh nhất: tính toán (accumulate) ở fp32 và cố định batch (batch=1 hoặc cùng cấu hình), cộng recompute LM head fp32 khi margin nhỏ.

### Cited Findings
- Tài liệu PyTorch: "Completely reproducible results are not guaranteed across PyTorch releases, individual commits, or different platforms"; kết quả có thể khác giữa CPU và GPU kể cả cùng seed. `cudnn.deterministic=True` chỉ kiểm soát thuật toán conv của cuDNN; `torch.use_deterministic_algorithms()` bao quát rộng hơn (lỗi nếu op không có bản deterministic), thường chậm hơn; `cudnn.benchmark=False` làm cuDNN chọn thuật toán xác định. (Trang đã đọc không nhắc `CUBLAS_WORKSPACE_CONFIG`.) — [PyTorch docs randomness (bản 2.15)](https://docs.pytorch.org/docs/2.15/notes/randomness.html)
- Nguyên nhân gốc: phép cộng dấu phẩy động không kết hợp; thứ tự reduction khác nhau giữa GPU, số GPU, tensor-parallel size, kernel selection. — [arXiv 2506.09501v2](https://arxiv.org/html/2506.09501v2), [arXiv 2609.25624](https://arxiv.org/abs/2609.25624)
- Thinking Machines: các op làm mất batch invariance là matmul (split-K khi batch nhỏ, đổi lệnh tensor-core), attention split-KV (FlashDecoding) và RMSNorm split-reduction; pointwise op không vấn đề. — [Thinking Machines](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/)
- fp16 ổn định hơn bf16 rõ rệt trong mọi bảng của 2506.09501 (ví dụ MATH500 DS-Qwen-7B diverge 86% fp16 vs 99,6% bf16; Std@Acc 5,74% vs 9,15%) vì fp16 có 10 bit mantissa so với 7 của bf16; fp32 gần như tái lập. Ghi chú: 2506.09501 đo bằng vLLM; thử nghiệm HF Transformers chỉ báo ở mức Std@Acc. — [arXiv 2506.09501v2](https://arxiv.org/html/2506.09501v2)
- Kết quả trái chiều trong 2609.26621 (abstract): dự đoán và xác nhận rằng "thêm tính toán FP32 khiến sự đồng thuận ở một số kiểu so sánh (cross-precision) tệ hơn" — tức nếu so một bản fp32 với bản fp16 thì không hội tụ; chỉ so sánh trong cùng một cấu hình mới có lợi. Cách sửa tốt nhất họ thử: tính lại LM head ở fp32 khi margin top-2 dưới ngưỡng, tăng khớp chính xác +22–36 điểm % trên A10G và +12–21 pp trên L4 và A100, thêm < 4% độ trễ ở batch ≤ 4; hiệu quả mất khi batch ≥ 8 hoặc FP8. — [arXiv abs 2609.26621](https://arxiv.org/abs/2609.26621)
- Bug cuBLASLt trên sm_120 liên quan TF32 split-K (nvjet_sm120 …tf32…splitK) gây illegal access/treo GPU với tải GEMM kéo dài; workaround `NVIDIA_TF32_OVERRIDE=0` (báo cáo 10/06/2026, laptop 5090, CUDA 13.3/driver 595; NVIDIA chưa có bản sửa tại 17/07/2026). Điều kiện là FP32 GEMM (không phải fp16), cho thấy TF32 là cờ cần tắt có chủ đích. — [NVIDIA forum](https://forums.developer.nvidia.com/t/cublaslt-sm-120-blackwell-tf32-split-k-nvjet-kernel-raises-warp-barrier-arrival-mismatch-intermittent-illegal-access-gpu-hang-rtx-5090/372787)
- Cộng đồng: batch=1 loại bỏ nhu cầu padding và triệt tiêu một lớp khác biệt; luôn đặt `padding_side="left"` + attention_mask; so sánh với phiên bản transformers vì hành vi đổi giữa các bản. — [HF forum](https://discuss.huggingface.co/t/results-of-model-generate-are-different-for-different-batch-sizes-of-the-decode-only-model/34878)

### Inferences
(Tất cả là khuyến nghị/suy luận, chưa có số đo cho đúng cấu hình này; chi phí là ước lượng.)
Checklist xếp hạng theo (khả năng giảm lệch) / (chi phí):
1. **Cố định batch: batch=1 hoặc luôn cùng một batch size và cùng cách sắp xếp/pad** (xếp câu theo độ dài cố định, không phụ thuộc tải). Nguồn: Thinking Machines (nguồn bất định lớn nhất là thay đổi batch), cộng đồng HF. Chi phí: batch=1 chậm hơn vài lần nhưng với 1000 câu × ~100 token trên 4B và 6 giờ thì khả thi; kiểm tra thời gian trên T4 trước. Đây là biện pháp rẻ và chắc nhất; lưu ý 2609.26621 cho thấy lợi ích của LM-head fp32 mất khi batch ≥ 8 vì lỗi từ thân model áp đảo.
2. **LM head (và logits) tính ở fp32** — `lm_head` cast sang float32 hoặc `logits.float()` trước argmax; ưu tiên bản có điều kiện (chỉ tính lại khi margin nhỏ). Bằng chứng: 2609.26621 (+12–36 pp khớp, <4% overhead ở batch ≤4). Chi phí: lm_head của model vocab ~150k × hidden 2560 ≈ 0,4B tham số, fp32 ≈ 1,5 GB — rẻ trên card 32 GB. Lưu ý chỉ sửa được lỗi phát sinh ở bước cuối, không sửa sai lệch tích luỹ trong 36 lớp.
3. **Tắt TF32**: `torch.backends.cuda.matmul.allow_tf32=False`, `torch.backends.cudnn.allow_tf32=False` (và `NVIDIA_TF32_OVERRIDE=0` nếu cần). Với fp16 thuần, TF32 gần như không tham gia, nhưng tắt giúp mọi phép fp32 (LM head, norm) giống nhau giữa T4 (không có TF32) và 5090 (có TF32) — T4 không hỗ trợ TF32, nên nếu để mặc định (matmul TF32 mặc định tắt trong PyTorch, cudnn mặc định bật) hai bên sẽ khác. Chi phí gần 0.
4. **Attention cố định**: dùng cùng một implementation trên cả hai nơi (`attn_implementation="eager"` hoặc `"sdpa"` ép một backend toán học, `torch.nn.attention.sdpa_kernel(SDPBackend.MATH)`), không để SDPA tự chọn flash/mem-efficient/cudnn khác nhau theo GPU (T4 sm_75 không có flash của FA2, 5090 có). Eager/MATH chậm và tốn bộ nhớ hơn nhưng với prompt dài vài nghìn token trên 4B vẫn ổn. Chưa có số đo cho trường hợp này; cần tự đo thời gian.
5. **Accumulate fp32 cho cả thân model (fp32 đầy đủ hoặc kiểu LayerCast)**: bằng chứng mạnh nhất (2506.09501: divergence 100% → 0–7% trên chuỗi dài). Chi phí: 4B fp32 ≈ 16 GB weight (vừa card 32 GB 5090, KHÔNG vừa T4 16 GB nếu kèm KV-cache/activation → T4 phải offload hoặc không dùng được), thời gian ≈ gấp đôi bf16 theo paper. Rủi ro: nếu đội nộp kết quả sinh ở T4 fp16 còn máy chấm chạy fp32 thì không giúp gì — mọi biện pháp phải giống nhau ở cả hai nơi. Vì vậy chỉ khả thi nếu cả hai bên cùng chạy được cấu hình đó.
6. **Cờ determinism của PyTorch** (`torch.use_deterministic_algorithms(True)`, `CUBLAS_WORKSPACE_CONFIG=:4096:8`, `cudnn.deterministic=True`, `cudnn.benchmark=False`): giúp run-to-run cùng máy (ví dụ 3/1000 chênh trên T4), nhưng theo tài liệu PyTorch không đảm bảo giữa nền tảng khác nhau. Rẻ; nên bật nhưng đừng kỳ vọng nó đóng cross-GPU. (Suy luận: `CUBLAS_WORKSPACE_CONFIG` là biến chuẩn cho deterministic cuBLAS — kiến thức nền, không phải từ trang đã fetch.)
7. **`torch.compile`**: thêm một nguồn khác biệt (fusion, autotune khác nhau theo GPU); không tìm thấy bằng chứng đo; khuyến nghị tránh. Không tìm thấy nguồn riêng cho KV-cache on/off và `device_map` splitting; với một process/một GPU và model 4B không cần chia device_map (chia tầng giữa GPU không đổi thứ tự reduction trong từng GEMM nhưng đưa thêm bước chuyển dtype/thiết bị — suy luận, không có nguồn).

### Gaps
- Không có nguồn đo riêng cho: torch.compile, KV-cache on/off, device_map, SDPA backend khác nhau → cross-GPU; không có số đo "fp32 logits đơn thuần giảm bao nhiêu lật giữa T4 và 5090" cho model 4B (chỉ có kết quả của 2609.26621 trên A10G/L4/A100 với model 1,1–7B, nguồn chỉ đọc abstract).
- Không xác minh được 2609.26621 chạy trên HF Transformers hay vLLM.

## 3. Near-tie: lật phần lớn do top-2 sát nhau? Có thủ thuật làm decoding bền?

### Takeaway
Có bằng chứng rằng lật xảy ra khi nhiễu số lớn hơn khoảng cách top-1/top-2 logit; tỉ lệ vị trí gần hoà nhỏ nhưng khác 0 và tỉ lệ rủi ro tỉ lệ tuyến tính với mức nhiễu. Thủ thuật đã công bố: tính lại LM head ở fp32 khi margin < ngưỡng.

### Cited Findings
- 2609.26621 (22/09/2026, abstract): kết quả phụ thuộc chủ yếu vào margin top-2 tại LM head so với nhiễu giữa hai ứng viên đó, không phải vào lỗi tích luỹ qua 22 lớp; thủ thuật có điều kiện (recompute LM head fp32 khi margin dưới ngưỡng) tăng khớp +12–36 pp với <4% overhead ở batch ≤ 4. — [arXiv abs](https://arxiv.org/abs/2609.26621)
- Ví dụ từ 2506.09501: tại điểm lệch (bf16), "know" 49,75% vs "have" 46,65% (khoảng cách ~3,1 điểm xác suất); paper nói khoảng cách "thường rất nhỏ ở reasoning model" nhưng không đưa phân phối tổng hợp. — [arXiv HTML v2](https://arxiv.org/html/2506.09501v2)
- Một tổng hợp qua search (không đọc trực tiếp được nguồn gốc con số) nói: khoảng 1% vị trí nằm trong 0,1 nat của hoà, phần vị trí bị lộ tăng gần tuyến tính theo mức nhiễu. Chưa xác minh được ở paper gốc → độ tin cậy thấp. — kết quả WebSearch, liên quan [arXiv 2609.26621](https://arxiv.org/pdf/2609.26621)
- Giải pháp ở tầng kernel: fused-upcast GEMM thứ tự cộng cố định → loại bỏ nguồn nhiễu thay vì né near-tie. — [arXiv 2609.25624](https://arxiv.org/abs/2609.25624)

### Inferences
- (Suy luận) Rằng "phần lớn lật cross-hardware đến từ near-tie" nhất quán với cơ chế (lật cần nhiễu > margin) và với abstract 2609.26621, nhưng chưa thấy thống kê "x% lật có margin < ε". Vì vậy cách đo trực tiếp ở mục 5 là cần thiết.
- (Suy luận, chưa có nguồn công bố cho việc này) Với đầu ra có thể chấp nhận bỏ trống (0 điểm thay vì -1): đáp án có margin top-2 nhỏ ở token nội dung (số/nhãn) có thể chuyển thành "bỏ trống" — vì kỳ vọng điểm của câu gần hoà ≈ 0 so với sai −1, nên bỏ trống không thua. Đây là ý tưởng margin-aware phù hợp với luật chấm; không tìm thấy paper "rounding logits" cho mục đích này. Làm tròn logit thô sẽ chỉ chuyển ranh giới lật chứ không loại bỏ.

### Gaps
- Không tìm thấy nghiên cứu công bố về "rounding logits" hoặc margin-aware greedy để chống lật cross-hardware ngoài LM-head recompute.
- Không có phân phối margin đo trực tiếp (nguồn 1%/0,1 nat chưa xác minh).

## 4. RTX 50-series (Blackwell sm_120): phiên bản tối thiểu và rủi ro khi nạp

### Takeaway
PyTorch ≥ 2.7.0 với wheel cu128 có sm_120; ảnh Docker pytorch 2.7.1 + CUDA 12.8 là phiên bản tối thiểu hợp lệ. Rủi ro nằm ở các thư viện biên dịch sẵn bên ngoài PyTorch (flash-attn, bitsandbytes, triton kernel, llama.cpp…), driver cũ, và các bug sm_120 mới ở cuBLASLt.

### Cited Findings
- Bản wheel đầu tiên có sm_120 trong arch list: `2.7.0.dev20250131+cu128` (nightly, 31/01/2025); nightly cu128 cài được từ 01/02/2025; wheel Windows từ 20/02/2025; từ nguồn thì sm_100/sm_120 đã được hỗ trợ. Thread không nêu driver tối thiểu. — [PyTorch forum](https://discuss.pytorch.org/t/pytorch-support-for-sm120/216099)
- PyTorch 2.7.0 là bản stable đầu tiên có sm_120 gốc với wheel CUDA 12.8 (kèm cuDNN, NCCL, Triton 3.3 cập nhật) — nguồn là tài liệu bên thứ ba (Salad) nên độ tin cậy trung bình. Thông báo "sm_120 is not compatible with the current PyTorch installation" xuất hiện khi cài bản cũ; kiểm tra bằng `torch.cuda.get_arch_list()` phải có `sm_120`. Có người báo CUDA 12.9 hệ thống vẫn lỗi với "PyTorch 2.7" (nguyên nhân không xác nhận trong thread — thường do wheel không phải cu128). — [Salad docs](https://docs.salad.com/container-engine/tutorials/machine-learning/pytorch-rtx5090.md), [PyTorch forum](https://discuss.pytorch.org/t/pytorch-support-for-sm120/216099?page=5)
- flash-attn 2.x: build từ nguồn cho sm_120 từng lỗi nvcc ở kernel backward (issue Dao-AILab/flash-attention, ngày không rõ); FA4 trên sm_120 từng ra output sai do mapping register theo kiểu SM80 (blog, có patch). SDPA tích hợp của PyTorch được báo là chạy được trên sm_120. — [FA issue](https://github.com/Dao-AILab/flash-attention/issues/1987), [FA4 sm120 blog](https://sorryhyunblog.vercel.app/posts/flash-attention-4-sm120)
- cuBLASLt TF32 split-K trên sm_120 gây illegal access / treo GPU (06/2026, CUDA 13.3, driver 595); workaround `NVIDIA_TF32_OVERRIDE=0`. Báo cáo trên bản laptop và stack CUDA 13, chưa có thông tin cho CUDA 12.8/torch 2.7.1. — [NVIDIA forum](https://forums.developer.nvidia.com/t/cublaslt-sm-120-blackwell-tf32-split-k-nvjet-kernel-raises-warp-barrier-arrival-mismatch-intermittent-illegal-access-gpu-hang-rtx-5090/372787)
- Các lỗi sm_120 ở stack khác (MLX mxfp4 lệch CPU, FlashInfer CUTLASS grouped GEMM garbage output) — liên quan nếu dùng các thư viện đó, không áp dụng cho PyTorch thuần. — kết quả WebSearch (mlx issue, flashinfer issue 2723)

### Inferences
Checklist kiểm tra khi container chạm 5090 lần đầu (khuyến nghị):
- Đầu `predict`: in `torch.__version__`, `torch.version.cuda`, `torch.cuda.get_arch_list()` (cần có `sm_120` hoặc `compute_120` để PTX JIT) và `torch.cuda.get_device_capability()`; fail-fast nếu không khớp.
- Không đóng gói wheel torch cũ/cu121/cu124 song song; đảm bảo không có gói nào kéo torch khác (pip dependency downgrade).
- Tránh gói có kernel biên dịch sẵn không có sm_120 (flash-attn, xformers, bitsandbytes cũ, auto-gptq/awq kernels, causal-conv1d, flash-linear-attention với Triton cũ). Nếu Qwen kiểu mới cần các kernel đó (ví dụ phần linear-attention), kiểm tra đường fallback thuần PyTorch có chạy cùng kết quả không. Triton 3.3 đi kèm 2.7 hỗ trợ Blackwell theo tài liệu bên thứ ba.
- Driver: CUDA 12.8 cần driver đủ mới (theo hiểu biết nền, khoảng ≥ 570; không xác minh được trong lần tra cứu này). Máy chấm có driver do BTC quyết định; ảnh không mang theo driver được → chạy `nvidia-smi` và xem thông báo `CUDA driver version is insufficient`.
- Lỗi JIT: nếu arch list thiếu sm_120, PyTorch sẽ cảnh báo "not compatible" hoặc lỗi "no kernel image is available"; đặt `CUDA_LAUNCH_BLOCKING` chỉ để debug. Cache kernel/triton/inductor có thể ghi vào thư mục không ghi được khi `/data` chỉ đọc → đặt `TRITON_CACHE_DIR`, `TORCH_HOME`, `HF_HOME` về nơi ghi được và `HF_HUB_OFFLINE=1`.
- Tắt TF32 (xem mục 2) cũng tránh nhánh kernel cuBLASLt TF32 split-K có bug trên sm_120.
- 2× 5090 mỗi process một GPU: dùng `CUDA_VISIBLE_DEVICES` cho từng process; kiểm tra không có P2P/NCCL (không cần với one-process-per-GPU).

### Gaps
- Không tìm thấy bug riêng của fp16 trên sm_120 với PyTorch SDPA/transformers (kết quả tìm kiếm: không có), nhưng không đồng nghĩa là không tồn tại.
- Không xác minh được driver tối thiểu cho CUDA 12.8 và issue riêng của torch 2.7.1 (so với 2.7.0) trong lần tra cứu này.
- Ngày chính xác phát hành 2.7.0 stable không có trong nguồn đã đọc (chỉ có dữ liệu nightly 2025).

## 5. Tự kiểm tra khi không có phần cứng đích

### Takeaway
Không có tự kiểm tra nào thay được chạy thật trên 5090, nhưng có thể ước lượng "số câu có nguy cơ" bằng (a) so sánh nhiều cấu hình ngay trên T4, (b) đếm margin top-2 nhỏ, (c) chạy thử trên 5090 qua cloud trong thời gian ngắn nếu có.

### Cited Findings
- Cơ chế lật = nhiễu > margin top-2, đo được từ log-prob top-k lưu lại — [arXiv abs 2609.26621](https://arxiv.org/abs/2609.26621) (nội dung chi tiết chưa đọc được).
- Phương pháp so sánh dùng trong nghiên cứu: chạy cùng dữ liệu qua nhiều cấu hình (GPU, số GPU, batch size) rồi đếm tỉ lệ mẫu khác và Std@Acc — [arXiv 2506.09501v2](https://arxiv.org/html/2506.09501v2).
- Run lặp cùng cấu hình cho kết quả bitwise giống (nếu batch không đổi) — [Thinking Machines](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/); do đó 3/1000 chênh ở hai lần chạy T4 là tín hiệu rằng batch/padding/tải khác giữa các lần chạy (cần kiểm tra).

### Inferences
Quy trình đề xuất (khuyến nghị, chưa kiểm chứng trên dữ liệu này):
1. **Chạy lặp 2× cùng cấu hình, bật deterministic** — nếu vẫn lệch, tìm nguồn (batch composition, autotune, thread order); mục tiêu 0 lệch.
2. **Chạy với batch=1 vs batch hiện tại; fp16 vs bf16; eager vs sdpa; lm_head fp32 vs fp16** và diff theo đáp án cuối (không phải text). Số câu đổi đáp án giữa các cấu hình = ước lượng dưới của lệch cross-GPU (T4↔5090 khác kiến trúc nên có thể lớn hơn).
3. **Lưu top-5 logprob tại mọi token nội dung** (trong lúc sinh: `output_scores=True`, `return_dict_in_generate=True`) và tính margin top-1−top-2 nhỏ nhất theo từng câu (chỉ ở token nằm trong giá trị đáp án, bỏ khoá JSON). Đếm số câu có margin < ε (ví dụ 0,05, 0,1, 0,25 nat); đồng thời đếm trong số câu lật ở bước 2 phần có margin nhỏ để hiệu chuẩn ε. Số câu có margin < ε × (xác suất lật theo hiệu chuẩn) = ước lượng số câu rủi ro; so với ngân sách 15 câu ròng (lưu ý: chỉ lật đúng↔sai mới tính điểm, lật hai chiều bù trừ).
4. **Nhiễu nhân tạo**: cộng nhiễu tương đối ~1e-3 (fp16 epsilon ≈ 9,8e-4) vào logits và đếm số argmax đổi — ước lượng nhanh độ nhạy không cần GPU khác.
5. **Thuê tạm 5090** (cloud theo giờ) chạy cùng container đúng 1 lần, vài chục phút cho 1000 câu × ~100 token model 4B — là cách duy nhất cho số đo thật và cũng kiểm tra luôn các rủi ro nạp ở mục 4.
6. Quyết định chính sách: nếu margin thấp ở token nội dung → cân nhắc bỏ trống (0 điểm) thay vì đáp án (kỳ vọng ~0 so với −1), khớp luật chấm.

### Gaps
- Không có nguồn công bố cho từng bước của quy trình trên (đây là thiết kế của người tổng hợp dựa trên cơ chế đã nêu); ngưỡng ε phải hiệu chuẩn bằng số liệu thực.
- Chưa đọc được phần phương pháp/đo margin của 2609.26621 (PDF không trích được văn bản, HTML 404).
