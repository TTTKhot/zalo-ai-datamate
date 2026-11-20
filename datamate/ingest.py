"""Read one business folder into raw tables (values kept as objects).

Generic structure handling only, no business meaning:
* header row = first well-filled, text-like row (title / filter rows above it are dropped);
* sheets or files with the same header are one logical table (monthly sheets, _1/_2 splits, one file per month
  named `X_T3_2025` / `X_Thang03_2025` / `2025_03_X`);
* repeated header rows and fully empty rows are removed; sheet name kept for year-less dates.
"""
from __future__ import annotations

import csv
import io
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .values import is_blank, plain, slug, year_from_label

TABLE_SUFFIXES = {'.csv', '.tsv', '.txt', '.xlsx', '.xlsm', '.xls', '.sqlite', '.sqlite3', '.db', '.parquet'}
META_COLUMNS = ('_file', '_sheet', '_row')


@dataclass
class RawTable:
    name: str
    frame: pd.DataFrame                     # original headers as column names + _file/_sheet/_row
    headers: list[str]
    sources: list[str] = field(default_factory=list)

    @property
    def data_columns(self):
        return [c for c in self.frame.columns if c not in META_COLUMNS]


def detect_header_row(raw: pd.DataFrame, scan_rows: int = 30) -> int:
    best, best_score = 0, -1.0
    head = raw.head(scan_rows)
    widths = head.apply(lambda r: sum(not is_blank(v) for v in r), axis=1)
    max_width = max(int(widths.max()), 1)
    for index, row in head.iterrows():
        cells = [v for v in row.tolist() if not is_blank(v)]
        if len(cells) < max(2, 0.6 * max_width):
            continue
        text = [c for c in cells if isinstance(c, str) and not re.fullmatch(r'[\d\s.,:/\-]+', c.strip())]
        unique = len({str(c).strip() for c in cells}) / len(cells)
        score = len(cells) / max_width + len(text) / len(cells) + unique
        if score > best_score + 1e-9:
            best, best_score = int(index), score
            if len(text) == len(cells) and unique == 1.0 and len(cells) == max_width:
                break
    return best


def _frame_from_raw(raw: pd.DataFrame) -> tuple[list[str], pd.DataFrame]:
    raw = raw.dropna(axis=1, how='all').reset_index(drop=True)
    if raw.empty:
        return [], raw
    row = detect_header_row(raw)
    headers, used = [], {}
    for i, value in enumerate(raw.iloc[row].tolist()):
        name = f'cot_{i + 1}' if is_blank(value) else re.sub(r'\s+', ' ', str(value)).strip()
        used[name] = used.get(name, 0) + 1
        headers.append(name if used[name] == 1 else f'{name}_{used[name]}')
    body = raw.iloc[row + 1:].copy()
    body.columns = headers
    body['_row'] = body.index + 1                        # 1-based source row
    keep = body[headers].apply(lambda r: any(not is_blank(v) for v in r), axis=1)
    body = body[keep]
    repeated = body[headers].apply(lambda r: all(plain(v) == plain(h) for v, h in zip(r, headers)
                                                 if not is_blank(v)), axis=1)
    return headers, body[~repeated].reset_index(drop=True)


def _read_csv(path: Path) -> list[tuple[str, pd.DataFrame]]:
    data = path.read_bytes()
    for encoding in ('utf-8-sig', 'utf-8', 'cp1258', 'utf-16'):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f'Cannot decode {path}')
    try:
        delimiter = csv.Sniffer().sniff(text[:20000], delimiters=',;\t|').delimiter
    except csv.Error:
        delimiter = '\t' if path.suffix.lower() == '.tsv' else ','
    raw = pd.read_csv(io.StringIO(text), sep=delimiter, header=None, dtype=object,
                      keep_default_na=False, na_values=[''], engine='python')
    return [('', raw)]


def _read_excel(path: Path) -> list[tuple[str, pd.DataFrame]]:
    try:
        import python_calamine  # noqa: F401  (5-20x faster, keeps cell types)
        engine = 'calamine'
    except ImportError:
        engine = 'xlrd' if path.suffix.lower() == '.xls' else None
    sheets = pd.read_excel(path, sheet_name=None, header=None, dtype=object, engine=engine)
    return [(name, raw) for name, raw in sheets.items()]


def _read_sqlite(path: Path) -> list[tuple[str, pd.DataFrame]]:
    uri = path.resolve().as_uri() + '?mode=ro'
    out = []
    with sqlite3.connect(uri, uri=True) as con:
        names = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%'")]
        for name in names:
            frame = pd.read_sql_query(f'SELECT * FROM "{name}"', con)
            raw = pd.concat([pd.DataFrame([frame.columns.tolist()]),
                             frame.astype(object).set_axis(range(frame.shape[1]), axis=1)], ignore_index=True)
            out.append((name, raw))
    return out


def _read_parquet(path: Path) -> list[tuple[str, pd.DataFrame]]:
    frame = pd.read_parquet(path)
    raw = pd.concat([pd.DataFrame([frame.columns.tolist()]),
                     frame.astype(object).set_axis(range(frame.shape[1]), axis=1)], ignore_index=True)
    return [('', raw)]


def _base_name(path: Path) -> str:
    stem = re.sub(r'(?:[_\-\s](?:\d{1,2}|20\d{2}))+$', '', path.stem)   # _1, _2, _2025
    return slug(stem) or slug(path.stem)


# a '_' token that is wholly a period mark: 03, 2025, 202503, t3, th03, thang3, m3, q1, quy2, and English month names
DATE_TOKEN = re.compile(r'(?:thang|th|t|m|quy|q)?\d+'
                        r'|jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?'
                        r'|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?')


def _core_name(base: str) -> str:
    """'banhang_t1' / 'banhang_thang01' / '2025_03_banhang' -> 'banhang': drop '_' tokens that are wholly a month/year
    mark. Used only to join tables with the SAME columns (one export file per month named in the middle / in front).
    A name made only of period marks ('thang3_2025') gives '' (all such files with the same columns are one table)."""
    return '_'.join(tok for tok in base.split('_') if not DATE_TOKEN.fullmatch(tok))


def _join_month_groups(groups: dict) -> dict:
    """Groups with identical columns whose names differ only by month/year tokens are one table (named by the rest)."""
    by_core: dict[tuple, list] = {}
    for key in groups:
        by_core.setdefault((_core_name(key[0]), key[1]), []).append(key)
    out = {}
    for (core, cols), keys in by_core.items():
        if len(keys) == 1:
            out[keys[0]] = groups[keys[0]]
            continue
        parts = [groups[k] for k in keys]
        frames = [p.frame.rename(columns=dict(zip(p.headers, parts[0].headers))) for p in parts]
        core = core or keys[0][0]                    # names were only period marks: keep the first file's name
        out[(core, cols)] = RawTable(name=core, frame=pd.concat(frames, ignore_index=True),
                                     headers=parts[0].headers, sources=[s for p in parts for s in p.sources])
    return out


def read_business(folder: str | Path, max_rows: int = 400_000) -> dict[str, RawTable]:
    folder = Path(folder)
    groups: dict[tuple, RawTable] = {}
    for path in sorted(p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in TABLE_SUFFIXES):
        if path.suffix.lower() == '.txt':
            continue
        reader = {'.csv': _read_csv, '.tsv': _read_csv, '.xlsx': _read_excel, '.xlsm': _read_excel,
                  '.xls': _read_excel, '.sqlite': _read_sqlite, '.sqlite3': _read_sqlite,
                  '.db': _read_sqlite, '.parquet': _read_parquet}[path.suffix.lower()]
        for part, raw in reader(path):
            headers, body = _frame_from_raw(raw)
            if not headers or body.empty:
                continue
            body['_file'] = path.name
            body['_sheet'] = part
            base = slug(part) if reader is _read_sqlite and slug(part) else _base_name(path)   # sqlite: real table name
            key = (base, tuple(plain(h) for h in headers))
            if key in groups:
                table = groups[key]
                table.frame = pd.concat([table.frame, body], ignore_index=True)
                table.sources.append(f'{path.name}:{part}')
            else:
                groups[key] = RawTable(name=key[0], frame=body, headers=headers,
                                       sources=[f'{path.name}:{part}'])
    groups = _join_month_groups(groups)
    tables, used = {}, {}
    for (base, _), table in groups.items():
        if len(table.frame) > max_rows:
            table.frame = table.frame.head(max_rows)
        used[base] = used.get(base, 0) + 1
        name = base if used[base] == 1 else f'{base}_{used[base]}'
        table.name = name
        tables[name] = table
    return tables


def sheet_years(table: RawTable) -> pd.Series:
    return table.frame['_sheet'].map(year_from_label)


def read_readme(folder: str | Path, text: str | None = None) -> dict:
    """README text + column descriptions.

    `columns`: per file stem -> {plain header: description} from '- **Col**: desc' lines under
    a heading that names the file ('' = no file heading). Inline notes like
    '- **Nhập hàng**: **Đơn giá** là giá nhập...' are kept with their context label.
    """
    if text is None:
        folder = Path(folder)
        paths = sorted(folder.glob('README*')) + sorted(folder.glob('readme*'))
        if not paths:
            return {'text': '', 'columns': {}, 'notes': {}}
        text = paths[0].read_text(encoding='utf-8-sig', errors='replace')
    columns, notes, current = {}, {}, ''
    for line in text.splitlines():
        heading = re.match(r'^#+\s*(.*)$', line)
        if heading:
            named = re.search(r'`([^`]+)`', heading.group(1))
            current = slug(Path(named.group(1)).stem) if named else ''
            continue
        # database-style notes: "`chi_tiet_don.TriGia` là thành tiền của dòng; `x.Y` là ..."
        for m in re.finditer(r'`([\w]+)\.([\w]+)`\s+(?:là|=)\s+([^;\n]+?)(?=;|\.\s|\.$|$)', line):
            columns.setdefault(slug(m.group(1)), {}).setdefault(plain(m.group(2)), m.group(3).strip())
        bullet =re.match(r'^\s*[-*]\s*\*\*(.+?)\*\*\s*[:：]\s*(.+)$', line)
        if not bullet:
            continue
        label, desc = bullet.group(1).strip(), bullet.group(2).strip()
        inline = list(re.finditer(r'\*\*([^*]+?)\*\*\s+(?:là|=)\s+([^;.\n]+)', desc))
        if inline:
            for m in inline:
                notes.setdefault(plain(m.group(1)), []).append(f'({label}) {m.group(2).strip()}')
        else:
            columns.setdefault(current, {}).setdefault(plain(label), desc)
    return {'text': text, 'columns': columns, 'notes': notes}


def readme_description(readme: dict, table_name: str, header: str) -> str:
    key = plain(header)
    cols = readme.get('columns', {})
    for stem, mapping in cols.items():
        if stem and (stem == table_name or slug(stem).startswith(table_name) or table_name.startswith(slug(stem))):
            if key in mapping:
                return mapping[key]
    if key in cols.get('', {}):
        return cols[''][key]
    return ' | '.join(readme.get('notes', {}).get(key, []))
