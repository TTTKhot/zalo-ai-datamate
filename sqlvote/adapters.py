"""Bridges to the DataMate v6 package (`datamate/`). Nothing here is imported unless you call it,
so sqlvote stays usable without torch / transformers / datamate.

  HFSamplingBackend(qwen)       - sqlvote backend on top of datamate.llm.QwenBackend (adapter switched off)
  canonical_tables(shop)        - v6 canonical views as extra tables for clean.build_shop_db
  datamate_tables_fn(cache_dir) - extra_tables_fn for run.predict: loads the v6 Shop and returns its views
"""
from __future__ import annotations

import contextlib
import threading

import pandas as pd

RENAME = {'group': 'product_group', 'order': 'order_col', 'table': 'table_col', 'user': 'user_col'}
VIEW_NOTE = ('bảng chuẩn hoá của DataMate v6: counts_for_revenue, qty_base, order_status... đã áp luật MẶC ĐỊNH của '
             'rulebook train; nếu rulebook của bộ đang trả lời hoặc README nói khác thì tính lại từ bảng thô')


class HFSamplingBackend:
    """generate(messages, n, temperature, seed, max_tokens) -> list[str] with an in-process transformers model.

    Uses the base weights (LoRA adapter off) so this route stays independent of the intent route.
    Not thread-safe by nature: a lock serialises calls, so run with Config.workers = 1."""

    def __init__(self, qwen_backend, top_p: float = 0.95):
        self.b, self.top_p = qwen_backend, top_p
        self.lock = threading.Lock()
        self.calls = 0

    def generate(self, messages, n: int = 1, temperature: float = 0.0, seed=None, max_tokens: int = 700) -> list[str]:
        from datamate.llm import chat_ids, tokenizer_of
        b = self.b
        torch = b.torch
        ids = chat_ids(b.processor, messages)
        tok = tokenizer_of(b.processor)
        texts, oom = [], None
        with self.lock:
            input_ids = torch.tensor([ids], device=b.model.device)
            # one sequence per generate call: the prompt carries the whole rulebook + README, and
            # num_return_sequences=n multiplies the attention/KV memory by n (OOM on a 16 GB T4).
            for i in range(n if temperature > 0 else 1):
                kwargs = {'input_ids': input_ids, 'attention_mask': torch.ones_like(input_ids),
                          'max_new_tokens': max_tokens}
                if temperature > 0:
                    if seed is not None:
                        torch.manual_seed(int(seed) + i)
                        if torch.cuda.is_available():
                            torch.cuda.manual_seed_all(int(seed) + i)
                    kwargs.update(do_sample=True, temperature=temperature, top_p=self.top_p)
                else:
                    kwargs.update(do_sample=False)
                off = b.model.disable_adapter() if getattr(b, 'adapter', None) else contextlib.nullcontext()
                try:
                    with torch.inference_mode(), off:
                        out = b.model.generate(**kwargs)
                    texts.append(tok.decode(out[0][len(ids):], skip_special_tokens=True))
                    del out
                except torch.cuda.OutOfMemoryError as e:
                    oom = f'OutOfMemoryError: {str(e)[:120]}'
                finally:
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                if oom:
                    break                      # longer samples would fail too; keep what we have
        if oom:
            import gc
            gc.collect()                       # the traceback held the activations; free them for the next question
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            if not texts:
                raise RuntimeError(oom)
        self.calls += 1
        return texts * n if temperature <= 0 and n > 1 else texts


def _kind(s: pd.Series) -> str:
    dtype = str(s.dtype)
    if dtype.startswith('datetime'):
        nn = s.dropna()
        return 'DATE' if nn.empty or (nn == nn.dt.normalize()).all() else 'TIMESTAMP'
    if dtype in ('bool', 'boolean'):
        return 'BOOLEAN'
    if pd.api.types.is_integer_dtype(s):
        return 'BIGINT'
    if pd.api.types.is_numeric_dtype(s):
        nn = s.dropna()
        return 'BIGINT' if len(nn) and (nn == nn.round()).all() else 'DOUBLE'
    return 'TEXT'


def canonical_tables(shop, prefix: str = 'v_') -> list[dict]:
    """datamate Shop -> [{'name','frame','columns','sources','notes'}] for build_shop_db(extra_tables=...)."""
    from datamate.sqlpath import COLUMN_DOC, frames_for_sql
    out = []
    for name, df in frames_for_sql(shop.views).items():
        df = df.rename(columns=RENAME)
        back = {v: k for k, v in RENAME.items()}
        cols = [{'name': c, 'type': _kind(df[c]), 'desc': COLUMN_DOC.get(back.get(c, c), '')} for c in df.columns]
        out.append({'name': prefix + name, 'frame': df, 'columns': cols,
                    'sources': ['view chuẩn hoá (DataMate v6)'], 'notes': [VIEW_NOTE]})
    return out


def datamate_tables_fn(cache_dir=None, mapper_backend=None):
    """extra_tables_fn for run.predict(..., extra_tables_fn=...). A shop whose views cannot be built
    still gets its cleaned raw tables (the failure is swallowed on purpose)."""
    def fn(shop_dir, shop_id):
        try:
            from datamate.pipeline import load_shop_cached
            return canonical_tables(load_shop_cached(shop_dir, shop_id, cache_dir, mapper_backend))
        except Exception:
            return None
    return fn
