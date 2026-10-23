#!/usr/bin/env python3
"""Read the assembly BOM into db.json, so every part's own BOM columns reach the plan.

    python3 scripts/read_bom.py db.json BOM.csv

Writes db['bom'] = {source, sha256, columns, uniform_columns, parts{ref: {column: text}}, not_in_netlist, not_in_bom}.
A part keeps its non-empty columns except the reference and value; a column written the same on every line (a status
note) says nothing about any part and is listed in uniform_columns instead. A line may name several parts
("R1, R2"). The text is kept as written: what it states about the part (ratings, tolerances, limits the part must meet)
is a design result; a calculation written there is the designer's and is not used (SKILL.md, independent review).
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import sys

REFERENCE_HEADERS = ('reference', 'references', 'ref', 'refdes', 'designator', 'designators', '位号')
VALUE_HEADERS = ('value', 'values', '值', '型号规格')
REF_SPLIT = re.compile(r'[,，;；\s]+')


def _column(headers, names):
    return next((h for h in headers if h.strip().lower() in names), None)


def read(path, db):
    raw = Path(path).read_bytes()
    text = raw.decode('utf-8-sig')
    reader = csv.DictReader(text.splitlines())
    headers = reader.fieldnames or []
    ref_col = _column(headers, REFERENCE_HEADERS)
    if ref_col is None:
        raise ValueError('%s: no reference column (one of %s)' % (path, ', '.join(REFERENCE_HEADERS)))
    value_col = _column(headers, VALUE_HEADERS)
    keep = [h for h in headers if h not in (ref_col, value_col)]
    lines = []
    for row in reader:
        refs = [r for r in REF_SPLIT.split(row.get(ref_col) or '') if r]
        fields = {h: (row.get(h) or '').strip() for h in keep}
        lines.append((refs, fields))
    seen = {h: {f[h] for _, f in lines if f[h]} for h in keep}
    uniform = [h for h in keep if len(seen[h]) == 1 and all(f[h] for _, f in lines)]
    parts = {}
    for refs, fields in lines:
        own = {h: v for h, v in fields.items() if v and h not in uniform}
        for ref in refs:
            parts[ref] = own
    netlist = set((db or {}).get('parts') or {})
    return {'source': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'columns': headers,
            'uniform_columns': uniform, 'parts': parts,
            'not_in_netlist': sorted(set(parts) - netlist), 'not_in_bom': sorted(netlist - set(parts))}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('db')
    parser.add_argument('bom')
    args = parser.parse_args(argv)
    db_path = Path(args.db)
    db = json.loads(db_path.read_text(encoding='utf-8'))
    try:
        db['bom'] = read(args.bom, db)
    except ValueError as exc:
        sys.exit('[FATAL] %s' % exc)
    db_path.write_text(json.dumps(db, ensure_ascii=False, indent=1), encoding='utf-8')
    bom = db['bom']
    print('BOM: %d parts, not in netlist %s, not in BOM %s' % (len(bom['parts']), bom['not_in_netlist'] or '-',
                                                                bom['not_in_bom'] or '-'))


if __name__ == '__main__':
    main()
