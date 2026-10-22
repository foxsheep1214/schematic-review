#!/usr/bin/env python3
"""Transcribe a requirement document verbatim (fixed requirements, step 1).

A requirement is a row of a Markdown table whose first header cell is an id column (ID, 编号, 需求编号, REQ), or a
list item `- <ID>：<text>` whose id has a separator (REQ-01, R.2.1). Each requirement keeps every column apart, as
written, with the section heading above it and a file:line locator; the file's sha256 binds the transcription. The
reviewer never retypes a requirement: the intent names the source (`requirement_source`) and states only what the
reviewer decides about each id. Nothing here judges a requirement.

    python3 scripts/requirements_extract.py 需求.md --json record/requirements.json
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SCHEMA_VERSION = 1
ID_HEADERS = {'id', '编号', '需求编号', 'req', '需求 id', '需求id'}
ID_RE = re.compile(r'^[A-Za-z][A-Za-z0-9]*(?:[-_.][A-Za-z0-9]+)+$')
LIST_RE = re.compile(r'^\s*(?:[-*+]|\d+[.)])\s+(?:\*\*|`)?([A-Za-z][A-Za-z0-9]*(?:[-_.][A-Za-z0-9]+)+)(?:\*\*|`)?\s*[:：]\s*(.+?)\s*$')
HEADING_RE = re.compile(r'^\s*#{1,6}\s+(.+?)\s*#*\s*$')
SEPARATOR_RE = re.compile(r'^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$')
JOIN = '；'


def _cells(line):
    body = line.strip()
    if body.startswith('|'):
        body = body[1:]
    if body.endswith('|'):
        body = body[:-1]
    return [c.strip() for c in body.split('|')]


def _plain_id(cell):
    return re.sub(r'^(\*\*|`)(.*)\1$', r'\2', cell.strip())


def extract(path):
    """{schema_version, path, sha256, items[{id, section, columns[{name, text}], locator}], errors}."""
    path = Path(path)
    raw = path.read_bytes()
    lines = raw.decode('utf-8').splitlines()
    items, errors, seen = [], [], {}
    section, header, i = None, None, 0
    while i < len(lines):
        line = lines[i]
        heading = HEADING_RE.match(line)
        if heading:
            section, header = heading.group(1), None
        elif line.strip().startswith('|'):
            cells = _cells(line)
            if header is None and i + 1 < len(lines) and SEPARATOR_RE.match(lines[i + 1]):
                header = cells if cells and cells[0].strip().lower() in ID_HEADERS else []
                i += 2
                continue
            if header:
                rid = _plain_id(cells[0])
                if ID_RE.match(rid):
                    columns = [{'name': name, 'text': cells[k] if k < len(cells) else ''}
                               for k, name in enumerate(header[1:], 1)]
                    items.append({'id': rid, 'section': section, 'columns': columns, 'locator': '%s:%d' % (path, i + 1)})
                    seen.setdefault(rid, []).append(i + 1)
        else:
            header = None
            listed = LIST_RE.match(line)
            if listed:
                rid = listed.group(1)
                items.append({'id': rid, 'section': section, 'columns': [{'name': 'text', 'text': listed.group(2)}],
                              'locator': '%s:%d' % (path, i + 1)})
                seen.setdefault(rid, []).append(i + 1)
        i += 1
    for rid, at in sorted(seen.items()):
        if len(at) > 1:
            errors.append('%s: requirement id %s appears on lines %s; one id is one requirement'
                          % (path, rid, ', '.join(map(str, at))))
    return {'schema_version': SCHEMA_VERSION, 'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(),
            'items': items, 'errors': errors}


def text(item):
    """A requirement's original text: its columns in order."""
    return JOIN.join(c['text'] for c in item['columns'] if c['text'])


def load(source):
    """(extraction, errors) for intent.requirement_source {path, sha256}."""
    if not isinstance(source, dict) or not isinstance(source.get('path'), str) or not isinstance(source.get('sha256'), str):
        return None, ['requirement_source must be {path, sha256} naming the requirement document (requirements_extract.py)']
    try:
        out = extract(source['path'])
    except (OSError, UnicodeDecodeError) as error:
        return None, ['requirement_source %s is not readable: %s' % (source['path'], error)]
    errors = list(out['errors'])
    if out['sha256'] != source['sha256']:
        errors.append('requirement_source %s: sha256 differs from the file; the document changed, transcribe it again '
                      'and review the changed requirements' % source['path'])
    return out, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('document')
    parser.add_argument('--json', help='write the transcription here')
    args = parser.parse_args()
    out = extract(args.document)
    if args.json:
        Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print('%d requirements, sha256=%s%s' % (len(out['items']), out['sha256'],
          ''.join('\nERROR ' + e for e in out['errors'])))
    return 1 if out['errors'] else 0


if __name__ == '__main__':
    sys.exit(main())
