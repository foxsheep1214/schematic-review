"""Freeze real R3 review ledgers as schema 3 fixtures for replay.py.

    python3 evals/ledger_replay/make_records.py <审查结果目录> 4b3b406 d32855c 3924cd7

Each source is a `SR-*-R3-全新独立审查-<tag>/record` directory written by an older SR (results schema 2).
The results are rewritten the way a reviewer writes schema 3 (scripts/tests/ledger_v3.py), the project path
prefix by `project/` and scratch work directories by `work/`, and the original gate's grading fields become the frozen answer: they
were computed by the SR the reviewer ran, not by the SR under test.
"""
import gzip
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'scripts' / 'tests')]
import ledger_v3  # noqa: E402
from validate_review import fingerprint  # noqa: E402

GATE_FIELDS = ('summary', 'insufficient_by_cause', 'categorized_summary', 'requirement_clarification_summary')


def strip(value, prefix):
    text = json.dumps(value, ensure_ascii=False).replace(prefix, 'project/')
    return json.loads(re.sub(r'(?:/private)?/tmp/[^/"]+/[^/"]+/', 'work/', text))


def write(path, value):
    with gzip.GzipFile(path, 'wb', mtime=0) as f:
        f.write(json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8'))


def work_items(gate):
    return {t['id']: [t.get('level'), t.get('due_stage')] for t in (gate.get('workflow') or {}).get('work_items') or []}


def main(source, tags):
    source = Path(source).resolve()
    prefix = str(source.parent) + '/'
    expected = json.loads((HERE / 'expected.json').read_text()) if (HERE / 'expected.json').exists() else {'records': {}}
    for tag in tags:
        d = next(source.glob('SR-*-R3-*-' + tag)) / 'record'
        load = lambda name: json.loads((d / name).read_text(encoding='utf-8'))
        plan, results, db, gate = load('review-plan.json'), load('review-results.json'), load('db.json'), load('review-gate.json')
        v3 = ledger_v3.as_sent(plan, results)
        plan, v3, db = strip(plan, prefix), strip(v3, prefix), strip(db, prefix)
        v3['plan_digest'], v3['db_digest'] = fingerprint(plan), fingerprint(db)
        assert not re.search(r'/Users/|/home/|/private/|"/tmp/', json.dumps([plan, v3, db], ensure_ascii=False)), tag
        out = HERE / 'records' / tag
        out.mkdir(parents=True, exist_ok=True)
        for name, value in (('review-plan', plan), ('review-results', v3), ('db', db)):
            write(out / (name + '.json.gz'), value)
        answer = {k: gate.get(k) for k in GATE_FIELDS}
        answer['potential_severity'] = {r['id']: r.get('potential_severity') for r in results['checks']
                                        if r.get('review_result') == 'INSUFFICIENT'}
        answer['work_items'] = work_items(gate)
        assert gate['valid'] and not gate['errors'], tag
        answer['grading_errors'] = []
        old = expected['records'].get(tag, {})
        expected['records'][tag] = {'source': d.parent.name, 'answer': answer,
                                    'known_deviations': old.get('known_deviations', {}),
                                    'baseline': old.get('baseline', {})}
    (HERE / 'expected.json').write_text(json.dumps(expected, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
