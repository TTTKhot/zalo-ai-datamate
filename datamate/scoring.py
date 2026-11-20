"""Rulebook §9 scoring (same rules as evaluate_stage4.py) + submission mapping for the new pipeline."""
from __future__ import annotations

import math
import re
import unicodedata


def _norm_text(value) -> str:
    text = unicodedata.normalize('NFC', str(value)).casefold()
    return re.sub(r'[\s\W_]+', '', text)


def to_submission(item: dict) -> dict:
    """Map one pipeline output to the official submission line."""
    qid = item.get('id') or item.get('question_id')
    status = item.get('status')
    if status == 'unanswerable':
        return {'id': qid, 'type': 'unanswerable', 'reason': str(item.get('reason', ''))}
    if status != 'answered':
        return {'id': qid, 'type': 'abstain'}
    kind = item.get('type') or item.get('answer_type', 'string')
    # predict.py logs keep the pipeline's own value in `pipeline_answer`; their `answer` is the final submission line
    answer = item['pipeline_answer'] if 'pipeline_answer' in item else item.get('answer')
    if kind == 'table' and isinstance(answer, list) and answer and isinstance(answer[0], dict):
        columns = list(answer[0].keys())
        answer = {'columns': columns, 'rows': [[row.get(c) for c in columns] for row in answer]}
    return {'id': qid, 'type': kind, 'answer': answer}


def _number_equal(a, b) -> bool:
    try:
        return math.isclose(float(a), float(b), rel_tol=0, abs_tol=1e-6 + 1e-9 * abs(float(b)))
    except (TypeError, ValueError):
        return False


def is_correct(pred: dict, gold: dict) -> bool:
    gtype = gold['type']
    if gtype == 'unanswerable':
        return pred['type'] == 'unanswerable'
    if pred['type'] in ('abstain', 'unanswerable'):
        return False
    answer, expected = pred.get('answer'), gold['answer']
    aliases = gold.get('alias') or []
    if gtype in ('number', 'percent'):
        return not isinstance(answer, (str, bool)) and _number_equal(answer, expected)
    if gtype == 'boolean':
        return answer is expected
    if gtype == 'date':
        return isinstance(answer, str) and answer[:len(expected)] == expected and len(answer) in (len(expected), len(expected) + 9)
    if gtype == 'string':
        accepted = {_norm_text(expected), *(_norm_text(a) for a in aliases)}
        return isinstance(answer, str) and _norm_text(answer) in accepted
    if gtype == 'list':
        if not isinstance(answer, list) or len(answer) != len(expected):
            return False
        for i, (a, e) in enumerate(zip(answer, expected)):
            alias = aliases[i] if i < len(aliases) else []
            ok = (_number_equal(a, e) if isinstance(e, (int, float)) else
                  _norm_text(a) in {_norm_text(e), *(_norm_text(x) for x in alias)})
            if not ok:
                return False
        return True
    if gtype == 'table':
        return isinstance(answer, dict) and answer.get('rows') and sorted(
            map(str, answer['rows'])) == sorted(map(str, expected['rows']))
    return False


