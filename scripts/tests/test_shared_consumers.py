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


