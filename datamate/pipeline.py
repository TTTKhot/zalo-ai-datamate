"""End-to-end for one business: ingest -> map -> views -> per question intent -> metric."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from .ingest import read_business, read_readme
from .intent import build_compact_messages, build_messages, parse_intent, sanitize_intent, validate_intent
from .slots import apply_cues, normalize_params
from .timex import periods_of, reconcile_periods
from .mapper import mapping_to_json, resolve_mapping
from .metrics import NeedsReview, Unanswerable, run
from .periods import Calendar
from .profile import profile_business
from .rules import build_views
from .selfcheck import shop_check


@dataclass
class Shop:
    business_id: str
    views: object
    mapping: dict
    names: dict
    report: dict
    seconds: float


def load_shop(folder, business_id, mapper_backend=None) -> Shop:
    started = time.time()
    tables = read_business(folder)
    readme = read_readme(folder)
    profiles = profile_business(tables, readme)
    log = []
    mapping, extra = resolve_mapping(tables, profiles, readme, mapper_backend, log)
    views = build_views(tables, mapping, extra['typed'], readme, extra.get('product_attrs'))
    names = shop_names(views)
    report = {'mapping': mapping_to_json(mapping), 'checks': extra['report'], 'notes': views.notes + log,
              'coverage': [str(views.data_start), str(views.data_end)], 'concepts': sorted(views.has),
              'selfcheck': shop_check(tables, mapping, views, (readme or {}).get('text', ''))}
    return Shop(business_id, views, mapping, names, report, round(time.time() - started, 1))


def load_shop_cached(folder, business_id, cache_dir=None, mapper_backend=None) -> Shop:
    """load_shop with an optional pickle cache (GPU-free runs, SFT data, answerability data)."""
    import pickle
    cache = Path(cache_dir) / f'{business_id}_shop.pkl' if cache_dir else None
    if cache and cache.exists():
        try:
            return pickle.loads(cache.read_bytes())
        except Exception:
            pass
    shop = load_shop(folder, business_id, mapper_backend)
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(pickle.dumps(shop))
    return shop


def shop_names(views) -> dict:
    lines = views.frames.get('sales_lines')
    names = {}
    if lines is not None:
        if not getattr(views, 'service_book', False):  # a service book's "product" is the free-text job cell
            names['products'] = sorted(lines['product'].dropna().unique().tolist())
        if 'staff' in lines and getattr(views, 'service_book', False):
            names['staff'] = sorted(lines['staff'].dropna().unique().tolist())
        names['customers'] = sorted(lines['customer'].dropna().unique().tolist())
        if 'payment_method' in lines:
            names['payment_methods'] = sorted(lines['payment_method'].dropna().unique().tolist())
    prods = views.frames.get('products')
    if prods is not None and 'group' in prods:
        names['groups'] = sorted(prods['group'].dropna().unique().tolist())
    return names


def answer(shop: Shop, record: dict, intent_fn, calendar: Calendar, gate=None) -> dict:
    """intent_fn(question, as_of, names) -> intent dict (LLM or scripted).

    gate: datamate.rulebook.Gate of the split's rulebook. A question that uses a rule the metric library does not
    implement as written (new / uncovered / modified rule) is not sent to the metric route: the library would answer
    with another definition (-1), so it abstains (route 'rule_gate')."""
    started = time.time()
    out = {'id': record['id'], 'question': record['question'], 'as_of': record.get('as_of_date')}
    blocked = ((getattr(shop, 'report', None) or {}).get('selfcheck') or {}).get('block')
    if blocked:                        # the shop's files were read wrong (datamate.selfcheck): every answer is a guess
        out.update(status='abstain', route='shop_check', reason='shop self-check: ' + '; '.join(blocked))
        out['seconds'] = round(time.time() - started, 3)
        return out
    if gate is not None:
        from .normalize import norm as _norm
        hit = gate.check(_norm(record['question']))
        if hit:
            out.update(status='abstain', route='rule_gate', rule_hit=hit,
                       reason=f"rulebook {hit['status']} rule: {hit['rule']}")
            out['seconds'] = round(time.time() - started, 3)
            return out
    try:
        intent = intent_fn(record['question'], record.get('as_of_date'), shop.names)
        out['intent'] = intent
        if intent is None:
            raise NeedsReview('no intent')
        problems = validate_intent(intent, shop.names)
        if problems:
            raise NeedsReview('; '.join(problems))
        if intent.get('answerable') is False:
            raise Unanswerable('intent marked unanswerable')
        result = run(shop.views, intent, record.get('as_of_date'), calendar)
        out.update(status='answered', **result)
    except Unanswerable as exc:
        out.update(status='unanswerable', reason=str(exc))
    except NeedsReview as exc:
        out.update(status='abstain', reason=str(exc))
    except Exception as exc:                           # never crash the run
        out.update(status='abstain', reason=f'{type(exc).__name__}: {exc}')
    out['seconds'] = round(time.time() - started, 3)
    return out


def postprocess_intent(intent: dict, norm: str | None, tagged) -> list[str]:
    """Fixed clean-up shared by every intent source: date-tagger reconciliation, structural params,
    vocabulary cues, sanitize. Returns notes of what changed (in place)."""
    fixes = []
    if intent.get('metric') not in ('debt_total', 'debtor_count', 'debt_table', 'stock', 'stock_value') \
            or not intent.get('periods'):
        periods, changed = reconcile_periods(intent.get('periods'), tagged)
        if changed:
            fixes.append(f'periods {intent.get("periods")} -> {periods} (date tagger)')
            intent['periods'] = periods
    fixes += normalize_params(intent)
    fixes += apply_cues(intent, norm)
    fixes += sanitize_intent(intent)
    return fixes


def question_context(question, as_of, names, normalizer=None, hint_fn=None):
    """(rule-normalised text, date-tagger periods, LLM hint text) for one question."""
    import re as _re
    from .values import plain as _plain
    vocab = {t for n in names.get('products', []) + names.get('customers', [])
             for t in _re.findall(r'[a-z0-9]+', _plain(n))}
    norm = None
    if normalizer:
        try:
            norm = normalizer(question, vocab)
        except TypeError:
            norm = normalizer(question)
    tagged = periods_of(norm, as_of) if norm else []
    hint = norm
    if hint_fn is not None:                        # neural normaliser: hint only, guarded
        try:
            hint = hint_fn(question, names) or norm
        except Exception:
            hint = norm
    return norm, tagged, hint


def llm_intent_fn(backend, normalizer=None, max_repairs=1, trace=None, prompt='full', hint_fn=None,
                  apply_fixes=True):
    """LLM -> intent JSON -> fixed clean-up + date-tagger reconciliation -> validate (1 repair round).

    prompt: 'full' (v5 prompt with few-shot) or 'compact' (LoRA-finetuned model).
    apply_fixes: False skips the cue rules (to measure what the finetuned model learned alone).
    trace (list) receives one dict per question: raw outputs and repairs, for logs and calibration."""
    build = build_compact_messages if prompt == 'compact' else build_messages

    def fn(question, as_of, names):
        norm, tagged, hint = question_context(question, as_of, names, normalizer, hint_fn)
        messages = build(question, as_of, names, hint, tagged)
        record = {'raw': [], 'repairs': 0, 'fixes': [], 'hint': hint if hint != norm else None}
        intent = None
        for attempt in range(max_repairs + 1):
            raw = backend.generate(messages)
            record['raw'].append(raw)
            intent = parse_intent(raw)
            if intent is not None:
                if apply_fixes:
                    record['fixes'] += postprocess_intent(intent, norm, tagged)
                else:
                    record['fixes'] += sanitize_intent(intent)
            problems = ['no JSON with "metric"'] if intent is None else validate_intent(intent, names)
            if not problems:
                break
            if attempt < max_repairs:
                record['repairs'] += 1
                messages = messages + [{'role': 'assistant', 'content': raw},
                                       {'role': 'user', 'content': 'Lỗi: ' + '; '.join(problems) +
                                        '. Trả lại đúng một JSON đã sửa.'}]
        if trace is not None:
            trace.append(record)
        return intent
    return fn
