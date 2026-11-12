"""知识必答清单：计划里每块电路对上典型电路的实现方案，方案的必算项和已知坑逐项有处置；校验入口和打包都核对。"""
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import knowledge_checklist as k

CIRCUIT = '''# 稳压

功能：降压

## 选方案时比较的量

### 不是方案

## 实现方案

### 方案甲

- **必需外围**：
  - 输出电容
- **必算项**：
  - 压差，见 [线性稳压器](../../计算方法/电源变换/线性稳压器.md)
  - 功耗
- **已知坑**：
  - 反灌
### 方案乙

- **必算项**：电流
- **已知坑**：无
'''
PLAN = {'owners': [{'kind': 'CIRCUIT', 'id': 'ldo_3v3', 'type': 'LDO', 'parts': ['U1']},
                   {'kind': 'CIRCUIT', 'id': 'usb', 'type': 'USB', 'parts': ['J1']}],
        'checks': [{'id': 'PWR-C01.U1'}], 'functions': [{'id': 'F-ldo_3v3'}]}


@pytest.fixture
def knowledge(tmp_path, monkeypatch):
    (tmp_path / '典型电路' / '电源变换').mkdir(parents=True)
    (tmp_path / '典型电路' / '电源变换' / 'reg.md').write_text(CIRCUIT, encoding='utf-8')
    monkeypatch.setattr(k, 'KNOWLEDGE', tmp_path)
    return tmp_path


def answered(data, fill):
    for row in data['items']:
        row.update(fill(row))
    return data


def test_items_are_the_must_calculate_and_pitfall_bullets_of_the_scheme(knowledge):
    found = k.implementations(CIRCUIT)
    assert list(found) == ['方案甲', '方案乙']                 # only the headings under 实现方案
    assert found['方案甲'] == [('必算项', '压差，见 线性稳压器'), ('必算项', '功耗'), ('已知坑', '反灌')]
    assert found['方案乙'] == [('必算项', '电流')]
    assert k.scheme_rows('c', 'reg#没有的方案') is None and k.scheme_rows('c', 'nothing#方案甲') is None
    assert k.search(['稳压', '方案乙']) == [('reg', ['方案甲', '方案乙'])] and k.search(['没有']) == []


def test_a_plan_without_circuits_asks_nothing_and_one_with_circuits_wants_the_file(knowledge):
    assert k.problems({'owners': []}, None) == []
    assert 'knowledge-checklist.json 缺失' in k.problems(PLAN, None)[0]


def test_every_circuit_is_matched_and_every_item_answered(knowledge):
    data = k.build(PLAN, None)
    assert [c['circuit'] for c in data['circuits']] == ['ldo_3v3', 'usb'] and data['items'] == []
    assert len(k.problems(PLAN, data)) == 2 and all('typical 写' in p for p in k.problems(PLAN, data))
    data['circuits'][0]['typical'] = 'reg#方案甲'
    data['circuits'][1]['typical'] = 'none'
    assert k.problems(PLAN, data) == ['必答清单 电路 usb：typical 为 none 时在 reason 写查过哪些典型电路、为什么都不对应',
                                      'knowledge-checklist.json 缺 3 项（方案改了或知识条目变了）：重跑 knowledge_checklist.py build 后补写处置']
    data['circuits'][1]['reason'] = '查过 usb、type-c，知识包没有 USB 2.0 设备口的条目'
    data = k.build(PLAN, data)
    assert [r['kind'] for r in data['items']] == ['必算项', '必算项', '已知坑']
    assert len(k.problems(PLAN, data)) == 3 and all('还没有写处置' in p for p in k.problems(PLAN, data))
    answered(data, lambda r: {'disposition': 'checked', 'where': ['PWR-C01.U1']} if r['kind'] == '必算项'
             else {'disposition': 'not_applicable', 'reason': '输出侧没有别的电源'})
    assert k.problems(PLAN, data) == []
    assert k.build(PLAN, data) == data                        # what was written stays
    answered(data, lambda r: {'where': ['PWR-C99'], 'reason': ''})
    found = k.problems(PLAN, data)
    assert sum('where 的 PWR-C99 不是计划里的检查项或功能编号' in p for p in found) == 2
    assert sum('不适用要在 reason 写理由' in p for p in found) == 1
    answered(data, lambda r: {'where': []})
    assert sum('checked 要在 where 列出' in p for p in k.problems(PLAN, data)) == 2
    data['circuits'][0]['typical'] = 'reg#方案丙'
    assert 'reg#方案丙 在知识包的典型电路里找不到' in k.problems(PLAN, data)[0]


def test_a_changed_entry_voids_the_old_answer(knowledge):
    data = k.build(PLAN, {'circuits': [{'circuit': 'ldo_3v3', 'typical': 'reg#方案乙'}, {'circuit': 'usb', 'typical': 'none', 'reason': 'x'}]})
    answered(data, lambda r: {'disposition': 'checked', 'where': ['F-ldo_3v3']})
    assert k.problems(PLAN, data) == []
    path = knowledge / '典型电路' / '电源变换' / 'reg.md'
    path.write_text(CIRCUIT.replace('**必算项**：电流', '**必算项**：电流与限流'), encoding='utf-8')
    assert k.problems(PLAN, data) == ['knowledge-checklist.json 缺 1 项（方案改了或知识条目变了）：重跑 knowledge_checklist.py build 后补写处置']


def test_the_command_builds_and_checks(knowledge, tmp_path):
    plan, path = tmp_path / 'review-plan.json', tmp_path / k.FILE
    plan.write_text(json.dumps(PLAN), encoding='utf-8')
    assert k.main(['build', str(plan), str(path)]) == 1
    data = json.loads(path.read_text(encoding='utf-8'))
    for row in data['circuits']:
        row.update(typical='none', reason='知识包没有对应条目')
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    assert k.main(['check', str(plan), str(path)]) == 0


def test_every_installed_scheme_yields_items_and_the_gates_read_the_checklist():
    for md in sorted((ROOT / 'references/knowledge/典型电路').rglob('*.md')):
        found = k.implementations(md.read_text(encoding='utf-8')) if md.name != 'README.md' else {}
        assert not found or any(found.values()), md.name     # a scheme may list neither kind; a whole entry that does lost its format
    for script in ('validate_review.py', 'pack_review.py'):
        assert 'knowledge_checklist.problems(' in (ROOT / 'scripts' / script).read_text(encoding='utf-8')
