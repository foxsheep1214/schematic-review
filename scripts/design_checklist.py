#!/usr/bin/env python3
"""A reconciliation list from ASG's design records: what the designer computed and which pin maps it wrote, as a
list of objects for SR to check on its own, never as evidence (Matrix R2 6.4, 2026-11-04).

    python3 scripts/design_checklist.py --design-closure <ASG>/record/design-closure.json \
        --reference-input <ASG>/record/reference-input.json [--scheme-criteria <ASG>/record/scheme-criteria.json] \
        [--results review-results.json] --json design-checklist.json

What is read: from each calculation its id, kind, the parts (refs) and requirements it is about, and the name of each
check it makes with every number taken out (`反接时 LTC4359 IN 对 VSS 幅值 vs 绝对最大 〈值〉`); from each pin map the
part, its part number and the pin numbers. What is not read: values, limits, operators, ratings, uncertainties,
parameters, coverage and conclusions. From scheme-criteria.json (ASG task 1.3) only each key block, its circuit
types and the design-rule ids it says can exclude a candidate scheme; not which candidate, why, or how the chosen
scheme meets it: SR checks each rule against the drawn circuit itself. The list says what to look at; SR computes every value itself from the
requirements, the design results and the manufacturers' documents (SKILL.md 审查纪律 1: designer records are clues
only). The list is not an input of the review: intent and evidence that cite it, or the ASG files, are refused
(independence.py), so it never reaches the ledger or the report.

With --results the list marks the parts no function of the SR ledger names yet: work still to do, not a finding.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SCHEMA_VERSION = 1
# a number with an optional unit: 40 V, 25.2 V, 1.68 A, −40～+70 ℃, 3.3 mΩ, 10 %
NUMBER_RE = re.compile(r'[−+-]?\d+(?:\.\d+)?(?:\s*[～~–-]\s*[−+-]?\d+(?:\.\d+)?)?\s*'
                       r'(?:[kMmunpµ]?(?:V|A|W|Ω|ohm|F|H|Hz|s)|℃|°C|%)?(?![A-Za-z0-9])')
VALUE = '〈值〉'
REF_WORD = r'(?<![A-Za-z0-9_]){}(?![A-Za-z0-9_])'


def unvalued(text):
    """The name with every number (and its unit) replaced by 〈值〉; part numbers like U201 or LTC4359 stay."""
    return NUMBER_RE.sub(lambda m: VALUE if re.match(r'[−+-]?\d', m.group(0)) and not _inside_word(m) else m.group(0),
                         str(text or '')).strip()


def _inside_word(match):
    """A digit run glued to letters on its left (U201, LTC4359, SN74HCS02) is a name, not a value."""
    text, start = match.string, match.start()
    return start > 0 and (text[start - 1].isalpha() or text[start - 1] == '_')


def _source(path):
    raw = Path(path).read_bytes()
    return json.loads(raw.decode('utf-8')), {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest()}


def calculations(closure):
    out = []
    for calc in (closure or {}).get('calculations') or []:
        if not isinstance(calc, dict) or not calc.get('id'):
            continue
        out.append({'id': calc['id'], 'kind': calc.get('kind'),
                    'refs': sorted({r for r in calc.get('refs') or [] if isinstance(r, str)}),
                    'requirements': [r for r in calc.get('requirements') or [] if isinstance(r, str)],
                    'checks': [unvalued(c.get('name')) for c in calc.get('checks') or []
                               if isinstance(c, dict) and c.get('name')]})
    return out


def pin_maps(reference):
    maps = (reference or {}).get('pin_maps') or {}
    items = maps.items() if isinstance(maps, dict) else ((m.get('ref'), m) for m in maps if isinstance(m, dict))
    out = []
    for ref, entry in sorted(items, key=lambda kv: str(kv[0])):
        if not isinstance(entry, dict) or not ref:
            continue
        identity = entry.get('identity') if isinstance(entry.get('identity'), dict) else {}
        out.append({'ref': ref, 'mpn': identity.get('mpn') or identity.get('value'),
                    'pins': sorted((entry.get('pins') or {}).keys(), key=lambda p: (len(p), p))})
    return out


def scheme_rules(scheme):
    """Each key block of ASG's record/scheme-criteria.json with the rule ids it holds can exclude a candidate."""
    out = []
    for block in (scheme or {}).get('blocks') or []:
        if not isinstance(block, dict) or not block.get('block'):
            continue
        out.append({'block': block['block'],
                    'circuit_types': [t for t in block.get('circuit_types') or [] if isinstance(t, str)],
                    'rules': [c['id'] for c in block.get('criteria') or [] if isinstance(c, dict) and isinstance(c.get('id'), str)]})
    return out


def named_refs(results):
    """Parts the SR ledger's functions name anywhere (conditions, calculations, margins, open and fail items)."""
    text = json.dumps((results or {}).get('functions') or [], ensure_ascii=False)
    return lambda ref: re.search(REF_WORD.format(re.escape(ref)), text) is not None


def build(closure=None, reference=None, results=None, sources=(), scheme=None):
    out = {'schema_version': SCHEMA_VERSION, 'generated_by': 'scripts/design_checklist.py', 'sources': list(sources),
           'use': ('对账清单：只列设计方算过的对象与计算名、写过脚表的器件，数值与结论不读；SR 自己按需求、设计结果和原厂资料'
                   '复算，不引用本清单或设计方记录（independence.py 拒收）'),
           'calculations': calculations(closure), 'pin_maps': pin_maps(reference)}
    if scheme is not None:
        out['scheme_rules'] = scheme_rules(scheme)
    if results is not None:
        named = named_refs(results)
        for calc in out['calculations']:
            calc['refs_not_in_ledger'] = [r for r in calc['refs'] if not named(r)]
        for entry in out['pin_maps']:
            entry['in_ledger'] = named(entry['ref'])
        out['summary'] = {'calculations': len(out['calculations']),
                          'calculations_with_parts_not_in_ledger': sum(1 for c in out['calculations'] if c['refs_not_in_ledger']),
                          'pin_maps': len(out['pin_maps']),
                          'pin_maps_not_in_ledger': sum(1 for p in out['pin_maps'] if not p['in_ledger'])}
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--design-closure', help="ASG record/design-closure.json")
    parser.add_argument('--reference-input', help="ASG record/reference-input.json")
    parser.add_argument('--scheme-criteria', help='ASG record/scheme-criteria.json (task 1.3 key-block rules)')
    parser.add_argument('--results', help='review-results.json, to mark the parts the ledger does not name yet')
    parser.add_argument('--json', help='write the list here (keep it outside record/: it is not a review input)')
    args = parser.parse_args(argv)
    if not args.design_closure and not args.reference_input and not args.scheme_criteria:
        parser.error('give --design-closure, --reference-input and/or --scheme-criteria')
    closure = reference = scheme = None
    sources = []
    if args.design_closure:
        closure, source = _source(args.design_closure)
        sources.append(source)
    if args.reference_input:
        reference, source = _source(args.reference_input)
        sources.append(source)
    if args.scheme_criteria:
        scheme, source = _source(args.scheme_criteria)
        sources.append(source)
    results = json.loads(Path(args.results).read_text(encoding='utf-8')) if args.results else None
    out = build(closure, reference, results, sources)
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.json:
        Path(args.json).write_text(text + '\n', encoding='utf-8')
    print('对账清单：计算 %d 项，脚表 %d 份%s' % (len(out['calculations']), len(out['pin_maps']), (
        '；台账未提到的：计算涉及的器件 %(calculations_with_parts_not_in_ledger)d 项，脚表 %(pin_maps_not_in_ledger)d 份'
        % out['summary']) if 'summary' in out else ''))
    for calc in out['calculations']:
        missing = calc.get('refs_not_in_ledger')
        print('  %s %s：%s%s' % (calc['id'], calc.get('kind') or '', '、'.join(calc['refs'][:8]),
                                ('；台账未提到 ' + '、'.join(missing)) if missing else ''))
    for block in out.get('scheme_rules') or []:
        print('  方案块 %s：%s' % (block['block'], '、'.join(block['rules']) or '无'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
