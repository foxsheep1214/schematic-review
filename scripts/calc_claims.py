#!/usr/bin/env python3
"""Recompute numbers a design document states and report where they disagree.

    python3 scripts/calc_claims.py claims.json [--json out.json]

claims.json is a list of claims taken from the design's calculation notes,
configuration tables or reports:

    {"id": "NTC-150C", "source": "design/calc.md", "locator": "table 3 row 2",
     "calculation": "model_bounds.ntc_resistance_bounds",
     "inputs": {...keyword arguments, each traceable to a datasheet or the schematic...},
     "claimed": {"r_min_ohm": 520.0}, "rel_tol": 0.02}

Each claimed field is compared with SR's own corner-enumerating recomputation.
MISMATCH means the stated number does not follow from the stated inputs under
SR's model: a candidate document error to read, not a verdict. Exit 1 when any
claim mismatches or cannot be recomputed, 2 when the claims file is malformed.
"""
import argparse
import json
import math
import sys

import calc

DEFAULT_REL_TOL = 0.01
CLAIM_FIELDS = {'id', 'source', 'locator', 'calculation', 'inputs', 'claimed'}


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def claim_errors(claim, index):
    where = 'claim %d' % index
    if not isinstance(claim, dict):
        return [where + ' must be an object']
    errors = []
    missing = sorted(CLAIM_FIELDS - set(claim))
    if missing:
        errors.append('%s (%s): missing %s' % (where, claim.get('id'), ', '.join(missing)))
    for key in ('id', 'source', 'locator', 'calculation'):
        if key in claim and not (isinstance(claim[key], str) and claim[key].strip()):
            errors.append('%s: %s must be non-empty text' % (where, key))
    if 'inputs' in claim and not isinstance(claim['inputs'], dict):
        errors.append(where + ': inputs must be an object of keyword arguments')
    claimed = claim.get('claimed')
    if 'claimed' in claim and not (isinstance(claimed, dict) and claimed
                                   and all(_number(v) for v in claimed.values())):
        errors.append(where + ': claimed must map result fields to finite numbers')
    tol = claim.get('rel_tol', DEFAULT_REL_TOL)
    if not (_number(tol) and 0 <= tol < 1):
        errors.append(where + ': rel_tol must be a fraction in [0, 1)')
    return errors


def check(claims):
    """Return (rows, errors). errors means the file itself is malformed."""
    if not isinstance(claims, list) or not claims:
        return [], ['claims must be a non-empty list']
    errors = [e for i, c in enumerate(claims) for e in claim_errors(c, i)]
    ids = [c.get('id') for c in claims if isinstance(c, dict)]
    errors += ['duplicate claim id ' + str(i) for i in sorted({i for i in ids if ids.count(i) > 1}, key=str)]
    if errors:
        return [], errors
    rows = []
    for claim in claims:
        code, output = calc.run(claim['calculation'], claim['inputs'])
        row = {'id': claim['id'], 'source': claim['source'], 'locator': claim['locator'],
               'calculation': claim['calculation'], 'inputs': claim['inputs']}
        if code:
            rows.append(dict(row, status='ERROR', error=output.get('error')))
            continue
        result, tol, fields = output['result'], claim.get('rel_tol', DEFAULT_REL_TOL), []
        for field, stated in sorted(claim['claimed'].items()):
            computed = result.get(field)
            if not _number(computed):
                fields.append({'field': field, 'claimed': stated, 'computed': computed, 'status': 'NOT_COMPUTED'})
                continue
            scale = max(abs(computed), abs(stated))
            ok = abs(computed - stated) <= tol * scale if scale else True
            fields.append({'field': field, 'claimed': stated, 'computed': computed,
                           'relative_difference': abs(computed - stated) / scale if scale else 0.0,
                           'status': 'MATCH' if ok else 'MISMATCH'})
        status = ('MATCH' if all(f['status'] == 'MATCH' for f in fields) else
                  'MISMATCH' if any(f['status'] == 'MISMATCH' for f in fields) else 'NOT_COMPUTED')
        rows.append(dict(row, status=status, rel_tol=tol, fields=fields,
                         flags=result.get('applicability_flags', []), basis=result.get('basis')))
    return rows, []


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('claims', help='JSON list of claims')
    parser.add_argument('--json', help='write the comparison here (evidence for DOC-Q01 / the related check)')
    args = parser.parse_args(argv)
    try:
        with open(args.claims, encoding='utf-8') as handle:
            claims = json.load(handle)
    except (OSError, ValueError) as error:
        print('ERROR:', error)
        return 2
    rows, errors = check(claims)
    if errors:
        for error in errors:
            print('ERROR:', error)
        return 2
    summary = {s: sum(r['status'] == s for r in rows) for s in ('MATCH', 'MISMATCH', 'NOT_COMPUTED', 'ERROR')}
    out = {'schema_version': 1, 'summary': summary, 'claims': rows,
           'note': 'MISMATCH is a candidate document error under SR model assumptions, not a verdict.'}
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as handle:
            json.dump(out, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
    for row in rows:
        detail = '; '.join('%s claimed %g computed %s' % (f['field'], f['claimed'], f['computed'])
                           for f in row.get('fields', []) if f['status'] != 'MATCH') or row.get('error') or ''
        print('%-12s %s  %s' % (row['status'], row['id'], detail))
    print('summary:', json.dumps(summary))
    return 0 if summary['MATCH'] == len(rows) else 1


if __name__ == '__main__':
    sys.exit(main())
