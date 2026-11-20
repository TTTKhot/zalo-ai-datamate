# DataMate — tụi mình đã làm gì (bản nháp)

Đội `be_cooked` · Zalo AI Challenge 2026, bảng Data Mate · điểm public cuối: **0,595**

## 1. Bài toán

- Mỗi cửa hàng có vài file Excel/CSV bán hàng và một file README mô tả.
- Người dùng hỏi bằng tiếng Việt, kiểu nhắn tin: "dthu t3 bn", "tháng rồi ai mua nhiều nhất".
- Hệ thống phải trả ra con số, tên, ngày… đúng theo một bộ luật chung (`rulebook.md`). Ví dụ: doanh thu không tính đơn huỷ.
- Chấm điểm: đúng +1, **sai −1**, bỏ trống 0.
- Ràng buộc: chạy trong Docker không có mạng, model mã nguồn mở, tổng dưới 15 tỉ tham số.
- Bộ test là các cửa hàng chưa từng thấy, mỗi cửa hàng đặt tên file, tên cột một kiểu.

## 2. Các hướng thầy gợi ý lúc đầu

- **ViSoLex** (model chuẩn hoá chữ viết tắt, không dấu, teencode)
  - Ý tưởng: sửa câu hỏi về tiếng Việt chuẩn rồi mới xử lý.
  - Đã làm: dựng notebook thử trên 3.000 câu train, so 4 kiểu: câu gốc, sửa bằng luật, sửa bằng ViSoLex, ViSoLex có kiểm tra an toàn.
  - Kết quả: nhờ ChatGPT chạy thử thì kết quả không cao. Tụi mình chưa tự ngồi review từng câu và không lưu lại con số cụ thể, nên đây chỉ là đánh giá sơ bộ.
  - Vấn đề thấy được: model có thể sửa luôn mã hàng, tên thuốc, con số trong câu. Sai một ký tự ở mã hàng là sai cả câu.
  - Quyết định: không đưa vào bản nộp. Lý do chắc chắn hơn nằm ở số đo bên dưới.
- **ViT5-base** (model sinh văn bản tiếng Việt)
  - Ý tưởng: dạy nó "khôi phục" câu nhiễu về câu sạch, có che số và tên hàng để không bị đổi.
  - Đã làm: viết xong code huấn luyện.
  - Chưa chạy trên GPU lần nào. GPU có hạn (khoảng 30 giờ/tuần) nên ưu tiên việc khác.
- **Số đo khiến tụi mình bỏ cả hai hướng chuẩn hoá bằng model:**
  - Lấy 249 câu, cho viết lại theo nhiều kiểu nhiễu, rồi xem model chính (Qwen) còn trả lời đúng không.
  - Viết tắt: giữ đúng 100%. Gõ sai chính tả: 100%. Giọng nhắn tin: 98%. Chen tiếng Anh: 98%.
  - Chỗ yếu duy nhất: số viết bằng chữ ("năm khách mua nhiều nhất"), giữ được 79%. Sửa bằng một luật nhỏ là xong.
  - Kết luận: Qwen tự đọc được câu nhiễu. Thêm một model chuẩn hoá thì tốn thời gian chạy và thêm rủi ro sửa sai.
  - Thứ giữ lại: một bộ luật nhỏ giải mã kiểu gõ Telex và khoảng hai chục từ viết tắt hay gặp (dthu, hqua, bn…). Kết quả chỉ đưa cho Qwen làm gợi ý, câu gốc vẫn giữ nguyên.
- **ViQuAD 2.0** (bộ dữ liệu hỏi đáp đọc hiểu tiếng Việt, có câu không trả lời được)
  - Chưa thử. Hỏi vài trợ lý AI thì đều nhận xét hướng này không hợp với bài, và tụi mình thấy lý do đó có cơ sở.
  - Lý do không hợp: model học từ ViQuAD trả lời bằng cách **trích một đoạn chữ** có sẵn trong văn bản. Ở bài này đáp án là số phải **tính ra** từ hàng nghìn dòng (cộng, lọc, xếp hạng), không có sẵn để trích.
  - Phần ý tưởng dùng được: nhận biết "câu không trả lời được". Tụi mình thử ý này bằng một model phân loại riêng (XLM-R) học trên dữ liệu của chính cuộc thi. Kết quả hỏng, xem mục 4, bước 5.

## 3. Vì sao chọn cách làm hiện tại

- **Model nhỏ tính toán kém.** Bắt model 4 tỉ tham số cộng mấy nghìn dòng hay viết câu truy vấn dài thì sai nhiều.
- **Luật phải làm chính xác tuyệt đối.** Rulebook quy định rõ từng thứ (đơn huỷ, đơn trả, đơn vị quy đổi). Code làm đúng 100% lần, model thì lúc nhớ lúc quên.
- **Sai bị trừ điểm.** Hệ thống phải biết lúc nào nên im lặng.
- Vì vậy chia việc:
  - Model chỉ làm một việc: đọc câu hỏi và điền vào một cái phiếu (hỏi cái gì, tháng nào, lọc theo gì).
  - Code tự viết làm phần còn lại: đọc file, áp luật, tính.
  - Cuối cùng có vài chốt chặn quyết định trả lời hay bỏ trống.

## 4. Pipeline: mỗi bước đã thử gì, giữ gì

**Bước 1. Đọc file của cửa hàng** (bảng nào là đơn hàng, cột nào là ngày, số lượng, tiền)
- Đã thử:
  - Luật đoán theo tên cột và nội dung cột.
  - Cho Qwen đọc README rồi tự gán vai cho từng bảng.
- Giữ: cả hai, kèm bước kiểm tra cứng (ví dụ cột ngày phải đọc ra được ngày).
- Vì sao: mỗi cửa hàng đặt tên một kiểu. Luật bắt được trường hợp quen, Qwen bắt được trường hợp README giải thích bằng lời.
- Đây là bước ăn điểm nhiều nhất. Đọc sai cấu trúc thì gần như cả cửa hàng sai.
- Các kiểu file đã phải xử lý riêng: file chia theo từng tháng, hoá đơn và dòng hàng nằm chung một sheet, cột số thứ tự dùng làm mã đơn, dòng tổng cộng ở cuối bảng.

**Bước 2. Hiểu câu hỏi**
- Đã thử:
  - Qwen 4 tỉ tham số, điền phiếu dạng JSON, kèm 11 ví dụ mẫu.
  - Qwen 9 tỉ tham số.
  - Dạy thêm Qwen bằng câu hỏi train (LoRA).
- Giữ: Qwen 4 tỉ, không dạy thêm.
- Vì sao:
  - Bản 9 tỉ: cùng 184 điểm trên 300 câu thử, chậm hơn khoảng 25%.
  - LoRA: trên cửa hàng train tăng nhẹ (234 lên 240). Trên public lại tụt, −0,060 so với +0,048 khi không dùng. Nó học thuộc kiểu câu của train.
- Thêm: một lớp luật từ vựng sửa lại phiếu sau khi model điền. Ví dụ "bán chạy nhất" luôn tính theo số lượng, các kiểu viết tháng ("t3", "tháng ba", "03/2026"). Riêng luật về cách viết tháng tăng gần 0,08 điểm.

**Bước 3. Tính đáp án**
- Đã thử:
  - Thư viện 35 phép tính viết tay (doanh thu, số đơn, top hàng, lãi gộp, công nợ…).
  - Cho Qwen viết SQL chạy song song để đối chiếu.
  - Cho Qwen viết SQL với nguyên rulebook trong đề bài, viết nhiều bản rồi bỏ phiếu.
- Giữ: thư viện viết tay.
- Vì sao:
  - SQL đối chiếu: trên train ngang điểm, không thêm gì. Trên public, những câu chỉ có SQL trả lời được thì 1 đúng, 15 sai.
  - SQL bỏ phiếu: hết bộ nhớ GPU hoặc mất khoảng 3 phút mỗi câu. Thử 20 câu được 1 đúng, 3 sai, 16 bỏ trống.

**Bước 4. Áp luật của rulebook**
- Mỗi khái niệm trong rulebook là một đoạn code có bài kiểm tra riêng.
- Rulebook của bộ public có thêm khái niệm mới so với train ("khách trung thành nhất", "khách sộp nhất", "giờ cao điểm"). Tụi mình viết thêm đúng theo định nghĩa trong đó.

**Bước 5. Quyết định trả lời hay bỏ trống**
- Đã thử:
  - Model phân loại "câu này trả lời được không" (XLM-R).
  - Chỉ trả lời khi cách tính tay và SQL ra cùng kết quả.
  - Chỉ trả lời khi hai lần chạy ra cùng kết quả.
  - Bỏ trống mọi câu đụng tới luật mới trong rulebook.
  - Các luật đơn giản ở mức cả cửa hàng.
- Giữ: các luật đơn giản.
  - Cửa hàng có trên 20% câu ra "không trả lời được" thì bỏ trống cả cửa hàng. Thường đó là dấu hiệu mình đọc sai file.
  - Câu ra "không trả lời được" thì bỏ trống luôn. Loại đáp án này sai nhiều hơn đúng.
  - Tự kiểm sau khi đọc file: tên hàng bán ra có khớp danh mục không, có mã đơn không, có thiếu tháng nào không. Thấy bất thường thì bỏ trống cả cửa hàng.
- Vì sao bỏ các cách kia:
  - XLM-R: huấn luyện không ổn định, cuối cùng không nhận ra được câu nào thuộc loại không trả lời được.
  - Hai đường đồng ý: ở cửa hàng đọc sai file, hai đường cùng sai giống nhau (20 đúng, 35 sai) vì dùng chung dữ liệu đã đọc.
  - Hai lần chạy đồng ý: nhóm câu "không đồng ý" vẫn đúng 61%. Bỏ trống nhóm đó là mất điểm.
  - Chặn luật mới: bỏ trống 42 câu thì 30 câu vốn đúng.
- Riêng bước này đưa điểm từ −0,171 lên +0,090 khi chưa sửa phép tính nào.

## 5. Điểm qua các mốc (leaderboard public)

- Bản đầu, trả lời hết mọi câu: **−0,171**
- Thêm các chốt bỏ trống: **+0,090**
- Sửa cách hiểu tháng và trạng thái đơn: **0,293**
- Sửa cách đọc file (hoá đơn gộp dòng hàng, bảng con): **0,443**
- Gộp file theo tháng, sổ giao hàng nhiều đợt, sổ dịch vụ: **0,525**
- Tự kiểm cấp cửa hàng, số thứ tự làm mã đơn (bản nộp Docker thứ nhất): **0,581**
- Thêm các từ xếp hạng trong rulebook (bản nộp Docker cuối): **0,595**
- Để so sánh: cho ChatGPT tự giải (không tính là bài nộp) được 0,908.

## 6. Cách làm để không học thuộc bộ public

- Giữ kín 6 cửa hàng train và 4 cửa hàng public: không bao giờ mở câu sai của chúng ra đọc, chỉ xem điểm tổng.
- Chỉ sửa khi một kiểu lỗi xuất hiện ở vài câu, thuộc ít nhất 2 cửa hàng. Sửa thành luật chung.
- Không có dòng code nào gắn với tên cửa hàng hay mã câu hỏi.
- Mỗi lần sửa phải qua đủ:
  - Bài kiểm tra riêng cho luật đó.
  - 24 cửa hàng train: không cửa hàng nào tụt điểm.
  - Bộ "phá dữ liệu": đổi tên cột, tên bảng, bỏ dấu, bỏ README, xem còn đọc đúng không.
  - Chạy lại bộ public: nhóm cửa hàng giữ kín không tụt.
- Trước mỗi lần nộp Docker: chạy đúng code đó với model thật trên GPU, so với bản trước.
- Dùng lời giải của ChatGPT để dò lỗi. Nó đúng khoảng 95% nên chỉ để tham khảo, không đưa vào bài nộp và không dùng để dạy model.

## 7. Bài học

- Cách chấm có trừ điểm thì nên làm phần "biết bỏ trống" trước tiên.
- Model nhỏ làm tốt một việc hẹp. Giao cho nó đúng việc đó, phần còn lại để code làm.
- Dữ liệu bẩn mới là phần khó: dòng tiêu đề lệch, file chia tháng, cột đặt tên lạ gây lỗi nhiều hơn câu hỏi khó.
- Ý nào cũng phải đo. Model lớn hơn, dạy thêm model, thêm tầng kiểm tra bằng model nghe đều hợp lý, đo ra đều không tăng điểm.
- Cần cách thử nhanh không tốn GPU. Tụi mình lưu câu trả lời của model lại rồi chạy code mới trên đó, mỗi lần thử mất vài phút thay vì 1,5 giờ.

## 8. Còn yếu ở đâu

- 3 trong 14 cửa hàng public (160 câu) vẫn bị bỏ trống hoàn toàn vì chưa đọc đúng file.
- Trong các câu đã trả lời, khoảng 14% còn khác lời giải tham khảo.
- Một số luật viết ra sau khi xem lỗi trên public, nên điểm ở vòng private có thể thấp hơn 0,595.
- Luật từ vựng viết tay chỉ phủ các kiểu hỏi đã gặp.
