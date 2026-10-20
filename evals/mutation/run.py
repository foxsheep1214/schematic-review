#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""变异门：把仓库复制到临时目录，逐条注入 mutations.json 里的具名缺陷，跑单元测试，记录杀死/存活。

    python3 evals/mutation/run.py                 全部变异 × 单元测试层与合同层，写 evals/mutation/RESULTS.md
    python3 evals/mutation/run.py --only M4 M9    只跑这几条
    python3 evals/mutation/run.py --tier unit     只跑单元测试层

单元测试层 = scripts/tests 去掉三块板级基准（典型电路、种子基准、KiCad 回放）；合同层 = 其中 `-m contract`。
门槛：每条变异都必须被单元测试层杀死（任一测试失败），有存活即退出 1。合同层一列只报告，不设门槛。
注入只发生在临时副本里；源仓库不改。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BENCHES = ('test_typical_circuits.py', 'test_seeded_bench.py', 'test_kicad_replay_bench.py')
TRAINING_RUNS = Path('evals') / 'training' / 'runs'


def IGNORE(directory, names):
    """What the working copy leaves out: VCS/cache dirs, the top-level review runs, and inside the
    tracked training rounds only the untracked bench/cold-run artefacts. Dropping every directory
    named `runs` used to drop the training rounds the ledger's latest entry lists, so the ledger
    test failed in every copy and every mutation looked killed."""
    rel = Path(directory).resolve().relative_to(ROOT.resolve()) if Path(directory).resolve() != ROOT.resolve() else Path('.')
    skip = {n for n in names if n in ('.git', '.claude', '__pycache__', '.pytest_cache')}
    if rel == Path('.'):
        skip |= {n for n in names if n == 'runs'}
    if rel == TRAINING_RUNS or TRAINING_RUNS in rel.parents:
        skip |= {n for n in names if n in ('reviews', 'seeded', 'replay', 'critic') or n.endswith('.log')}
    return skip


def pytest_command(tier):
    command = [sys.executable, '-m', 'pytest', 'scripts/tests', '-x', '-q', '--no-header',
               '-p', 'no:cacheprovider']
    command += ['--ignore=scripts/tests/' + name for name in BENCHES]
    if tier == 'contract':
        command += ['-m', 'contract']
    return command


def first_failure(output):
    return next((line for line in output.splitlines() if line.startswith(('FAILED', 'ERROR'))), '')


def run_mutation(mutation, tiers, workdir):
    copy = Path(workdir) / mutation['id']
    shutil.copytree(ROOT, copy, ignore=IGNORE)
    target = copy / mutation['file']
    text = target.read_text(encoding='utf-8')
    count = text.count(mutation['old'])
    if count != 1:
        return dict(mutation, error='pattern found %d times (need exactly 1)' % count)
    target.write_text(text.replace(mutation['old'], mutation['new'], 1), encoding='utf-8')
    row = {key: mutation[key] for key in ('id', 'name', 'file')}
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    for tier in tiers:
        started = time.time()
        done = subprocess.run(pytest_command(tier), cwd=copy, capture_output=True, text=True, env=env)
        output = done.stdout + done.stderr
        # pytest 退出码 5 = 没收集到测试，不能算杀死
        status = 'KILLED' if done.returncode not in (0, 5) else 'SURVIVED'
        row[tier] = {'status': status, 'first_failure': first_failure(output)[:160],
                     'seconds': round(time.time() - started, 1)}
    shutil.rmtree(copy, ignore_errors=True)
    return row


def clean_copy_passes(tiers, workdir):
    """The unmutated copy must pass the unit tier, otherwise every kill below is spurious."""
    copy = Path(workdir) / 'baseline'
    shutil.copytree(ROOT, copy, ignore=IGNORE)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    done = subprocess.run(pytest_command('unit'), cwd=copy, capture_output=True, text=True, env=env)
    shutil.rmtree(copy, ignore_errors=True)
    if done.returncode != 0:
        print('baseline: the unmutated copy fails the unit tier, kills would be meaningless:\n'
              + first_failure(done.stdout + done.stderr), file=sys.stderr)
        return False
    return True


def table(rows, tiers):
    head = '| 变异 | 说明 | 文件 | ' + ' | '.join(tiers) + ' | 首个失败的测试（单元层） |'
    lines = [head, '|' + '---|' * (4 + len(tiers))]
    for row in rows:
        if 'error' in row:
            lines.append(f"| {row['id']} | {row['name']} | `{row['file']}` | " + ' | '.join('ERROR' for _ in tiers)
                         + f" | {row['error']} |")
            continue
        first = (row.get('unit') or row[tiers[0]])['first_failure'].replace('|', '\\|')
        lines.append(f"| {row['id']} | {row['name']} | `{row['file']}` | "
                     + ' | '.join(row[t]['status'] for t in tiers) + f' | {first} |')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='变异门：注入具名缺陷，确认单元测试能杀死')
    parser.add_argument('--only', nargs='*', help='只跑这些变异编号')
    parser.add_argument('--tier', choices=('unit', 'contract', 'both'), default='both')
    parser.add_argument('--jobs', type=int, default=max(1, (os.cpu_count() or 2) // 2))
    parser.add_argument('--out', default=str(HERE / 'RESULTS.md'), help='结果表（Markdown）')
    parser.add_argument('--json', help='另存 JSON')
    args = parser.parse_args()
    mutations = json.loads((HERE / 'mutations.json').read_text(encoding='utf-8'))
    if args.only:
        mutations = [m for m in mutations if m['id'] in args.only]
    tiers = ['unit', 'contract'] if args.tier == 'both' else [args.tier]
    with tempfile.TemporaryDirectory(prefix='sr-mutation-') as workdir:
        if not clean_copy_passes(tiers, workdir):
            return 1
        with ThreadPoolExecutor(args.jobs) as pool:
            rows = list(pool.map(lambda m: run_mutation(m, tiers, workdir), mutations))
    text = table(rows, tiers)
    print(text)
    survivors = [r['id'] for r in rows if 'error' in r or r.get(tiers[0], {}).get('status') != 'KILLED']
    if args.out:
        Path(args.out).write_text(
            '# 变异门结果\n\n由 `python3 evals/mutation/run.py` 生成；门槛是单元层全部 KILLED。\n\n'
            + text + '\n\n' + ('存活：' + ', '.join(survivors) if survivors else '全部杀死。') + '\n',
            encoding='utf-8')
    if args.json:
        Path(args.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')
    if survivors:
        print('survived: ' + ', '.join(survivors), file=sys.stderr)
    return 1 if survivors else 0


if __name__ == '__main__':
    sys.exit(main())
