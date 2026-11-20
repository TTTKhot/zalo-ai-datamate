"""Rulebook concepts the rule library understands.

Each entity is a kind of table a shop export can contain; each field is a
column role. `syn` lists generic Vietnamese/English header vocabulary (accent-free)
used only to propose candidates; the LLM and the fixed checks decide.
Nothing here names a business, a file or a question.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Field:
    name: str
    kind: str            # id | date | datetime | money | number | text | category | bool
    desc: str
    syn: tuple = ()
    required: bool = False


@dataclass(frozen=True)
class Entity:
    name: str
    desc: str
    fields: tuple
    table_hints: tuple = ()
    one_row_per: str = ''           # key field that must be unique (header tables)

    def field(self, name):
        return next(f for f in self.fields if f.name == name)


F = Field
ENTITIES = {e.name: e for e in [
    Entity('sales_line', 'Dòng hàng của đơn bán (mỗi dòng một mặt hàng trong một đơn).', (
        F('order_id', 'id', 'mã đơn / mã hoá đơn của dòng', ('ma don', 'ma hoa don', 'so hoa don', 'ma don hang', 'order', 'invoice', 'so phieu', 'ma phieu'), True),
        F('order_date', 'date', 'ngày đặt / ngày bán', ('ngay', 'ngay dat', 'ngay ban', 'ngay thang', 'thoi gian', 'date')),
        F('status', 'category', 'trạng thái / kết quả của đơn', ('trang thai', 'ket qua', 'tinh trang', 'status')),
        F('customer_name', 'text', 'tên khách hàng', ('khach hang', 'ten khach', 'doi tac', 'khach', 'customer')),
        F('customer_code', 'id', 'mã khách hàng', ('ma kh', 'ma khach', 'ma khach hang', 'customer id')),
        F('product_name', 'text', 'tên hàng / món', ('ten hang', 'ten san pham', 'san pham', 'mat hang', 'noi dung', 'ten mon', 'hang hoa', 'product', 'item', 'ten thuoc')),
        F('product_code', 'id', 'mã hàng', ('ma hang', 'ma sp', 'ma san pham', 'sku', 'ma hh', 'ma thuoc')),
        F('unit', 'category', 'đơn vị tính của dòng', ('don vi', 'dvt', 'don vi tinh', 'unit')),
        F('qty', 'number', 'số lượng theo đơn vị của dòng', ('so luong', 'sl', 'so luong san pham', 'qty', 'quantity'), True),
        F('qty_base', 'number', 'số lượng đã quy ra đơn vị cơ bản', ('quy ra', 'quy doi', 'so luong quy doi', 'dv le', 'don vi co ban')),
        F('unit_price', 'money', 'đơn giá bán một đơn vị của dòng', ('don gia', 'gia ban', 'gia', 'gia san pham', 'price')),
        F('line_discount', 'money', 'giảm giá trên dòng', ('giam gia', 'chiet khau', 'ck', 'discount')),
        F('line_total', 'money', 'thành tiền dòng sau giảm giá dòng', ('thanh tien', 'tong tien', 'thanh tien sau giam', 'tri gia', 'amount', 'total')),
        F('unit_cost', 'money', 'giá vốn một đơn vị bán', ('gia von', 'cost')),
        F('staff', 'id', 'nhân viên bán', ('nhan vien', 'nv', 'thu ngan', 'nguoi ban', 'staff', 'ma nv')),
        F('payment_method', 'category', 'hình thức thanh toán', ('thanh toan', 'hinh thuc thanh toan', 'phuong thuc thanh toan', 'payment')),
        F('channel', 'category', 'kênh bán', ('kenh', 'kenh ban', 'nguon', 'channel')),
        F('order_time', 'datetime', 'thời điểm tạo đơn (giờ)', ('thoi gian tao', 'gio', 'thoi diem', 'created')),
        F('delivery_date', 'date', 'ngày giao (đợt giao)', ('ngay giao', 'dot giao')),
     ), ('chi tiet', 'hoa don', 'don hang', 'ban hang', 'ban le', 'sales', 'order')),
    Entity('order', 'Hoá đơn / đơn hàng, mỗi dòng một đơn.', (
        F('order_id', 'id', 'mã đơn', ('ma don', 'ma hoa don', 'so hoa don', 'ma don hang', 'order', 'invoice'), True),
        F('order_date', 'date', 'ngày đặt', ('ngay', 'ngay dat', 'ngay ban', 'thoi gian', 'date'), True),
        F('order_time', 'datetime', 'thời điểm tạo đơn (có giờ)', ('thoi gian tao', 'gio', 'created', 'thoi diem')),
        F('customer_code', 'id', 'mã khách', ('ma kh', 'ma khach', 'ma khach hang')),
        F('customer_name', 'text', 'tên khách', ('khach hang', 'ten khach', 'doi tac', 'khach')),
        F('goods_total', 'money', 'tổng tiền hàng trước giảm giá đơn', ('tong tien hang', 'tien hang')),
        F('order_discount', 'money', 'giảm giá trên cả đơn', ('giam gia', 'chiet khau', 'voucher', 'khuyen mai')),
        F('order_total', 'money', 'số khách phải trả cho cả đơn (sau giảm giá, gồm phí giao)', ('tong sau giam gia', 'khach can tra', 'tong thanh toan', 'phai tra', 'tong cong')),
        F('paid_amount', 'money', 'khách đã trả lúc mua', ('khach da tra', 'da tra', 'da thanh toan')),
        F('shipping_fee', 'money', 'phí giao hàng', ('phi giao', 'phi ship', 'van chuyen')),
        F('vat', 'money', 'thuế VAT', ('vat', 'thue')),
        F('payment_method', 'category', 'hình thức thanh toán ghi trên đơn', ('phuong thuc thanh toan', 'hinh thuc thanh toan', 'thanh toan')),
        F('status', 'category', 'trạng thái đơn', ('trang thai', 'tinh trang', 'ket qua')),
        F('staff', 'id', 'nhân viên', ('nhan vien', 'nv', 'thu ngan', 'nguoi ban', 'ma nv')),
        F('channel', 'category', 'kênh bán', ('kenh', 'kenh ban', 'nguon')),
        F('note', 'text', 'ghi chú', ('ghi chu', 'note')),
     ), ('hoa don', 'don hang', 'order', 'invoice'), 'order_id'),
    Entity('product', 'Danh mục hàng hoá, mỗi dòng một mặt hàng.', (
        F('product_code', 'id', 'mã hàng', ('ma hang', 'ma sp', 'ma san pham', 'sku', 'ma thuoc')),
        F('product_name', 'text', 'tên hàng', ('ten hang', 'ten san pham', 'ten thuoc', 'san pham'), True),
        F('base_unit', 'category', 'đơn vị cơ bản', ('dvt', 'don vi', 'don vi co ban', 'don vi tinh')),
        F('group', 'category', 'nhóm hàng', ('nhom hang', 'nhom', 'loai', 'danh muc', 'category')),
        F('unit_cost', 'money', 'giá vốn một đơn vị cơ bản', ('gia von', 'cost')),
        F('sale_price', 'money', 'giá bán niêm yết', ('gia ban', 'price')),
        F('is_prescription', 'category', 'thuốc kê đơn hay không', ('ke don', 'thuoc ke don', 'ban theo don', 'rx')),
        F('active_ingredient', 'text', 'hoạt chất', ('hoat chat', 'thanh phan')),
        F('item_kind', 'category', 'loại hàng hoá (mua về bán / pha chế / dịch vụ)', ('loai hang hoa', 'loai hang')),
     ), ('san pham', 'hang hoa', 'danh muc', 'product', 'thuoc'), 'product_code'),
    Entity('unit_conversion', 'Bảng quy đổi đơn vị lớn sang đơn vị cơ bản.', (
        F('product_code', 'id', 'mã hàng', ('ma hang', 'ma sp')),
        F('product_name', 'text', 'tên hàng', ('ten hang', 'ten san pham')),
        F('unit', 'category', 'đơn vị lớn / quy đổi', ('don vi quy doi', 'dvt', 'don vi lon', 'don vi'), True),
        F('factor', 'number', 'số đơn vị cơ bản trong 1 đơn vị lớn', ('ti le quy doi', 'ty le quy doi', 'quy doi', 'he so'), True),
        F('base_unit', 'category', 'đơn vị cơ bản', ('don vi co ban',)),
        F('price', 'money', 'giá bán đơn vị lớn', ('gia ban', 'gia')),
     ), ('quy doi', 'don vi tinh', 'don vi', 'unit')),
    Entity('customer', 'Danh sách khách hàng.', (
        F('customer_code', 'id', 'mã khách', ('ma khach hang', 'ma kh', 'ma khach'), True),
        F('customer_name', 'text', 'tên khách', ('ten khach hang', 'ten khach', 'khach hang')),
        F('customer_group', 'category', 'nhóm khách', ('nhom khach', 'loai khach', 'nhom', 'hang thanh vien')),
        F('phone', 'id', 'điện thoại', ('dien thoai', 'sdt', 'phone')),
     ), ('khach hang', 'customer'), 'customer_code'),
    Entity('purchase', 'Phiếu nhập hàng, mỗi dòng một phiếu.', (
        F('purchase_id', 'id', 'mã phiếu nhập', ('ma nhap hang', 'ma phieu nhap', 'so phieu', 'ma phieu'), True),
        F('purchase_date', 'date', 'ngày phiếu', ('thoi gian', 'ngay', 'ngay nhap'), True),
        F('supplier', 'id', 'nhà cung cấp', ('ma ncc', 'nha cung cap', 'ncc', 'supplier')),
        F('total', 'money', 'tổng tiền phiếu nhập', ('can tra ncc', 'tong tien', 'thanh tien', 'tong cong')),
        F('status', 'category', 'trạng thái phiếu', ('trang thai',)),
        F('note', 'text', 'ghi chú', ('ghi chu',)),
     ), ('nhap hang', 'phieu nhap', 'purchase'), 'purchase_id'),
    Entity('purchase_line', 'Dòng hàng của phiếu nhập.', (
        F('purchase_id', 'id', 'mã phiếu nhập', ('ma nhap hang', 'ma phieu nhap', 'so phieu', 'ma phieu')),
        F('purchase_date', 'date', 'ngày nhập (khi bảng nhập phẳng)', ('ngay nhap', 'ngay', 'thoi gian')),
        F('product_code', 'id', 'mã hàng', ('ma hang', 'ma sp')),
        F('product_name', 'text', 'tên hàng', ('ten hang', 'ten san pham')),
        F('unit', 'category', 'đơn vị nhập', ('dvt', 'don vi', 'don vi tinh')),
        F('qty', 'number', 'số lượng nhập', ('so luong', 'sl'), True),
        F('unit_cost', 'money', 'đơn giá nhập theo đơn vị nhập', ('don gia', 'gia nhap')),
        F('line_total', 'money', 'thành tiền dòng nhập', ('thanh tien',)),
        F('supplier', 'id', 'nhà cung cấp', ('ncc', 'nha cung cap', 'ma ncc')),
        F('lot', 'id', 'số lô', ('so lo', 'lo', 'lot')),
        F('expiry_date', 'date', 'hạn dùng', ('han dung', 'han su dung', 'hsd', 'expiry')),
     ), ('chi tiet nhap', 'nhap hang', 'phieu nhap')),
    Entity('stock_snapshot', 'Báo cáo tồn kho tại cuối kỳ dữ liệu.', (
        F('product_code', 'id', 'mã hàng', ('ma hang', 'ma sp')),
        F('product_name', 'text', 'tên hàng', ('ten hang',)),
        F('unit', 'category', 'đơn vị', ('dvt', 'don vi')),
        F('qty_on_hand', 'number', 'tồn cuối kỳ (đơn vị cơ bản)', ('ton cuoi ky', 'ton kho', 'ton', 'so luong ton'), True),
        F('lot', 'id', 'số lô', ('so lo', 'lo')),
        F('expiry_date', 'date', 'hạn dùng', ('han dung', 'hsd')),
     ), ('ton kho', 'bao cao ton', 'stock', 'inventory')),
    Entity('payment', 'Sổ quỹ / phiếu thu: mỗi lần khách trả tiền cho một đơn là một dòng.', (
        F('payment_id', 'id', 'mã phiếu thu', ('ma phieu', 'so phieu')),
        F('payment_time', 'datetime', 'thời điểm trả', ('thoi gian', 'ngay', 'ngay tra'), True),
        F('order_id', 'id', 'mã đơn được trả', ('ma hoa don', 'ma don'), True),
        F('method', 'category', 'phương thức', ('phuong thuc thanh toan', 'hinh thuc')),
        F('amount', 'money', 'số tiền trả lần đó', ('gia tri', 'so tien', 'tien'), True),
     ), ('so quy', 'thu', 'payment', 'phieu thu')),
    Entity('expense', 'Sổ chi phí.', (
        F('expense_date', 'date', 'ngày chi', ('ngay', 'thoi gian'), True),
        F('category', 'category', 'loại chi phí', ('loai', 'khoan muc', 'noi dung')),
        F('amount', 'money', 'số tiền chi', ('so tien', 'tien', 'gia tri'), True),
     ), ('chi phi', 'expense')),
    Entity('supplier', 'Danh sách nhà cung cấp.', (
        F('supplier_code', 'id', 'mã NCC', ('ma ncc', 'ma nha cung cap'), True),
        F('supplier_name', 'text', 'tên NCC', ('ten ncc', 'ten nha cung cap', 'nha cung cap')),
     ), ('nha cung cap', 'ncc', 'supplier'), 'supplier_code'),
    Entity('staff', 'Danh sách nhân viên / thợ.', (
        F('staff_code', 'id', 'mã NV', ('ma nv', 'ma nhan vien'), True),
        F('staff_name', 'text', 'tên NV', ('ten nhan vien', 'ho ten', 'nhan vien', 'ten tho', 'ho ten tho')),
        F('commission_pct', 'number', 'phần trăm hoa hồng của nhân viên / thợ', ('hoa hong', 'phan tram hoa hong',
          'ti le hoa hong', 'ty le hoa hong', 'hoa hong phan tram')),
     ), ('nhan vien', 'staff', 'danh sach tho', 'tho'), 'staff_code'),
    # rulebook "Giao nhiều đợt": one row = one item in one delivery round of one order. Three required fields (order,
    # round number, delivery date) so it cannot take an ordinary sales / purchase / catalogue table.
    Entity('delivery', 'Sổ giao hàng: mỗi dòng một mặt hàng trong một đợt giao của một đơn.', (
        F('order_id', 'id', 'mã đơn được giao', ('ma don', 'ma bill', 'ma don hang', 'ma hoa don', 'so hoa don'), True),
        F('batch', 'number', 'lượt / đợt giao của đơn (1, 2, 3)', ('luot giao', 'lan giao', 'dot giao', 'dot'), True),
        F('delivery_date', 'date', 'ngày giao', ('ngay giao', 'ngay cho', 'ngay giao hang', 'ngay van chuyen'), True),
        F('product_name', 'text', 'tên hàng', ('ten hang', 'ten hang hoa')),
        F('qty', 'number', 'số lượng giao (đơn vị cơ bản)', ('so luong giao', 'sl thuc giao', 'sl giao')),
        F('driver', 'text', 'người giao / tài xế', ('nguoi cho', 'nguoi giao', 'tai xe', 'nguoi giao hang')),
        F('vehicle', 'id', 'biển số xe', ('bien so xe', 'bien so')),
     ), ('giao hang', 'phieu giao', 'so giao', 'delivery')),
    Entity('price_history', 'Bảng giá theo ngày áp dụng.', (
        F('product_code', 'id', 'mã hàng', ('ma hang',)),
        F('product_name', 'text', 'tên hàng', ('ten hang',)),
        F('effective_date', 'date', 'ngày áp dụng', ('ngay ap dung', 'tu ngay', 'ngay'), True),
        F('price', 'money', 'giá mới', ('gia ban', 'gia moi', 'gia'), True),
     ), ('bang gia', 'lich su gia', 'price')),
    # service shops (repair, spa, salon...): a hand-kept book where one row is one ticket / one visit, the money cell
    # is the ticket total and a free-text cell lists the jobs done. Read as a sales book with one line per ticket
    # (rules.build_views). The job column is required so it cannot take an expense book (date + amount + content).
    Entity('service_ticket', 'Sổ dịch vụ / sửa chữa: mỗi dòng một phiếu (một lượt khách), tiền là tổng cả phiếu.', (
        F('ticket_date', 'date', 'ngày làm phiếu', ('ngay', 'ngay sua', 'ngay lam', 'ngay nhan', 'thoi gian', 'date'), True),
        F('work', 'text', 'các việc đã làm cho phiếu (ghi chung một ô)', ('lam gi', 'cong viec', 'viec lam', 'dich vu',
          'noi dung sua', 'hang muc', 'sua gi', 'hang muc sua', 'viec da lam', 'dich vu da lam'), True),
        F('amount', 'money', 'tổng tiền cả phiếu', ('tien', 'so tien', 'tong tien', 'thanh tien', 'tien phieu',
          'tien cong', 'thu'), True),
        F('technician', 'text', 'thợ / người làm phiếu', ('tho', 'tho sua', 'tho lam', 'nguoi lam', 'ky thuat vien', 'ktv',
          'nhan vien', 'nguoi sua')),
        F('vehicle', 'text', 'xe / máy mang tới (dòng xe, biển số)', ('xe', 'bien so', 'bien so xe', 'loai xe', 'dong xe',
          'may')),
        F('customer_name', 'text', 'tên khách', ('khach hang', 'ten khach', 'khach')),
        F('note', 'text', 'ghi chú', ('ghi chu', 'note')),
     ), ('sua xe', 'sua chua', 'dich vu', 'phieu sua', 'so sua', 'bao duong', 'service', 'repair')),
]}

STATUS_CLASSES = ('hoàn thành', 'huỷ', 'trả hàng', 'đang giao')
