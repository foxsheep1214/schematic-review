"""受控修改本地数据，证明消费者读取；默认分类字段与原行为另由原有回归覆盖。"""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def run(code):
    subprocess.run([sys.executable, '-B', '-c', code], cwd=ROOT, check=True, capture_output=True, text=True)


def test_titles_are_consumed_from_local_vocabulary(tmp_path):
    vocabulary = json.loads((ROOT / 'references/shared/vocabulary.json').read_text())
    vocabulary['device_kinds'][0]['title'] = '受控继电器标题'
    vocabulary['circuit_types'][0]['title'] = '受控变换器标题'
    path = tmp_path / 'vocabulary.json'
    path.write_text(json.dumps(vocabulary))
    run("import sys; sys.path.insert(0, 'scripts'); import guideline_criteria as g; "
        + "g.VOCABULARY_PATH = __import__('pathlib').Path(%r); " % str(path)
        + "import device_kinds as dk, catalog; assert dk.KINDS['relay'].title == '受控继电器标题'; assert catalog.CIRCUIT_TYPES[0].title == '受控变换器标题'; assert dk.KINDS['relay'].wearout == 'RELAY'; assert catalog.CIRCUIT_TYPES[0].subjects[0] == 'PWR-C02'")


def test_assumed_package_changes_real_proposal(tmp_path):
    data = json.loads((ROOT / 'references/shared/guideline-criteria.json').read_text())
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
