"""Hot-rule bench: real open boards plus transcribed datasheet facts, run through SR's evidence rules.

Each case binds evidence checks to placeholder documents that name the real source (sources.json
keeps URL and SHA-256), runs lint with intent + evidence, and compares the per-check result with
the hand-classified answer. Each mutation applies one value or connection change and must flip the
checks it lists; every other check keeps its unmutated answer.

    python3 -B evals/hot_bench/run.py [--sut <SR root>] [--json out.json]
Exit 1 on any MISMATCH.
"""
import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent


def load_sr(root):
    sys.path.insert(0, str(Path(root) / 'scripts'))
    import parse_kicad
    from lint import Lint
    from audit_datasheets import build_datasheet_audit
    from electrical_contract import db_fingerprint, dependency_refs, document_fingerprint, validate_evidence
    return parse_kicad, Lint, build_datasheet_audit, db_fingerprint, dependency_refs, document_fingerprint, validate_evidence


def mutate(db, intent, checks, mutation):
    db, intent, checks = copy.deepcopy(db), copy.deepcopy(intent), copy.deepcopy(checks)
    for a, b in [mutation['swap_pin_names']] if 'swap_pin_names' in mutation else []:
        for table in ('pinname', 'declared_pinname'):
            names = db.get(table) or {}
            names[a], names[b] = names.get(b), names.get(a)
            for node in (a, b):
                if names.get(node) is None:
                    names.pop(node, None)
    for ref in mutation.get('remove_parts', []):
        db['parts'].pop(ref)
        for node in [n for n in db['pin2net'] if n.split('.')[0] == ref]:
            net = db['pin2net'].pop(node)
            db['nets'][net] = [n for n in db['nets'][net] if n != node]
            for table in ('pinname', 'pintype', 'declared_pinname', 'declared_pintype'):
                (db.get(table) or {}).pop(node, None)
    if 'add_resistor' in mutation:
        r = mutation['add_resistor']
        db['parts'][r['ref']] = {'value': r['value'], 'part': 'R', 'prim': 'Device:R', 'nc': False}
        for pin, end in (('1', r['a']), ('2', r['b'])):
            net = db['pin2net'][end] if '.' in end else end
            node = '%s.%s' % (r['ref'], pin)
            db['pin2net'][node] = net
            db['nets'].setdefault(net, []).append(node)
            db['pintype'][node] = 'PASSIVE'
    for net, window in (mutation.get('intent_rail') or {}).items():
        intent.setdefault('power_rails', {}).setdefault(net, {})['voltage_v'] = window
    for cid, override in (mutation.get('evidence_override') or {}).items():
        check = next(c for c in checks if c['id'] == cid)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(check.get(key), dict):
                check[key] = dict(check[key], **value)
            else:
                check[key] = value
    return db, intent, checks


def bind(sr, db, checks, sources, directory):
    _, _, build_audit, db_fp, dep_refs, doc_fp, _ = sr
    by_ref = {}
    for check in checks:
        for ref in dep_refs(db, check):
            by_ref.setdefault(ref, check['source'])
    pending = build_audit(db, required_refs=sorted(by_ref))
    entries = []
    for material in pending['materials']:
        # Parts the checks only touch through the netlist (pull resistors, dividers) carry no source.
        source = next((by_ref[r] for r in material['refdes'] if r in by_ref), None)
        doc = sources['documents'][source] if source else {'url': 'board BOM value', 'sha256': '-', 'title': 'BOM'}
        path = Path(directory) / (material['material_id'] + '.pdf')
        path.write_bytes(('%%PDF-1.4\nhot_bench placeholder for %s\n%s\nsha256 %s\n'
                          % (source or material['identity'], doc['url'], doc['sha256'])).encode())
        entries.append({'identity': material['identity'], 'status': 'FOUND', 'identity_verified': True,
                        'source_kind': 'package', 'path': str(path),
                        'document_model': material['identity'], 'document_version': doc['title']})
    audit = build_audit(db, resolution={'schema_version': 1, 'entries': entries}, required_refs=sorted(by_ref))
    evidence = {'schema_version': 2, 'checks': []}
    for check in checks:
        item = {k: v for k, v in check.items() if k != 'source'}
        refs = []
        for ref in dep_refs(db, item):
            material = next(x for x in audit['materials'] if ref in x['refdes'])
            document = material['document']
            refs.append({'ref': ref, 'identity': material['identity'], 'document_model': document['document_model'],
                         'document_version': document['document_version'], 'sha256': doc_fp(document['path']),
                         'locator': check['citation'], 'identity_resolution': 'board BOM value matches the datasheet part'})
        item['basis'] = {'db_sha256': db_fp(db), 'state': 'board as published; stated operating conditions',
                         'sources': refs}
        evidence['checks'].append(item)
    return evidence, audit


def run_case(sr, case, sources, mutation=None):
    parse_kicad, Lint, *_ = sr
    validate = sr[-1]
    db = parse_kicad.parse((HERE / case['fixture']).read_text(encoding='utf-8'))
    intent, checks = case.get('intent') or {}, case['checks']
    if mutation:
        db, intent, checks = mutate(db, intent, checks, mutation)
    with tempfile.TemporaryDirectory() as tmp:
        evidence, audit = bind(sr, db, checks, sources, tmp)
        errors = validate(evidence)
        if errors:
            return {c['id']: 'EVIDENCE_INVALID: ' + '; '.join(errors[:2]) for c in checks}
        lint = Lint(db, intent=intent, evidence=evidence, datasheet_audit=audit)
        lint.run()
        got = {}
        for item in lint.results:
            if item.get('check_id') in {c['id'] for c in checks}:
                got[item['check_id']] = item.get('review_result') or item.get('kind')
        return {c['id']: got.get(c['id'], 'NOT_RUN') for c in checks}


def run(root):
    sr = load_sr(root)
    cases = json.loads((HERE / 'cases.json').read_text(encoding='utf-8'))
    sources = json.loads((HERE / 'sources.json').read_text(encoding='utf-8'))
    rows = []
    for case in cases['cases']:
        base = run_case(sr, case, sources)
        for cid, want in case['expected'].items():
            rows.append({'case': case['id'], 'variant': 'as-published', 'check': cid,
                         'expected': want, 'actual': base[cid], 'status': 'MATCH' if base[cid] == want else 'MISMATCH'})
        for mutation in case.get('mutations', []):
            got = run_case(sr, case, sources, mutation)
            for cid, want in dict(case['expected'], **mutation['expected']).items():
                rows.append({'case': case['id'], 'variant': mutation['id'], 'check': cid, 'expected': want,
                             'actual': got[cid], 'status': 'MATCH' if got[cid] == want else 'MISMATCH'})
    return {'revision': cases['revision'], 'rows': rows,
            'mismatches': sum(r['status'] == 'MISMATCH' for r in rows)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--sut', default=str(HERE.parents[1]))
    parser.add_argument('--json')
    args = parser.parse_args(argv)
    result = run(args.sut)
    for row in result['rows']:
        if row['status'] != 'MATCH':
            print('%(status)s %(case)s/%(variant)s %(check)s expected=%(expected)s actual=%(actual)s' % row)
    print('%d rows, %d mismatches' % (len(result['rows']), result['mismatches']))
    if args.json:
        Path(args.json).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
    return 1 if result['mismatches'] else 0


if __name__ == '__main__':
    sys.exit(main())
