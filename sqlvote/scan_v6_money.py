"""For every shop of a split: how many canonical sales lines of datamate v6 look like a lost k / tr multiplier?

  python sqlvote/scan_v6_money.py <folder that contains datamate/> <split dir>

A line is suspect when its line_total is
  * not an integer (e.g. '1,45tr' read as 1.45), or
  * far below qty * unit_price (only the total lost its multiplier), or
  * between 0 and 1000 đồng while the shop's median line is at least 5000 (e.g. '25k' read as 25).
Run it before and after fixing datamate/values.py; the suspect counts should drop to (almost) zero.
"""
import sys
import time
from pathlib import Path

import pandas as pd


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    v6, split = sys.argv[1], sys.argv[2]
    sys.path.insert(0, v6)
    from datamate.pipeline import load_shop
    for folder in sorted(p for p in (Path(split) / 'data').iterdir() if p.is_dir()):
        t = time.time()
        try:
            shop = load_shop(folder, folder.name, mapper_backend=None)
            lines = shop.views.frames.get('sales_lines')
            if lines is None or 'line_total' not in lines:
                print(f'{folder.name}: không có sales_lines.line_total', flush=True)
                continue
            lt = pd.to_numeric(lines['line_total'], errors='coerce')
            gross = pd.to_numeric(lines.get('qty'), errors='coerce') * pd.to_numeric(lines.get('unit_price'), errors='coerce')
            frac = lt.notna() & (lt != lt.round())
            small = (lt.abs() < 0.01 * gross.abs()) & (gross.abs() >= 1000)
            tiny = (lt.abs() > 0) & (lt.abs() < 1000) & (lt.abs().median() >= 5000)
            n = int((frac | small | tiny).sum())
            print(f'{folder.name}: {len(lines)} dòng | nghi mất hệ số: {n} ({n / max(len(lines), 1):.1%}) '
                  f'[không nguyên {int(frac.sum())}, nhỏ hơn 1% qty*giá {int(small.sum())}, dưới 1000đ {int(tiny.sum())}] '
                  f'({time.time() - t:.0f}s)', flush=True)
        except Exception as exc:
            print(f'{folder.name}: LỖI {type(exc).__name__}: {str(exc)[:160]}', flush=True)


if __name__ == '__main__':
    main()
