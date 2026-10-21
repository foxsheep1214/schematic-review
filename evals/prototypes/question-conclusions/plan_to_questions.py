#!/usr/bin/env python3
"""Prototype: turn a review plan into questions (docs/2026-10-20-question-conclusion-design.md §3.1).

    python3 plan_to_questions.py review-plan.json -o questions.json [--strict]

One question per (subject, concern). A circuit's rows merge across states into one question per rule,
and circuits whose rows of one rule name the same parts and nets share that question (one judgement, not
one per circuit); rules that are facets of one concern on one subject (the four decoupling rules on a
supply group, the pin rules on a device) merge into one question. Plan rows marked NA are left out; every other row is
traced by exactly one question (`check_ids`). Tool observations travel with the question: inventory
gaps as MISSING_INPUT (flagged `input` when the review supplies it), lint findings as SUSPECT.
--strict exits 1 when any input gap is still open (the design wants those supplied before questions).
This never touches the main review path.
"""
import argparse
import hashlib
import json
import sys
from collections import OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
import catalog
from validate_review import input_gap

SCHEMA = 'question-conclusions-proto-1'
# Rules that are facets of one concern on one subject.
CONCERNS = {
    'DECOUPLING': ('PWR-C09', 'PWR-C10', 'PWR-D02', 'PWR-T03'),
    'PINS': ('DEV-D02', 'DEV-D05'),
}
CONCERN_OF = {rule: name for name, rules in CONCERNS.items() for rule in rules}
# Object fields that name a tool inventory item; the first present one is the subject.
INVENTORY_KEYS = ('decoupling_group', 'i2c_region', 'inductive_load', 'power_switch', 'input_filter',
                  'power_up', 'diff_pair', 'supervision', 'optocoupler', 'passive_stress')
PLAIN_KEYS = ('ref', 'net', 'feature', 'requirement_id', 'circuit_type', 'board')


def subject_of(obj, check_id):
    """(kind, name) the row is about."""
    if obj.get('circuit'):
        return 'circuit', obj['circuit']
    for key in INVENTORY_KEYS:
        if obj.get(key):
            return key, str(obj[key])
    if not obj.get('ref') and isinstance(obj.get('node'), str):
        return 'ref', obj['node'].split('.')[0]
    for key in PLAIN_KEYS:
        if obj.get(key):
            return key, str(obj[key])
    if obj.get('page') is not None:
        return 'page', str(obj['page'])
    return 'check', check_id


def _anchors(obj):
    refs = [obj['ref']] if isinstance(obj.get('ref'), str) else []
    refs += [r for r in obj.get('refs') or [] if isinstance(r, str)]
    if isinstance(obj.get('node'), str):
        refs.append(obj['node'].split('.')[0])
    nets = [obj['net']] if isinstance(obj.get('net'), str) else []
    nets += [n for n in obj.get('nets') or [] if isinstance(n, str)]
    return refs, nets


def _region_gaps(plan):
    gaps = {}
    for state in (plan.get('i2c_topology') or {}).get('states') or []:
        for region in state.get('regions') or []:
            if isinstance(region, dict) and region.get('id'):
                gaps.setdefault(region['id'], []).extend(g for g in region.get('gaps') or [] if isinstance(g, str))
    return gaps


def _uniq(values):
    return list(OrderedDict.fromkeys(v for v in values if v))


def build(plan):
    region_gaps = _region_gaps(plan)
    groups = OrderedDict()
    for check in plan.get('checks') or []:
        if not isinstance(check, dict) or check.get('applicability') == 'NA':
            continue
        cid, rule = check['id'], check.get('rule') or check['id'].split('.')[0]
        obj = check.get('object') if isinstance(check.get('object'), dict) else {}
        kind, name = subject_of(obj, cid)
        concern = CONCERN_OF.get(rule) if kind != 'circuit' else None
        if kind == 'circuit':
            refs, nets = _anchors(obj)
            parts = (tuple(sorted(set(refs))), tuple(sorted(set(nets))))
            key = (kind, parts if any(parts) else name, rule)
        else:
            key = (kind, name, concern or rule)
        group = groups.setdefault(key, {'rows': [], 'concern': concern or rule, 'kind': kind, 'names': []})
        group['rows'].append((check, obj))
        if name not in group['names']:
            group['names'].append(name)
    questions, inputs = [], []
    for group in groups.values():
        rows, kind, name = group['rows'], group['kind'], '+'.join(group['names'])
        rules = sorted({c.get('rule') or c['id'].split('.')[0] for c, _ in rows})
        refs, nets = [], []
        for _, obj in rows:
            r, n = _anchors(obj)
            refs += r
            nets += n
        label = name if kind not in INVENTORY_KEYS else ' '.join(_uniq(refs + nets)) or name
        asks = _uniq(c.get('question', '').split('（')[0] for c, _ in rows) or [
            '%s：%s' % (label, '；'.join(catalog.title(r) or r for r in rules))]
        observations = []
        for check, obj in rows:
            for gap in (check.get('inventory_gaps') or []) + region_gaps.get(obj.get('i2c_region'), []):
                observations.append(('MISSING_INPUT', gap))
            if check.get('lint_kind') and isinstance(obj.get('lint_detail'), str):
                observations.append(('SUSPECT', obj['lint_detail']))
        observations = [{'id': 'O-%d' % (i + 1), 'kind': k, 'says': s,
                         'input': k == 'MISSING_INPUT' and input_gap(s)}
                        for i, (k, s) in enumerate(_uniq(observations))]
        inputs += [o['says'] for o in observations if o['input']]
        slug = hashlib.sha1(json.dumps([kind, name, group['concern']], ensure_ascii=False).encode()).hexdigest()[:10]
        questions.append({
            'id': 'Q-%s-%s' % (group['concern'], slug),
            'concern': group['concern'],
            'subject': {'kind': kind, 'name': name,
                        **({'circuit': name, 'circuits': group['names']} if kind == 'circuit' else {}),
                        'refs': _uniq(refs), 'nets': _uniq(nets)},
            'ask': '；'.join(asks),
            'criteria': _uniq(c.get('criterion') for c, _ in rows),
            'conditions': {'states': sorted({o['state'] for _, o in rows if isinstance(o.get('state'), str)})},
            'rules': rules,
            'check_ids': [c['id'] for c, _ in rows],
            'undetermined': any(c.get('applicability') == 'UNDETERMINED' for c, _ in rows),
            'observations': observations,
        })
    return {'schema': SCHEMA,
            'questions': questions,
            'summary': {'rows': sum(len(q['check_ids']) for q in questions), 'questions': len(questions),
                        'inputs_to_supply': _uniq(inputs)}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('plan')
    parser.add_argument('-o', '--out', required=True)
    parser.add_argument('--strict', action='store_true')
    args = parser.parse_args(argv)
    out = build(json.loads(Path(args.plan).read_text(encoding='utf-8')))
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps(out['summary'], ensure_ascii=False))
    return 1 if args.strict and out['summary']['inputs_to_supply'] else 0


if __name__ == '__main__':
    sys.exit(main())
