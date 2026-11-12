"""知识包（references/knowledge/）与清单 knowledge-sync.json 一致：逐文件 SHA-256、没有多出或缺少的文件、清单指纹对得上；
核对只读本技能，不读知识框架目录。同步（scripts/knowledge_package.py sync）从框架目录取内容并报差异。"""
import hashlib
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import knowledge_package as k
import plan_review

MANIFEST, PACKAGE = k.MANIFEST, 'references/knowledge'


def problems(root):
    return k.problems(root)


def test_installed_package_matches_its_manifest():
    assert problems(ROOT) == []


def test_plan_records_the_installed_version_and_fingerprint():
    manifest = json.loads((ROOT / MANIFEST).read_text(encoding='utf-8'))
    assert plan_review.knowledge_identity() == {'knowledge_version': manifest['knowledge_version'],
                                                'knowledge_fingerprint': manifest['fingerprint']}


@pytest.fixture
def local_copy(tmp_path):
    shutil.copytree(ROOT / PACKAGE, tmp_path / PACKAGE)
    shutil.copyfile(ROOT / MANIFEST, tmp_path / MANIFEST)
    assert problems(tmp_path) == []
    return tmp_path


def test_edited_missing_and_extra_files_are_caught(local_copy):
    package = local_copy / PACKAGE
    (package / 'README.md').write_text('改过', encoding='utf-8')
    (package / '原件勘误.md').unlink()
    (package / '多出来的.md').write_text('x', encoding='utf-8')
    assert sorted(problems(local_copy)) == ['README.md：内容与清单不符', '原件勘误.md：缺失', '多出来的.md：清单里没有']


def test_a_manifest_edited_by_hand_is_caught(local_copy):
    path = local_copy / MANIFEST
    manifest = json.loads(path.read_text(encoding='utf-8'))
    (local_copy / PACKAGE / 'README.md').write_text('改过', encoding='utf-8')
    manifest['files']['README.md'] = hashlib.sha256('改过'.encode()).hexdigest()
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')
    assert problems(local_copy) == ['清单指纹不符']


def test_no_package_means_no_identity(tmp_path):
    assert plan_review.knowledge_identity(tmp_path) == {}


def test_file_changes_tell_a_moved_entry_from_an_added_and_a_removed_one():
    old = {'典型电路/ldo.md': 'a', '典型电路/buck.md': 'b', '计算方法/x.md': 'c', '器件参数/p.md': 'd', '旧/README.md': 'e'}
    new = {'典型电路/电源变换/ldo.md': 'a', '典型电路/电源变换/buck.md': 'B', '计算方法/x.md': 'C', '器件参数/q.md': 'd',
           '新/README.md': 'e'}
    assert k.file_changes(old, new) == {
        'added': ['器件参数/q.md', '新/README.md'], 'removed': ['器件参数/p.md', '旧/README.md'], 'changed': ['计算方法/x.md'],
        'moved': [('典型电路/buck.md', '典型电路/电源变换/buck.md', True), ('典型电路/ldo.md', '典型电路/电源变换/ldo.md', False)]}


def test_criteria_changes_are_by_rule_id_and_value_name():
    old = {'criteria': [{'id': 'G01-001', 'title': 'a'}, {'id': 'G01-002', 'title': 'b'}], 'engineering_values': {'x': {'value': 1}}}
    new = {'criteria': [{'id': 'G01-001', 'title': 'A'}, {'id': 'G01-003', 'title': 'c'}], 'engineering_values': {'x': {'value': 1}}}
    assert k.criteria_changes(old, new) == {
        'criteria': {'added': ['G01-003'], 'removed': ['G01-002'], 'changed': ['G01-001']},
        'engineering_values': {'added': [], 'removed': [], 'changed': []}}


def framework_from(skill, framework):
    """A framework directory holding what the skill has installed (knowledge only)."""
    for name in k.COMPONENTS:
        shutil.copytree(skill / PACKAGE / name, framework / name)
    for name in k.SINGLE_FILES:
        (framework / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(skill / PACKAGE / name, framework / name)
    (framework / '版本记录.md').write_text('# 版本记录\n\n**现行版本：9.8.7**（2030-01-02）\n', encoding='utf-8')
    return framework


def test_collect_takes_the_components_and_names_the_version(tmp_path):
    framework = framework_from(ROOT, tmp_path)
    (framework / '典型电路' / '.DS_Store').write_bytes(b'x')
    (framework / '设计实例').mkdir()
    (framework / '设计实例' / 'card.md').write_text('范例', encoding='utf-8')
    assert k.framework_version(framework) == ('9.8.7', '2030-01-02')
    files = k.collect(framework, '9.8.7', '2030-01-02', '2030-01-03')
    installed = k.manifest(ROOT)['files']
    assert set(files) == set(installed)                       # no .DS_Store, no 设计实例
    assert {n: k.sha(d) for n, d in files.items() if n != 'README.md'} == {n: d for n, d in installed.items() if n != 'README.md'}
    assert '9.8.7（2030-01-02）同步，2030-01-03 取' in files['README.md'].decode('utf-8')


def test_collect_refuses_a_renamed_component_and_a_repeated_circuit_name(tmp_path):
    framework = framework_from(ROOT, tmp_path)
    shutil.copyfile(framework / '典型电路' / '电源变换' / 'ldo.md', framework / '典型电路' / '总线与接口' / 'ldo.md')
    with pytest.raises(ValueError, match='文件名重复：ldo'):
        k.collect(framework, '9.8.7', '2030-01-02', '2030-01-03')
    (framework / '失效与故障分析').rename(framework / '失效分析')
    with pytest.raises(ValueError, match='知识框架里没有：失效与故障分析'):
        k.collect(framework, '9.8.7', '2030-01-02', '2030-01-03')


def test_the_shared_manifest_is_the_one_the_guideline_tool_verifies():
    import guideline_criteria as g
    assert g.verify_installed(ROOT)['library_version'] == k.manifest(ROOT)['knowledge_version']
