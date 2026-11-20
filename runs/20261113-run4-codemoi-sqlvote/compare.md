# So sánh 2 lần chạy trên 20 câu chung

- **v6**: 300 câu trong file, 300 câu có gold
- **sqlvote**: 20 câu trong file, 20 câu có gold

## Tổng

lần chạy | PA | đúng | sai | bỏ trống | đúng / đã trả lời
---|---|---|---|---|---
v6 | +0.8000 | 18 | 2 | 0 | 90.0%
sqlvote | +0.0000 | 0 | 0 | 20 | 0.0%

## Theo loại đáp án gold (PA / đúng / sai)

loại | số câu | v6 | sqlvote
---|---|---|---|
date | 1 | +1.00 / 1 / 0 | +0.00 / 0 / 0
number | 13 | +0.85 / 12 / 1 | +0.00 / 0 / 0
percent | 5 | +1.00 / 5 / 0 | +0.00 / 0 / 0
unanswerable | 1 | -1.00 / 0 / 1 | +0.00 / 0 / 0

## Theo shop (PA)

shop | số câu | v6 | sqlvote
---|---|---|---|
biz_101 | 4 | +0.50 | +0.00
biz_105 | 4 | +1.00 | +0.00
biz_117 | 4 | +1.00 | +0.00
biz_122 | 4 | +0.50 | +0.00
biz_129 | 4 | +1.00 | +0.00

## Bảng chéo: hàng = v6, cột = sqlvote

 | correct | wrong | abstain
---|---|---|---
correct | 0 | 0 | 18
wrong | 0 | 0 | 2
abstain | 0 | 0 | 0

## Ước lượng khi ghép hai đường (luật cố định, chỉ dùng gold để chấm)

cách ghép | PA | đúng | sai | bỏ trống | đúng / đã trả lời
---|---|---|---|---|---
v6, bỏ trống thì lấy sqlvote | +0.8000 | 18 | 2 | 0 | 90.0%
sqlvote, bỏ trống thì lấy v6 | +0.8000 | 18 | 2 | 0 | 90.0%
chỉ trả lời khi v6 và sqlvote trùng đáp án | +0.0000 | 0 | 0 | 20 | 0.0%

## Câu khác nhau (để phân tích lỗi)

### v6 đúng, sqlvote bỏ trống (18 câu)

- `q_daa477dd5e4a` biz_101 — tháng 6/2026 bán ra bao nhiu kg Nếp cái hoa vàng
  - gold number: 33
  - v6: number: 33
  - sqlvote: (bỏ trống)
- `q_e0aef192cb11` biz_101 — dthu ngày nào cao nhất trong tháng 6 năm 2026?
  - gold date: 2026-06-01
  - v6: date: 2026-06-01
  - sqlvote: (bỏ trống)
- `q_e22420e26cbb` biz_101 — Số kg Nếp cái hoa vàng bán được trong tháng 11/2025 là bao nhiêu?
  - gold number: 39
  - v6: number: 39
  - sqlvote: (bỏ trống)
- `q_ea88d1f6dcfd` biz_129 — check gium cho toi biet dthu thang 9/2025
  - gold number: 1096349500
  - v6: number: 1096349500
  - sqlvote: (bỏ trống)
- `q_ebfba62ad2d4` biz_129 — cua hang ban dc bao nhieu don trong quy 3 nam 2025
  - gold number: 6178
  - v6: number: 6178
  - sqlvote: (bỏ trống)
- `q_ece3c46e24d3` biz_105 — dthu tu dau thang nay den het hom nay tang hay giam bao nhieu % so voi cung ky thang roi do
  - gold percent: 2.83
  - v6: percent: 2.83
  - sqlvote: (bỏ trống)
- `q_ecf144db70a1` biz_129 — Tính đến hết ngày 14/08/2026, khách hàng còn nợ cửa hàng tổng cộng bao nhiêu tiền?
  - gold number: 2854584
  - v6: number: 2854584
  - sqlvote: (bỏ trống)
- `q_ef76bfbc0321` biz_129 — Số đơn bị huỷ trong tháng 4 năm 2026 là bao nhiêu?
  - gold number: 39
  - v6: number: 39
  - sqlvote: (bỏ trống)
- `q_f06ff238b76c` biz_117 — gia ban mot m3 Cat san lap vao ngay 21/06/2025 la bao nhieu z
  - gold number: 240000
  - v6: number: 240000
  - sqlvote: (bỏ trống)
- `q_f07d1a553011` biz_117 — Tháng 8/2025 có bao nhiêu đơn có doanh thu từ 3.300.000 đồng trở lên?
  - gold number: 88
  - v6: number: 88
  - sqlvote: (bỏ trống)
- `q_f1c5c01b78e0` biz_105 — Tháng 2/2026 có mấy đơn có dthu từ 130.000 đồng trở lên?
  - gold number: 385
  - v6: number: 385
  - sqlvote: (bỏ trống)
- `q_f1f68541c1b6` biz_122 — So với tháng liền trước, doanh thu tháng 8 năm 2025 thay đổi bao nhiêu %?
  - gold percent: -10.35
  - v6: percent: -10.35
  - sqlvote: (bỏ trống)
- `q_f1fad9500cbd` biz_122 — Trung bình mỗi đơn tuần trước mang về bao nhiêu doanh thu?
  - gold number: 85165
  - v6: number: 85165
  - sqlvote: (bỏ trống)
- `q_f321dd447d00` biz_105 — cho hoir giá bán một ly cà phê sữa (l) vào ngày 10/06/2025 laf bnhiu
  - gold number: 35000
  - v6: number: 35000
  - sqlvote: (bỏ trống)
- `q_f3d26f111d55` biz_117 — xem giúp tuần rồi, số ddown ca chiều tăng hay giảm bao nhiu % so vs ca sáng
  - gold percent: -55.17
  - v6: percent: -55.17
  - sqlvote: (bỏ trống)
- `q_f4966c224caa` biz_105 — Cho hỏi tháng 3/2026 cửa hàng có bao nhiêu % đơn bị huỷ?
  - gold percent: 2.2
  - v6: percent: 2.2
  - sqlvote: (bỏ trống)
- `q_f4c328691e9b` biz_117 — dthu tu dau thang nay den het hom nay tang hay giam bn % so voi cung ky thang trc
  - gold percent: -32.31
  - v6: percent: -32.31
  - sqlvote: (bỏ trống)
- `q_f5a2e8472196` biz_122 — cho toi biet doanh thu thang 1/2026
  - gold number: 256542200
  - v6: number: 256542200
  - sqlvote: (bỏ trống)
