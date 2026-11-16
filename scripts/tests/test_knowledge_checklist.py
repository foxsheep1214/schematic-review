"""知识必答清单：计划里每块电路对上典型电路的实现方案，方案的必算项和已知坑逐项有处置；校验入口和打包都核对。"""
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import knowledge_checklist as k
import knowledge_source

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
    monkeypatch.setattr(knowledge_source, 'knowledge_dir', lambda: tmp_path)
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
    data['circuits'][1]['reason'] = '查过 usb、type-c，知识框架没有 USB 2.0 设备口的条目'
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
    assert 'reg#方案丙 在知识框架的典型电路里找不到' in k.problems(PLAN, data)[0]


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
        row.update(typical='none', reason='知识框架没有对应条目')
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    assert k.main(['check', str(plan), str(path)]) == 0


def test_every_framework_scheme_yields_items_and_the_gates_read_the_checklist():
    for md in sorted((knowledge_source.knowledge_dir() / '典型电路').rglob('*.md')):
        found = k.implementations(md.read_text(encoding='utf-8')) if md.name != 'README.md' else {}
        assert not found or any(found.values()), md.name     # a scheme may list neither kind; a whole entry that does lost its format
    for script in ('validate_review.py', 'pack_review.py'):
        assert 'knowledge_checklist.problems(' in (ROOT / 'scripts' / script).read_text(encoding='utf-8')


DECLARED = {'典型电路/电源变换/buck.md': ('POWER_CONVERTER', '通用'),
            '器件参数/mosfet.md': ('通用', 'mosfet'),
            '失效与故障分析/tvs.md': ('POWER_PROTECTION（输入端）', 'tvs、fuse'),
            '接口约定/rs485.md': ('RS485', '通用')}


@pytest.fixture
def declared(tmp_path, monkeypatch):
    """临时小框架：几个带词表声明的条目，环境变量指过去。"""
    from framework_fixtures import small_framework
    framework = small_framework(tmp_path / 'framework')
    for path, (circuits, kinds) in DECLARED.items():
        md = framework / '知识' / path
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text('# %s\n\n电路类型：%s\n器件类别：%s\n\n## 内容\n\n电路类型：ANALOG\n' % (md.stem, circuits, kinds), encoding='utf-8')
    monkeypatch.setenv('HARDWARE_KNOWLEDGE_FRAMEWORK', str(framework))
    return framework


def test_entries_are_listed_by_component_from_their_declarations(declared, tmp_path, capsys):
    found = k.entries_by_component(['POWER_CONVERTER', 'POWER_PROTECTION', 'ANALOG'], ['mosfet'])
    assert list(found) == ['典型电路', '器件参数', '失效与故障分析']          # component order, ANALOG below 二级标题 is not a declaration
    assert found['典型电路'] == [('典型电路/电源变换/buck.md', ['POWER_CONVERTER'])]
    assert found['失效与故障分析'] == [('失效与故障分析/tvs.md', ['POWER_PROTECTION'])]
    assert k.main(['entries', 'mosfet', 'RS485']) == 0
    out = capsys.readouterr().out
    assert '器件参数\n  器件参数/mosfet.md  mosfet' in out and '接口约定/rs485.md  RS485' in out and 'buck' not in out
    assert k.main(['entries', 'RS-485']) == 1 and '不在知识框架词表里：RS-485' in capsys.readouterr().out
    plan = tmp_path / 'review-plan.json'
    plan.write_text(json.dumps({'guidelines': {'circuit_types': ['POWER_CONVERTER'], 'device_kinds': ['fuse']}}), encoding='utf-8')
    assert k.main(['entries', str(plan)]) == 0
    out = capsys.readouterr().out
    assert 'buck.md  POWER_CONVERTER' in out and 'tvs.md  fuse' in out and 'mosfet' not in out


def test_declared_entries_missing_from_the_record_are_hints_not_failures(declared, tmp_path, capsys):
    plan = {'owners': [], 'guidelines': {'circuit_types': ['POWER_CONVERTER'], 'device_kinds': ['mosfet', 'tvs']}}
    assert k.problems(plan, None) == []
    assert [h.split(' ')[0] for h in k.hints(plan, None)] == ['典型电路/电源变换/buck.md', '器件参数/mosfet.md', '失效与故障分析/tvs.md']
    data = {'circuits': [{'circuit': 'c1', 'typical': 'buck#方案甲'}],
            'entries': [{'entry': '器件参数/mosfet.md', 'disposition': 'read'},
                        {'entry': '失效与故障分析/tvs.md', 'disposition': 'not_applicable', 'reason': ''}]}
    assert [h.split(' ')[0] for h in k.hints(plan, data)] == ['失效与故障分析/tvs.md']   # 不适用要写理由
    data['entries'][1]['reason'] = '本板 TVS 只在信号口，输入端没有'
    assert k.hints(plan, data) == []
    # without a guidelines section the circuit types come from the checks
    assert [h.split(' ')[0] for h in k.hints({'checks': [{'id': 'x', 'circuit_type': 'RS485'}]}, None)] == ['接口约定/rs485.md']
    del data['entries'][1]
    paths = tmp_path / 'review-plan.json', tmp_path / k.FILE
    paths[0].write_text(json.dumps(plan), encoding='utf-8')
    paths[1].write_text(json.dumps(dict(data, schema_version=k.SCHEMA_VERSION), ensure_ascii=False), encoding='utf-8')
    assert k.main(['check', str(paths[0]), str(paths[1])]) == 0
    out = capsys.readouterr().out
    assert out.startswith('提示:\n  - 失效与故障分析/tvs.md 声明了本板的 tvs') and out.endswith('PASS\n')
    assert k.build(plan, data)['entries'] == data['entries']                    # build keeps the record


def test_the_plan_records_the_board_scope_and_the_gate_shows_the_hints(declared, tmp_path):
    plan = {'owners': [], 'knowledge_scope': {'circuit_types': ['RS485'], 'device_kinds': ['mosfet']},
            'guidelines': {'circuit_types': ['POWER_CONVERTER'], 'device_kinds': []}}
    assert k.board_scope(plan) == (['RS485'], ['mosfet'])                    # knowledge_scope first, rules or not
    from test_validate_review import fixture
    p, r, db = fixture()
    p['knowledge_scope'] = {'circuit_types': [], 'device_kinds': ['mosfet']}
    paths = []
    for name, data in (('plan', p), ('results', r), ('db', db)):
        paths.append(tmp_path / (name + '.json'))
        paths[-1].write_text(json.dumps(data), encoding='utf-8')
    import os
    env = dict(os.environ, HARDWARE_KNOWLEDGE_FRAMEWORK=str(declared))
    proc = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts' / 'validate_review.py'), *map(str, paths[:2]),
                           '--db', str(paths[2]), '--json', str(tmp_path / 'gate.json')], capture_output=True, text=True, env=env)
    gate = json.loads((tmp_path / 'gate.json').read_text(encoding='utf-8'))
    assert [h.split(' ')[0] for h in gate.get('knowledge_hints', [])] == ['器件参数/mosfet.md'], proc.stderr
    assert not any('mosfet.md' in e for e in gate['errors'])                  # a hint, never an error


def test_what_the_review_feeds_back_to_the_framework(knowledge):
    """A circuit no typical circuit matches and the reviewer's `issues` are the review's feedback to the knowledge
    framework: a report section and the rows pack_review.py writes as record/knowledge-gaps.json."""
    data = k.build(PLAN, None)
    data['circuits'][1].update(typical='none', reason='查过 usb、type-c，没有 USB 2.0 设备口的条目')
    assert k.gaps(data)['counts'] == {'no_typical_circuit': 1} and k.gaps(None)['gaps'] == [] and k.render_gaps(None) == []
    issue = {'component': '器件参数', 'target': '器件参数/08_电源管理/x.md', 'kind': '错', 'detail': '压差写的是典型值',
             'evidence': '手册 p7 表 6.5'}
    data['issues'] = [dict(issue, kind='不对')]
    assert any('kind 写' in p for p in k.problems(PLAN, data))
    data['issues'] = [dict(issue, component='技能')]
    assert any('component 写' in p for p in k.problems(PLAN, data))
    data['issues'] = [{k2: v for k2, v in issue.items() if k2 != 'evidence'}]
    assert any('都要写' in p for p in k.problems({'owners': []}, data))      # checked on a plan without circuits too
    data['issues'] = [issue, dict(issue, component='设计准则', target='G04-017', kind='缺', detail='没有覆盖开漏输出')]
    assert not [p for p in k.problems(PLAN, data) if 'issues' in p]
    assert k.build(PLAN, data)['issues'] == data['issues'] and 'issues' not in k.build(PLAN, None)   # build keeps them
    rows = k.gaps(data)['gaps']
    assert [(r['signal'], r['component'], r['item']) for r in rows] == [
        ('no_typical_circuit', '典型电路', 'usb'), ('knowledge_issue', '器件参数', '器件参数/08_电源管理/x.md'),
        ('knowledge_missing', '设计准则', 'G04-017')]
    assert rows[1]['detail'] == '错：压差写的是典型值（依据：手册 p7 表 6.5）'
    text = '\n'.join(k.render_gaps(data))
    assert text.startswith('## 对知识框架的反馈') and '共 3 条' in text and '| 设计准则 | 知识框架查不到 | G04-017 |' in text
