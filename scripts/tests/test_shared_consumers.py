"""受控修改本地数据，证明消费者读取；默认分类字段与原行为另由原有回归覆盖。"""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import guideline_criteria
import knowledge_source
from framework_fixtures import small_framework


def run(code, framework=None):
    env = dict(os.environ)
    if framework:
        env[knowledge_source.ENV_VAR] = str(framework)
    subprocess.run([sys.executable, '-B', '-c', code], cwd=ROOT, check=True, capture_output=True, text=True, env=env)


def test_titles_are_consumed_from_framework_vocabulary(tmp_path):
    framework = small_framework(tmp_path / 'framework')
    path = framework / knowledge_source.vocabulary_path().relative_to(knowledge_source.framework_root())
    vocabulary = json.loads(path.read_text())
    vocabulary['device_kinds'][0]['title'] = '受控继电器标题'
    vocabulary['circuit_types'][0]['title'] = '受控变换器标题'
    path.write_text(json.dumps(vocabulary))
    run("import sys; sys.path.insert(0, 'scripts'); "
        + "import device_kinds as dk, catalog; assert dk.KINDS['relay'].title == '受控继电器标题'; assert catalog.CIRCUIT_TYPES[0].title == '受控变换器标题'; assert dk.KINDS['relay'].wearout == 'RELAY'; assert catalog.CIRCUIT_TYPES[0].subjects[0] == 'PWR-C02'", framework)


def test_assumed_package_changes_real_proposal(tmp_path):
    data = guideline_criteria.load()
    data['engineering_values']['assumed_resistor_package']['value'] = '0201'
    path = tmp_path / 'criteria.json'
    path.write_text(json.dumps(data))
    run("import sys, os; sys.path[:0] = ['scripts', 'scripts/tests']; "
        + "os.environ['GUIDELINE_CRITERIA_TESTING'] = '1'; os.environ['GUIDELINE_CRITERIA'] = %r; " % str(path)
        + "from test_passive_stress import board, proposals; "
        + "db, intent = board(); db['parts']['R1'].update(jedec='', value='100'); "
        + "from test_decoupling import rebind; rebind(db,intent); "
        + "_, rows = proposals(db,intent); calc = rows['R1']['proposal']['calculation']; "
        + "assert calc['p_floor_w'] == 0.05, calc; assert calc['v_floor_v'] == 15, calc")
