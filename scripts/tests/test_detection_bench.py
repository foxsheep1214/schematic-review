"""Detection accounting must preserve unknowns, alternative targets and provenance."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('detection_bench', ROOT / 'evals/detection/run.py')
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


def test_alternative_seed_targets_credit_defect_without_double_counting():
    data = {'records': [dict(board='b', defect='d', site='r', targets=['A', 'B'], auto=['A'])]}
    rows = bench.seeded_rows(data, {'A': ['C1'], 'B': ['C1', 'C2']})
    table, unmapped = bench.aggregate({'C1': {}, 'C2': {}}, {'A': ['C1'], 'B': ['C2']}, rows)
    assert [table[c]['counts']['hit'] for c in table] == [1, 1]
    assert not unmapped


def test_pointed_or_other_is_not_a_detection_and_error_is_not_a_miss():
    data = {'records': [dict(board='b', defect='d', site=str(i), targets=['A'],
                            auto=[], other=['B'], pointed=['A'], **extra)
                        for i, extra in enumerate(({}, {'error': 'crashed'}))]}
    assert [r['status'] for r in bench.seeded_rows(data, {'A': ['C']})] == ['miss', 'error']


def test_unknown_does_not_become_a_false_negative():
    rows = bench.known_rows([dict(id='x', criteria=['C'], caught='unknown', sr_rules=[],
                                 note='not replayed', kind='review_process')])
    table, _ = bench.aggregate({'C': {}}, {}, rows)
    assert table['C']['counts'] == {'unknown': 1}
    assert not table['C']['real']


def test_false_alarm_controls_and_unclassified_are_separate():
    data = {'b': {'rows': [dict(rule='A', status=s) for s in
                          ('KNOWN_FALSE_ALARM', 'FALSE_ALARM_BACK', 'FIXED',
                           'FALSE_ALARM_GONE', 'UNCLASSIFIED', 'ERROR')]}}
    rows = bench.typical_rows(data, {'A': ['C']})
    table, _ = bench.aggregate({'C': {}}, {'A': ['C']}, rows)
    assert table['C']['counts'] == {'fp': 2, 'tn': 2, 'unclassified': 1, 'error': 1}


def test_unmapped_findings_remain_visible():
    rows = bench.typical_rows({'b': {'rows': [dict(rule='NO-MAP', status='KNOWN_FALSE_ALARM')]}}, {})
    table, unmapped = bench.aggregate({'C': {}}, {}, rows)
    assert not table['C']['counts']
    assert unmapped == rows


def test_duplicate_identity_rejected_but_separate_benches_retained():
    row = dict(id='x', origin='seeded', criteria=['C'], status='hit')
    with pytest.raises(ValueError, match='duplicate observation'):
        bench.aggregate({'C': {}}, {}, [row, row])
    table, _ = bench.aggregate({'C': {}}, {}, [row, dict(row, origin='typical')])
    assert table['C']['counts']['hit'] == 2


def test_historical_miss_and_real_truth_are_distinct_from_process():
    records = [dict(id=str(i), criteria=['C'], caught=False, sr_rules=[], note='source', kind=k)
               for i, k in enumerate(('electrical', 'review_process'))]
    table, _ = bench.aggregate({'C': {}}, {}, bench.known_rows(records))
    assert table['C']['counts']['miss'] == 2
    assert table['C']['real']['miss'] == 1


@pytest.mark.skipif(not bench.KNOWN.is_file(), reason='电路评测集不在本机')
def test_committed_known_defects_have_valid_sources_and_identifiers():
    criteria = {c['id']: c for c in bench.read(ROOT / 'references/shared/guideline-criteria.json')['criteria']}
    bench.validate_known(bench.read(bench.KNOWN), criteria,
                         [r.id for r in bench.catalog.RULES])


def test_invalid_truth_label_rejected():
    with pytest.raises(ValueError, match='caught must'):
        bench.validate_known([dict(id='x', caught=None)], {}, {})


def test_report_distinguishes_unique_sites_from_criterion_associations():
    data = {'records': [dict(board='b', defect='d', site='r', targets=['A'], auto=['A'])]}
    rows = bench.seeded_rows(data, {'A': ['C1', 'C2']})
    criteria = {'C1': {'title': 'one'}, 'C2': {'title': 'two'}, 'C3': {'title': 'unknown'}}
    table, unmapped = bench.aggregate(criteria, {'A': ['C1', 'C2', 'C3']}, rows)
    report = bench.render(criteria, table, rows, unmapped, [], [])
    assert '正例 2，命中 2' in report
    assert '| seeded | 1 | 1 | 0 |' in report
    assert '没有任何已知缺陷或正例：1 条' in report
    assert '有检查但无已确认真缺陷检出结果：3 条' in report


def test_missing_seed_baseline_is_an_explicit_error():
    rows = bench.seeded_rows({'records': [], 'baselines': {'broken': {'error': 'no db'}}}, {})
    assert rows[0]['status'] == 'error'
    assert rows[0]['criteria'] == []
