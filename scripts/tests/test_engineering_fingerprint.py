"""M4: engineering identity, document integrity, historical semantics and actual alternate input.
The identity covers the framework files the guideline and derating data are read from plus the skill's own two scripts;
the tests change copies of them in a small temporary framework and skill root."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if ROOT.name == 'scripts':
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import guideline_criteria as g
import knowledge_source as ks
from framework_fixtures import small_framework


@pytest.fixture
def package(tmp_path, monkeypatch):
    """A small framework and a skill root holding copies of the two scripts, both in effect for the test."""
    framework = small_framework(tmp_path / 'framework')
    skill = tmp_path / 'skill'
    for name in g.SKILL_FILES:
        (skill / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, skill / name)
    monkeypatch.setenv(ks.ENV_VAR, str(framework))
    monkeypatch.setattr(g, 'SKILL_ROOT', skill)
    return tmp_path


def test_the_identity_names_each_controlled_input_by_relative_path(package):
    names = set(g.shared_files())
    assert set(g.SKILL_FILES) | set(g.FRAMEWORK_FILES) <= names
    assert {n for n in names if n.endswith('_准则登记.json')}
    assert all(not Path(n).is_absolute() for n in names)


def test_framework_prose_outside_the_controlled_files_changes_nothing(package):
    before = g.shared_versions()
    notes = package / 'framework' / '知识' / '设计准则' / '维护说明.md'
    notes.write_text('合成维护历史补充。\n')
    (package / 'framework' / '知识' / '设计准则' / '工具').mkdir()
    (package / 'framework' / '知识' / '设计准则' / '工具' / 'readme.md').write_text('合成说明。\n')
    after = g.shared_versions()
    assert {k: v for k, v in after.items() if k != 'read_date'} == {k: v for k, v in before.items() if k != 'read_date'}
    assert g.identity_errors(before) == []


@pytest.mark.parametrize('kind', ['registry', 'vocabulary', 'derating', 'derating_doc', 'floors', 'stress_spec',
                                  'scripts/guideline_criteria.py', 'scripts/stress_check.py'])
def test_each_controlled_input_changes_fingerprint(package, kind):
    before = g.shared_digest()
    framework = package / 'framework'
    if kind.startswith('scripts/'):
        path = package / 'skill' / kind
        path.write_text(path.read_text() + '\nSYNTHETIC_ALGORITHM = lambda value: value + 1\n')
    else:
        path = {'registry': sorted(ks.registry_dir().glob('G0*_准则登记.json'))[0], 'vocabulary': ks.vocabulary_path(),
                'derating': ks.derating_path(), 'derating_doc': ks.derating_doc_path(),
                'floors': ks.commodity_path(), 'stress_spec': ks.stress_spec_path()}[kind]
        path.write_bytes(path.read_bytes() + b'\n')
    assert g.shared_digest() != before


def test_digest_is_a_sorted_relative_path_hash_map_not_implicit_list_order(package, monkeypatch):
    files = g.shared_files()
    expected = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    assert g.shared_digest() == expected
    monkeypatch.setattr(g, 'SKILL_FILES', tuple(reversed(g.SKILL_FILES)))
    monkeypatch.setattr(g, 'FRAMEWORK_FILES', tuple(reversed(g.FRAMEWORK_FILES)))
    assert g.shared_digest() == expected
    # Path names themselves bind the file role (even if the multiset of hashes is unchanged).
    swapped = dict(files)
    swapped['scripts/guideline_criteria.py'], swapped['scripts/stress_check.py'] = files['scripts/stress_check.py'], files['scripts/guideline_criteria.py']
    assert g._digest(swapped) != expected


def test_old_format_records_are_rejected_not_promoted(package):
    """Any non-current record must be regenerated, never migrated."""
    current = g.shared_versions()
    for fmt in (None, 'shared-paths-sha256-v2', 'shared-files-sha256-lines-v1'):
        old = dict(current)
        old.pop('fingerprint_format')
        if fmt:
            old['fingerprint_format'] = fmt
        original = copy.deepcopy(old)
        assert any('fingerprint format' in e for e in g.identity_errors(old))
        assert old == original


@pytest.mark.parametrize('field,value', [('fingerprint_format', None), ('fingerprint_format', 'unknown'),
                                       ('shared_sha256', '0'*64), ('library_version', 'another-version')])
def test_new_identity_requires_version_digest_and_explicit_format(package, field, value):
    record = g.shared_versions()
    if value is None:
        record.pop(field)
    else:
        record[field] = value
    assert g.identity_errors(record)


def test_the_read_date_is_recorded_but_not_compared(package):
    record = g.shared_versions()
    assert record['read_date']
    assert g.identity_errors(dict(record, read_date='1999-01-01')) == []


def test_alternate_input_binds_real_bytes_even_when_test_mode_is_explicit(tmp_path, monkeypatch):
    monkeypatch.delenv('GUIDELINE_CRITERIA', raising=False)
    installed = g.shared_versions()
    library = g.load()
    library['engineering_values']['assumed_resistor_package']['value'] = '0201'
    override = tmp_path / 'alternate.json'
    raw = json.dumps(library, ensure_ascii=False).encode()
    override.write_bytes(raw)
    monkeypatch.setenv('GUIDELINE_CRITERIA', str(override))
    monkeypatch.setenv('GUIDELINE_CRITERIA_TESTING', '1')
    effective = g.shared_versions(bundle=g.load())
    assert effective['shared_sha256'] != installed['shared_sha256']
    assert effective['guideline_input'] == {'kind': 'alternate', 'sha256': hashlib.sha256(raw).hexdigest()}
    assert g.identity_errors(installed)
    assert g.identity_errors(effective) == []
    override.write_bytes(raw + b'\n')
    assert g.shared_versions()['shared_sha256'] != effective['shared_sha256']
    with pytest.raises(ValueError, match='changed during identity'):
        stale = copy.deepcopy(library)
        stale['library_version'] = 'stale-input'
        g.shared_versions(bundle=stale)


def test_recorded_label_never_prints_the_current_identity_for_old_records():
    record = {'library_version': 'historical', 'shared_sha256': '1'*64}
    label = g.shared_label(identity=record)
    assert '设计准则 111111111111（日期未记录' in label


def test_sr_rule_identity_ignores_documents_that_are_not_rules(package):
    import skill_identity
    skill = package / 'skill'
    (skill / 'SKILL.md').write_text('## 审查纪律\n按记录核对。\n')
    (skill / 'references').mkdir()
    (skill / 'references' / 'workflow-handoff.md').write_text('交接说明。\n')
    before = skill_identity.engineering_identity(skill)
    (skill / 'references' / 'workflow-handoff.md').write_text('交接说明，补充。\n')
    assert skill_identity.engineering_identity(skill) == before
    (skill / 'references' / 'margin-verdicts.md').write_text('判法变化：边界相等也记失败。\n')
    assert skill_identity.engineering_identity(skill)['digest'] != before['digest']
