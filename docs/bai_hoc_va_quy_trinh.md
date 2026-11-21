# Bài học từ DataMate và quy trình cho các cuộc thi sau

Viết ngày 21/11/2026, sau khi chạy bản Docker nộp cuối trên bộ private test.

## 0. Tóm tắt

- **Kết quả:** public **0,595** (ChatGPT tự giải được 0,908). Private: **500/500 câu bỏ trống, 0 điểm**.
- **Nguyên nhân chính:** hệ thống chỉ được dạy hiểu sổ bán hàng. Bộ private phần lớn là những loại hình hoạt động khác
  hẳn, không phải bán hàng, và rulebook cũng bị viết lại. Gặp thứ lạ, các chốt chặn chọn bỏ trống, nên điểm 0 chứ không
  bị âm.
- **Dấu hiệu báo trước đã có:** số ngành trong rulebook tăng từ 3 (train) lên 6 (public) rồi 12 (private). Ta có thấy
  bước 3 → 6, nhưng chỉ viết thêm code cho từng ngành mới thay vì đổi sang cách làm tổng quát.
- **5 bài học lớn:**
  1. Đọc đề để tìm **cái gì sẽ thay đổi**, rồi thiết kế hệ thống chịu được thay đổi đó.
  2. **Ngoại suy xu hướng** từ train sang public để đoán private.
  3. Bộ đánh giá phải **mô phỏng được private**, kể cả trường hợp "khác hẳn", không chỉ trường hợp "chưa gặp nhưng
     cùng kiểu".
  4. **Đừng chạy theo leaderboard public.**
  5. Thử ý tưởng trên **phần cứng giống máy chấm** trước khi bỏ một hướng vì "chạy không nổi".

## 1. Chuyện gì đã xảy ra (số liệu)

### Đề thay đổi qua từng bộ

| | Train | Public | Private |
|---|---|---|---|
| Số shop / câu | 30 shop | 14 shop / 1000 câu | 14 shop / 500 câu |
| Số ngành trong rulebook | 3 | 6 (thêm 3 ngành mới) | 12, phần lớn là ngành mới |
| Kiểu dữ liệu | sổ bán hàng | sổ bán hàng, vài kiểu file lạ | phần lớn **không phải** sổ bán hàng |
| Luật cốt lõi | | như train | một số luật cơ bản về doanh thu và thời gian **bị viết lại**, có luật ngược hẳn train |

Câu hỏi private vì thế cũng hỏi về những khái niệm không có trong train, chứ không phải các câu quen như "doanh thu
tháng 3".

### Hệ thống của ta phản ứng thế nào

- Bước đọc file chỉ biết các "vai" của bảng bán hàng (dòng bán, đơn, sản phẩm, khách, nhập hàng, công nợ…). Các loại sổ
  không phải bán hàng không khớp vai nào → nhiều shop không có bảng nào được nhận đúng.
- Bước tính là thư viện 35 phép tính viết tay cho bán hàng. Câu ngoài thư viện → bỏ trống hoặc "không trả lời được".
- Có 2 shop làm code dừng hẳn vì lỗi `KeyError('purchase_date')`.
- Chốt chặn: shop có hơn 20% câu "không trả lời được" thì bỏ trống cả shop (9/14 shop bị chặn), và mọi câu "không trả
  lời được" đều bỏ trống. Trước chốt chặn có 17 câu có đáp án; sau chốt chặn còn 0.

### Những gì đã làm tốt (nên giữ cho lần sau)

- **Chốt bỏ trống.** Cách chấm có trừ điểm (sai −1), nên khi gặp dữ liệu lạ, hệ thống bỏ trống chứ không đoán bừa. Ở
  public, riêng bước này đưa điểm từ −0,171 lên +0,090.
- **Giữ kín dữ liệu để đo.** 6 shop train và 4 shop public không bao giờ được mở ra đọc lỗi. Mỗi lần sửa phải qua test
  riêng, đo trên 24 shop, và bộ "phá dữ liệu" (đổi tên cột, bỏ dấu…).
- **Thử nhanh không cần GPU.** Lưu câu trả lời của model rồi chạy lại code mới trên đó: mỗi lần thử vài phút thay vì
  1,5 giờ.
- **Đóng gói Docker đúng hạn**, có log đúng yêu cầu, đúng định dạng.

## 2. Nguyên nhân gốc (vì sao ta đi tới thiết kế đó)

1. **Thiết kế "đóng".** Ta chọn: model chỉ điền phiếu, code tự tính bằng thư viện có sẵn. Cách này chính xác với những
   gì đã biết, nhưng có **trần cứng**: thứ gì không có trong thư viện thì không bao giờ trả lời được. Nó đúng với một
   bài cố định, sai với một bài mà mỗi vòng mở rộng phạm vi.
2. **Thấy xu hướng nhưng xử lý theo kiểu đuổi theo.** Khi public thêm 3 ngành và khái niệm mới ("khách sộp nhất", "giờ
   cao điểm"), ta viết thêm code cho đúng các khái niệm đó. Câu hỏi nên đặt lúc ấy: *"Nếu private thêm 6 ngành nữa thì
   sao?"*
3. **Tối ưu theo leaderboard public.** Nhiều bản sửa được tìm ra từ lỗi trên public. Một tính năng làm hệ thống thận
   trọng hơn với luật mới (cổng rulebook) **bị tắt vì làm public giảm 0,02**. Leaderboard public đo "giống public" chứ
   không đo "giống private".
4. **Bộ đánh giá không có trường hợp "khác hẳn".** Shop giữ kín vẫn là shop bán hàng. Bộ "phá dữ liệu" chỉ đổi tên
   cột/bảng. Không có bài thử nào kiểu "một ngành chưa từng thấy" hay "một luật bị đảo ngược". Vì vậy mọi con số đều
   báo ổn.
5. **Môi trường phát triển khác máy chấm.** Ta làm trên Kaggle T4 16 GB, quota ~30 giờ/tuần; máy chấm là 2×RTX 5090
   32 GB, 6 giờ. Hướng tổng quát hơn (cho model đọc nguyên rulebook + README rồi viết SQL, nhiều bản, bỏ phiếu) bị bỏ vì
   **hết bộ nhớ trên T4** và chậm ~3 phút/câu. Ta chưa từng thử nó trên máy giống máy chấm. Cũng vì T4 mà lần chạy
   private trên Kaggle còn lệch với máy chấm ở 3 shop.
6. **Công sức dàn trải.** LoRA, XLM-R, ViT5, ViSoLex, SQL đối chiếu, SQL bỏ phiếu, Qwen 9B, bảng calibration: cuối cùng
   **tất cả đều tắt** trong bản nộp. Mỗi hướng đều được đo cẩn thận (tốt), nhưng hướng nào cũng nằm trong cùng khuôn
   "shop bán hàng" (không giải quyết rủi ro lớn nhất).

Ghi chú công bằng: các trợ lý AI dùng trong dự án (kể cả Claude) cũng đi theo cùng cách đo này, nên cũng không chỉ ra rủi
ro ở mục 2 đủ sớm.

## 3. Bài học, viết thành nguyên tắc

1. **Thứ gì đề đưa vào lúc chạy thì sẽ thay đổi.** Ở đây đó là `rulebook.md`, `README.md` của từng shop,
   `calendar.csv` và dữ liệu. Hệ thống phải *đọc* chúng lúc chạy, không được *chép* nội dung của chúng vào code.
2. **Ngoại suy xu hướng.** Lập bảng so train với public (như mục 1). Thứ gì tăng từ train lên public thì giả định nó còn
   tăng mạnh hơn ở private.
3. **Tổng quát trước, chuyên biệt sau.** Dựng một đường đi tổng quát (chậm hơn, kém chính xác hơn) chạy được với mọi
   loại dữ liệu. Code viết tay cho trường hợp quen chỉ là **lối tắt** cho nhanh và chính xác hơn, không phải con đường
   duy nhất.
4. **Đánh giá phải giống private nhất có thể:**
   - giữ kín theo **nhóm** (cả một ngành, một kiểu file), không chỉ giữ kín từng shop;
   - tự tạo bộ thử **ngoài phân phối**: nhờ LLM sinh shop thuộc ngành mới, viết code tính đáp án, rồi đo hệ thống trên
     đó;
   - thử **đảo luật**: sửa một điều trong rulebook xem hệ thống có đổi theo không.
5. **Leaderboard public chỉ để kiểm tra, không phải để leo.** Đặt hạn mức (ví dụ tối đa 20% bản sửa được lấy từ lỗi
   public). Một tính năng làm public giảm nhẹ nhưng làm hệ thống bền hơn thì cân nhắc giữ.
6. **Môi trường giống máy chấm.** Trước khi bỏ một hướng vì "hết bộ nhớ" hay "quá chậm", thử nó vài giờ trên GPU giống
   máy chấm (thuê theo giờ). Ghi rõ lý do bỏ là *do bản thân hướng đó* hay *do máy mình yếu*.
7. **Mỗi ý tưởng có hạn và tiêu chí dừng.** Trước khi làm, ghi: giả thuyết, chi phí dự kiến, con số nào thì giữ, con số
   nào thì bỏ. Rủi ro lớn nhất của bài (ở đây là "đề mở rộng") phải được làm trước các tinh chỉnh nhỏ.
8. **Chấm có trừ điểm → làm chốt bỏ trống sớm.** (Lần này đã làm tốt.)

## 4. Quy trình tổng thể cho một cuộc thi (checklist theo giai đoạn)

### Giai đoạn 0: đọc đề (ngày 1–2)
- [ ] Đọc hết đề, luật, hướng dẫn nộp (cả file PDF). Ghi lại: định dạng đáp án, cách chấm, giới hạn model, phần cứng và
      thời gian của máy chấm, luật tái lập, mọi mốc hạn.
- [ ] Lập bảng **"cố định / sẽ thay đổi"**: cái gì giống nhau ở mọi bộ, cái gì được đưa vào lúc chạy.
- [ ] Ước lượng ngân sách: số giờ GPU mỗi tuần, thời gian chạy hết bộ test trên máy chấm.

### Giai đoạn 1: hiểu dữ liệu (ngày 2–4)
- [ ] Xem mọi bộ có trong tay (train, public, mẫu…). Lập bảng so sánh như mục 1.
- [ ] Viết **giả thuyết về private**: nó sẽ khác train/public ở đâu? Ghi ra file, xem lại mỗi tuần.

### Giai đoạn 2: bản đơn giản nhất chạy hết đường (tuần 1)
- [ ] Bản đầu tiên chạy từ đầu đến cuối và cho ra file nộp đúng định dạng, dù điểm thấp.
- [ ] Đóng gói nộp thử sớm (Docker, nếu đề yêu cầu) để biết khó khăn kỹ thuật ngay.
- [ ] Dựng bộ đánh giá: chấm điểm ở máy, dữ liệu giữ kín theo nhóm, bộ ngoài phân phối tự tạo.

### Giai đoạn 3: vòng lặp cải thiện
- [ ] Phân tích lỗi theo **lớp lỗi**, không sửa từng câu.
- [ ] Mỗi bản sửa: một test nhỏ + đo trên dữ liệu giữ kín + đo trên bộ ngoài phân phối.
- [ ] Ghi **nhật ký thí nghiệm**: ý tưởng | giả thuyết | chi phí | kết quả | giữ/bỏ. Mỗi tuần hỏi lại: rủi ro lớn nhất
      hiện tại là gì, mình đã làm gì với nó?

### Giai đoạn 4: đóng băng (3 ngày trước hạn)
- [ ] Ngừng thêm tính năng, chỉ sửa lỗi.
- [ ] Chạy bản cuối trên phần cứng giống máy chấm, kiểm thời gian và bộ nhớ (lần này: OOM chỉ lộ ra trên T4).
- [ ] Kiểm tái lập: chạy hai lần, so kết quả.

### Giai đoạn 5: sau cuộc thi
- [ ] Viết rút kinh nghiệm như tài liệu này, khi còn nhớ rõ.

## 5. Bộ câu hỏi tự kiểm trước mỗi quyết định lớn

- Nếu bộ test có loại dữ liệu mình **chưa từng thấy**, hệ thống sẽ làm gì?
- Nếu một luật trong rulebook bị **đảo ngược**, code có tự đổi theo không, hay vẫn làm theo luật cũ?
- Con số "tăng điểm" này đo trên dữ liệu nào? Dữ liệu đó **giống private đến đâu**?
- Hướng này bị bỏ vì **bản thân nó** kém, hay vì **máy mình** yếu?
- Nếu chỉ còn một tuần, mình làm việc gì trước? Việc đó có giảm được rủi ro lớn nhất không?

## 6. Nếu làm lại một bài kiểu DataMate (gợi ý, chưa kiểm chứng)

- **Đường tổng quát làm xương sống:** model đọc README + rulebook + vài dòng mẫu của mọi bảng, viết code (pandas/SQL),
  chạy trong môi trường cách ly, tự kiểm kết quả (chạy vài lần, so kết quả, kiểm đơn vị). Chọn model mạnh nhất vừa giới
  hạn đề (< 15B tham số) và vừa máy chấm (32 GB). Phải **đo** trên máy giống máy chấm trước khi tin.
- **Code viết tay làm lối tắt** cho các khái niệm quen (doanh thu, số đơn…), dùng để đối chiếu và tăng độ chính xác.
- **Giữ chốt bỏ trống**, nhưng đo trên bộ ngoài phân phối để biết nó chặn đúng hay chặn oan.
- Chuẩn bị sẵn bộ thử "ngành mới" và "luật đảo" ngay từ tuần đầu.
