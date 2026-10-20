#!/usr/bin/env python3
"""训练语料冷跑 / 热审输入包（README 第 2、7 节）。

cold：每块板 parse_kicad → db.json，lint → lint.json + plan.json。
hot：只准备输入包（db.json + pack.json），审查本身由审查 agent 按 SKILL.md 完成。
fix pair 只跑 before 版，板 id 为 "<pair id>.before"；成熟板跑其 schematic。
第三方原理图从 --cache/<仓库名>/<schematic> 取；语料条目带 fixture 时直接用仓库内夹具。
"""
import argparse, json, pathlib, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / 'scripts'


def boards(corpus_dir, names, split):
    out = []
    for name in names:
        data = json.load(open(corpus_dir / f'{name}.json', encoding='utf-8'))
        if name == 'fix-pairs':
            for p in data.get('pairs', []):
                out.append({'board': p['id'] + '.before', 'corpus': name, 'split': p.get('split'),
                            'repo': p['repo'], 'schematic': p['before']['schematic'], 'fixture': None})
        else:
            for b in data.get('boards', []):
                out.append({'board': b['id'], 'corpus': name, 'split': b.get('split'),
                            'repo': b['repo'], 'schematic': b.get('schematic'), 'fixture': b.get('fixture')})
    return [b for b in out if split == 'all' or b['split'] == split]


def source_path(entry, cache):
    if entry['fixture']:
        return ROOT / entry['fixture']
    if cache is None:
        return None
    return cache / entry['repo'].rstrip('/').rsplit('/', 1)[-1] / entry['schematic']


def run(cmd, log):
    with open(log, 'w', encoding='utf-8') as fh:
        return subprocess.run([sys.executable, '-B', *map(str, cmd)], stdout=fh, stderr=subprocess.STDOUT).returncode


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--corpus', default='fix-pairs,mature-boards', help='逗号分隔的语料文件名（不带 .json）')
    ap.add_argument('--corpus-dir', default=str(ROOT / 'evals/training/corpus'))
    ap.add_argument('--split', default='train', choices=['train', 'holdout', 'all'])
    ap.add_argument('--mode', default='cold', choices=['cold', 'hot'])
    ap.add_argument('--cache', help='第三方仓库缓存目录（build_fix_pairs.py 的 --cache）')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    out = pathlib.Path(args.out); out.mkdir(parents=True, exist_ok=True)
    cache = pathlib.Path(args.cache) if args.cache else None
    index = []
    for entry in boards(pathlib.Path(args.corpus_dir), args.corpus.split(','), args.split):
        src = source_path(entry, cache)
        rec = dict(entry, source=str(src) if src else None, mode=args.mode)
        bdir = out / entry['board']; bdir.mkdir(exist_ok=True)
        if src is None or not src.exists():
            rec['error'] = 'schematic not found (give --cache or fixture)'
            index.append(rec); print('SKIP', entry['board'], rec['error']); continue
        t0 = time.time()
        rec['parse_exit'] = run([SCRIPTS / 'parse_kicad.py', src, '-o', bdir / 'db.json'], bdir / 'parse.log')
        if args.mode == 'cold':
            rec['lint_exit'] = run([SCRIPTS / 'lint.py', bdir / 'db.json', '--json', bdir / 'lint.json',
                                    '--plan-json', bdir / 'plan.json'], bdir / 'lint.log')
        else:
            json.dump({'db': 'db.json', 'intent': None, 'materials': [],
                       'todo': '审查 agent 按 SKILL.md 补 intent、资料目录，产出 review-results.json / gate / 报告'},
                      open(bdir / 'pack.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        rec['seconds'] = round(time.time() - t0, 1)
        index.append(rec); print(args.mode.upper(), entry['board'], f"parse={rec['parse_exit']}", f"{rec['seconds']}s")
    json.dump(index, open(out / 'index.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
