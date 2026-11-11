"""知识包（references/knowledge/）与清单 knowledge-release.json 一致：逐文件 SHA-256、没有多出或缺少的文件、清单指纹对得上。
算法照硬件设计知识框架 工具/knowledge_package.py 的 verify-installed，在本仓库自带，不读框架目录（2026-11-10 接入知识包）。"""
import hashlib
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import plan_review

MANIFEST, PACKAGE = 'knowledge-release.json', 'references/knowledge'


def problems(root):
    root = Path(root)
    manifest = json.loads((root / MANIFEST).read_text(encoding='utf-8'))
    payload = root / PACKAGE
    actual = {str(p.relative_to(payload)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(payload.rglob('*')) if p.is_file()}
    found = ['%s：%s' % (name, '缺失' if name not in actual else '内容与清单不符')
             for name, digest in manifest['files'].items() if actual.get(name) != digest]
    found += ['%s：清单里没有' % name for name in actual if name not in manifest['files']]
    canonical = json.dumps(manifest['files'], ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    if hashlib.sha256(canonical).hexdigest() != manifest['fingerprint']:
        found.append('清单指纹不符')
    return found


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
