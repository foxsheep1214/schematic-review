#!/usr/bin/env python3
"""Pack a finished review into the fixed, small delivery layout.

    <review dir>/
      审查报告.md          the only human-facing file (render_report.py)
      record/
        manifest.json      inputs by path + SHA-256, SR version, packed files
        review-plan.json  review-results.json  review-gate.json  db.json  intent.json  lint-cold/hot.json
        circuit-candidates.json  notes.json   when the intent declares circuits / the report has notes
        evidence/          only files that a check's evidence actually cites

The report is rendered again from the packed plan, results, gate and notes (with the title and
detail it was rendered with) and must be the same text; the gate must be valid and the ledger a
board verdict, not a scoped hot review (SR self-check 2.3). Schematic projects, datasheets,
requirements and earlier reviews are referenced by path and hash, never copied. Anything else at the top level, or a cited source that is neither packed
nor a declared input, fails the pack so the directory stays exactly this shape.
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
from render_report import SR_SECTION, jargon_in, notes_errors, render, sr_feedback_errors  # noqa: E402
from report_html import to_html
import circuit_decisions
import results_model

HISTORY_RULE = 'REQ-H02'
LEDGER = ('review-plan.json', 'review-results.json', 'review-gate.json', 'db.json', 'intent.json',
          'lint-cold.json', 'lint-hot.json')
OPTIONAL_LEDGER = ('circuit-candidates.json',       # required as soon as the intent declares circuits
                   'notes.json')                    # the plain-language notes the report was rendered with
SKILL_ROOT = Path(__file__).resolve().parents[1]    # SR's own documents are pinned by skill_version, never inputs
EVIDENCE_NOTE_BYTES = 300 * 1024                    # a cited file this large is a document, not an excerpt (5.2 audit)
# a text extract of a datasheet or standard (R7: ds/U601.txt, std/USBPD.txt, sources/Kingbright-….txt)
DATASHEET_TEXT_RE = re.compile(r'(?:^|/)(?:ds|datasheets?|std|standards?|sources|manuals?)/[^/]+\.txt$', re.I)


def ledger_name(source):
    """The ledger file a relative source names (db.json, record/review-results.json), else None: SR's plan and derive
    cite the netlist and this record, reviewers cite the plan; those resolve to record/, they are never copied."""
    name = source[len(RECORD) + 1:] if source.startswith(RECORD + '/') else source
    return name if name in LEDGER + OPTIONAL_LEDGER else None


def inside_skill(path):
    try:
        return Path(path).resolve().is_relative_to(SKILL_ROOT)
    except OSError:
        return False


def input_pdfs(declared):
    """Every PDF under the declared inputs, by lower-case stem."""
    out = {}
    for fp in declared:
        root = Path(fp['path'])
        files = [root] if root.is_file() else [q for q in root.rglob('*.pdf') if q.is_file()] if root.is_dir() else []
        for f in files:
            if f.suffix.lower() == '.pdf':
                out.setdefault(f.stem.lower(), f)
    return out


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


def candidate_errors(record):
    """A review whose intent declares circuits carries the candidate file they were decided from, bound to its
    netlist, and the circuits equal the decisions; a hand-drawn circuit list is not packed (no legacy path)."""
    try:
        intent = json.loads((record / 'intent.json').read_text(encoding='utf-8'))
        db = json.loads((record / 'db.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    if not isinstance(intent, dict) or not (intent.get('circuits') or intent.get('circuit_decisions')
                                            or 'circuit_candidates_sha256' in intent):
        return []
    path = record / 'circuit-candidates.json'
    if not path.is_file():
        return ['intent.circuits without record/circuit-candidates.json: circuits are decided from candidates '
                '(circuit_candidates.py, then circuit_decisions.py --write); a hand-drawn circuit list is not packed']
    try:
        candidates = json.loads(path.read_text(encoding='utf-8'))
    except ValueError:
        return ['record/circuit-candidates.json is not JSON']
    return ['circuit-candidates: ' + e for e in circuit_decisions.validate(intent, candidates, db)]


def skill_version():
    root = Path(__file__).resolve().parents[1]
    try:
        return subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'], capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def rendered_errors(out, record, title=None, detail='compact'):
    """The report is what render_report.py writes from the packed ledger; the gate is valid and a board verdict."""
    load = lambda name: json.loads((record / name).read_text(encoding='utf-8'))
    plan, results, gate = load('review-plan.json'), load('review-results.json'), load('review-gate.json')
    notes = load('notes.json') if (record / 'notes.json').is_file() else None
    errors = []
    if gate.get('valid') is not True:
        errors.append('review-gate.json is not valid; fix what validate_review.py reports and run it again before packing')
    if results.get('review_scope') is not None:
        errors.append('review-results.json declares review_scope: a scoped hot review is not a board verdict and is not '
                      'delivered')
    problems = sr_feedback_errors((notes or {}).get('sr_feedback')) + notes_errors(notes)
    if problems:
        return errors + ['notes.json: ' + '; '.join(problems)]
    if (out / REPORT).read_text(encoding='utf-8') != render(plan, results, gate, notes, title, detail):
        errors.append('%s is not what render_report.py writes from the packed ledger%s; re-render it from the current '
                      'plan, results, gate and notes (pass --notes, --title and --detail as rendered) instead of '
                      'editing it' % (REPORT, ' and notes.json' if notes is not None else ''))
    return errors


def pack(out, ledger, evidence_root, inputs, title=None, detail='compact'):
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
    declared, notes = {}, []
    for name, path in inputs.items():
        if not Path(path).exists():
            errors.append('input %s does not exist: %s' % (name, path))
        elif inside_skill(path):
            notes.append('input %s lies inside the SR skill directory (%s): not needed, skill_version pins it and '
                         'citations into it resolve by themselves' % (name, path))
        else:
            declared[name] = fingerprint(path)
    if errors:
        return errors, None
    # Reject output symlinks before writing any ledger or evidence file.
    if not contained(record / 'evidence', out):
        return ['record/evidence escapes review directory'], None
    for name, src in ledger.items():
        if name not in LEDGER + OPTIONAL_LEDGER or not contained(record / name, out):
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
    errors += rendered_errors(out, record, title, detail)
    errors += candidate_errors(record)
    items = results_model.open_items(results)
    unfinished = sorted(c.get('id', '?') for c in results.get('checks') or [] if isinstance(c, dict)
                        and c.get('review_result') == 'INSUFFICIENT'
                        and (items.get(c.get('open_ref')) or ({}, {}))[1].get('kind') == 'REVIEW_INCOMPLETE'
                        and not str(c.get('id', '')).startswith(HISTORY_RULE + '.'))
    if unfinished:
        errors.append('review not finished, nothing to deliver yet: finish reading/computing these checks, or record '
                      'manual_verification where only the SR tool is limited: ' + ', '.join(unfinished))
    unresolved, skill_cited, datasheet_texts, pdfs = [], False, [], input_pdfs(declared.values())
    for source in sorted(cited_sources(results)):
        if source.startswith(('http://', 'https://')):
            continue
        # Absolute original inputs are references, never archive member names.
        if Path(source).is_absolute():
            if inside_skill(source) and Path(source).is_file():
                skill_cited = True                      # SR's own reference, pinned by skill_version (D)
            elif not input_member(source, declared.values()):
                unresolved.append(source)
            continue
        if not safe_relative(source):
            errors.append('unsafe evidence path: ' + source)
            continue
        if ledger_name(source):                         # the record itself: cited in place, never copied (A)
            if not (record / ledger_name(source)).is_file():
                unresolved.append(source)
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
            size = target.stat().st_size
            if size > EVIDENCE_NOTE_BYTES:              # B
                notes.append('evidence %s is %d KB: a whole document is an input (--input, cited by path and page), '
                             'record/evidence holds excerpts, crops and figures' % (RECORD + '/evidence/' + source, size // 1024))
            if DATASHEET_TEXT_RE.search(source):
                datasheet_texts.append(source)
        elif not input_member(source, declared.values()):
            unresolved.append(source)
    if unresolved:
        errors.append('cited evidence is neither in --evidence-root nor a declared input: ' + ', '.join(unresolved))
    if datasheet_texts:                                 # C
        if not pdfs:
            errors.append('%d cited datasheet or standard text extracts (%s) but no declared input holds a PDF: declare '
                          'the datasheet directory (--input datasheets=<原厂资料目录>) so the manifest records the '
                          'documents by path and hash; the extract stays an excerpt'
                          % (len(datasheet_texts), ', '.join(datasheet_texts[:3])))
        for source in datasheet_texts:
            pdf = pdfs.get(Path(source).stem.lower())
            if pdf is not None:
                notes.append('evidence %s is the text of the declared input %s: cite the input by path and page, the '
                             'extract need not be packed' % (source, pdf))
    errors += broken_report_links(out)
    errors += packed_errors(out, packed)
    if skill_cited:
        declared['skill'] = {'path': str(SKILL_ROOT), 'kind': 'skill', 'commit': skill_version()}
    manifest = {'schema_version': 1, 'skill_version': skill_version(), 'inputs': declared,
                'packed': dict(sorted(packed.items())), 'report_sha256': sha256(out / REPORT),
                'evidence_bytes': sum((out / p).stat().st_size for p in packed if p.startswith(RECORD + '/evidence/')),
                'notes': notes}
    (record / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return errors, manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('out', help='review directory holding 审查报告.md')
    for name in LEDGER:
        parser.add_argument('--' + name.split('.')[0], required=True, metavar='PATH')
    parser.add_argument('--circuit-candidates', metavar='PATH', help='required when intent.json declares circuits')
    parser.add_argument('--notes', metavar='PATH', help='the notes.json the report was rendered with')
    parser.add_argument('--title', help='the --title the report was rendered with')
    parser.add_argument('--detail', choices=('compact', 'full'), default='compact',
                        help='the --detail the report was rendered with')
    parser.add_argument('--evidence-root', help='work directory that cited evidence paths are relative to')
    parser.add_argument('--input', action='append', default=[], metavar='NAME=PATH',
                        help='schematic project, datasheets, requirements, previous review ... (referenced, not copied)')
    args = parser.parse_args(argv)
    ledger = {name: getattr(args, name.split('.')[0].replace('-', '_')) for name in LEDGER + OPTIONAL_LEDGER
              if getattr(args, name.split('.')[0].replace('-', '_'))}
    inputs = dict(item.split('=', 1) for item in args.input)
    errors, manifest = pack(args.out, ledger, args.evidence_root, inputs, args.title, args.detail)
    for e in errors:
        print('ERROR:', e)
    for n in (manifest or {}).get('notes') or []:
        print('NOTE:', n)
    print('FAIL' if errors else 'PASS')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
