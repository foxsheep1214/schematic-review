#!/usr/bin/env python3
"""Compare parameter citations with independently transcribed manufacturer table rows.

The reviewer supplies both rows, including identity, parameter, conditions, basis,
unit, value, source, locator and the reference document SHA-256. This checks the
transcription comparison and source binding, not PDF extraction or authenticity.
An engineering limit is not a manufacturer rating. Different test conditions are
NOT_COMPARABLE, never a fabricated numeric contradiction.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

# Deliberately small, explicit unit registry. Unknown units remain unverified.
UNITS = {'T': ('flux', 1), 'mT': ('flux', 1e-3), 'V': ('voltage', 1),
         'mV': ('voltage', 1e-3), 'A': ('current', 1), 'mA': ('current', 1e-3),
         'ohm': ('resistance', 1), 'kohm': ('resistance', 1e3)}
BASES = {'typical', 'minimum', 'maximum', 'engineering_limit'}


def _validate(row, reference=False):
    if not isinstance(row, dict):
        raise ValueError('parameter row must be an object')
    for key in ('identity', 'parameter', 'basis', 'unit', 'source', 'locator'):
        if not isinstance(row.get(key), str) or not row[key].strip():
            raise ValueError('parameter row needs ' + key)
    if row['basis'] not in BASES:
        raise ValueError('unknown basis')
    if not isinstance(row.get('conditions'), dict) or not row['conditions']:
        raise ValueError('explicit test conditions required')
    json.dumps(row['conditions'], allow_nan=False)
    value = row.get('value')
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('value must be finite')
    digest = hashlib.sha256(Path(row['source']).read_bytes()).hexdigest()
    if reference:
        if digest != row.get('sha256'):
            raise ValueError('reference document hash mismatch')
    return digest


def check(claims):
    if not isinstance(claims, list) or not claims:
        return [], ['claims must be a non-empty list']
    rows, errors, seen = [], [], set()
    for index, claim in enumerate(claims):
        key = claim.get('id') if isinstance(claim, dict) else None
        if not isinstance(key, str) or not key.strip() or key in seen:
            errors.append(f'claim {index}: missing or duplicate ID')
            continue
        seen.add(key)
        try:
            a, b = claim.get('claimed'), claim.get('reference')
            claim_hash = _validate(a)
            reference_hash = _validate(b, True)
            if Path(a['source']).resolve() == Path(b['source']).resolve():
                raise ValueError('claim and independent reference must be different documents')
            context = [k for k in ('identity', 'parameter', 'conditions', 'basis') if a[k] != b[k]]
            au, bu = UNITS.get(a['unit']), UNITS.get(b['unit'])
            if 'engineering_limit' in (a['basis'], b['basis']):
                status, reason = 'OUT_OF_SCOPE', 'engineering limit needs a design-margin calculation, not attribution equality'
            elif context or not au or not bu or au[0] != bu[0]:
                status, reason = 'NOT_COMPARABLE', 'different/unsupported context: ' + ', '.join(context or ['unit'])
            else:
                match = math.isclose(a['value'] * au[1], b['value'] * bu[1], rel_tol=1e-9, abs_tol=0)
                status = 'MATCH' if match else 'MISMATCH'
                reason = 'same parameter, basis and test conditions; attribution only'
            rows.append({'id': key, 'status': status, 'reason': reason, 'claimed': a, 'reference': b,
                         'inputs_sha256': {a['source']: claim_hash, b['source']: reference_hash}})
        except (OSError, TypeError, ValueError) as exc:
            rows.append({'id': key, 'status': 'ERROR', 'reason': str(exc)})
    return rows, errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('claims', type=Path)
    parser.add_argument('--json', type=Path)
    args = parser.parse_args(argv)
    try:
        claims = json.loads(args.claims.read_text())
        rows, errors = check(claims)
    except (OSError, ValueError) as exc:
        rows, errors = [], [str(exc)]
    result = {'claims': rows, 'errors': errors,
              'scope': 'Citation comparison only; manually verify table extraction and manufacturer identity.'}
    if args.json:
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    for row in rows:
        print(row['status'], row['id'], row['reason'])
    for error in errors:
        print('ERROR', error)
    return 2 if errors else 0 if all(r['status'] == 'MATCH' for r in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())
