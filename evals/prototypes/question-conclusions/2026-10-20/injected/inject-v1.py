"""Phase-1 injection runner: the same ten errors (design §8.4) into both arms; detected = new errors vs baseline."""
import copy, json, os, shutil, subprocess, sys
from pathlib import Path
SR = Path(os.environ.get('SR_ROOT') or Path(__file__).resolve().parents[5])  # 在 scratchpad 运行时设 SR_ROOT
W = Path(__file__).resolve().parent  # 旧格式（arm-b/arm-b2，单值最坏情况 + 余量）；所调原型脚本的旧路径已改名，仅作记录
B = W / (sys.argv[1] if len(sys.argv) > 1 else 'b')
sys.path.insert(0, str(SR / 'scripts'))
from validate_review import fingerprint
from derive_rows import DERIVED_FIELDS

def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def dump(o, p): Path(p).write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding='utf-8')

def plan_with_lint(extra):
    from plan_review import build_review_plan
    from lint import Lint
    db, intent = load(W / 'base/db.json'), load(W / 'base/intent.json')
    return build_review_plan(db, intent, lint_findings=Lint(db, None, intent, None, None).run() + [extra])

# ---------- arm A ----------
def run_a(rr, plan, tag):
    d = W / 'inj' / 'a' / tag
    if d.exists(): shutil.rmtree(d)
    d.mkdir(parents=True)
    for x in ('evidence', 'intent.json', 'references'):
        src = B / x
        (shutil.copytree if src.is_dir() else shutil.copy)(src, d / x)
    rr = copy.deepcopy(rr)
    rr['plan_digest'] = fingerprint(plan)
    for row in rr['checks']:   # rows bound to a function are re-derived, as the workflow does
        if row.get('function_id'):
            for k in DERIVED_FIELDS + ('rationale',):
                row.pop(k, None)
    dump(plan, d / 'plan.json'); dump(rr, d / 'review-results.json')
    der = subprocess.run([sys.executable, str(SR / 'scripts/derive_rows.py'), 'plan.json', 'review-results.json',
                          '-o', 'review-results.json'], cwd=d, capture_output=True, text=True)
    val = subprocess.run([sys.executable, str(SR / 'scripts/validate_review.py'), 'plan.json', 'review-results.json',
                          '--db', str(W / 'base/db.json'), '--json', 'gate.json'], cwd=d, capture_output=True, text=True)
    gate = load(d / 'gate.json') if (d / 'gate.json').exists() else {'errors': ['no gate output: ' + val.stderr[-300:]]}
    derive_err = [l for l in (der.stdout + der.stderr).splitlines() if l.strip()] if der.returncode else []
    return {'derive_exit': der.returncode, 'derive_errors': derive_err, 'errors': gate.get('errors') or [],
            'release': gate.get('release')}

def xlat(rr): return next(f for f in rr['functions'] if f['id'] == 'FN-UART-XLAT')
def judgement(fn, aspect): return next(j for j in fn['judgements'] if j['aspect'] == aspect)

def a_injections(rr0, plan0):
    out = {}
    def mk(): return copy.deepcopy(rr0), copy.deepcopy(plan0)
    # 1 negative margin judged pass: esp-reset level aspect loses its fail item and gets a pass judgement
    rr, p = mk(); f = xlat(rr)
    f['fails'][0]['decides'] = [d for d in f['fails'][0]['decides'] if d['aspect'] != '逻辑电平与驱动匹配']
    judgement(f, '逻辑电平与驱动匹配')['states'] = ['run', 'esp-reset']
    out[1] = (rr, p)
    # 2 an aspect nobody answers
    rr, p = mk(); f = xlat(rr)
    f['judgements'] = [j for j in f['judgements'] if j['aspect'] != '接口方向语义']
    out[2] = (rr, p)
    # 3 netlist R18 10k written as 4.7k and used
    rr, p = mk(); f = xlat(rr)
    c5 = next(c for c in f['conditions'] if c['id'] == 'c5'); c5['says'] = c5['says'].replace('R18 10 k', 'R18 4.7 k')
    m = next(m for m in f['calculation']['margin'] if m['aspect'] == '掉电与跨域注入'); m['value'] = -0.351
    f['calculation']['result'] += '；注入 (5.25−3.6)/4.7 k = 0.351 mA'
    out[3] = (rr, p)
    # 4 cites a clause that does not exist
    rr, p = mk(); judgement(xlat(rr), '接口方向语义')['conditions'] = ['c99']
    out[4] = (rr, p)
    # 5 formula result disagrees with the stated worst value (2.2×10k×50pF = 1.1 µs written as 0.3 µs)
    rr, p = mk(); f = xlat(rr)
    f['calculation']['result'] = f['calculation']['result'].replace('上升 ≤ 1.1 µs', '上升 ≤ 0.3 µs')
    next(m for m in f['calculation']['margin'] if m['aspect'] == '时序裕量')['value'] = 8.4
    out[5] = (rr, p)
    # 6 positive public-bound margin kept open (timing aspect)
    rr, p = mk(); f = xlat(rr)
    f['calculation']['margin'] = [m for m in f['calculation']['margin'] if m['aspect'] != '时序裕量']
    f['open'] = [{'key': 'NODE-C', 'kind': 'VENDOR_DATUM', 'what': 'U1 RXD 输入电容未给', 'decides': [{'aspect': '时序裕量'}],
                  'checked': ['c2'], 'why_insufficient': '§6 只给门限不给输入电容', 'acquisition': 'WCH FAE',
                  'scope': '115200 bps，节点总电容', 'closure': '节点电容 ≤ 50 pF',
                  'severity': {'level': 'P3', 'class': 'OPTIMIZATION', 'affects': 'UART 调试链路', 'consequence': '高波特率误码'},
                  'worst_case': {'bound': {'condition': 'c2', 'value': '取 50 pF', 'basis': 'TYPICAL_CURVE'},
                                 'result': '上升 ≤ 1.1 µs', 'margin': {'value': 7.6, 'unit': 'µs', 'against': '位宽 8.7 µs'}}}]
    out[6] = (rr, p)
    # 7 undecided without saying who provides it
    rr, p = mk(); f = xlat(rr)
    f['calculation']['margin'] = [m for m in f['calculation']['margin'] if m['aspect'] != '时序裕量']
    f['open'] = [{'key': 'NODE-C', 'kind': 'VENDOR_DATUM', 'what': 'U1 RXD 输入电容未给', 'decides': [{'aspect': '时序裕量'}],
                  'checked': ['c2'], 'why_insufficient': '§6 只给门限不给输入电容',
                  'scope': '115200 bps，节点总电容', 'closure': '节点电容 ≤ 50 pF',
                  'severity': {'level': 'P3', 'class': 'OPTIMIZATION', 'affects': 'UART 调试链路', 'consequence': '高波特率误码'},
                  'worst_case': {'not_boundable_reason': '手册无输入电容', 'operating_point_specified': True,
                                 'curves_checked': [{'source': 'evidence/ds/ch340ds1-v3c.txt', 'locator': 'p8 §6'}]}}]
    out[7] = (rr, p)
    # 8 a tool suspicion on the link nobody answers
    rr, _ = mk(); out[8] = (rr, plan_with_lint({'rule': 'PWR-A01', 'name': '电源轨疑似无驱动', 'detail': SUSPECT,
                                                'kind': 'FINDING', 'page': 1, 'ref': 'R19'}))
    # 9 fail without a fix
    rr, p = mk(); rr['findings'][0].pop('remediation'); rr['findings'][0].pop('recommendation', None)
    out[9] = (rr, p)
    # 10 fact contrary to the netlist (crossing written swapped)
    rr, p = mk()
    for fn in rr['functions']:
        judgement(fn, '接口方向语义')['says'] = 'U1.8 TXD 经 D6 到 U6.35 U0TXD，U6.34 U0RXD 经 D7 到 U1.9 RXD，收发交叉正确'
    out[10] = (rr, p)
    return out

SUSPECT = 'R19 把 U6 U0RXD 上拉到 Net-(U1-V3)，CH340 5 V 模式下 V3 无保证窗口'

# ---------- arm B ----------
def run_b(qs, cs, tag):
    d = W / 'inj' / B.name / tag
    d.mkdir(parents=True, exist_ok=True)
    dump(qs, d / 'questions.json'); dump(cs, d / 'cards.json')
    r = subprocess.run([sys.executable, str(SR / 'evals/prototypes/question-cards/cards_check.py'), str(d / 'questions.json'),
                        str(B / 'clauses.json'), str(d / 'cards.json'), '--db', str(W / 'base/db.json'),
                        '--evidence-root', str(W / 'b'), '-o', str(d / 'check.json')], capture_output=True, text=True)
    out = load(d / 'check.json')
    return {'errors': ['%s/%s %s: %s' % (e['check'], e['code'], e.get('question'), e['message']) for e in out['errors']],
            'release': out['summary']['release']}

def b_injections(qs0, cs0):
    def card(cs, k):
        # k is 'CIRCUIT/RULE' (arm b) or 'CIRCUIT/RULE@state'; merged questions match any of their circuits
        where, _, state = k.partition('@')
        circuit, rule = where.split('/')
        qids = [x['id'] for x in qs0['questions'] if x['rules'][0] == rule and circuit in (x['subject'].get('circuits') or [x['subject']['name']])]
        hits = [c for c in cs if c['question'] in qids and (not state or state in (c.get('states') or [state]))]
        return hits[0]
    qid = {k: card(cs0, k)['question'] for k in ('UART-XLAT/SIG-C09', 'UART-XLAT/SIG-T04')}
    out = {}
    def mk(): return copy.deepcopy(qs0), copy.deepcopy(cs0)
    qs, cs = mk(); c = card(cs, 'UART-XLAT/SIG-C07@esp-reset'); c['outcome'] = 'PASS'; c.pop('fix'); c.pop('severity'); out[1] = (qs, cs)
    qs, cs = mk(); cs.remove(card(cs, 'UART-XLAT/SIG-T04')); out[2] = (qs, cs)
    qs, cs = mk(); b = card(cs, 'UART-XLAT/SIG-C08@esp-reset')['basis']
    b['worst_case']['inputs']['r18']['value'] = 4.7; b['worst_case']['value'] = 0.351; b['margin']['value'] = -0.351; out[3] = (qs, cs)
    qs, cs = mk(); card(cs, 'UART-XLAT/SIG-T04')['basis']['clauses'] = ['K-NOPE']; out[4] = (qs, cs)
    qs, cs = mk(); b = card(cs, 'UART-XLAT/SIG-C09')['basis']; b['worst_case']['value'] = 300; b['margin']['value'] = 8380; out[5] = (qs, cs)
    qs, cs = mk(); c = card(cs, 'UART-XLAT/SIG-C09')
    c.update(outcome='UNDECIDED', best_bound=c.pop('basis'), loose_input='c_node',
             missing={'what': 'U1 RXD 输入电容', 'from': 'VENDOR', 'closes_when': '节点电容 ≤ 50 pF'},
             severity={'level': 'P3', 'consequence': '高波特率误码'}); out[6] = (qs, cs)
    qs, cs = mk(); c = card(cs, 'UART-XLAT/SIG-C09'); c.pop('basis')
    c.update(outcome='UNDECIDED', best_bound=None, searched=[{'source': 'evidence/ds/ch340ds1-v3c.txt', 'locator': 'p8 §6'}],
             missing={'what': 'U1 RXD 输入电容'}, severity={'level': 'P3', 'consequence': '高波特率误码'}); out[7] = (qs, cs)
    qs, cs = mk(); q = next(x for x in qs['questions'] if x['id'] == qid['UART-XLAT/SIG-C09'])
    q['observations'] = [{'id': 'O-1', 'kind': 'SUSPECT', 'says': SUSPECT, 'input': False}]; out[8] = (qs, cs)
    qs, cs = mk(); card(cs, 'UART-XLAT/SIG-C07@esp-reset').pop('fix'); out[9] = (qs, cs)
    qs, cs = mk()
    for k in _t04(cs, card):
        f = card(cs, k)['basis']['facts']
        f[1] = {'node': 'D6.2', 'net_same_as': 'U6.35', 'means': 'D6 阳极接 U6 U0TXD'}
        f[2] = {'node': 'U6.34', 'net_same_as': 'D7.1', 'means': 'U6 U0RXD 接 D7 阴极'}
    out[10] = (qs, cs)
    return out

def _t04(cs, card):
    seen, keys = [], []
    for k in ('UART-XLAT/SIG-T04', 'UART-DBG/SIG-T04'):
        c = card(cs, k)
        if not any(c is x for x in seen):
            seen.append(c); keys.append(k)
    return keys

NAMES = {1: '余量为负却判通过', 2: '一个方面/问题没人回答', 3: '网表阻值写成另一值参与计算', 4: '引用不存在的条款',
         5: '算式结果与最坏值不一致', 6: '公开界余量为正却挂起', 7: '判不了却没写找谁', 8: '工具疑点无人回应',
         9: '不通过没有改法', 10: '事实结论与网表不符（交叉写反）'}

def main():
    rr0, plan0 = load(W / 'a/review-results.json'), load(W / 'a/plan.json')
    qs0, cs0 = load(B / 'questions.json'), load(B / 'cards.json')
    base_a, base_b = run_a(rr0, plan0, 'base'), run_b(qs0, cs0, 'base')
    assert not base_a['errors'] and not base_a['derive_exit'], base_a
    assert not base_b['errors'], base_b
    res = []
    ai, bi = a_injections(rr0, plan0), b_injections(qs0, cs0)
    for n in range(1, 11):
        a, b = run_a(*ai[n], 'i%02d' % n), run_b(*bi[n], 'i%02d' % n)
        na = [e for e in a['derive_errors'] + a['errors'] if e not in base_a['errors']]
        nb = [e for e in b['errors'] if e not in base_b['errors']]
        res.append({'n': n, 'error': NAMES[n], 'A': {'caught': bool(na), 'by': na, 'derive_exit': a['derive_exit']},
                    'B': {'caught': bool(nb), 'by': nb}})
    dump(res, W / ('injections-%s.json' % B.name))
    for r in res:
        print('%2d %-22s A=%s B=%s' % (r['n'], r['error'], 'Y' if r['A']['caught'] else '-', 'Y' if r['B']['caught'] else '-'))
        for e in r['A']['by'][:2]: print('     A:', e[:200])
        for e in r['B']['by'][:2]: print('     B:', e[:200])
    print('A', sum(r['A']['caught'] for r in res), 'B', sum(r['B']['caught'] for r in res))

main()
