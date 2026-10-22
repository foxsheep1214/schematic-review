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

A declared ASG delivery (the input itself, its record/ or a file in it, or a folder inside the
delivery such as the schematic) brings its own records for SR to re-judge: record/selection.json
needs a selection review that passes review_selection.validate, record/calculations needs a
calc_claims result with at least one recomputed claim, and record/preflight-delivery.json needs
a document-summary audit that read that very file. Each must be cited evidence, so it is packed.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPORT = '审查报告.md'
REPORT_HTML = '审查报告.html'
RECORD = 'record'
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_report import SR_SECTION, jargon_in  # noqa: E402
from report_html import to_html
import review_selection

HISTORY_RULE = 'REQ-H02'
LEDGER = ('review-plan.json', 'review-results.json', 'review-gate.json', 'db.json', 'intent.json',
          'lint-cold.json', 'lint-hot.json')


def plain_language_errors(report):
    """Text written for the designer must be plain: everything except the count table (labels fixed by
    render_report) and what follows the SR section (SR feedback, index)."""
    body = report.split('\n' + SR_SECTION)[0].split('\n## 索引')[0]
    if '\n## 数字一览' in body:
        head, rest = body.split('\n## 数字一览', 1)
        body = head + ('\n## ' + rest.split('\n## ', 1)[1] if '\n## ' in rest else '')
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


def input_member(source, inputs):
    """A cited source belongs to a declared input by full path, by path inside an input directory,
    or, for a bare file name, by exactly one input file of that name. Never by name alone when the
    citation carries a directory, so a same-named new file elsewhere is not mistaken for an input."""
    path = Path(source)
    if not path.is_absolute() and not safe_relative(source):
        return False
    matches = []
    for fp in inputs:
        root = Path(fp['path'])
        if root.is_file():
            files = [root]
        else:
            if not path.is_absolute() and contained(root / path, root) and (root / path).is_file():
                return True
            files = [q for q in root.rglob('*') if q.is_file() and contained(q, root)]
        if path.is_absolute() and path.resolve() in [f.resolve() for f in files]:
            return True
        if len(path.parts) == 1:
            matches += [f for f in files if f.name == path.name]
    return len({sha256(f) for f in matches}) == 1


def safe_relative(source):
    path = Path(source)
    return bool(source) and not path.is_absolute() and '..' not in path.parts


def contained(path, root):
    return Path(path).resolve().is_relative_to(Path(root).resolve())


def packed_errors(out, packed):
    """A successful pack must be independently readable from every manifest key."""
    errors = []
    for name, digest in packed.items():
        path = Path(out) / name
        if not safe_relative(name) or not contained(path, out):
            errors.append('packed path escapes review: ' + name)
        elif not path.is_file():
            errors.append('packed file missing: ' + name)
        elif sha256(path) != digest:
            errors.append('packed hash mismatch: ' + name)
    return errors


LINK_RE = re.compile(r'\]\(([^)\s]+)\)')


def broken_report_links(out):
    """Every relative link in the delivered report must open a file in the packed review."""
    report = Path(out) / REPORT
    if not report.is_file():
        return []
    broken = []
    for target in LINK_RE.findall(report.read_text(encoding='utf-8')):
        target = target.split('#', 1)[0]
        if not target or re.match(r'^[a-z][a-z0-9+.-]*:', target, re.I):
            continue
        if not (Path(out) / target).exists():
            broken.append(target)
    return ['%s links to files missing from the packed review: %s' % (REPORT, ', '.join(sorted(set(broken))))] \
        if broken else []


# How far up from a declared file a delivery is looked for: a schematic file sits two folders below the delivery
# (<delivery>/原理图/<file>); the record directory of a delivery is never deeper than that from its declared files.
DELIVERY_DEPTH = 3


def delivery_records(inputs):
    """record/ directories of ASG deliveries among the declared inputs."""
    found = set()
    for path in inputs:
        path = Path(path).resolve()
        places = [path] + list(path.parents)[:DELIVERY_DEPTH]
        for place in places:
            rec = place if place.name == RECORD else place / RECORD
            if (rec / 'selection.json').is_file() or (rec / 'calculations').is_dir() \
                    or (rec / 'preflight-delivery.json').is_file():
                found.add(rec)
                break
    return sorted(found)


def delivery_review_errors(records, products):
    """A delivery's own selection, calculations and preflight are re-judged, not only its schematic.
    products: the packed JSON evidence files, {packed path: parsed value}."""
    def kind(test):
        return [k for k, v in products.items() if isinstance(v, dict) and v.get('schema_version') == 1 and test(v)]
    selections = kind(lambda v: isinstance(v.get('roles'), list) and 'asg_record' in v)
    claims = kind(lambda v: isinstance(v.get('claims'), list) and isinstance(v.get('summary'), dict))
    audits = kind(lambda v: v.get('check_id') == 'DOC-Q01.DERIVED-SUMMARY')
    cite = 'and cite it from the check it supports so it is packed'
    errors = []
    for rec in records:
        if (rec / 'selection.json').is_file():
            problems = {}
            for key in selections:
                try:
                    problems[key] = review_selection.validate(products[key], rec.parent)
                except (OSError, ValueError, AttributeError) as error:
                    problems[key] = [str(error)]
            if not any(p == [] for p in problems.values()):
                detail = ('; '.join('%s: %s' % (k, '; '.join(v[:3])) for k, v in problems.items())
                          or 'no selection review is cited')
                errors.append('ASG delivery %s has selection.json but no finished selection review (%s); run '
                              'review_selection.py worksheet/validate %s' % (rec, detail, cite))
        if (rec / 'calculations').is_dir() and any(p.is_file() for p in (rec / 'calculations').rglob('*')):
            computed = [k for k in claims if any(isinstance(c, dict) and c.get('status') in ('MATCH', 'MISMATCH')
                                                 for c in products[k]['claims'])]
            if not computed:
                errors.append('ASG delivery %s has calculations but no cited calc_claims result with a recomputed '
                              'claim%s; write the deciding design numbers as claims, run calc_claims.py --json %s'
                              % (rec, ' (%s recompute nothing)' % ', '.join(claims) if claims else '', cite))
        preflight = rec / 'preflight-delivery.json'
        if preflight.is_file():
            digest = sha256(preflight)
            if not any(digest in (products[k].get('inputs_sha256') or {}).values() for k in audits):
                errors.append('ASG delivery %s has %s but no cited audit_document_summaries.py result that read '
                              'its current bytes%s; run it on the delivered calculations, preflight and report %s'
                              % (rec, preflight.name, ' (%s audit other files)' % ', '.join(audits) if audits else '',
                                 cite))
    return errors


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
        markdown = (out / REPORT).read_text(encoding='utf-8')
        errors += plain_language_errors(markdown)
        if not (out / REPORT_HTML).is_file():
            errors.append('missing %s; run render_report.py, it writes both copies' % REPORT_HTML)
        elif (out / REPORT_HTML).read_text(encoding='utf-8') != to_html(markdown):
            errors.append('%s does not match %s; re-render instead of editing either copy' % (REPORT_HTML, REPORT))
    extra = sorted(p.name for p in out.iterdir() if p.name not in (REPORT, REPORT_HTML, RECORD)
                   and not p.name.startswith('.')) if out.is_dir() else []
    if extra:
        errors.append('only %s, %s and %s/ belong at the top level; move these to the work directory: %s'
                      % (REPORT, REPORT_HTML, RECORD, ', '.join(extra)))
    declared = {}
    for name, path in inputs.items():
        if not Path(path).exists():
            errors.append('input %s does not exist: %s' % (name, path))
        else:
            declared[name] = fingerprint(path)
    if errors:
        return errors, None
    # Reject output symlinks before writing any ledger or evidence file.
    if not contained(record / 'evidence', out):
        return ['record/evidence escapes review directory'], None
    for name, src in ledger.items():
        if name not in LEDGER or not contained(record / name, out):
            errors.append('unsafe ledger target: ' + name)
        if not Path(src).is_file():
            errors.append('missing ledger: ' + str(src))
    if not contained(record / 'manifest.json', out):
        errors.append('manifest escapes review directory')
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
    unresolved = []
    for source in sorted(cited_sources(results)):
        if source.startswith(('http://', 'https://')):
            continue
        # Absolute original inputs are references, never archive member names.
        if Path(source).is_absolute():
            if not input_member(source, declared.values()):
                unresolved.append(source)
            continue
        if not safe_relative(source):
            errors.append('unsafe evidence path: ' + source)
            continue
        candidate = Path(evidence_root) / source if evidence_root else None
        if candidate and not contained(candidate, evidence_root):
            errors.append('evidence path escapes work directory: ' + source)
            continue
        if candidate and candidate.is_file():
            # This round's evidence wins over any same-named file inside an input.
            target = record / 'evidence' / source
            if not contained(target, record / 'evidence'):
                errors.append('evidence target escapes archive: ' + source)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if candidate.resolve() != target.resolve():  # re-packing an already packed review
                shutil.copyfile(candidate, target)
            packed[RECORD + '/evidence/' + source] = sha256(target)
        elif not input_member(source, declared.values()):
            unresolved.append(source)
    if unresolved:
        errors.append('cited evidence is neither in --evidence-root nor a declared input: ' + ', '.join(unresolved))
    products = {}
    for key in packed:
        if key.startswith(RECORD + '/evidence/') and key.endswith('.json'):
            try:
                products[key] = json.loads((out / key).read_text(encoding='utf-8'))
            except (OSError, ValueError):
                pass
    errors += delivery_review_errors(delivery_records(inputs.values()), products)
    errors += broken_report_links(out)
    errors += packed_errors(out, packed)
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
