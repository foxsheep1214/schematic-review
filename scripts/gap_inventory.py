#!/usr/bin/env python3
"""List what a review is still missing, before the review starts, ranked by what it unblocks.

    python3 scripts/gap_inventory.py review-plan-cold.json [--datasheet-audit datasheet-audit.json] \
        [--json gap-inventory.json] [--md 资料请求.md]

Reads the required_inputs of every waiting check and groups them by who has to
supply them: assembly data (BOM/population), part data (datasheets, pinouts,
exact part numbers), requirements, drawings, or the reviewer's own tracing.
Each request names the parts it concerns and how many checks it unblocks, so
the designer can send the few documents that open most of the review instead
of the review ending with dozens of INSUFFICIENT rows for the same missing file.
This is a work list, never a verdict.
"""
import argparse
from collections import OrderedDict, defaultdict
import json
import re
import sys

from electrical_contract import load_json

# Who supplies an input, keyed by the text before the first ':' (or the whole key).
OWNERS = OrderedDict((
    ('assembly', ('装配资料（BOM/装配表）', ('population', 'population-unverified', 'assembly state unverified',
                                          'intent.assemblies'))),
    ('part_data', ('器件资料（手册、脚表、准确型号）', ('datasheet', 'datasheets', 'datasheet-requirement',
                                                  'official-full-pinout', 'unverified-device-pinout',
                                                  'intent.devices', 'intent.device_kinds', 'datasheet/platform',
                                                  'connector drawing/opposite-side pinout', 'datasheet-audit'))),
    ('requirements', ('需求与平台约束', ('requirements', 'platform_checklist', 'power_rails', 'firmware'))),
    ('drawings', ('图纸', ('schematic_pdf',))),
))
REVIEWER = ('reviewer', '审查者自行追踪或计算（不向设计方索取）')
REF_RE = re.compile(r'^[A-Z]{1,4}\d+$')
# Plain resistors and capacitors are judged on conservative floors (references/commodity-floors.md), so their
# datasheets are the reviewer's own tracking, never a request to the designer (R6 acceptance 2026-10-24, codex1
# SR-01: 93 of them were listed as vendor material gaps). Safety capacitors (CX/CY), varistors and thermistors are not.
COMMODITY_REF_RE = re.compile(r'^[RC]\d+$')
COMMODITY_INPUT = '普通阻容的专属手册：按保守档计算（commodity-floors.md），不向设计方索取'


def commodity(refs):
    return bool(refs) and all(COMMODITY_REF_RE.match(ref) for ref in refs)


def owner_of(key):
    head = key.split(':', 1)[0].strip()
    stem = head.split('.', 2)
    if head in ('datasheet', 'datasheets', 'datasheet-audit') and commodity(refs_in(key)):
        return REVIEWER[0]
    for owner, (_, prefixes) in OWNERS.items():
        for prefix in prefixes:
            if head == prefix or head.startswith(prefix + '.') or '.'.join(stem[:2]) == prefix:
                return owner
    return REVIEWER[0]


def refs_in(key):
    """Reference designators a request names: 'population:C9', 'intent.devices.U2: ...'."""
    found = set()
    head, _, tail = key.partition(':')
    for token in re.split(r'[\s.:,/+]+', head + ' ' + tail.split(' ', 1)[0]):
        if REF_RE.match(token) and not re.match(r'^(SIG|PWR|DEV|DOC|REQ|PRO|NET|DRV|RST|ANA)\d', token):
            found.add(token)
    return sorted(found)


def group_key(entry):
    """One request per thing the supplier sends: one BOM answers every population gap,
    one datasheet answers a part's pinout, kind and ratings."""
    head = entry['input'].split(':', 1)[0].strip()
    if entry['owner'] == 'part_data' and len(entry['refs']) == 1:
        return ('part', entry['refs'][0])
    if entry['owner'] == REVIEWER[0] and head in ('datasheet', 'datasheets', 'datasheet-audit') and commodity(entry['refs']):
        return ('commodity',)
    if entry['owner'] in ('assembly', REVIEWER[0]) and entry['refs']:
        return ('kind', entry['owner'], head)
    rail = re.match(r'^(power_rails\..+?)\.(?:available_a_min|citation|load_a|refs|state|voltage_v)\b', head)
    if rail:
        return ('kind', entry['owner'], rail.group(1))
    return ('input', entry['input'])


def group(entries):
    merged = OrderedDict()
    for entry in entries:
        key = group_key(entry)
        target = merged.setdefault(key, {'owner': entry['owner'], 'inputs': [], 'refs': set(), 'checks': [],
                                         'rules': set()})
        target['inputs'].append(entry['input'])
        target['refs'].update(entry['refs'])
        target['checks'] += entry['checks']
        target['rules'] |= entry['rules']
        if entry.get('status'):
            target['status'] = entry['status']
        if key[0] == 'part':
            target['input'] = '%s 的器件资料' % key[1]
        elif key[0] == 'commodity':
            target['input'] = COMMODITY_INPUT
        elif key[0] == 'kind':
            target['input'] = key[2]
        else:
            target['input'] = entry['input']
    return merged.values()


def finish(entry):
    return dict(entry, refs=sorted(entry['refs']), rules=sorted(r for r in entry['rules'] if r),
                checks=sorted({c for c in entry['checks'] if c}), unblocks=len({c for c in entry['checks'] if c}))


def build(plan, audit=None):
    requests = OrderedDict()
    for check in plan.get('checks') or []:
        if not isinstance(check, dict) or check.get('readiness') != 'WAITING_EVIDENCE':
            continue
        for key in check.get('required_inputs') or []:
            if not isinstance(key, str) or not key.strip():
                continue
            entry = requests.setdefault(key, {'input': key, 'owner': owner_of(key), 'refs': refs_in(key),
                                              'checks': [], 'rules': set()})
            entry['checks'].append(check.get('id'))
            entry['rules'].add(check.get('rule'))
    for material in (audit or {}).get('materials') or []:
        if isinstance(material, dict) and material.get('status') in ('MISSING', 'NOT_FOUND'):
            key = 'datasheet-audit:%s' % material.get('identity')
            refs = sorted(material.get('refdes') or [])
            entry = requests.setdefault(key, {'input': key, 'owner': REVIEWER[0] if commodity(refs) else 'part_data',
                                              'refs': refs, 'checks': [], 'rules': set()})
            entry['status'] = material.get('status')
    rows = sorted((finish(e) for e in group(requests.values())), key=lambda e: (-e['unblocks'], e['input']))
    by_owner = OrderedDict((owner, []) for owner in list(OWNERS) + [REVIEWER[0]])
    for row in rows:
        by_owner[row['owner']].append(row)
    by_ref = defaultdict(set)
    for row in rows:
        if row['owner'] != REVIEWER[0]:
            for ref in row['refs']:
                by_ref[ref].add(row['input'])
    waiting = {c.get('id') for c in plan.get('checks') or [] if isinstance(c, dict)
               and c.get('readiness') == 'WAITING_EVIDENCE'}
    external = {c for row in rows if row['owner'] != REVIEWER[0] for c in row['checks']}
    return {'schema_version': 1,
            'summary': {'checks': len(plan.get('checks') or []), 'waiting_checks': len(waiting),
                        'waiting_on_external_inputs': len(external),
                        'requests': {owner: len(items) for owner, items in by_owner.items()}},
            'by_owner': by_owner,
            'by_ref': OrderedDict(sorted((ref, sorted(v)) for ref, v in by_ref.items())),
            'note': 'Work list from the plan; the count is how many waiting checks name the input, not a severity.'}


def markdown(inventory, limit=40):
    names = dict({k: v[0] for k, v in OWNERS.items()}, **{REVIEWER[0]: REVIEWER[1]})
    s = inventory['summary']
    out = ['# 审查前的资料请求', '',
           '共 %d 条检查，其中 %d 条还在等资料；%d 条等的是设计方或供应商能提供的资料。'
           '按“能解开的检查条数”从多到少列出，先补前面的几项。' % (
               s['checks'], s['waiting_checks'], s['waiting_on_external_inputs']), '']
    for owner, rows in inventory['by_owner'].items():
        if not rows:
            continue
        out += ['## %s（%d 项）' % (names[owner], len(rows)), '', '| 需要的资料 | 涉及位号 | 解开检查数 | 涉及规则 |',
                '|---|---|---:|---|']
        for row in rows[:limit]:
            refs = '、'.join(row['refs'][:8]) + ('等' if len(row['refs']) > 8 else '')
            heads = list(OrderedDict.fromkeys(x.split(':', 1)[0].strip() for x in row['inputs']))
            what = row['input'] if len(row['inputs']) == 1 else '%s（%s）' % (
                row['input'], '%d 个位号' % len(row['refs']) if row['refs'] and not row['input'].endswith('器件资料')
                else '、'.join(h[len(row['input']) + 1:] if h.startswith(row['input'] + '.') else h for h in heads[:6]))
            out.append('| %s | %s | %d | %s |' % (what.replace('|', '\\|'), refs or '—', row['unblocks'],
                                                 '、'.join(row['rules'][:6])))
        if len(rows) > limit:
            out.append('| 另有 %d 项，见 JSON |  |  |  |' % (len(rows) - limit))
        out.append('')
    return '\n'.join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('plan')
    parser.add_argument('--datasheet-audit')
    parser.add_argument('--json')
    parser.add_argument('--md')
    args = parser.parse_args(argv)
    try:
        plan = load_json(args.plan)
        audit = load_json(args.datasheet_audit) if args.datasheet_audit else None
    except (OSError, ValueError) as error:
        print('ERROR:', error)
        return 2
    if not isinstance(plan, dict) or not isinstance(plan.get('checks'), list):
        print('ERROR: plan must be a review plan with checks')
        return 2
    inventory = build(plan, audit)
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as handle:
            json.dump(inventory, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
    text = markdown(inventory)
    if args.md:
        with open(args.md, 'w', encoding='utf-8') as handle:
            handle.write(text + '\n')
    else:
        print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
