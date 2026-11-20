"""Fake Qwen for subprocess tests of datamate.launch / predict (env DATAMATE_TEST_BACKEND=fake_backend:FakeQwen).

Intent prompts get the scripted parser's JSON, SQL prompts the fixed templates of smoke_predict.py; shops are read
from DATAMATE_TEST_DATA (a data root with data/<biz>/).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import smoke_predict                                      # noqa: E402
from datamate.llm import FnBackend                       # noqa: E402
from datamate.pipeline import load_shop                  # noqa: E402


class FakeQwen(FnBackend):
    def __init__(self, *a, **k):
        super().__init__(smoke_predict.fake_generate)
        root = Path(os.environ['DATAMATE_TEST_DATA'])
        for d in sorted((root / 'data').iterdir()):
            if d.is_dir() and d.name not in smoke_predict.SHOPS:
                smoke_predict.SHOPS[d.name] = load_shop(d, d.name)
