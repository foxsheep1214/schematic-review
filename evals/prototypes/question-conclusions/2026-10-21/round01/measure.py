#!/usr/bin/env python3
"""Measure the undecided-side guards on the 156 INSUFFICIENT rows of a past review round.

    python3 measure.py <round-01 dir> [-o OUT_DIR]

Writes two versions of the same rows and runs conclusions_check.py on each:

as-written  every row transcribed as it was reviewed: undecided, its missing inputs, its consequence as the
            failure path, its severity. Shows what the checker catches without changing any judgement.
rewritten   every row rewritten under the new rules according to triage.json (one reviewer's classification):
            E rows become numeric passes built only from numbers the row itself quotes, recomputed by the checker;
            B rows become passes with a BOM constraint; R rows pass as the recommended configuration with netlist
            facts; P rows stay undecided with a failure path, one gap per key (missing.same_as); N rows stay
            undecided without a failure path, so the checker refuses them; a parent row follows its children.

The reduction from E, B, R and same_as is checked by the machine; the N reduction rests on the reviewer not being
able to name a failure path, which the checker forces but cannot judge.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
import conclusions_check as cc

CLASS_OF = {'P0': 'DAMAGE_OR_HAZARD', 'P1': 'REQUIRED_FUNCTION', 'P2': 'LOCAL_OR_DATA', 'P3': 'OPTIMIZATION'}

NOTES = 'evidence/notes.md'
CLAUSES = [
    ('K-RAIL', 'REQUIREMENT', 'REQ04', '系统 3.3 V 轨 3.20–3.40 V'),
    ('K-VIN', 'ASSUMPTION', '行 PWR-C02 理由', '电池 3.7 V 经二极管后 VIN ≥ 3.2 V；USB 最高 5.25 V'),
    ('K-IEN', 'DATASHEET', 'RT9080 EN 电气表', 'EN 输入电流 0.1 µA（25 °C）'),
    ('K-RT-EN', 'DATASHEET', 'RT9080 EN 电气表', 'EN 高 > 0.9 V，低 < 0.4 V'),
    ('K-RT-ILIM', 'DATASHEET', 'RT9080 §14', '限流最小 610 mA（25 °C）'),
    ('K-ESP-PD', 'DATASHEET', 'ESP32-S3 模块 GPIO 表', '内部弱下拉约 45 kΩ（典型）'),
    ('K-ESP-VIL', 'DATASHEET', 'ESP32-S3 模块 p27', 'VIL ≤ 0.25·VDD，VDD 3.2 V 时 0.8 V'),
    ('K-ESP-ROC', 'DATASHEET', 'ESP32-S3 模块推荐工作条件', 'VDD 3.0–3.6 V'),
    ('K-DIN-II', 'DATASHEET', 'WS2812 B/C 版电气表', 'DIN 输入漏电 ≤ 1 µA（25 °C，5 V）'),
    ('K-WS-VDD', 'DATASHEET', 'WS2812 B-V6 / C-V1.2 电气表', 'VDD 最低 3.3 V（B-V6）或 3.7 V（C-V1.2）'),
    ('K-LOAD', 'REQUIREMENT', 'REQ05', 'VBATT 连续 250 mA、峰值 450 mA'),
    ('K-D2-ABS', 'DATASHEET', 'D2 绝对最大额定', 'IF 3 A'),
    ('K-MAX-IOL', 'DATASHEET', 'MAX17048 pp2-3', 'SDA/SCL VOL 0.4 V 时灌电流 4 mA'),
    ('K-SD-PU', 'STANDARD', 'SD 物理层规范 上拉电阻', 'CMD/DAT 上拉 10–100 kΩ'),
]


def inp(rng, unit, source):
    item = dict(rng) if isinstance(rng, dict) else {'value': rng}
    item['unit'] = unit
    item['from'] = {'clause': source} if isinstance(source, str) else {'db': source}
    return item


def numeric(calc, inputs, limit, unit, direction, clause):
    return {'kind': 'NUMERIC', 'calc': calc, 'inputs': inputs,
            'criterion': {'limit': limit, 'unit': unit, 'direction': direction, 'clause': clause}}


GPIO45 = numeric('vdd * (r19 * rpd / (r19 + rpd)) / (r17 + r19 * rpd / (r19 + rpd))', {
    'vdd': inp({'min': 3.2, 'max': 3.4}, 'V', 'K-RAIL'),
    'r17': inp({'min': 9.5, 'max': 10.5}, 'kΩ', {'ref': 'R17', 'parse': 'resistance'}),
    'r19': inp({'min': 95, 'max': 105}, 'kΩ', {'ref': 'R19', 'parse': 'resistance'}),
    'rpd': inp({'typical': 45}, 'kΩ', 'K-ESP-PD')}, 0.9, 'V', 'value_above_limit', 'K-RT-EN')
EN_R13 = numeric('vin - i * r', {
    'vin': inp({'min': 3.2, 'max': 5.25}, 'V', 'K-VIN'),
    'i': inp({'at_25c': 0.1, 'quantity': 'leakage_current'}, 'µA', 'K-IEN'),
    'r': inp({'min': 95, 'max': 105}, 'kΩ', {'ref': 'R13', 'parse': 'resistance'})}, 0.9, 'V', 'value_above_limit', 'K-RT-EN')


def i2c(ref):
    return numeric('(vdd - vol) / r', {
        'vdd': inp(3.4, 'V', 'K-RAIL'), 'vol': inp(0.4, 'V', 'K-MAX-IOL'),
        'r': inp({'min': 2.09, 'max': 2.31}, 'kΩ', {'ref': ref, 'parse': 'resistance'})}, 4, 'mA', 'value_below_limit', 'K-MAX-IOL')


def engineering(row):
    """Numeric pass for an E row, from numbers the row quotes; None when the row quotes too little."""
    key, rid = row['key'], row['id']
    if key == 'I2C电平':
        return i2c('R12' if 'SCL' in rid else 'R15')
    if key == 'GPIO45 EN默认' or (key == 'LDO EN漏电' and '.U1' in rid or 'PHYSICAL-U1' in rid):
        return GPIO45
    if key == 'LDO EN漏电':
        return EN_R13
    if key == 'GPIO46默认':
        return numeric('i * r', {'i': inp({'at_25c': 1, 'quantity': 'leakage_current'}, 'µA', 'K-DIN-II'), 'r': inp({'typical': 45}, 'kΩ', 'K-ESP-PD')},
                       0.8, 'V', 'value_below_limit', 'K-ESP-VIL')
    if key == '3.3V轨容量':
        load = 0.25 if rid.endswith('3-3V') else 0.2
        return numeric('ilim - iload', {'ilim': inp({'at_25c': 0.61}, 'A', 'K-RT-ILIM'),
                                        'iload': inp(load, 'A', 'K-LOAD')}, 0, 'A', 'value_above_limit', 'K-RT-ILIM')
    if key == '电池二极管VF':
        return numeric('i', {'i': inp(0.45, 'A', 'K-LOAD')}, 3, 'A', 'value_below_limit', 'K-D2-ABS')
    if key == 'ESP全温门限' and rid == 'DEV-C05.U3':
        return numeric('vdd - vmin', {'vdd': inp({'min': 3.2, 'max': 3.4}, 'V', 'K-RAIL'),
                                      'vmin': inp(3.0, 'V', 'K-ESP-ROC')}, 0, 'V', 'value_above_limit', 'K-ESP-ROC')
    return None


# Keys the triage kept apart whose rows wait on word-for-word the same missing input as another key's owner
# (the checker's DUPLICATE_GAP finds them): they share that owner's gap.
MERGED = {'启动段调节窗口': '电池态LDO余量', 'LDO套开关规则': '电池态LDO余量', 'USB态LDO窗口': '电池态LDO余量'}
WHY = {}
# E keys whose quoted numbers no longer decide once the quantity's own floor applies: what stays open and how it fails.
OPENED = {'GPIO46默认': {
    'mechanism': '热态 DIN 漏电经内部下拉把 GPIO46 抬过 VIL，上电 strap 读错',
    'missing': {'what': 'WS2812 DIN 输入漏电在最高工作温度下的保证值（手册只给 25 °C ≤1 µA）', 'from': 'VENDOR',
                'closes_when': '取得高温漏电上限，或在 GPIO46 加外部下拉使漏电压降有界'},
    'severity': {'level': 'P1', 'class': 'REQUIRED_FUNCTION', 'consequence': '启动模式读错，无法正常启动'}}}

# Board-level procurement rows name no object; the parts their constraint is on.
KEY_REFS = {'R8额定': ['R8'], '连接器载流': ['J1', 'J3', 'J4'], 'LDO输出Ceff': ['C1', 'C3', 'C4', 'C5', 'C7', 'C8', 'C11', 'C13'],
            '连接器/LED针序': ['J1', 'J2', 'J3', 'J4', 'D1', 'D4', 'D5']}


# A parent row (REQ-Q07 / REQ-D01) follows the key of its child that stays open; None: its children all close.
PARENT = {146: None, 147: None, 148: '电池态LDO余量', 149: None, 150: '电池态LDO余量', 151: 'EN复位RC',
          152: '电池态LDO余量', 153: None, 154: None, 155: None}

D6_WINDOW = numeric('vdd - vmin', {'vdd': inp({'min': 3.2, 'max': 3.4}, 'V', 'K-RAIL'),
                                   'vmin': inp({'min': 3.3, 'max': 3.7}, 'V', 'K-WS-VDD')}, 0, 'V', 'value_above_limit', 'K-WS-VDD')


def fill(basis):
    """Add the result range the checker will recompute (the reviewer writes it; here taken from the checker)."""
    if basis and basis.get('kind') == 'NUMERIC':
        probe = cc.Checker([], [], [], {}, '.')
        ranges = {n: tuple(v * cc.unit_scale(i['unit']) for v in cc._input_range(i)) for n, i in basis['inputs'].items()}
        import itertools
        vals = [probe._compute(basis, dict(zip(ranges, c))) / cc.unit_scale(basis['criterion']['unit'])
                for c in itertools.product(*[sorted(set(r)) for r in ranges.values()])]
        basis = dict(basis, result={'min': min(vals), 'max': max(vals)})
    return basis


def decided_pass(basis):
    """True when the worst corner of a filled numeric basis already passes."""
    lo, hi = basis['result']['min'], basis['result']['max']
    limit = basis['criterion']['limit']
    return limit - hi > 0 if basis['criterion']['direction'] == 'value_below_limit' else lo - limit > 0


def as_written(row, check):
    o = check['binding']['object']
    ia = check.get('impact_assessment') or {}
    vendor = check['gap_cause'] == 'EXTERNAL_DATA'
    c = {'question': row['id'], 'outcome': 'UNDECIDED',
         'missing': {'what': ' | '.join(check.get('missing_inputs') or []), 'from': 'VENDOR' if vendor else 'DESIGN',
                     'closes_when': '取得缺失输入后重判'},
         'failure_path': {'mechanism': ia.get('consequence') or '', **({'state': o['state']} if o.get('state') else {})},
         'severity': {'level': check['potential_severity'], 'class': CLASS_OF[check['potential_severity']],
                      'consequence': ia.get('consequence') or ''}}
    if vendor:
        c['searched'] = [{'source': e['source'], 'locator': str(e['locator'])} for e in check.get('evidence') or []]
    return c


def rewritten(row, check, first, db):
    base = as_written(row, check)
    o = check['binding']['object']
    cls, key = row['cls'], row['key']
    if cls == 'Q':
        key = PARENT[row['i']]
        if key is None:
            return None
        return {'question': row['id'], 'outcome': 'UNDECIDED', 'missing': {'same_as': first[key]},
                'failure_path': {'mechanism': WHY[key]}}
    opened = None
    if cls == 'E':
        basis = engineering(row)
        if basis is not None and decided_pass(fill(basis)):
            return {'question': row['id'], 'outcome': 'PASS', 'basis': fill(basis)}
        # quotes too little to rewrite, or the floor leaves it open: stays open on its own gap
        opened, cls = (fill(basis) if basis else None), 'P'
    if cls == 'B':
        tail = row['id'].split('.')[-1].replace('PHYSICAL-', '')
        refs = [r for r in (o.get('refs') or [o.get('ref'), tail]) if r in db['parts']] or KEY_REFS[key]
        return {'question': row['id'], 'outcome': 'PASS',
                'basis': {'kind': 'CONSTRAINT', 'refs': refs, 'requires': row['why']}}
    if cls == 'R':
        return {'question': row['id'], 'outcome': 'PASS', 'basis': {
            'kind': 'RECOMMENDED', 'clause': 'K-SD-PU', 'deviations': [],
            'facts': [{'ref': r, 'ref_value_is': '10k', 'means': 'SD 上拉 10 kΩ，在规范范围内'} for r in
                      ('R1', 'R2', 'R3', 'R4', 'R5', 'R6')]}}
    path = dict(base['failure_path'], mechanism=row['why'] if cls == 'P' else '')
    owner = first.get(MERGED.get(key, key))
    if owner != row['id']:
        return {'question': row['id'], 'outcome': 'UNDECIDED', 'missing': {'same_as': owner}, 'failure_path': path}
    c = dict(base)
    c['failure_path'] = path
    if key == 'D6供电窗口':
        opened, c['loose_input'] = fill(D6_WINDOW), 'vdd'
    elif opened:
        c['loose_input'] = next(n for n, i in opened['inputs'].items() if any(k in i for k in cc.ENGINEERING))
        c['missing'], c['severity'] = OPENED[key]['missing'], OPENED[key]['severity']
        c['failure_path'] = dict(path, mechanism=OPENED[key]['mechanism'])
    if opened:
        c['basis'] = opened
        c.pop('searched', None)
    return c


def run(round_dir, out_dir):
    results = json.loads((round_dir / 'review-results.json').read_text(encoding='utf-8'))
    db = json.loads((round_dir / 'review-corrected-v1' / 'db.json').read_text(encoding='utf-8'))
    rows = json.loads((HERE / 'triage.json').read_text(encoding='utf-8'))
    checks = {c['id']: c for c in results['checks'] if c.get('review_result') == 'INSUFFICIENT'}
    assert len(rows) == len(checks) == 156
    (out_dir / 'evidence').mkdir(parents=True, exist_ok=True)
    (out_dir / NOTES).write_text('# 条款出处\n\n' + '\n'.join('- %s（%s）：%s，%s' % (k, kind, loc, says)
                                 for k, kind, loc, says in CLAUSES) + '\n', encoding='utf-8')
    clauses = [{'id': k, 'kind': kind, 'source': NOTES, 'locator': loc, 'says': says} for k, kind, loc, says in CLAUSES]

    def question(row):
        state = checks[row['id']]['binding']['object'].get('state')
        return {'id': row['id'], 'rules': [row['id'].split('.')[0]], 'check_ids': [row['id']],
                'conditions': {'states': [state] if state else []}, 'observations': []}

    # The first row of each key that stays open owns the gap; the rest say same_as.
    first = {}
    for row in rows:
        basis = engineering(row) if row['cls'] == 'E' else None
        if row['cls'] in ('P', 'N') or (row['cls'] == 'E' and not (basis and decided_pass(fill(basis)))):
            first.setdefault(row['key'], row['id'])
            WHY.setdefault(row['key'], OPENED[row['key']]['mechanism'] if row['key'] in OPENED else row['why'])
    versions = {
        'as-written': [as_written(r, checks[r['id']]) for r in rows],
        'rewritten': [c for c in (rewritten(r, checks[r['id']], first, db) for r in rows) if c],
    }
    metrics = {}
    for name, conclusions in versions.items():
        answered = {c['question'] for c in conclusions}
        qs = {'questions': [question(r) for r in rows if r['id'] in answered]}
        d = out_dir / name
        d.mkdir(exist_ok=True)
        for fname, data in (('questions.json', qs), ('clauses.json', clauses), ('conclusions.json', conclusions)):
            (d / fname).write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        out = cc.check(qs, clauses, conclusions, db, out_dir)
        (d / 'check.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        refused = {e['question'] for e in out['errors']}
        metrics[name] = {
            'rows': len(rows), 'questions': len(qs['questions']), 'outcomes': out['summary']['outcomes'],
            'gaps': out['summary']['gaps'], 'constraints': len(out['summary']['constraints']),
            'errors_by_code': dict(Counter(e['code'] for e in out['errors'])),
            'refused_questions': len(refused),
            'derived': {o: n for o, n in Counter(x['outcome'] for x in out['derived']).items()}}
    by_class = Counter(r['cls'] for r in rows)
    metrics['triage'] = {'rows_by_class': dict(by_class),
                         'gaps_by_class': {k: len({r['key'] for r in rows if r['cls'] == k}) for k in by_class},
                         'e_rows_rewritten': sum(1 for r in rows if r['cls'] == 'E' and engineering(r) is not None)}
    (out_dir / 'metrics.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return metrics


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('round_dir')
    parser.add_argument('-o', '--out', default=str(HERE))
    args = parser.parse_args(argv)
    print(json.dumps(run(Path(args.round_dir), Path(args.out)), ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
