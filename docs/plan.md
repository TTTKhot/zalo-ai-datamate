# Kế hoạch: "đường rulebook" — đọc rulebook của bộ dữ liệu lúc chạy

Ngày viết: 2026-11-14. Người viết: planner. Người thực thi: phiên Claude chính. Chỉ là thiết kế, chưa sửa code.

Ràng buộc đã giữ khi viết kế hoạch này:
- Không mở câu hỏi, log hay lỗi từng câu của 6 shop giữ kín (biz_104, 106, 110, 114, 119, 126). Mọi số đo dưới đây
  lấy từ 24 shop còn lại.
- Public test: chỉ đọc `public_test/public_test/rulebook.md` để biết rulebook đổi THEO KIỂU GÌ. Không đọc
  `questions.jsonl` hay `data/` của public. Không thiết kế gì riêng cho một định nghĩa cụ thể của rulebook public.

---

## 0. Tóm tắt cho người đọc vội

1. **Nên làm, nhưng làm theo 3 nấc, nấc sau chỉ giữ khi có số đo.**
   - Nấc 1 (CPU, chắc ăn): đọc rulebook lúc chạy, so với rulebook train, và dựng **cổng** phát hiện "câu hỏi dùng một
     định nghĩa mà thư viện metric không có / đã bị đổi". Câu bị cổng bắt mà không có đường nào trả lời chắc thì
     **bỏ trống** thay vì để đường metric đoán sai (−1 → 0).
   - Nấc 2 (cần GPU để đo): với câu bị cổng bắt, Qwen viết SQL với **vài dòng rulebook liên quan** trong prompt
     (không phải nguyên rulebook), 2 bản nháp, chỉ trả lời khi 2 bản trùng nhau.
   - Nấc 3 (cần GPU, rủi ro cao nhất): cho đường này truy vấn **bảng thô đã làm sạch** của `sqlvote/clean.py` để
     trả lời câu về bảng/cột chưa gán vai (ngành mới).
2. **Số đo quyết định cách thiết kế** (lần 6, 17 shop không giữ kín có log tải về, 164 câu): đường SQL hiện tại đứng
   một mình chỉ đúng 73, sai 61, không ra kết quả 30 (đúng 54% số câu có kết quả), trong khi đường metric đúng 147/164.
   Tức là Qwen 4B viết SQL tự do **không đủ tin để trả lời một mình** với luật chấm +1/−1. Vì vậy đường rulebook
   không bao giờ thay đường metric ở câu thư viện đã có; nó chỉ chạy ở câu cổng bắt, và phải qua bước "2 bản trùng".
3. **Bằng chứng rằng đưa dòng luật vào prompt có ích:** `cancel_rate` — luật "mẫu số là mọi đơn, mọi trạng thái"
   không có trong `sqlpath.RULES` → SQL sai 11/11 câu có kết quả. Đây là phép thử "ẩn luật" tự nhiên đã có sẵn.
4. **Một lần chạy Kaggle, ước 4,5–5,5 giờ** (mục 7), không train LoRA trong lần này.
5. **Phương án lùi không cần GPU thêm:** chỉ giữ nấc 1 (cổng + bỏ trống).
6. **Cần người dùng xác nhận trước khi bắt đầu:** hạn nộp. `docs/sqlvote_goi_y.md` ghi "hạn đóng băng 23:59 16/11";
   `docs/tong_ket_cho_fable.md` để trống. Nếu hạn đúng là 16/11 thì chỉ đủ thời gian cho nấc 1 + nấc 2 và MỘT lần
   chạy GPU; nấc 3 chỉ làm nếu nấc 1–2 xong trước tối 15/11.

---

## 1. Chẩn đoán

### 1.1 Rulebook đổi theo kiểu gì giữa các bộ (đo bằng script tách dòng, mục 9)
| | Train | Public |
|---|---|---|
| Số "mục luật" (một dòng bảng hoặc một gạch đầu dòng) | 79 | 101 |
| Ký tự cả file | 14.650 | 18.799 |
| Mục mới | — | 25 (§3 xếp hạng +7, §6 ngành +14 trong đó 3 ngành mới, còn lại rải ở §1, §2, §5, §8) |
| Mục bị bỏ | — | 3: "Tồn theo đơn vị lớn", "Giá nhập bình quân…", "Giá bán X ngày D" |
| Mục giữ tên nhưng đổi nội dung | — | 3, cả ba đều là **thêm câu làm rõ**, câu cũ còn nguyên |

Bốn kiểu thay đổi cần xử lý (đây là thứ được phép học từ rulebook public, không phải nội dung từng luật):
- **K1 — thuật ngữ mới có định nghĩa**: tên luật là cụm từ người hỏi sẽ dùng, thân luật là công thức.
- **K2 — ngành mới**: mục con `### <ngành>` với thực thể mới (một dòng sổ = một lượt/phiếu), cột mới, bảng mới.
- **K3 — luật cũ được thêm câu** (bổ sung) hoặc, ở bộ khác, có thể bị sửa tham số.
- **K4 — luật cũ bị bỏ**.
Định dạng không đổi: tiêu đề `## N. Tên mục`, mục con `###`, bảng 2 cột, thuật ngữ in đậm `**…**`, tham chiếu `§N`.

### 1.2 Hệ thống hiện tại làm gì với các kiểu đó
- `datamate/` không đọc `rulebook.md` (đã grep: không có chỗ nào mở file này). Mọi định nghĩa nằm trong
  `metrics.py`, `rules.py`, `periods.py`, `slots.py` và chuỗi `sqlpath.RULES`.
- K1: prompt ý định chỉ liệt kê metric có sẵn (`intent.METRIC_DOC`), nên một thuật ngữ mới kiểu "khách … nhất" sẽ bị
  ép vào metric gần nhất (`top_customers` theo doanh thu) và **trả lời sai có hệ thống (−1)**. Không có cơ chế nào
  biết rằng câu hỏi đang dùng một định nghĩa lạ.
- K2: 7 view chuẩn (`sqlpath.TABLES`) không chứa bảng không gán vai; đường SQL chỉ thấy view chuẩn.
- K3/K4: hằng số viết cứng (giờ ca, cửa sổ Tết, đầu tuần…) không đổi theo rulebook.

### 1.3 Qwen 4B viết SQL tốt tới đâu (lần 6, `runs/20261114-0608/state/run_v5_sql/logs`, 17 shop không giữ kín, 164 câu)
| | SQL đúng | SQL sai | SQL không có kết quả |
|---|---|---|---|
| Đường metric đúng (147) | 67 | 55 | 25 |
| Đường metric sai (13) | 2 | 6 | 5 |
| Đường metric bỏ trống (4) | 4 | 0 | 0 |

Theo metric (đúng/sai/không): revenue 34/21/15 · quantity 11/4/4 · avg_order_value 11/2/0 · **cancel_rate 0/11/2** ·
order_count 6/1/1 · best_day 1/4/2 · unit_price 2/3/1 · top_customers 0/3/0.
Thời gian mỗi câu (cả hai đường): trung vị 17,9 giây, p90 36,9 giây.

Đọc số này thế nào:
- SQL một mình: 73 − 61 = +12 điểm trên 164 câu. Dùng nó thay đường metric là mất điểm nặng.
- Lỗi SQL chia hai loại: (a) thiếu luật (cancel_rate: 0 đúng), (b) sai hình dạng đáp án (hỏi "ngày nào" mà trả
  `MAX(line_total)`). Loại (a) là thứ đường rulebook chữa được; loại (b) cần gợi ý kiểu đáp án và ví dụ trong prompt.
- Lưu ý: log tải về của lần 6 chỉ có 17/24 shop (biz_122 chỉ 4 câu, biz_123–130 thiếu) → 164 câu, không phải 240.

### 1.4 Truy hồi dòng luật bằng từ khoá có đủ không (thử nhanh trên CPU, 2.388 câu của 24 shop)
Cách thử: tách rulebook train thành mục; chấm điểm IDF trên từ + cặp từ không dấu (tên luật nhân 3); nhãn "dòng luật
đúng" suy từ metric của `scripted_intent`. Kết quả: r@1 = 0,59 · r@3 = 0,81 · r@5 = 0,87.
- Tốt khi câu hỏi dùng đúng thuật ngữ: giá nhập bình quân 1,00 · mặt hàng ế 0,81/0,96 · hiệu ứng tăng giá r@3 1,00.
- Kém khi câu hỏi nói kiểu khác: "số đơn" hỏi thành "mấy bill" (r@5 0,34); "khách mua nhiều nhất" (r@1 0,28).
Kết luận: từ khoá đủ để **đưa 6–8 dòng ứng viên vào prompt** (mỗi mục luật trung vị chỉ 153 ký tự, dài nhất 420), nhưng
chưa đủ để **một mình quyết định định tuyến** khi câu hỏi diễn đạt lại → cổng cần thêm bước hỏi Qwen ở vùng lưng chừng
(mục 3.2).

### 1.5 Kích thước prompt
- Schema 7 view chuẩn: 2.278–3.610 ký tự/shop. Schema bảng thô của sqlvote: 1.399–7.001 ký tự (1–7 bảng). README:
  2.100–3.700 ký tự.
- sqlvote OOM ở 20–25 nghìn ký tự (~8–10 nghìn token, tức ~2,5 ký tự/token). Prompt SQL hiện tại ~4 nghìn ký tự chạy
  ổn. Thiết kế dưới đây đặt trần **9.000 ký tự (~3.600 token)**.

---

## 2. Thiết kế tổng thể

```
rulebook.md của bộ đang chạy
   └─ rulebook.parse → mục luật {mục, ngành, tên, thân, cụm kích hoạt, tham chiếu §}
        └─ so với ảnh chụp rulebook train → trạng thái mỗi mục:
             giống | bổ sung | sửa | mới | (mục train không còn → bị bỏ)
           + mục train mà thư viện chưa có metric → "chưa phủ"

mỗi câu hỏi
   ├─ cổng (CPU, trước khi gọi Qwen): cụm kích hoạt của mục mới / chưa phủ / sửa có trong câu hỏi không?
   │     không  → đường metric như hiện nay (KHÔNG đổi gì khi rulebook = train)
   │     có     → đường rulebook
   └─ đường rulebook: 6–8 dòng luật liên quan + schema rút gọn + mốc ngày → Qwen viết SQL, 2 bản nháp
         2 bản trùng đáp án → trả lời (qua calibration);  không trùng / lỗi → bỏ trống
```

Nguyên tắc an toàn quan trọng nhất: **khi rulebook lúc chạy giống hệt rulebook train thì cổng chỉ bắt các mục "chưa
phủ"**; mọi câu khác đi đúng đường cũ. Nhờ đó điểm trên train không thể tụt vì phần "mới/sửa", và phần "chưa phủ" đo
được ngay bằng đáp án train.

---

## 3. Trả lời 6 câu hỏi thiết kế

### 3.1 Tách rulebook và truy hồi (không mạng, không thêm model)

**Tách** (`datamate/rulebook.py`, hàm `parse(path) -> list[Rule]`):
- Một mục = một dòng của bất kỳ bảng markdown nào có ≥ 2 cột (không dựa vào tên cột `Luật | Mặc định`), hoặc một
  gạch đầu dòng dưới tiêu đề `##`. Lưu: `section` (số và tên mục `##`), `industry` (tên `###` nếu có), `title` (ô đầu),
  `body` (các ô còn lại), `refs` (các `§N` trong thân).
- `triggers` (cụm kích hoạt) của mục, lấy theo định dạng chứ không theo nội dung:
  1. tên luật, tách theo dấu phẩy thành từng cụm ("Nợ thêm, trả nợ, thu nợ trong kỳ" → 3 cụm);
  2. thuật ngữ in đậm đang được định nghĩa trong thân: `**X** =`, `**X** là`, `**X**:`, `**X** bằng`,
     "`**X**, **Y** cùng nghĩa với …`".
  Mỗi cụm được bỏ dấu, hạ chữ thường, bỏ từ dừng (dùng `values.plain`, cùng cách với `normalize.norm`).
- Bỏ qua §9 (định dạng đáp án) và §7 khi truy hồi cho câu hỏi; hai mục này đưa vào prompt dưới dạng một đoạn tóm tắt
  cố định ngắn (đã có sẵn trong `sqlvote/prompt.py` luật 5–6).

**So với train** (`datamate/rulebook_base.json`, sinh bằng `python -m datamate.rulebook snapshot data/train/rulebook.md`):
- Ảnh chụp chứa mọi mục của rulebook train: khoá = (số mục, ngành, tên đã chuẩn hoá), thân, và `covered_by` =
  danh sách metric/luật trong code đang thực hiện mục đó (điền tay MỘT lần, theo metric chứ không theo shop hay câu;
  vd "Tỉ lệ đơn huỷ trong kỳ" → `cancel_rate`; "Giao nhiều đợt" → rỗng).
- Ghép mục lúc chạy với ảnh chụp: tên trùng sau chuẩn hoá, không thì trigram tên ≥ 0,8 trong cùng mục `##`.
- Trạng thái: `giống` (thân trùng) · `bổ sung` (mọi câu/vế của thân cũ còn trong thân mới, chỉ thêm) · `sửa` (còn lại) ·
  `mới` (không ghép được) · `chưa phủ` (ghép được nhưng `covered_by` rỗng) · mục train không còn → `bị bỏ`.
- Không tìm thấy `rulebook.md` → coi như mọi mục `giống` (chạy đúng như hiện nay).

**Truy hồi** (`rulebook.retrieve(question_norm, k=8)`):
- Điểm = tổng IDF của từ và cặp từ liền nhau (không dấu) trùng giữa câu hỏi đã qua `normalize.norm` và mục luật; phần
  trùng với tên/cụm kích hoạt nhân 3; chia cho độ dài mục. IDF tính trên chính rulebook lúc chạy (79–101 mục, tức thì).
- Thêm trigram ký tự cho từ không khớp nguyên (chịu lỗi gõ) — cùng hàm `_trigrams` đã có ở `intent.py`.
- Mở rộng theo tham chiếu: mục được chọn có `§N` → thêm dòng ĐẦU của mục `##N` (vd "Đơn tính vào doanh thu").
- Mục của ngành: mỗi shop được gán nhiều nhất một ngành `###` bằng độ trùng từ giữa (README + tên bảng + tên cột)
  và (tên ngành + các mục của ngành); nếu vượt ngưỡng thì mọi mục của ngành đó luôn là ứng viên cho shop.
- Không dùng XLM-R để nhúng: XLM-R base chưa tinh chỉnh cho truy hồi cho kết quả kém, và ta không có dữ liệu cặp
  (câu hỏi, dòng luật) ngoài train để tinh chỉnh mà không overfit vào 79 mục train.
- Chịu không dấu/viết tắt: mọi so khớp trên dạng không dấu sau `norm` (đã giải telex, viết tắt `dthu`, `hqua`…).
  Đo riêng theo họ nhiễu ở mục 6.1.

### 3.2 Cổng định tuyến (câu nào đi đường nào)

Tính trước khi gọi Qwen, hoàn toàn bằng CPU:
- `fire(question)` = mục có điểm kích hoạt cao nhất trong các mục trạng thái `mới` / `chưa phủ` / `sửa`.
  Điểm kích hoạt của một cụm = tỉ lệ (theo IDF) số từ của cụm có mặt trong câu hỏi. Từ **chưa từng xuất hiện ở bất kỳ
  đâu trong rulebook train** được cộng trọng số (đó là dấu hiệu mạnh của thuật ngữ mới).
- Ba vùng:
  - điểm ≥ `T_hi` (khởi điểm 0,8, và cụm có ≥ 2 từ nội dung hoặc 1 từ chưa từng thấy) → **bắt**;
  - `T_lo` ≤ điểm < `T_hi` (khởi điểm 0,4) → hỏi Qwen một câu ngắn: đưa câu hỏi + tối đa 5 tên luật ứng viên, trả về số
    thứ tự hoặc 0 (prompt ~600 ký tự, sinh ≤ 5 token, ước 2–3 giây); chỉ gọi ở vùng này nên ít câu phải trả thêm thời gian;
  - dưới `T_lo` → không bắt.
- Hai ngưỡng chọn trên 24 shop bằng phép thử "bỏ một luật" (mục 6.1), không chọn trên shop giữ kín.

Bảng quyết định:
| Tình huống | Đường đi | Đáp án cuối |
|---|---|---|
| Không bắt | metric như hiện nay | như hiện nay |
| Bắt mục `mới` hoặc `chưa phủ` | rulebook; **không gọi bước ý định** (tiết kiệm ~8 giây) | đáp án rulebook nếu 2 bản nháp trùng, không thì bỏ trống |
| Bắt mục `bổ sung` | metric (luật cũ còn nguyên) | như hiện nay, thêm đặc trưng `rule=bo_sung` cho calibration |
| Bắt mục `sửa`, tham số đọc được (mục 3.3) | metric với tham số mới | như hiện nay |
| Bắt mục `sửa`, không đọc được tham số | cả hai đường | trả lời khi metric = rulebook; khác nhau → bỏ trống |
| Không bắt nhưng đường metric bỏ trống (`unknown metric`, không ra JSON) | rulebook (thay cho `sql_only` hiện tại) | đáp án rulebook nếu 2 bản trùng |
| Shop không dựng được bảng bán nào, hoặc câu hỏi khớp bảng chưa gán vai hơn view chuẩn (mục 3.4) | rulebook trên bảng thô | như dòng 2 |
| Mục `bị bỏ` | metric như cũ | như hiện nay (lý do: bỏ luật thường nghĩa là bộ đó không hỏi loại câu ấy; nếu vẫn hỏi thì định nghĩa cũ là phỏng đoán tốt nhất) |

"Bỏ trống thay vì đoán" là giá trị chắc chắn nhất của cổng: ở câu dùng định nghĩa lạ, đường metric gần như chắc chắn
trả lời theo định nghĩa khác.

### 3.3 Khi rulebook đổi tham số của luật đang viết cứng
- `rulebook.params(rules) -> dict`: một số ít bộ đọc tham số, mỗi bộ gắn với một mục train có hằng số trong code:
  giờ ca sáng/chiều (`HH:MM–HH:MM`), cửa sổ Tết (ngày âm đầu/cuối), ngày đầu tuần, "N ngày gần nhất" có gồm hôm nay,
  số chữ số làm tròn phần trăm. Mỗi bộ là regex trên thân mục; **đọc không ra → trả `None` → mục thành "sửa, không đọc
  được" → đi cả hai đường** (không bao giờ đoán).
- `periods.py`, `metrics.py`, `timex.py` nhận tham số qua `Calendar`/`Ctx` thay cho hằng số; mặc định = giá trị train.
- Đây là việc số 7 của kế hoạch cũ, gộp vào đây. Kiểm tra bằng rulebook giả (đổi giờ ca, đổi ngày đầu tuần) → đáp án
  đổi đúng; rulebook train → đáp án không đổi (test hồi quy).

### 3.4 Prompt, ngân sách token, bảng chưa gán vai

**Prompt** (`datamate/rulepath.py`), trần 9.000 ký tự; vượt thì cắt theo thứ tự: giá trị mẫu của cột → ví dụ → mục luật
điểm thấp nhất:
| Phần | Trần ký tự | Nguồn |
|---|---|---|
| Hệ thống: nhiệm vụ, hình dạng đáp án theo TYPE, làm tròn, khuôn trả lời `TYPE:` + `SQL:` | 1.100 | rút từ `sqlvote/prompt.py` SYSTEM_A (bỏ NOTE/PERIOD) |
| LUẬT ÁP DỤNG: 6–8 mục (tên + thân nguyên văn) + dòng đầu mục được tham chiếu | 2.400 | `rulebook.retrieve` |
| SCHEMA: chỉ các bảng liên quan (≤ 3 bảng), mỗi cột 1 dòng có mô tả | 3.500 | xem dưới |
| Mốc ngày đã tính sẵn + kỳ từ `timex` | 600 | `sqlpath.resolved_periods`, `sqlvote/dates.date_facts` |
| Tên hàng/khách khớp câu hỏi | 400 | `intent.relevant_names` hoặc `sqlvote.schema.ValueIndex` |
| 2 ví dụ đã kiểm chứng (câu hỏi → TYPE → SQL) | 800 | ngân hàng ví dụ, mục dưới |
Sinh tối đa 300 token. Ước lượng: ~11 giây/bản nháp trên T4 (prompt gấp ~2 hiện tại, phần sinh như cũ) → 2 bản ~22 giây,
bù lại không gọi bước ý định ở câu bị bắt. Chỉ câu bị cổng bắt mới trả chi phí này.

**Hai bản nháp, không lấy mẫu ngẫu nhiên** (BTC có ngưỡng tái lập 0,03): bản 1 greedy với prompt chuẩn; bản 2 greedy với
biến thể (đảo thứ tự mục luật + yêu cầu ghi một dòng "luật dùng:" trước SQL). Trùng nhau theo khoá của cách chấm
(`sqlvote.engine.answer_key`). Thêm 3 kiểm tra cố định: TYPE của hai bản giống nhau; kết quả không rỗng/NULL; đáp án
bằng 0 hoặc danh sách rỗng → bỏ trống (train chỉ có 4/2.462 đáp án số bằng 0, theo `docs/sqlvote_goi_y.md` mục 8).

**Ví dụ trong prompt**: ngân hàng (câu hỏi, SQL ra đúng đáp án) dựng trên GPU từ 24 shop bằng `sqlvote/bank.py`
(`--save-bank`); lúc chạy chọn 2 ví dụ có mục luật truy hồi gần nhất. Trong phép thử ẩn luật, ví dụ thuộc nhóm đang ẩn
bị loại (không thì là lộ đề). Lần chạy GPU đầu chưa có ngân hàng → dùng 4 ví dụ viết tay cố định trên view chuẩn, đều
là câu doanh thu/số đơn cơ bản (không thuộc nhóm ẩn nào).

**Bảng cho SQL — hai mức:**
- Mức A — view chuẩn + cột đi kèm. Giữ 7 view của `sqlpath.TABLES` (đã áp luật mặc định: `counts_for_revenue`,
  `qty_base`…). Thêm vào `rules.build_views`: mọi cột của bảng đã gán vai mà **không được gán khái niệm nào** được giữ
  lại dưới tên `x_<tên không dấu>` (số/ngày đã làm sạch bằng `values.py`), mô tả lấy từ README. Như vậy câu hỏi về một
  cột lạ (tiền giảm, phí, người làm…) vẫn truy vấn được trên bảng đã có sẵn bộ lọc đơn hợp lệ. Schema trong prompt chỉ
  nêu cột `x_` nào có từ trùng với câu hỏi hoặc mục luật truy hồi.
- Mức B — bảng thô đã làm sạch, cho bảng **không gán được vai nào** (sổ sửa xe, lô, đợt giao, sổ góp, bảo hành…).
  Tái dùng `sqlvote/`: `clean.read_shop` / `build_shop_db` (đọc, tìm dòng tiêu đề, bỏ chân trang, số/ngày, cột `_4tt`
  trạng thái 4 loại, cột `_dv`), `schema.schema_text` (mỗi cột kèm tên gốc + mô tả README), `schema.ValueIndex`,
  `dates.date_facts`, `engine.check_sql / to_answer / answer_key`. Không chép code: `rulepath.py` import các hàm này
  (kiểm tra `datamate_submit/` và `Dockerfile` có đóng gói `sqlvote/`).
  Chọn bảng: chấm độ trùng từ giữa (câu hỏi + mục luật truy hồi) và (tên bảng + tên cột + mô tả README); lấy ≤ 3 bảng.
  Nếu bảng điểm cao nhất là bảng đã gán vai → dùng mức A; nếu là bảng chưa gán vai → mức B (đăng ký cả view chuẩn lẫn
  bảng thô vào cùng DuckDB để SQL nối được, như `sqlvote/adapters.canonical_tables` đã làm).
  Dòng README mô tả cách ghi (không phải mô tả cột) được tách thành câu và truy hồi như mục luật, tối đa 3 câu.
- Vì mức B không có sẵn bộ lọc đơn hợp lệ, dòng đầu §1 (đơn tính vào doanh thu) và dòng "Trạng thái đơn" §8 luôn được
  thêm vào LUẬT ÁP DỤNG ở mức B.

### 3.5 Phép thử "ẩn luật" — đo chỉ bằng train (phần quan trọng nhất)

Ý tưởng: làm cho hệ thống "quên" một phần thư viện rồi xem đường rulebook có tự làm lại được không, chấm bằng đáp án
train. Bốn phép thử, xếp theo mức giống tình huống thật:

**T1 — luật chưa phủ có thật (không cần giả lập).** Các mục train mà thư viện không có metric: "Giao nhiều đợt",
"Lô gần hết hạn nhất", "Mặt hàng hết hàng cuối ngày", "Lãi ròng"… Trên 24 shop có khoảng 35 câu (đếm theo từ khoá:
đợt giao 12, lô/hạn dùng 19, lãi ròng 3, hết hàng 1). Ít nhưng là điểm THẬT: hiện các câu này sai hoặc bỏ trống.

**T2 — ẩn metric.** Cờ chỉ dùng khi thử `--hide-metrics a,b,c` trong `datamate.predict`: xoá metric khỏi `METRIC_DOC`,
và mọi mục luật có `covered_by` nằm trọn trong danh sách ẩn chuyển thành `chưa phủ`. Nhóm ẩn (số câu scripted trên 24 shop):
| Nhóm | Metric ẩn | Vì sao chọn | Số câu |
|---|---|---|---|
| H1 xếp hạng | `top_products` 76, `top_customers` 81, `best_day` 99, `top_supplier` 6 | giống kiểu K1 nhất (định nghĩa "… nhất") | 262 |
| H2 tỉ lệ / trung bình có định nghĩa riêng | `cancel_rate` 118, `avg_order_value` 145, `avg_purchase_price` 28 | luật trái trực giác (mẫu số, làm tròn, bình quân theo lượng) → biết model có ĐỌC luật không | 291 |
| H3 đếm theo điều kiện | `unsold_products` 27, `customers_min_orders` 31, `products_min_orders` 6, `cancelled_count` 89 | định nghĩa tập hợp | 153 |
| H4 nghiệp vụ nhiều bước | `new_debt_and_repaid` 39, `price_effect` 70, `debt_aging` 4, `expiring` 9 | kỳ vọng model KHÔNG làm được → đo xem nó có biết bỏ trống không | 122 |
Mỗi nhóm lấy mẫu 50 câu (chỉ câu scripted đang đúng, để tách lỗi tầng dữ liệu; chia đều theo shop; hạt giống cố định).
Không ẩn `revenue`, `order_count`, `quantity`: đó là nền mà mọi rulebook đều có và view chuẩn đã mã hoá.

**T3 — thuật ngữ bịa (thử cả chuỗi cổng → truy hồi → SQL với mục "mới").** Thêm vào bản sao rulebook train 6 dòng có
tên do ta đặt, thân luật viết bằng lời, và đáp án tính được bằng thư viện sẵn có với tham số khác (không cần ai gán
nhãn): vd một tên bịa cho "khách có nhiều đơn nhất" (= `top_customers` `by=orders`), "mặt hàng có doanh thu cao nhất"
(= `top_products` `by=revenue`), "ngày có doanh thu cao nhất" (= `best_day`), "phần trăm đơn huỷ trên mọi đơn"
(= `cancel_rate`), "số mặt hàng có mặt ở ít nhất N đơn", "nhà cung cấp có tiền nhập cao nhất". Câu hỏi sinh bằng cách
thay cụm metric trong câu train có sẵn bằng tên bịa (giữ nguyên phần thời gian). 6 tên × 20 câu = 120.
**Tên bịa phải khác mọi thuật ngữ trong rulebook public** (không dùng lại "sộp", "trung thành", "cao điểm"…).

**T4 — luật đảo (rulebook SỬA một luật đang viết cứng).** Bản sao rulebook train với 3 dòng bị sửa thân, đáp án mới vẫn
tính được bằng thư viện: "Bán chạy" → theo số tiền (= `top_products by=revenue`); "Khách mua nhiều nhất" → theo số đơn;
"Ca sáng" → đổi giờ (sau bước tham số 3.3). 3 luật × 20 câu = 60. Chấm: +1 theo định nghĩa mới; **−1 nếu trả lời theo
định nghĩa cũ**; 0 nếu bỏ trống.

**T5 — ẩn vai bảng (thử mức B).** Cờ thử `--hide-roles purchases,purchase_lines,payments`: mapper bỏ vai các bảng đó →
câu `purchase_total`, `top_supplier`, `avg_purchase_price`, `debt_total` phải trả lời từ bảng thô. Lấy 60 câu.

**Phần đo được trên CPU (không cần Qwen):**
| Đo | Cách | Tiêu chí |
|---|---|---|
| Tách rulebook | 79 mục train; file public tách ra 101 mục (chỉ kiểm tra định dạng, không lưu nội dung vào test) | đúng số mục, không mục nào rỗng thân |
| Truy hồi | script mục 9, r@k theo metric | r@8 ≥ 0,90 trên các metric không phải `revenue` |
| Cổng, "bỏ một luật" | lần lượt coi từng mục có `covered_by` là `mới`; trên 2.524 câu của 24 shop: tỉ lệ bắt đúng (câu có metric scripted thuộc mục đó) và bắt nhầm (câu khác) | bắt nhầm ≤ 2%; bắt đúng ≥ 0,60 chỉ bằng từ khoá, ≥ 0,85 khi tính cả vùng lưng chừng gửi cho Qwen |
| Cổng dưới nhiễu | chạy lại phép trên với biến thể của `datamate/augment.py` (no_accent, abbrev, telex, filler; và typo, reorder là họ giữ kín) | mỗi họ mất ≤ 5 điểm % bắt đúng |
| Rulebook = train | scripted 24 shop trước/sau | điểm không đổi (1663), không shop nào tụt |
| T4 phần "chặn" | với rulebook đảo, câu thuộc luật bị sửa không được trả lời bằng định nghĩa cũ | 0 câu |
| Tham số | rulebook giả đổi giờ ca / đầu tuần | đáp án đổi đúng |
| Trần prompt | dựng prompt cho mọi câu T1–T5, không gọi model | 100% ≤ 9.000 ký tự |
| An toàn SQL | `sqlpath.validate_sql` nhận bảng thô + cột `x_` | test fixture |

**Phần cần GPU (một lần chạy, mục 7):** chất lượng SQL của Qwen ở T1–T5, bước hỏi Qwen ở vùng lưng chừng, thời gian.

**Tiêu chí giữ / bỏ** (tính trên câu được trả lời của đường rulebook; "chính xác" = đúng / (đúng + sai)):
| Kết quả | Quyết định |
|---|---|
| Chính xác ≥ 0,75 trên 24 shop (T1–T3) VÀ trên shop giữ kín điểm chế độ ẩn cao hơn "chỉ cổng" ≥ 10 điểm / 240 câu | giữ nấc 2 |
| Chính xác 0,55–0,75 | chỉ giữ các ô calibration có p > 0,5 (theo kiểu đáp án, mức A/B); phần còn lại bỏ trống |
| Chính xác < 0,55, hoặc T4 có câu trả lời theo định nghĩa cũ | bỏ nấc 2, giữ nấc 1 (cổng + bỏ trống) |
| Bản "không có dòng luật" (đối chứng) chính xác ngang bản có luật (chênh < 10 điểm %) | đường này không thật sự đọc luật → không tin nó ở thuật ngữ mới; lùi về nấc 1 |
| T5 chính xác < 0,6 | tắt mức B; shop không dựng được bảng bán → bỏ trống các câu ngoài view chuẩn |
| H4 (nghiệp vụ khó): số sai > số đúng | thêm luật chặn: mục luật có thân dài > 300 ký tự hoặc ≥ 2 tham chiếu § → chỉ bỏ trống (đo lại bằng phát lại log, không cần GPU) |
| p90 thời gian câu bị bắt > 60 giây | bỏ bản nháp 2 ở các ô calibration đã đủ chính xác, hoặc giảm 8 → 5 mục luật |

Điểm "chế độ ẩn" trên shop giữ kín: chạy 6 shop × 40 câu với H1+H2+H3 cùng ẩn; chỉ đọc 3 con số tổng:
S_ẩn (có đường rulebook), S_cổng (ẩn, đường rulebook tắt → các câu bị bắt bỏ trống), S_đủ (thư viện đầy đủ, đã có từ
lần 7). Tỉ lệ khôi phục = (S_ẩn − S_cổng) / (S_đủ − S_cổng). S_cổng tính được bằng phát lại, không cần chạy thêm.

---

## 4. Các bước thực thi (theo thứ tự)

Sau MỖI bước: `python -m pytest -q tests` và scripted 24 shop không đổi điểm (1663) — vì rulebook train không kích hoạt
gì ngoài mục "chưa phủ".

| # | Việc | File | Điều kiện xong | Kiểm tra bằng |
|---|---|---|---|---|
| B0 | Hỏi người dùng: hạn nộp, giới hạn thời gian mỗi câu, rulebook nằm ở đâu trong `/data` của đề | — | có câu trả lời | — |
| B1 | Tách rulebook + ảnh chụp train + trạng thái mục + cụm kích hoạt | mới `datamate/rulebook.py`, `datamate/rulebook_base.json` | 79 mục train, mọi mục `giống`/`chưa phủ`; rulebook giả trong test ra đủ 5 trạng thái | test fixture (rulebook nhỏ tự viết, thuật ngữ bịa) |
| B2 | Truy hồi + công cụ đo | `datamate/rulebook.py`, mới `tests/rulebook_eval.py` (chuyển từ script scratchpad mục 9; từ chối shop giữ kín như `perturb_shops.py`) | r@8 đạt tiêu chí; in bảng theo metric | CPU, 24 shop |
| B3 | Cổng (3 vùng; vùng lưng chừng tạm coi là "không bắt" khi không có backend) + nối vào `predict.py`: tìm `rulebook.md` như `find_calendar`; log thêm `rule_hits`, `rule_status`, `route` | `datamate/rulebook.py`, `datamate/predict.py`, `datamate/pipeline.py` | phép "bỏ một luật" đạt tiêu chí; rulebook train → 0 câu đổi đường ngoài mục chưa phủ | `tests/rulebook_eval.py --loro`, scripted |
| B4 | Tham số từ rulebook (giờ ca, Tết, đầu tuần, N ngày, làm tròn %) | `datamate/rulebook.py`, `periods.py`, `timex.py`, `metrics.py` | rulebook giả đổi tham số → đáp án đổi đúng; không đọc được → `None` | test fixture; `perturb_shops.py` không cần (không đụng mapper) |
| B5 | Đường SQL có luật, mức A: prompt mới, 2 bản nháp, so khoá chấm, cột `x_` trong view | mới `datamate/rulepath.py`; `rules.py` (cột `x_`), `sqlpath.py` (validate nhận cột `x_`) | prompt ≤ 9.000 ký tự cho mọi câu T1–T4; chạy trọn với backend giả trả SQL viết tay | test fixture + `tests/smoke_predict.py`; **`perturb_shops.py` 24 shop vì đụng `rules.py`** |
| B6 | Cờ thử `--hide-metrics`, `--hide-roles`, `--rulebook <file>`; script dựng bộ câu T1–T5 + rulebook bịa/đảo + đáp án | `datamate/predict.py`, mới `tests/hidden_rules.py` | sinh `state/hidden/*.jsonl` (câu hỏi + đáp án) chỉ từ 24 shop; bộ shop giữ kín chỉ là danh sách id do script chọn, không in nội dung | CPU |
| B7 | Mức B: bảng thô qua `sqlvote.clean`, chọn bảng, gán ngành | `datamate/rulepath.py` | T5 chạy trọn với backend giả; `python -m pytest -q sqlvote/tests` qua | CPU. **Chỉ làm nếu B1–B6 xong mà còn ≥ 5 giờ trước lúc đẩy Kaggle** |
| B8 | Calibration: thêm giá trị `route` (`rule_a`, `rule_b`) và `drafts` (trùng / lệch) vào `features`; ô mới có prior thấp (0,3) để chưa có dữ liệu thì bỏ trống | `datamate/calibration.py` | test: ô chưa thấy → bỏ trống | test fixture |
| B9 | Notebook: bước `RUN['rulepath']` chạy các bộ T1–T5 + chế độ ẩn trên shop giữ kín; thêm biến vào `SCALAR_VARS/DICT_VARS` | `notebooks/build_notebook.py`, `kaggle/kaggle_cycle.py` | `python notebooks/build_notebook.py` chạy; thử khô bằng backend giả | CPU |
| B10 | **Hỏi người dùng → một lần chạy Kaggle** (mục 7) | — | tải được `state/` | Kaggle |
| B11 | Đọc kết quả theo bảng tiêu chí 3.5; học calibration từ 24 shop; chốt cấu hình; ghi `docs/datamate_v6_handoff.md` | `kaggle/analyze_run.py` (thêm bảng theo `route`) | bảng số + quyết định giữ/bỏ từng nấc | CPU |
| B12 | Nộp public (nếu được nộp nhiều lần): bản không có và bản có đường rulebook | — | hai điểm public | BTC chấm |

Thứ tự ưu tiên khi thiếu thời gian: B1 → B3 → B5 → B6 → B9 → B10. B2 rút gọn (dùng luôn script scratchpad), B4 và B7 bỏ được.

Việc tuỳ chọn, KHÔNG làm trong đợt này (ghi lại để khỏi quên): "truy vấn ghép" — thay SQL tự do bằng JSON có khung
(nhóm theo thực thể nào, số đo nào, điều kiện tối thiểu, lấy đầu/cuối) chạy bằng code cố định trên view chuẩn. Có thể
chính xác hơn SQL tự do với model 4B, nhưng chỉ phủ được luật kiểu xếp hạng/đếm (khoảng 1/3 số mục mới), tốn ~5–6 giờ
viết, và từ vựng của khung rất dễ bị vẽ theo các định nghĩa đã nhìn thấy ở rulebook public. Chỉ cân nhắc nếu B11 cho
thấy SQL tự do hỏng chủ yếu vì hình dạng đáp án chứ không vì hiểu luật.

---

## 5. Rủi ro và cách đo khách quan

| Rủi ro | Biểu hiện | Cách giảm / đo |
|---|---|---|
| Thiết kế vẽ theo rulebook public | cụm kích hoạt, tên bịa, bộ đọc tham số trùng với nội dung public | chỉ dùng ĐỊNH DẠNG (bảng, in đậm, §, ###); test dùng rulebook tự viết; tên bịa khác thuật ngữ public; bộ đọc tham số chỉ cho hằng số đang có trong code train |
| `covered_by` thành chỗ hard-code | gắn theo shop hoặc câu | chỉ gắn mục luật ↔ tên metric; rà soát khi review: không có business_id, không có id câu |
| Phép thử ẩn luật lạc quan | Qwen đã "biết" bán chạy là gì từ kiến thức chung; câu hỏi train quen dạng | nhóm H2 (luật trái trực giác) + bản đối chứng không có dòng luật; T3 dùng tên bịa; T4 dùng luật đảo; báo riêng từng nhóm, không gộp |
| Chỉ chọn câu scripted đang đúng | đánh giá cao hơn thực tế vì bỏ câu dữ liệu khó | ghi rõ khi báo cáo; điểm chế độ ẩn trên shop giữ kín lấy mọi câu, không lọc |
| Ngưỡng cổng khớp quá sát 24 shop | bắt nhầm tăng ở shop lạ | 2 ngưỡng chọn bằng "bỏ một luật" trên 24 shop, sau đó khoá; đo một lần trên shop giữ kín (chỉ tổng số câu bị bắt và điểm) |
| Calibration cho ô mới chỉ có vài chục câu | ngưỡng nhiễu | prior mạnh (10–20, như Fable đã đề nghị), ô chưa có dữ liệu mặc định bỏ trống |
| Ngành mới không giống gì trong train | T5 chỉ giả lập "bảng không vai", không giả lập "thực thể mới" | nói thẳng: mức B không đo được đầy đủ bằng train; thước đo thật duy nhất là điểm public có/không có mức B (B12) |
| Bắt nhầm làm mất câu đang đúng | câu doanh thu thường bị đẩy sang SQL | cổng chỉ xét mục `mới/chưa phủ/sửa`; rulebook = train thì điểm scripted phải y nguyên |
| Thời gian / bộ nhớ | prompt dài, 2 bản nháp | trần 9.000 ký tự kiểm tra trên CPU; đo p90 trong lần chạy; đường SQL đối chiếu hiện tại (tốn ~nửa thời gian, chưa thêm điểm) là thứ cắt trước nếu đề giới hạn thời gian |
| `sqlvote/` chưa nằm trong gói nộp | mức B lỗi import trong Docker | B7 kiểm tra `datamate_submit/`; lỗi import → tự tắt mức B, không làm hỏng lần chạy |

Thước đo khách quan, theo độ tin giảm dần: (1) điểm public có/không có đường rulebook; (2) điểm chế độ ẩn trên 6 shop
giữ kín (chỉ số tổng); (3) T3/T4 trên 24 shop; (4) họ nhiễu giữ kín typo/reorder cho cổng. Số trên 24 shop của T1–T2 là
ước lượng lạc quan vì ngưỡng cổng chọn trên chính các shop đó.

Phương án lùi:
- Qwen 4B viết SQL từ định nghĩa mới quá kém (chính xác < 0,55): giữ nấc 1. Hệ thống vẫn hơn hiện tại ở chỗ không trả lời
  sai có hệ thống các câu dùng định nghĩa lạ.
- Cổng bắt nhầm nhiều (> 2%) mà không hạ được: chỉ bật cổng cho cụm kích hoạt có từ chưa từng thấy trong rulebook train.
- Mức B không ổn: tắt riêng mức B.
- Hết thời gian trước khi chạy GPU: nộp bản nấc 1 (không cần GPU để kiểm chứng phần chặn).

---

## 6. Có đáng làm hơn các việc ở mục 7 / 9.3 của `docs/tong_ket_cho_fable.md` không?

Có, với phần nấc 1; có điều kiện với nấc 2–3. Lý do: đây là **dịch chuyển phân phối duy nhất đã được xác nhận** (25/101
mục luật public không có trong train, 3 ngành mới); các việc về độ bền khác đang phòng những dịch chuyển giả định.

| Việc trong kế hoạch 9.3 | Đề nghị |
|---|---|
| 0. Đọc lần 7 | **Giữ**, làm trước (quyết định LoRA và calibration; không tốn GPU) |
| 1. Chạy thử nộp bài | **Giữ, vẫn là ưu tiên số 1**; gộp vào lần chạy Kaggle ở mục 7. Điểm public cũng là thước đo tốt nhất cho việc này |
| 2. So mapper LLM ↔ heuristic | Giữ, gộp vào cùng lần chạy (rất ngắn) |
| 3. Đưa cue vào `scripted_intent` | **Hoãn** (làm đẹp công cụ đo, không thêm điểm) |
| 4. Perturb họ cấu trúc / độ lớn | **Hoãn** |
| 5. Nhận vai cột theo giá trị | **Hoãn** (noreadme đã 96,6%); mức B của kế hoạch này là lưới đỡ cho bảng không nhận được vai |
| 6. Lớp lỗi thu nợ, price_effect, đơn vị lớn… | **Dừng**. "Tồn theo đơn vị lớn" là mục đã bị bỏ ở rulebook public; các lớp còn lại là đào sâu thêm luật train |
| 7. Tăng cường SFT cho LoRA | **Bỏ** (đã thống nhất không đầu tư thêm LoRA) |
| Việc cũ "đọc tham số rulebook" | Gộp vào B4 |

---

## 7. Lần chạy Kaggle duy nhất (phải hỏi người dùng trước)

Không train LoRA, không XLM-R. Qwen 4B 4-bit, T4 ×2.
| Phần | Số câu | Ước giây/câu | Giờ GPU (cộng 2 máy) |
|---|---|---|---|
| T1 luật chưa phủ thật (24 shop) | ~35 | 22 | 0,2 |
| T2 ẩn metric H1–H4 (24 shop) | 200 | 22 | 1,2 |
| T3 thuật ngữ bịa | 120 | 22 | 0,7 |
| T4 luật đảo (cả hai đường) | 60 | 30 | 0,5 |
| T5 ẩn vai bảng (nếu có B7) | 60 | 25 | 0,4 |
| Đối chứng "không có dòng luật" trên 100 câu của T2 | 100 | 22 | 0,6 |
| Chế độ ẩn trên 6 shop giữ kín × 40 câu | 240 | 25 | 1,7 |
| Dựng ngân hàng ví dụ (câu SQL ra đúng đáp án, 24 shop) | lấy từ T1–T2 | 0 | 0 |
| Chạy thử nộp bài `predict.sh` offline 2 shop + so mapper LLM/heuristic 24 shop | — | — | 0,8 |
| Nạp model, đọc 30 shop, dựng DuckDB | — | — | 0,6 |
| **Tổng** | ~815 | | **~6,7 giờ GPU ≈ 3,5 giờ đồng hồ với 2 GPU** |

Dự phòng chậm hơn ước lượng 40% → **4,5–5,5 giờ đồng hồ**, trong hạn mức ~30 giờ/tuần. Nếu phải cắt: bỏ T5, giảm T2
xuống 30 câu/nhóm, giảm shop giữ kín xuống 25 câu/shop (~2,5 giờ). Chạy bằng `kaggle/kaggle_cycle.py` qua subagent
`kaggle-runner`; đừng đẩy lần khác trước khi tải xong (Kaggle chỉ giữ output của version mới nhất).

---

## 8. Điểm chưa chắc

1. Hạn nộp (16/11?) và số lần được nộp public — quyết định có làm B7, B12 hay không.
2. Tỉ lệ câu public thật sự dùng định nghĩa mới: không biết và không được xem. Nếu nhỏ, lợi ích chủ yếu đến từ ngành mới
   (mức B) — đúng phần khó đo nhất bằng train.
3. Ước 11 giây/bản nháp là ngoại suy từ prompt 4.000 ký tự; prompt 9.000 ký tự chưa từng chạy trên T4.
4. Hai bản nháp greedy với prompt khác nhau có thể cùng sai giống nhau; mức độ chỉ biết sau lần chạy.
5. Luật mới thuộc loại "cách ghi trong file" (§8) hoặc "ghi chung ô" (ngành) ảnh hưởng tới bước đọc dữ liệu, không phải
   định tuyến câu hỏi; kế hoạch này KHÔNG xử lý chúng (không có cách đo bằng train). Có thể thử đưa các mục §8 `mới` vào
   prompt của mapper LLM, nhưng chưa có phép đo nên để ngoài.
6. Nhãn truy hồi ở mục 1.4 suy từ `scripted_intent` nên không sạch (vd `days_min_revenue` không có dòng luật nào);
   r@k thật có thể cao hơn hoặc thấp hơn vài điểm.

---

## 9. Script đo đã dùng (để phiên chính chuyển thành `tests/rulebook_eval.py`)

- `C:\Users\HO\AppData\Local\Temp\claude\e5357798daed7eea\96b4e043-3ea4-400a-8063-f916aee1e46e\scratchpad\measure.py`
  — tách rulebook và so train/public (chỉ đếm), SQL đứng một mình trên log lần 6, truy hồi r@k, kích thước schema.
- `C:\Users\HO\AppData\Local\Temp\claude\e5357798daed7eea\96b4e043-3ea4-400a-8063-f916aee1e46e\scratchpad\m2.py`
  — phân bố metric scripted và đếm từ khoá luật chưa phủ trên 24 shop.

Cả hai loại 6 shop giữ kín ngay ở bước đọc (`VAL`), chạy bằng
`PYTHONUTF8=1 PYTHONIOENCODING=utf-8 PYTHONPATH=. python <file>` từ thư mục dự án.
