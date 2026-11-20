"""Which part of the code implements each rule of the TRAIN rulebook (filled once, by metric / module, never by shop
or question). Keys = datamate.rulebook.Rule.key of data/train/rulebook.md. An empty list = the rule has no
implementation ("uncovered": questions about it go to the rulebook route / abstain, docs/plan.md).
Regenerate the snapshot after editing: python -m datamate.rulebook snapshot data/train/rulebook.md
"""
R, P, F = 'rules.py', 'periods.py+timex.py', 'scoring/format'
COVERED = {
    # §1 orders and revenue
    '1||don tinh vao doanh thu': ['revenue', R],
    '1||ban duoc bao nhieu tien thu ve bao nhieu tien': ['revenue'],
    '1||don thuoc ky nao': ['revenue', 'order_count', P],
    '1||don bi huy': ['cancelled_count', R],
    '1||so don': ['order_count'],
    '1||doanh thu mot don': ['revenue', 'avg_order_value'],
    '1||doanh thu theo hinh thuc thanh toan': ['revenue'],
    '1||doanh thu theo nhom khach': ['revenue'],
    '1||ti le don huy trong ky': ['cancel_rate'],
    '1||phan tram thay doi tang truong': ['compare'],
    '1||chenh lech hon kem tang giam bao nhieu so khong phai %': ['compare'],
    # §2 time
    '2||ngay x hom nay hom qua': [P], '2||den het ngay x tinh den hom nay': [P], '2||tu x den y nhom x y': [P],
    '2||n ngay gan nhat': [P], '2||qua n hon n tren n duoi n': ['slots.py'], '2||tuan': [P], '2||thang m y': [P],
    '2||thang nay': [P], '2||tu dau nam tu dau nam toi nay': [P], '2||thang m quy q khong ghi nam': [P],
    '2||tet nam y dip tet mua tet': [P], '2||ca sang ca chieu': ['shift filter'],
    # §3 ranking
    '3||mat hang': [R], '3||nhom hang': ['group filter'], '3||ban chay': ['top_products'],
    '3||ban duoc bao nhieu don vi': ['quantity'], '3||hang loi nhat': ['top_products', 'gross_profit'],
    '3||xac dinh khach': [R, 'top_customers'], '3||nhan vien ban gioi nhat': [],
    '3||gia tri trung binh mot don': ['avg_order_value'],
    # §4 debts
    '4||don duoc tinh vao no': ['debt_total'], '4||no mot don tai ngay x': ['debt_total', 'debt_table'],
    '4||no theo khach': ['debt_table', 'debtor_count'], '4||don cod don ban qua san tmdt': ['debt_total', R],
    '4||tuoi no': ['debt_aging'], '4||no them tra no thu no trong ky': ['new_debt_and_repaid'],
    # §5 stock, purchases, cost
    '5||tien nhap hang trong ky': ['purchase_total'], '5||nhap tru ban chenh nhap va ban': ['purchase_minus_sales'],
    '5||gia nhap binh quan mot mat hang trong thang': ['avg_purchase_price'], '5||ton theo don vi lon': ['stock'],
    '5||gia tri hang ton kho': ['stock_value'], '5||mat hang het hang cuoi ngay': [],
    '5||mat hang khong ban duoc trong ky e': ['unsold_products'], '5||gia ban x ngay d': ['unit_price'],
    '5||hieu ung tang gia': ['price_effect'], '5||gia von': ['gross_profit'], '5||lai gop': ['gross_profit'],
    '5||lai rong mot thang': ['net_profit'],
    # §6 industries
    '6|ca phe|size m size l': ['size filter'], '6|nha thuoc|thuoc ke don': ['prescription filter'],
    '6|nha thuoc|hang het han trong n ngay toi': ['expiring'],
    '6|nha thuoc|doanh thu theo hoat chat': ['active_ingredient filter'],
    '6|nha thuoc|lo gan het han nhat cua mot thuoc': [], '6|vat lieu xay dung|giao nhieu dot': [],
    # §7 unanswerable, §8 file conventions, §9 answer format, §10 words: implemented across the pipeline
    '7||thong tin file khong ghi thi khong suy ra tu': ['metrics Unanswerable'],
    '7||khong co du lieu khac voi bang 0 ky nam': ['metrics Unanswerable'],
    '7||ky chi co mot phan nam trong khoang ngay co': [P],
    '8||ten goi nhan': [R], '8||o de trong o cac dong sau cua cung mot nhom dong': [R], '8||trang thai don': [R],
    '8||hai dong cua cung mot don giong nhau o moi o': [R], '8||bang khong ghi theo don': [R],
    '8||ngay khong ghi nam': ['values.py'],
    '9||number': [F], '9||percent': [F], '9||date': [F], '9||boolean': [F], '9||string': [F], '9||list': [F],
    '9||table': [F], '9||unanswerable': [F],
    '9||so phan tram khop tuyet doi tien dung tung dong': [F], '9||lam tron tien ra so le lam tron ve dong': [F],
    '9||chuoi khong phan biet hoa thuong khoang trang dau cau': [F],
    '9||danh sach dung ca tap va thu tu top k': [F], '9||bang nhau hai doi tuong bang nhau o tieu chi': [F],
    '9||bang moi dong mot doi tuong cot dau la ten': [F],
    '10||don vi co ban don vi lon': [R],
}
