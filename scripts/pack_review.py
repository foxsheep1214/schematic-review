#!/usr/bin/env python3
"""Pack a finished review into the fixed, small delivery layout.

    <review dir>/
      审查报告.md          the only human-facing file (render_report.py)
      record/
        manifest.json      inputs by path + SHA-256, SR version, packed files
        review-plan.json  review-results.json  review-gate.json  db.json  intent.json  lint-cold/hot.json
        evidence/          only files that a check's evidence actually cites

Schematic projects, datasheets, requirements and earlier reviews are referenced by path and
hash, never copied. Anything else at the top level, or a cited source that is neither packed
nor a declared input, fails the pack so the directory stays exactly this shape.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPORT = '审查报告.md'
RECORD = 'record'
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_report import jargon_in  # noqa: E402

HISTORY_RULE = 'REQ-H02'
LEDGER = ('review-plan.json', 'review-results.json', 'review-gate.json', 'db.json', 'intent.json',
          'lint-cold.json', 'lint-hot.json')


def plain_language_errors(report):
    """Text written for the designer (everything above the tool-gap and count sections) must be plain."""
    body = report.split('\n## 审查工具的不足')[0].split('\n## 数字一览')[0]
    errors = []
    for number, line in enumerate(body.splitlines()[1:], 2):
        words = jargon_in(line)
        if words:
            errors.append('%s line %d uses %s; rewrite the record text or notes in plain words and re-render: %s'
                          % (REPORT, number, '/'.join(words), line.strip()[:80]))
    return errors


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def fingerprint(path):
    path = Path(path).resolve()
    if path.is_file():
        return {'path': str(path), 'kind': 'file', 'sha256': sha256(path)}
    files = sorted(p for p in path.rglob('*') if p.is_file() and not p.name.startswith('.'))
    tree = hashlib.sha256()
    for p in files:
        tree.update(('%s\0%s\n' % (p.relative_to(path).as_posix(), sha256(p))).encode())
    return {'path': str(path), 'kind': 'directory', 'files': len(files), 'tree_sha256': tree.hexdigest()}


def cited_sources(value):
    """Every evidence {source, locator} anywhere in the results."""
    found = set()
    if isinstance(value, dict):
        if isinstance(value.get('source'), str) and 'locator' in value:
            found.add(value['source'])
        for v in value.values():
            found |= cited_sources(v)
    elif isinstance(value, list):
        for v in value:
            found |= cited_sources(v)
    return found


def skill_version():
    root = Path(__file__).resolve().parents[1]
    try:
        return subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'], capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def pack(out, ledger, evidence_root, inputs):
    out = Path(out)
    errors = []
    record = out / RECORD
    if not (out / REPORT).is_file():
        errors.append('missing %s; run render_report.py first' % REPORT)
    else:
        errors += plain_language_errors((out / REPORT).read_text(encoding='utf-8'))
    extra = sorted(p.name for p in out.iterdir() if p.name not in (REPORT, RECORD) and not p.name.startswith('.')) \
        if out.is_dir() else []
    if extra:
        errors.append('only %s and %s/ belong at the top level; move these to the work directory: %s'
                      % (REPORT, RECORD, ', '.join(extra)))
    declared = {}
    for name, path in inputs.items():
        if not Path(path).exists():
            errors.append('input %s does not exist: %s' % (name, path))
        else:
            declared[name] = fingerprint(path)
    if errors:
        return errors, None
    (record / 'evidence').mkdir(parents=True, exist_ok=True)
    packed = {}
    for name, src in ledger.items():
        target = record / name
        if Path(src).resolve() != target.resolve():
            shutil.copyfile(src, target)
        packed[RECORD + '/' + name] = sha256(target)
    results = json.loads((record / 'review-results.json').read_text(encoding='utf-8'))
    unfinished = sorted(c.get('id', '?') for c in results.get('checks') or [] if isinstance(c, dict)
                        and c.get('review_result') == 'INSUFFICIENT' and c.get('gap_cause') == 'REVIEW_INCOMPLETE'
                        and not str(c.get('id', '')).startswith(HISTORY_RULE + '.'))
    if unfinished:
        errors.append('review not finished, nothing to deliver yet: finish reading/computing these checks, or record '
                      'manual_verification where only the SR tool is limited: ' + ', '.join(unfinished))
    input_names = set()
    for fp in declared.values():
        p = Path(fp['path'])
        input_names |= {p.name} | ({q.name for q in p.rglob('*') if q.is_file()} if p.is_dir() else set())
    unresolved = []
    for source in sorted(cited_sources(results)):
        if source.startswith(('http://', 'https://')) or Path(source).name in input_names:
            continue
        candidate = Path(evidence_root) / source if evidence_root else None
        if candidate and candidate.is_file():
            target = record / 'evidence' / source
            target.parent.mkdir(parents=True, exist_ok=True)
            if candidate.resolve() != target.resolve():  # re-packing an already packed review
                shutil.copyfile(candidate, target)
            packed[RECORD + '/evidence/' + source] = sha256(target)
        else:
            unresolved.append(source)
    if unresolved:
        errors.append('cited evidence is neither in --evidence-root nor a declared input: ' + ', '.join(unresolved))
    manifest = {'schema_version': 1, 'skill_version': skill_version(), 'inputs': declared,
                'packed': dict(sorted(packed.items())), 'report_sha256': sha256(out / REPORT)}
    (record / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return errors, manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('out', help='review directory holding 审查报告.md')
    for name in LEDGER:
        parser.add_argument('--' + name.split('.')[0], required=True, metavar='PATH')
    parser.add_argument('--evidence-root', help='work directory that cited evidence paths are relative to')
    parser.add_argument('--input', action='append', default=[], metavar='NAME=PATH',
                        help='schematic project, datasheets, requirements, previous review ... (referenced, not copied)')
    args = parser.parse_args(argv)
    ledger = {name: getattr(args, name.split('.')[0].replace('-', '_')) for name in LEDGER}
    inputs = dict(item.split('=', 1) for item in args.input)
    errors, _ = pack(args.out, ledger, args.evidence_root, inputs)
    for e in errors:
        print('ERROR:', e)
    print('FAIL' if errors else 'PASS')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
