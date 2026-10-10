#!/usr/bin/env python3
"""Rebuild the slimmed KiCad XML fixtures from the frozen deliveries listed in sources.json.

Only elements parse_kicad.py does not read are dropped (title blocks, datasheet and
description text, timestamps, library lists, non-dnp properties, non-MPN fields).
A fixture is written only if parsing it gives exactly the same db as parsing the
original export, so the fixture is a lossless stand-in for the SR input layer.
Third-party originals stay where they are; only the slimmed copy enters the repo.
"""
import argparse
import hashlib
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from parse_kicad import MPN_FIELD, parse  # noqa: E402
from parse_netlist import integrity_problems  # noqa: E402

LIMIT = 200 * 1024
# design/source keeps the original export path and date; db.export_meta reads them.
DROP_COMP = ('datasheet', 'description', 'tstamps')
DROP_LIBPART = ('description', 'docs', 'footprints', 'fields')


def slim(xml_text):
    root = ET.fromstring(xml_text)
    design = root.find('design')
    if design is not None:
        for sheet in design.findall('sheet'):
            for child in list(sheet):
                sheet.remove(child)
            sheet.attrib.pop('tstamps', None)
        for child in design.findall('textvar'):
            design.remove(child)
    for comp in root.findall('./components/comp'):
        for tag in DROP_COMP:
            for child in comp.findall(tag):
                comp.remove(child)
        for prop in comp.findall('property'):
            if prop.get('name') != 'dnp':
                comp.remove(prop)
        fields = comp.find('fields')
        if fields is not None:
            for field in list(fields):
                if not MPN_FIELD.match((field.get('name') or '').strip()):
                    fields.remove(field)
            if not len(fields):
                comp.remove(fields)
        path = comp.find('sheetpath')
        if path is not None:
            path.attrib.pop('tstamps', None)
    for libpart in root.findall('./libparts/libpart'):
        for tag in DROP_LIBPART:
            for child in libpart.findall(tag):
                libpart.remove(child)
    for child in root.findall('libraries'):
        root.remove(child)
    ET.indent(root, space=' ')
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='unicode') + '\n'


def db_of(xml_text):
    db = parse(xml_text)
    problems = integrity_problems(db)
    return db, problems


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--batch-root', type=Path,
                    default=Path(os.environ.get('ASG_BATCH_ROOT', '~/Documents/ChatGPT/Auto-Development/'
                                                'ASG提升计划/2026-10-08-10轮')).expanduser(),
                    help='ASG batch directory holding round-NN/asg-delivery (read only)')
    ap.add_argument('--source', action='append', help='rebuild only these source ids')
    ap.add_argument('--override', action='append', default=[], metavar='ID=PATH',
                    help='read a source from another path (e.g. a source whose original moved)')
    args = ap.parse_args()
    overrides = dict(item.split('=', 1) for item in args.override)
    sources = json.loads((HERE / 'sources.json').read_text(encoding='utf-8'))
    for src in sources['sources']:
        if args.source and src['id'] not in args.source:
            continue
        path = Path(overrides.get(src['id']) or (args.batch_root / src['original']['path']))
        raw = path.read_bytes()
        if sha256(raw) != src['original']['sha256']:
            sys.exit('%s: original %s does not match the recorded sha256' % (src['id'], path))
        text = raw.decode('utf-8')
        slimmed = slim(text)
        full_db, full_problems = db_of(text)
        slim_db, slim_problems = db_of(slimmed)
        if full_db != slim_db or full_problems != slim_problems:
            sys.exit('%s: slimmed fixture parses differently from the original' % src['id'])
        data = slimmed.encode('utf-8')
        if len(data) > LIMIT:
            sys.exit('%s: slimmed fixture is %d bytes, over the %d byte limit' % (src['id'], len(data), LIMIT))
        out = HERE / src['fixture']['path']
        out.write_bytes(data)
        print('%s: %d -> %d bytes, sha256 %s' % (src['id'], len(raw), len(data), sha256(data)))
        if sha256(data) != src['fixture']['sha256']:
            print('  fixture sha256 differs from sources.json; update it after review')


if __name__ == '__main__':
    main()
