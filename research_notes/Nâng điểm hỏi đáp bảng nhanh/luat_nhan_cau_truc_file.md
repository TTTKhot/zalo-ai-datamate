# Luật rule-based nhận diện cấu trúc file CSV/Excel lộn xộn (pandas/openpyxl, không model lúc chạy)

Ghi chú chung: ngày truy cập 2026-11-16. Mọi con số là của tác giả bài báo trên tập dữ liệu của họ (open-data CSV của Canada, spreadsheet SAUS/CIUS/GovUK/DeEx...), KHÔNG phải sổ sách tiếng Việt của shop. Tôi đã tải PDF gốc của Pytheas, Strudel, Auto-Tables, SpreadsheetLLM và đọc bằng pdftotext; các bảng số của Strudel bị lỗi layout khi trích nên chỉ ghi những gì đọc rõ. Không mở được: bài DeExcelerator gốc (CIKM 2013), bài Senbazuru gốc, bài Wrangler gốc (chỉ có kết quả tìm kiếm tóm tắt).

## 1. Phát hiện dòng header (có dòng tiêu đề/ghi chú phía trên, header 2+ dòng, merged cells)

### Takeaway
Luật "header hợp lệ" của Pytheas (mọi cột có giá trị khác rỗng và duy nhất; ghép header nhiều dòng bằng cách "prepend" giá trị dòng trên xuống các ô bên dưới/bên phải cho tới ô khác rỗng kế tiếp) là bộ luật đơn giản, đã công bố, dễ cài đặt nhất. Dòng context phía trên header được giả định chỉ có giá trị ở cột đầu. Header là loại dòng khó nhất trong các luật của Pytheas (P/R ≈ 88%), nên cần kiểm tra chéo bằng kiểu dữ liệu body.

### Cited Findings
- Pytheas (VLDB 2020): bảng = Context (tuỳ chọn) + Header (một hay nhiều dòng liên tiếp, có thể phân cấp) + Body (dòng data, có thể xen subheader). Dòng context "thường chỉ có giá trị ở cột đầu tiên". Một số bảng có cột trái làm index nên header của cột đó rỗng; vài cột cuối có thể là cột ghi chú — [Pytheas, VLDB 2020](https://www.vldb.org/pvldb/vol13/p2075-christodoulakis.pdf)
- Luật "header hợp lệ" của Pytheas: mọi cột có giá trị header khác rỗng và duy nhất; ngoại lệ cho phép rỗng: bảng 2 cột thì cột đầu; 3–4 cột thì 1–2 cột đầu; còn lại thì 1–2 cột đầu và/hoặc cuối — [Pytheas, mục 3.3.5](https://www.vldb.org/pvldb/vol13/p2075-christodoulakis.pdf)
- Thuật toán tìm header: tìm dòng data đầu tiên (FDL), rồi quét ngược lên (bỏ dòng trống, tối đa một số dòng không rỗng) tới khi một dòng đơn hoặc một khoảng dòng được ghép lại cho ra header hợp lệ; dừng ngay khi tìm được. Header nhiều dòng: với mỗi giá trị khác rỗng ở dòng i, ghép (prepend) vào các ô dưới nó và sang phải tới ô khác rỗng kế tiếp (ví dụ "2012" + "Revenue" + "Net" thành "2012 Revenue Net"). Dòng cuối của header mà mọi giá trị nằm trong ngoặc, hoặc chỉ ô đầu khác rỗng, bị coi là "header metadata", không ghép — [Pytheas, mục 3.3.5, Hình 6](https://www.vldb.org/pvldb/vol13/p2075-christodoulakis.pdf)
- Dự phòng: nếu không có header hợp lệ, nới điều kiện duy nhất và tìm một dòng đơn có giá trị ở mọi cột; chỉ cho phép nới cho bảng đầu tiên của file để tránh nhận footnote thành header — [Pytheas, mục 3.3.5](https://www.vldb.org/pvldb/vol13/p2075-christodoulakis.pdf)
- Luật loại header (consequent N=không phải data) của Pytheas: dòng toàn snake_case/camelCase; có từ khoá tổng hợp ở ô không phải ô đầu; ô đầu bắt đầu và kết thúc bằng ngoặc và các ô khác rỗng; giá trị chữ lặp theo khoảng đều (kiểu nhãn nhóm) — [Pytheas, luật LR3–LR6](https://www.vldb.org/pvldb/vol13/p2075-christodoulakis.pdf)
- Chọn dòng data đầu tiên không phải "dòng D đầu tiên" mà là vị trí tối đa hoá độ khớp của chuỗi dòng; tác giả báo tiêu chí này tốt hơn cách ngây thơ (không nêu số riêng ở đoạn đã đọc) — [Pytheas, mục 3.3.4](https://www.vldb.org/pvldb/vol13/p2075-christodoulakis.pdf)
- Số đo: tìm đúng bảng (table body) P/R = 95.9%/95.7% trên 2000 file Canada, so với ≈89.6%/81.3% của các phương pháp trước; gán nhãn đúng mọi dòng của file 95.6% so với tối đa 86.9% — [Pytheas, VLDB 2020](https://www.vldb.org/pvldb/vol13/p2075-christodoulakis.pdf)
- Theo từng lớp dòng (Canadian2K, trung bình 10-fold): data P/R ≈ 99.9/99.9; header P/R ≈ 88.1/88.7; subheader ≈ 82.9/92.8; context ≈ 91.6/88.7; footnote ≈ 90.0/60.1 (khoảng tin cậy rộng, ±10–16 cho footnote). Heuristic CSV "tối đa 2 dòng header, dòng đầu file có 0/1 dấu phân cách là comment" cho data top-only chỉ P ≈ 67.9% — [Pytheas, Bảng 4](https://www.vldb.org/pvldb/vol13/p2075-christodoulakis.pdf)
- Pytheas đánh giá "nghiêm": một dòng sai trong bảng lớn là cả bảng sai. Kết quả quốc tế (2511 file thêm, 4 nước): F-measure tìm bảng > 95.7% kể cả khi chỉ train ở một nước — [Pytheas, tóm tắt](https://www.vldb.org/pvldb/vol13/p2075-christodoulakis.pdf)
- Dữ liệu 1798 file khảo sát: ~8% bảng có footnote; ít bảng không có header; file Mỹ >91% không có header (khác nhau theo nguồn) — [Pytheas, mục 4.1](https://www.vldb.org/pvldb/vol13/p2075-christodoulakis.pdf)
- Strudel (EDBT 2021, Jiang/Vitagliano/Naumann): các lớp metadata/header/group/data/derived/notes; đặc trưng gồm EmptyCellRatio, NumericalCellRatio, StringCellRatio, LinePosition, DataTypeMatching (so kiểu với dòng không rỗng gần nhất), EmptyNeighboringLines, CellLengthDifference. Tác giả nhận xét Pytheas yếu ở lớp thiểu số (group, derived) vì luật không hợp với dataset khác SAUS; group của Pytheas bị ràng buộc "chỉ ô trái cùng khác rỗng, nằm giữa các dòng data" — [Strudel paper](https://hpi.de/oldsite/fileadmin/user_upload/fachgebiete/naumann/publications/PDFs/2021_jiang_structure.pdf)
- openpyxl: `ws.merged_cells.ranges` liệt kê từng vùng gộp; chỉ ô trên-trái giữ giá trị, các ô còn lại None (pandas cho NaN). Pandas khi đọc header nhiều dòng/index_col tự forward-fill để round-trip với `to_excel(merged_cells=True)`; docstring khuyên dùng `set_index` sau khi đọc thay vì `index_col` nếu không muốn fill — [pandas io/excel/_base docstring](https://xorbits-fork.readthedocs.io/en/latest/_modules/pandas/io/excel/_base.html); tóm tắt các cách làm: [Statology](https://www.statology.org/pandas-read-excel-merged-cells/)
- SpreadsheetLLM (arXiv 2024-07) mô tả heuristic neo cấu trúc: liệt kê "dòng/cột có độ lệch" (khác biệt giá trị, merged cells, viền, màu), lọc ứng viên theo tỉ lệ số/chữ trong mỗi dòng, dùng tỉ lệ ô chữ hay ô dạng năm/ngày để phát hiện header ứng viên. Riêng heuristic này chỉ đạt F1 46.3% (EoB-0) và 65.0% (EoB-2) trên bộ kiểm tra của họ vì khó phân biệt header/title/note; mở rộng thêm k dòng/cột lân cận quanh neo thì phủ tốt hơn (k=4 cho F1 tổng 0.759 khi dùng với GPT4 fine-tuned) — [SpreadsheetLLM](https://arxiv.org/pdf/2407.09025)

### Inferences
- Suy luận: cho sổ sách shop, cài luật Pytheas theo thứ tự: (1) ứng viên "dòng data đầu" = dòng đầu tiên mà các ô cùng cột, nhìn 3–5 dòng bên dưới, có chung kiểu (số/ngày/chữ); (2) quét ngược lên tìm header duy nhất, khác rỗng; (3) nếu dòng trên chỉ có vài ô khác rỗng và nằm trong các merged range ngang (openpyxl `merged_cells`) thì ghép làm nhãn nhóm. Dùng `merged_cells` của openpyxl là thông tin mà CSV không có, nên đáng tin hơn các luật giá trị.
- Suy luận: tên cột ghép "nhóm + con" nên giữ cả hai (như Pytheas "2012 Revenue Net"), để hai cột con trùng tên ở hai nhóm khác nhau (ví dụ "SL" dưới "Tháng 1" và "Tháng 2") không đụng nhau; đây là cách duy nhất bảo đảm tính duy nhất của header.
- Suy luận (chưa có số đo công bố): ô header-lẫn-ghi-chú kiểu "(đơn vị: đồng)" nằm dưới header là loại "header metadata" của Pytheas, tránh ghép.
- Failure mode: header có cột trống hợp lệ (cột STT không tên) làm luật "mọi cột khác rỗng" từ chối header đúng; cần ngoại lệ cột đầu/cuối rỗng như Pytheas. File sạch mà cột đầu là dữ liệu chữ không phải header (không có header) sẽ bị luật "quét lên" nuốt dòng data đầu thành header — chỉ chấp nhận nếu dòng đó vi phạm kiểu của body.
- Failure mode: luật SpreadsheetLLM về "chữ/số" kém khi header là số (năm "2023", "1","2","3" là số ngày) — header dạng số bị coi là data.

### Gaps
- Không tìm được số chính xác riêng cho "header nhiều dòng" ngoài mức header ≈ 88% của Pytheas; không có số cho luật dựa trên `merged_cells` của openpyxl (là luật suy luận).
- Không mở được bài "Table header detection" riêng (không tìm ra bài cụ thể phù hợp trong lần tìm kiếm).

## 2. Dòng không phải data trong body (tổng phụ, tổng cộng, ghi chú, dòng trống, tiêu đề nhóm)

### Takeaway
Hai luật có bằng chứng: (a) từ khoá "total/sum…" ở ô đầu của dòng (Pytheas LR1, Strudel anchor) và (b) kiểm tra số học "ô bằng tổng các ô phía trên/cùng hàng" (Strudel derived cell detection). Dòng "derived" là lớp khó nhất ở cả hai bài: hay bị nhầm thành data (Strudel) và recall của footnote thấp (Pytheas ≈ 60%).

### Cited Findings
- Pytheas có 27 luật cột nhãn D (data) và 22 luật cột nhãn N, cộng 4 luật dòng N và 1 luật dòng D theo bảng tổng hợp; nhóm "keyword" là các luật dùng từ khoá do họ chọn từ mẫu khảo sát — [Pytheas, Bảng 3](https://www.vldb.org/pvldb/vol13/p2075-christodoulakis.pdf)
- Luật dòng: LR1 "giá trị đầu dòng chứa từ khoá tổng hợp" thì nghiêng D (data/aggregation vẫn thuộc thân bảng); LR2 "có ô null-equivalent trong dòng" thì nghiêng D; LR7 "giá trị đầu khớp từ khoá footnote và từ ô thứ 3 trở đi rỗng" thì N — [Pytheas, mục 3.2.3](https://www.vldb.org/pvldb/vol13/p2075-christodoulakis.pdf)
- Subheader (dòng nhãn nhóm trong thân bảng) của Pytheas: mọi ô trừ ô trái cùng đều rỗng, VÀ (a) dòng đó bị chấm N nhưng dòng kế tiếp lại là D, hoặc (b) giá trị ô đó xuất hiện ở một ô sau trong cùng cột kèm từ khoá tổng hợp (ví dụ nhãn "Nhóm A" và dòng "Tổng Nhóm A"). Subheader được giữ trong thân bảng, không làm kết thúc bảng — [Pytheas, mục 3.3.4](https://www.vldb.org/pvldb/vol13/p2075-christodoulakis.pdf)
- Điểm cuối bảng: dòng đầu tiên i mà độ tin N > D (trừ khi là subheader). Footnote = các dòng không-data liền kề đáy bảng — [Pytheas, mục 3.3.4–3.3.6](https://www.vldb.org/pvldb/vol13/p2075-christodoulakis.pdf)
- Strudel định nghĩa derived cell: ô tổng hợp giá trị các ô số khác cùng bảng, thường nằm ở dòng trên/dưới cùng hoặc cột trái/phải cùng của vùng data. Thuật toán phát hiện (Algorithm 2): ô chứa từ khoá tổng hợp là "neo"; chỉ các ô số cùng hàng/cột với neo là ứng viên; cộng dồn từng dòng lên trên (rồi xuống dưới, rồi cùng cách cho cột) và kiểm tra tổng có gần bằng ứng viên trong sai số delta, kèm ngưỡng coverage; chỉ xét hàm sum (và mean theo quan sát: sum và mean là hai hàm chiếm ưu thế) — [Strudel, mục 5.5](https://hpi.de/oldsite/fileadmin/user_upload/fachgebiete/naumann/publications/PDFs/2021_jiang_structure.pdf). Giá trị cụ thể của delta/coverage bị mất khi trích PDF, không ghi được.
- Kết quả Strudel: "xác định dòng derived là nhiệm vụ khó nhất ở mọi dataset"; chúng chủ yếu bị phân nhầm thành data vì giống data về kiểu dữ liệu và vị trí; khoảng 11.4% dòng derived của GovUK bị coi là header khi chúng nằm giữa header và data và cách bằng dòng trống. Khoảng 2/3 ô derived của CIUS bị coi là data vì file dùng lược đồ cố định không có từ khoá. Trên Bảng 6, F1 dòng derived chỉ khoảng 0.34–0.83 tuỳ dataset theo cách đọc của tôi (bảng bị rối layout; coi là xấp xỉ) — [Strudel](https://hpi.de/oldsite/fileadmin/user_upload/fachgebiete/naumann/publications/PDFs/2021_jiang_structure.pdf)
- Strudel còn nhận xét: lỗi của lớp thiểu số (non-data) thường bị dự đoán thành "data" vì data chiếm đa số — [Strudel, mục 6.3.1](https://hpi.de/oldsite/fileadmin/user_upload/fachgebiete/naumann/publications/PDFs/2021_jiang_structure.pdf)
- Footnote Pytheas: P ≈ 90%, R ≈ 60% (CI rộng) — [Pytheas, Bảng 4](https://www.vldb.org/pvldb/vol13/p2075-christodoulakis.pdf)

### Inferences
- Suy luận: để thực dụng, loại dòng khỏi body theo 3 nhóm luật độc lập, mỗi luật "ghi cờ" chứ không xoá ngay; chỉ xoá khi ≥ 2 cờ cùng bật hoặc 1 cờ mạnh:
  1. Cờ từ khoá tổng hợp (tổng, cộng, total, sum, tổng cộng, thành tiền…) ở ô văn bản đầu dòng (không ở cột mô tả sản phẩm giữa dòng). Dùng danh sách từ khoá chung tiếng Việt, không gắn shop.
  2. Cờ số học: ô số của dòng ≈ tổng các ô cùng cột phía trên liên tục (từ đầu bảng hoặc từ dòng tổng trước), sai số tương đối ~1e-6 hoặc tuyệt đối nhỏ; đây là cờ chính xác nhất (hiếm khi sai dương) nhưng recall thấp nếu không có từ khoá (Strudel: bỏ sót khi lược đồ cố định).
  3. Cờ cấu trúc: dòng chỉ có ô cột đầu khác rỗng (hoặc chỉ 1–2 ô) trong khi cột khoá (mã đơn, tên hàng) rỗng, đặc biệt cạnh dòng sau có đủ giá trị; hoặc dòng ngoài cùng đáy toàn text (ghi chú).
- Suy luận: dòng phụ trong đơn (voucher, phí ship) không có từ khoá tổng hợp, nên cần luật riêng: cột "tên hàng" chứa từ khoá phi-hàng (voucher, giảm giá, phí vận chuyển/ship, freeship…) và/hoặc số âm. Nên coi đây là bảng "dòng phụ phí" riêng, không xoá, để câu hỏi về phí ship vẫn trả lời được.
- Failure mode (làm hỏng file sạch): tên hàng thật chứa từ khoá (ví dụ "Combo cộng 2", "Tổng hợp vitamin") → chỉ áp luật từ khoá cho ô đầu dòng hoặc khi các cột khoá còn lại rỗng. Luật số học có thể trùng ngẫu nhiên khi dữ liệu nhỏ (hai dòng 0): yêu cầu tổng ≥ 3 dòng và giá trị khác 0.
- Failure mode: xoá nhầm dòng tổng phụ là đúng với ledger, nhưng xoá nhầm "dòng đầu đơn" (khi giá trị đơn chỉ nằm ở dòng đầu) là thảm hoạ. Nên kiểm tra trên toàn cột: sau khi xoá, tổng cột còn lại phải ≈ giá trị dòng tổng (kiểm tra đóng) — nếu khớp thì chắc chắn.

### Gaps
- Không tìm được số P/R cho riêng luật "từ khoá tổng" (chỉ có ablation tổng thể trong Pytheas, Hình 12, chưa đọc kỹ).
- Không có nguồn về từ khoá tổng hợp tiếng Việt; danh sách từ khoá trên là đề xuất.

## 3. "Ô trống nghĩa là giống dòng trên" (merged cell hay nhóm trực quan): khi nào an toàn để forward-fill

### Takeaway
Nguồn công bố cho thấy forward-fill được dùng như một toán tử riêng (Auto-Tables `ffill` với tham số start_idx/end_idx, tức là chỉ áp cho một khoảng cột chỉ định, chính xác tham số đạt 0.875–1.0), và pandas tự ffill chỉ cho index_col/header. Không có nguồn nào công bố luật "khi nào ffill an toàn"; các luật dưới đây là suy luận.

### Cited Findings
- Auto-Tables (VLDB 2023): 8 toán tử gồm stack, wide-to-long, transpose, pivot, explode, ffill, subtitles. `ffill` có tham số `start_idx`, `end_idx` và mô tả "fill structurally empty cells in tables"; `subtitles` (copy, ffill, del) chuyển tiêu đề phụ thành một cột — [Auto-Tables, Bảng 1](https://arxiv.org/pdf/2307.14565)
- Bộ test 244 trường hợp thực; hệ thống chuyển thành công 75% test ở top-3; độ chính xác tham số top-1 ở Bảng 10 từ 0.875 tới 1.0 (ffill cũng là một trong các cột được dự đoán start/end idx; tôi không tách chính xác số riêng cho ffill vì layout bảng bị rối) — [Auto-Tables](https://arxiv.org/pdf/2307.14565)
- Phát biểu quan trọng của bài: tham số phải đoán đúng chính xác, "cannot be off"; và thứ tự ffill với stack/wide-to-long ảnh hưởng kết quả — [Auto-Tables](https://arxiv.org/pdf/2307.14565)
- Wrangler (CHI 2011): có nhóm biến đổi "positional" gồm điền dữ liệu từ ô lân cận; gợi ý biến đổi được xếp hạng theo dữ liệu người dùng chọn và lọc biến đổi "suy biến" không có tác dụng; người dùng xem preview trước khi nhận. Tôi không tìm ra luật quyết định khi nào gợi ý fill — [Wrangler, CHI 2011 (UW)](https://idl.uw.edu/papers/wrangler) (tóm tắt từ kết quả tìm kiếm, chưa đọc toàn bài)
- pandas khi đọc Excel: ô gộp chỉ có giá trị ở trên-trái, còn lại NaN; docstring nói pandas forward-fill các giá trị thiếu của index/header để round-trip với `to_excel(merged_cells=True)`, và khuyên dùng `set_index` sau khi đọc nếu không muốn fill — [pandas io/excel/_base](https://xorbits-fork.readthedocs.io/en/latest/_modules/pandas/io/excel/_base.html)
- Pytheas ghép header phân cấp bằng quy tắc "giá trị trên áp xuống các cột tới ô khác rỗng kế tiếp" (một dạng forward-fill ngang giới hạn bởi ô khác rỗng) — [Pytheas, mục 3.3.5](https://www.vldb.org/pvldb/vol13/p2075-christodoulakis.pdf)
- SpreadsheetLLM nhận ra các ô cùng giá trị/ô gộp là "dư thừa" khi mã hoá (inverted index gộp ô cùng giá trị); đây là về nén, không phải chuẩn hoá — [SpreadsheetLLM](https://arxiv.org/pdf/2407.09025)

### Inferences
Luật suy luận để quyết định ffill cột (mỗi điều kiện phải đủ, tính trên toàn cột/toàn sheet, không từng ô):
1. Ứng viên cột: cột là "khoá/thuộc tính cấp đơn" (mã đơn, ngày, tên khách, kênh bán, phương thức thanh toán…) — xác định bằng tên cột chuẩn hoá hoặc kiểu (chuỗi/ngày). KHÔNG ffill cột số lượng/đơn giá/thành tiền của dòng hàng (blank có thể là 0 hay thiếu).
2. Mẫu "khối": các ô rỗng phải nằm liên tục thành khối ngay sau một ô khác rỗng (mẫu `X, _, _, Y, _`) và dòng đầu của mỗi khối có đủ giá trị ở các cột khoá khác. Nếu trống nằm rải rác (không liền sau giá trị) thì là thiếu dữ liệu thật, không ffill.
3. Tỉ lệ rỗng của cột nằm trong khoảng hợp lý (ví dụ 20–90%); cột rỗng gần 0% hoặc rỗng gần 100% đều không ffill.
4. Dòng đầu bảng không được rỗng ở cột đó (nếu rỗng thì không có giá trị để điền); không ffill xuyên qua dòng tổng/dòng phụ (ngắt tại dòng đã bị gắn cờ non-data hoặc dòng toàn rỗng).
5. Kiểm tra đóng: sau ffill, đếm số "nhóm" của khoá đơn (mã đơn) theo hai cách (khối liên tục vs. giá trị duy nhất); nếu một mã đơn xuất hiện ở hai khối không liền nhau thì có sự cố, giữ nguyên (không fill) và gắn cờ.
6. Nếu cột đã được Excel gộp ô (openpyxl `merged_cells` bao phủ đúng các ô rỗng dọc) thì độ tin cậy cao nhất: fill chính xác theo vùng gộp, không dùng ffill toàn cột.
- Failure mode: ffill ngày mà dòng trống do nhập sót sẽ gán sai ngày cho đơn; ffill cột "ghi chú" sẽ nhân ghi chú ra mọi dòng; ffill qua ranh giới sheet/tháng khi nối nhiều sheet (phải ffill trong từng sheet trước khi nối).
- Gợi ý kiểm thử: lấy bảng sạch, chọn cột khoá cấp đơn, "kiểu Excel hoá": giữ giá trị ở dòng đầu mỗi đơn, xoá các dòng sau; phải khôi phục 100%. Phép thử ngược (bảng sạch không có dòng lặp): cột không có mẫu khối thì luật không được fill bất cứ ô nào.

### Gaps
- Không tìm được nguồn công bố nêu luật quyết định ffill an toàn của Wrangler/Foofah; Foofah (chương trình tổng hợp theo ví dụ, VLDB 2017) không được đọc trong lần này. TableSense chưa mở.

## 4. Nhiều bảng trong một sheet; một bảng trải trên nhiều sheet/file

### Takeaway
Luật đơn giản (dòng/cột trống, dòng "lệch" biên) đã được dùng nhưng độ chính xác tự thân thấp (SpreadsheetLLM heuristic 46–65% F1 cho ranh giới bảng); phần ghép Pytheas có luật gộp hai bảng liền nhau nếu cùng số cột. Ghép sheet qua "cùng tập header chuẩn hoá" không có số công bố; là luật suy luận.

### Cited Findings
- Pytheas: nếu phát hiện hai bảng liền nhau và bảng sau không có header, mà số cột bằng nhau thì gộp — [Pytheas, mục 3.3](https://www.vldb.org/pvldb/vol13/p2075-christodoulakis.pdf)
- Pytheas chỉ xử lý bảng xếp dọc trong CSV (không xét bảng cạnh nhau theo chiều ngang); giới hạn đầu vào 25 cột trái nhất để tăng tốc — [Pytheas, mục 4](https://www.vldb.org/pvldb/vol13/p2075-christodoulakis.pdf)
- Heuristic CSV của Mitlöhner (so sánh trong Pytheas): "dòng đầu có 0 hoặc 1 dấu phân cách là comment; nhiều bảng được tìm khi số dấu phân cách khác nhau"; kết quả data top-only kém (P ≈ 67.9% so với Pytheas 97.4%) — [Pytheas, Bảng 4 và mục 4.2](https://www.vldb.org/pvldb/vol13/p2075-christodoulakis.pdf)
- SpreadsheetLLM Phụ lục C: ứng viên ranh giới bảng = tổ hợp 2 dòng bất kỳ (trên/dưới) và 2 cột (trái/phải) từ các dòng/cột "mất cân bằng" (chữ, merge, viền, màu, font); lọc bằng tỉ lệ số/chữ trong từng ranh giới; khi hai ứng viên chồng nhau thì chọn theo vị trí tương đối và sự hiện diện header. Heuristic thuần đạt F1 46.3% (EoB-0) / 65.0% (EoB-2) — [SpreadsheetLLM](https://arxiv.org/pdf/2407.09025)
- Mô hình học (TableSense-CNN) được SpreadsheetLLM nhắc là mốc so sánh; SpreadsheetLLM tuyên bố cải thiện 12.3% so với nó, F1 78.9% với model fine-tuned (không phải rule-based; ghi để so thang) — [SpreadsheetLLM](https://arxiv.org/pdf/2407.09025)
- Strudel nêu rõ "bảng trong verbose CSV thường bị tách thành nhiều đoạn, mỗi đoạn là một nhóm với group header" — [Strudel](https://hpi.de/oldsite/fileadmin/user_upload/fachgebiete/naumann/publications/PDFs/2021_jiang_structure.pdf)

### Inferences
- Suy luận: một sheet = nhiều bảng khi có ≥ 2 dòng liên tiếp hoàn toàn rỗng (hoặc 1 dòng rỗng + một dòng mới trông như header: toàn chuỗi, duy nhất, khác rỗng, kế đó là dòng có kiểu khác). Với tệp của chủ shop, một dòng trống đơn lẻ giữa các đơn rất phổ biến, nên KHÔNG tách bảng chỉ vì một dòng trống; chỉ tách khi dòng sau trống có header-like lặp lại hoặc số cột khác hẳn.
- Suy luận: luật "union-compatible": hai sheet cùng bảng nếu tập header chuẩn hoá (bỏ dấu/hoa thường/khoảng trắng) giống nhau ≥ ~80% Jaccard và thứ tự cột tương tự; với các sheet tháng, kiểm tra thêm tên sheet khớp mẫu tháng/năm. Sheet có header khác hẳn (bảng tra cứu viết tắt) hai cột ngắn: tách riêng thành bảng tra, nếu cột 1 là mã ngắn và cột 2 là diễn giải dài.
- Suy luận: khi ghép nhiều sheet cần thêm cột nguồn (tên sheet) và chạy mọi bước chuẩn hoá (ffill, dòng phụ, STT) TRONG từng sheet trước khi nối; STT khởi động lại mỗi sheet là bằng chứng ủng hộ ghép, không dùng làm khoá.
- Failure mode: bảng chủ shop có cột phụ ghi chú nằm sát bên phải bảng (cách một cột trống) bị luật "cột trống là biên" tách mất; sheet tổng hợp/báo cáo đầu workbook có thể có header giống hệt sheet tháng nhưng là bảng tổng, ghép vào sẽ đếm đôi (kiểm tra: tổng cột sheet đó ≈ tổng các sheet khác).

### Gaps
- Không tìm được số chính xác riêng cho "ghép sheet theo header chuẩn hoá"; không có nghiên cứu công bố được đọc.
- Chưa mở TableSense (AAAI 2019) để lấy số cho CNN so với luật; chỉ có số thứ cấp qua SpreadsheetLLM.

## 5. Phân tích số/ngày theo ngữ cảnh địa phương (dấu thập phân, ngày serial, ngày dạng text, số dạng text)

### Takeaway
Quyết định theo cả cột chứ không theo ô: pandas/dateutil `dayfirst` chỉ là "ưu tiên", có thể phân tích cùng một cột theo hai kiểu khác nhau; dùng `format=` rõ ràng sau khi suy ra quy ước từ các ô không nhập nhằng (ví dụ ngày > 12). Ngày Excel là số serial tính từ 1899-12-30 (hệ 1900), có hệ 1904; openpyxl có thể nhận nhầm số thành ngày qua định dạng.

### Cited Findings
- pandas: `dayfirst=True` không nghiêm ngặt, chỉ ưu tiên; ví dụ `pd.to_datetime(["31/12/2014","10/03/2011"])` đọc phần tử đầu theo day-first, phần tử sau không (vì dateutil bỏ qua ưu tiên khi day-first không cho ngày hợp lệ) — [pandas issue 12585](https://www.github.com/pandas-dev/pandas/issues/12585) (và [pandas.to_datetime docs](https://pandas.pydata.org/docs/reference/api/pandas.to_datetime.html))
- pandas 2.x có `format="mixed"` xử lý theo từng phần tử; tài liệu cảnh báo rủi ro, nên dùng kèm dayfirst — [pandas.to_datetime docs](https://pandas.pydata.org/docs/reference/api/pandas.to_datetime.html)
- openpyxl: mặc định hệ ngày 1900 (serial 1 = 1900-01-01), có hệ 1904; hàm `from_excel` dùng epoch `1899-12-30`; có hành vi riêng cho tháng 1–2/1900 — [openpyxl: Dates and Times](https://openpyxl.readthedocs.io/en/3.1/datetime.html)
- openpyxl nhận nhầm định dạng: format chứa chữ "H" (ví dụ ETH) bị coi là ngày làm số 3 thành 3/1/1900 — [openpyxl issue 1413](https://foss.heptapod.net/openpyxl/openpyxl/-/issues/1413)
- pandas: đổi engine xlrd sang openpyxl làm thay đổi cách đọc ngày (xlrd bỏ phần ngày cho giá trị 0–1) — [kết quả tìm kiếm tóm tắt về pandas issue, chưa đọc trang gốc](https://pandas.pydata.org/docs/reference/api/pandas.to_datetime.html); mức độ tin cậy trung bình
- Đọc ép kiểu chuỗi để không mất định dạng: `read_excel(..., converters={'Date': str})` là mẹo cộng đồng, không phải hành vi tài liệu hoá — [Stack Overflow qua kiwix](https://kaweah.freedombox.rocks/kiwix/content/stackoverflow.com_en_all_2023-11/questions/74827913/pandas-converts-my-date-string-value-in-date-column-to-an-integer)
- Pytheas dùng chữ ký ký tự (A/D/S/dấu câu) và "pattern chung tiền tố" của các ô cùng cột để phát hiện ô lệch kiểu — một cách kiểm thuần kiểu theo cột dùng được cho số/ngày — [Pytheas, mục 3.2](https://www.vldb.org/pvldb/vol13/p2075-christodoulakis.pdf)
- CleverCSV (cho CSV; không dùng cho xlsx): phát hiện dialect (dấu phân cách, quote, escape) bằng "data consistency measure" gồm điểm pattern và điểm type; tác giả báo ~97% độ chính xác, +21% trên CSV bất thường so với csv.Sniffer. Một benchmark độc lập (P-CSVsniffer) báo thấp hơn (72.96% bảng tổng, 84.25% trên file không lỗi khi đọc 6144 ký tự) nhưng không rõ metric — [CleverCSV docs/tóm tắt](https://tessl.io/registry/tessl/pypi-clevercsv); [P-CSVsniffer](https://github.com/ws-garcia/P-CSVsniffer). Ghi chú: 97% là con số tác giả, tôi chưa đọc bài gốc.

### Inferences
Luật suy luận để chọn quy ước theo cột (đều chạy trên TOÀN cột, rồi áp cho mọi ô):
1. Số dạng text: gỡ ký tự không số/khoảng trắng (₫, đ, VND, nbsp); nhận diện hậu tố `k`, `tr`/`triệu`, `nghìn` chỉ khi tỉ lệ ô trong cột có hậu tố (hoặc đều là dạng số + hậu tố) ≥ ngưỡng; một cột không được trộn đơn vị lệch (kiểm tra thang: sau chuyển đổi, trung vị gần các cột cùng loại).
2. Dấu thập phân: nếu có ô chứa cả `.` và `,` thì dấu cuối cùng là thập phân; nếu mọi ô có đúng một loại dấu và mọi nhóm sau dấu có đúng 3 chữ số (`1.234`, `12.345.678`) thì đó là phân cách hàng nghìn; nhóm sau dấu có 1–2 chữ số (hoặc ≠ 3) thì là dấu thập phân. Giá trị đơn lẻ "1.234" là nhập nhằng — quyết theo cột (đa số theo luật trên) không theo ô; với tiền VND (thường là số nguyên lớn) mặc định là phân cách nghìn.
3. Ngày text: thử các định dạng cố định (`%d/%m/%Y`, `%m/%d/%Y`, `%Y-%m-%d`, `%d-%m`, `%d/%m`); chọn quy ước mà TẤT CẢ ô không rỗng đều parse được; nếu có ô có số thứ nhất > 12 thì loại m/d; nếu cả hai đều thoả (mọi ô ≤ 12) thì mặc định d/m (Việt Nam) và gắn cờ độ tin thấp. Không dùng `dayfirst=` đơn lẻ vì nó "ưu tiên" chứ không ép (xem trên).
4. Ngày thiếu năm: chỉ gán năm từ tên sheet/tên file khi tên khớp mẫu năm 4 chữ số hoặc `tháng/năm` rõ ràng; trường hợp cột ngày có tháng giảm dần (12 → 1) trong một sheet thì cảnh báo năm có thể đổi giữa chừng. Kiểm tra: ngày sau khi gán năm phải nằm trong cùng tháng với tên sheet nếu sheet là sheet tháng.
5. Serial Excel: ô kiểu `datetime` do openpyxl trả về đã được đổi; ô số trong khoảng ~ 36500–60000 ở cột mà phần lớn ô khác là ngày thì coi là serial; kiểm tra `date_1904` trước (`wb.epoch`), và không dùng số nhỏ (<60) như ngày.
6. Cột kiểu hỗn hợp (một phần datetime thật, một phần text): chuẩn hoá thành một quy ước chung theo quyết định cột ở bước 3, báo cờ nếu tỉ lệ ô không parse được > ~2%.
- Failure mode: cột mã đơn dạng số (`1.234`) bị đọc là số thập phân; cột mã sản phẩm "1,5" hay kích cỡ; cột phần trăm; chữ `k` trong tên hàng (không phải ô số). Đọc xlsx nên dùng giá trị thực của ô (openpyxl `data_only=True` cho công thức; kiểm tra `cell.number_format`), không dùng giá trị hiển thị.
- Kiểm thử bằng nhiễu: từ bảng sạch, đổi 30–100% ô tiền thành chuỗi `"1.234.567"`, `"1,234,567"`, `"1234k"`, `"1,5tr"`, đổi ngày thành `d/m/Y`, `m/d/Y` (chỉ khi ngày > 12 để có đáp án), serial; thuật toán phải khôi phục 100% hoặc từ chối (cờ), không được ra giá trị sai im lặng.

### Gaps
- Không tìm được nguồn công bố cho các quy ước tiếng Việt cụ thể (`k`, `tr`); luật trên đều là suy luận.
- Chưa kiểm chứng trên pandas bản mới nhất (2026) việc `to_datetime` có đổi hành vi suy đoán định dạng; nên chạy thử trên bản cài trong Docker.

## 6. Bộ kiểm tra "structure sanity" và checklist luật xếp hạng

### Takeaway
Các bài công bố dùng cùng vài bất biến: số cột không đổi, kiểu thuần theo cột, không có chuỗi giống header trong thân bảng, số dòng/cột hợp lý, "độ phủ" aggregation. Bất biến mạnh nhất để chặn lỗi thảm hoạ là kiểm tra đóng (tổng cột sau khi xoá dòng tổng khớp với dòng tổng). Bảng xếp hạng dưới đây là suy luận từ bằng chứng ở trên, không phải kết quả công bố.

### Cited Findings
- Pytheas dựa trên "column-value coherency": cell và ngữ cảnh cột có chung chữ ký (cả chữ số, cùng kiểu chữ hoa/thường, độ dài ô > 30% độ dài tối thiểu ngữ cảnh, giá trị lặp trong cột) là bằng chứng data; vi phạm là bằng chứng không phải data — [Pytheas, luật CR1–CR6](https://www.vldb.org/pvldb/vol13/p2075-christodoulakis.pdf)
- Pytheas báo "độ tin cậy" của ranh giới bảng (cFDL, hàm của độ tin các dòng lân cận hai phía ranh giới) và dùng nó để chọn file cần gán nhãn tay (active learning) — [Pytheas, mục 3.3.4](https://www.vldb.org/pvldb/vol13/p2075-christodoulakis.pdf); đây là mẫu để làm "cờ độ tin cậy": khi thấp thì bỏ trống câu hỏi.
- Strudel đo các đặc trưng kiểm sanity: tỉ lệ ô rỗng, tỉ lệ ô số/chữ, khớp kiểu với dòng không rỗng liền kề (Bhattacharyya trên histogram độ dài ô), số dòng rỗng liền kề, độ phủ derived — [Strudel](https://hpi.de/oldsite/fileadmin/user_upload/fachgebiete/naumann/publications/PDFs/2021_jiang_structure.pdf)
- Ablation của Pytheas (Hình 12) có kết quả khi bỏ từng nhóm luật; chưa đọc chi tiết — [Pytheas](https://www.vldb.org/pvldb/vol13/p2075-christodoulakis.pdf)

### Inferences
Bộ kiểm thử sanity tối thiểu (mỗi mục có thể làm trong < 30 phút), chạy trên mỗi sheet/bảng sau chuẩn hoá:
1. Số cột thân bảng không đổi và ≥ 2; không có cột tên rỗng/trùng sau chuẩn hoá (trừ cột index chấp nhận).
2. Thuần kiểu theo cột: ≥ 95% ô không rỗng cùng một kiểu (số/ngày/chuỗi); cột vi phạm bị gắn cờ không dùng.
3. Không có chuỗi giống header (giá trị bằng tên cột hoặc ≥ 70% ô là chuỗi giống tên cột khác) trong thân bảng: header lặp lại giữa trang.
4. Khoá nhóm (mã đơn, STT): sau chuẩn hoá, STT đơn điệu tăng trong một sheet (khởi động lại giữa sheet = sheet mới/bảng mới); mã đơn xuất hiện thành các khối liền nhau.
5. Kiểm tra đóng: nếu có dòng tổng bị xoá, tổng cột còn lại ≈ dòng tổng (sai số ~1e-6); nếu không khớp thì giữ dòng, gắn cờ.
6. Tính hợp lý số: thành tiền ≈ số lượng × đơn giá (nếu cả 3 cột có); ngày nằm trong khoảng hợp lý của tên sheet/file; không có số âm lẽ ra dương (ngoài dòng giảm giá/hoàn tiền).
7. Số dòng sau chuẩn hoá ≥ ngưỡng (ví dụ ≥ 70%) so với số dòng thô không rỗng; mất quá nhiều dòng = nghi ngờ luật lọc; nếu vi phạm thì lùi về xử lý bảo thủ (chỉ bỏ dòng trống).

Checklist luật xếp hạng (theo độ an toàn/giá trị trên mỗi giờ cài; xếp hạng là phán đoán của tôi):
1. (≈1 giờ) Header hợp lệ kiểu Pytheas + quét ngược từ dòng data đầu; header "mọi cột khác rỗng, duy nhất" (header ≈ 88% P/R trong Pytheas; kết hợp kiểm tra kiểu body). Tụt khi: file sạch không có header; cột index trống.
2. (≈1 giờ) Header 2 dòng: ghép nhãn nhóm + nhãn con, dùng openpyxl `merged_cells` để điền nhãn nhóm vào mọi cột trong vùng gộp (Pytheas cách ghép; không có số riêng). Tụt khi: dòng 1 là tiêu đề bảng gộp toàn bảng (không phải nhóm cột) — kiểm tra bằng số cột nhãn con.
3. (≈1 giờ) Dòng context/ghi chú trên header: dòng chỉ có ô cột đầu khác rỗng hoặc toàn text, nằm trên header (Pytheas context R/P ≈ 89–92%).
4. (≈1.5 giờ) Dòng tổng/tổng phụ: từ khoá ở ô đầu + kiểm tra tổng số học + kiểm tra đóng (nguồn: Pytheas LR1, Strudel §5.5; derived là lớp khó nhất ở Strudel). Tụt khi: từ khoá nằm trong tên hàng; tổng ngẫu nhiên.
5. (≈1 giờ) Quyết định định dạng số/ngày theo cột (mục 5); từ chối khi nhập nhằng.
6. (≈1.5 giờ) ffill cột khoá theo luật 6 điều (mục 3), ưu tiên vùng gộp openpyxl.
7. (≈1 giờ) Dòng trống/dòng nhãn nhóm (subheader: chỉ ô trái cùng khác rỗng và dòng sau là data; Pytheas P/R 83/93).
8. (≈1 giờ) Union sheet theo header chuẩn hoá + sheet tra cứu tách riêng.
9. (≈2 giờ) Tách nhiều bảng trong một sheet: ít ưu tiên hơn vì tỉ lệ gặp thấp và heuristic thuần chỉ ≈46–65% F1 (SpreadsheetLLM); chỉ nên làm khi thấy trong dữ liệu thật.

Cách test nhanh bằng nhiễu (đều dùng bảng sạch đã biết đáp án và so sánh bảng khôi phục với bảng gốc, 100% hoặc bỏ trống):
- Chèn 1–4 dòng tiêu đề/ghi chú (toàn cột đầu) phía trên; chèn dòng ghi chú đáy.
- Tách header thành 2 dòng: nhóm (merged ngang) + con; thử cả nhóm bị bỏ trống ở vài cột.
- Chèn dòng tổng phụ sau mỗi nhóm đơn và một dòng tổng cuối bảng (có và không có từ khoá); chèn dòng voucher/phí ship.
- "Kiểu Excel hoá" cột khoá: giữ giá trị ở dòng đầu đơn, xoá các dòng sau (mục 3); và đối chứng: bảng sạch không có lặp thì luật không tác động.
- Tách bảng theo tháng thành nhiều sheet, mỗi sheet khởi động lại STT; thêm sheet tra cứu viết tắt.
- Đổi số thành chuỗi các kiểu dấu/hậu tố, ngày dạng text/serial/không năm (mục 5).
- Kiểm tra bảo toàn: chạy toàn pipeline trên bảng sạch (không nhiễu): kết quả phải bằng bảng gốc (đo "tổn hại file sạch" riêng với "phục hồi file nhiễu").
- Chú ý theo kinh nghiệm cũ của dự án: kiểm tra công cụ biến đổi có thực tế không trước khi tin kết quả tụt (đã có hai lần "tụt giả"); đây là kinh nghiệm dự án, không phải nguồn bên ngoài.

### Gaps
- Chưa có số công bố cho độ chính xác của bộ bất biến sanity (chúng là thực hành, không phải kết quả đo công bố).
- Không đọc được DeExcelerator, Senbazuru (bài gốc), TableSense, Foofah; tìm kiếm chỉ trả về tóm tắt thứ cấp. Senbazuru: chỉ biết "giảm 72–92% công sức người" trên 100 spreadsheet web (SSW 2013), không phải accuracy — [Senbazuru SSW 2013](https://web.eecs.umich.edu/~michjc/papers/spreadsheets_ssw2013.pdf) (qua tóm tắt tìm kiếm).
- Chưa có dữ liệu nào về sổ sách tiếng Việt cụ thể; mọi số công bố đến từ dữ liệu mở tiếng Anh/Pháp và spreadsheet thống kê.
