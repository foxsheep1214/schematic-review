"""Phase-1 injection runner: the same fifteen errors (design §8.4; 11–15 are over-strict) into both arms; detected = new errors vs baseline."""
import copy, json, os, shutil, subprocess, sys
from pathlib import Path
SR = Path(os.environ.get('SR_ROOT') or Path(__file__).resolve().parents[5])  # 在 scratchpad 运行时设 SR_ROOT
W = Path(__file__).resolve().parent  # 原在 scratchpad：a/ b3/ base/（db.json 与手册不进仓库）
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
    # 11 fail computed at the worst corner only (favourable corner would pass)
    rr, p = mk(); f = xlat(rr)
    m = next(m for m in f['calculation']['margin'] if m['aspect'] == '逻辑电平与驱动匹配')
    m.update(value=-1.65, against='U6 引脚上限 3.6 V（esp-reset，最坏角点 VF=0，VF 取 0–1.5 V）')
    out[11] = (rr, p)
    # 12 fail against a limit the reviewer assumed: already in the valid baseline (允许注入 0 mA，取不允许)
    out[12] = mk()
    # 13 severity above its consequence class
    rr, p = mk(); rr['findings'][0]['severity'] = 'P0'; out[13] = (rr, p)
    # 14 one change counted as two defects
    rr, p = mk(); f = xlat(rr); f2 = copy.deepcopy(rr['findings'][0])
    f2['id'] = 'F-002'; f2['check_ids'] = ['SIG-C08.UART-XLAT-ESP-RESET.U1']
    rr['findings'][0]['check_ids'] = [c for c in rr['findings'][0]['check_ids'] if not c.startswith('SIG-C08')]
    rr['findings'].append(f2)
    fail = f['fails'][0]
    fail['decides'] = [d for d in fail['decides'] if d['aspect'] != '掉电与跨域注入']
    f['fails'].append(dict(copy.deepcopy(fail), key='RXD-5V-INJECT', finding_id='F-002',
                           decides=[{'aspect': '掉电与跨域注入', 'states': ['esp-reset']}]))
    out[14] = (rr, p)
    # 15 a requirement nobody set, graded
    rr, p = mk(); f = xlat(rr)
    f['calculation']['margin'] = [m for m in f['calculation']['margin'] if m['aspect'] != '时序裕量']
    f['open'] = [{'key': 'BAUD', 'kind': 'REQUIREMENT', 'what': '调试口波特率需求未定', 'decides': [{'aspect': '时序裕量'}],
                  'severity': {'level': 'P1', 'class': 'REQUIRED_FUNCTION', 'affects': 'UART 调试链路',
                               'consequence': '波特率过高时误码'}}]
    out[15] = (rr, p)
    return out

SUSPECT = 'R19 把 U6 U0RXD 上拉到 Net-(U1-V3)，CH340 5 V 模式下 V3 无保证窗口'

# ---------- arm B ----------
def run_b(qs, cs, tag):
    d = W / 'inj' / B.name / tag
    d.mkdir(parents=True, exist_ok=True)
    dump(qs, d / 'questions.json'); dump(cs, d / 'conclusions.json')
    r = subprocess.run([sys.executable, str(SR / 'evals/prototypes/question-conclusions/conclusions_check.py'), str(d / 'questions.json'),
                        str(B / 'clauses.json'), str(d / 'conclusions.json'), '--db', str(W / 'base/db.json'),
                        '--evidence-root', str(W / 'b'), '-o', str(d / 'check.json')], capture_output=True, text=True)
    out = load(d / 'check.json')
    return {'errors': ['%s/%s %s: %s' % (e['check'], e['code'], e.get('question'), e['message']) for e in out['errors']],
            'release': out['summary']['release']}

def b_injections(qs0, cs0):
    qid = {x['rules'][0]: x['id'] for x in qs0['questions']}
    def c(cs, rule, state=None):
        return next(x for x in cs if x['question'] == qid[rule] and (state is None or state in (x.get('states') or [])))
    out = {}
    def mk(): return copy.deepcopy(qs0), copy.deepcopy(cs0)
    qs, cs = mk(); x = c(cs, 'SIG-C07', 'esp-reset'); x['outcome'] = 'PASS'; x.pop('fix'); x.pop('severity')
    c(cs, 'SIG-C08', 'esp-reset')['fix'] = copy.deepcopy(c(cs0, 'SIG-C07', 'esp-reset')['fix']); out[1] = (qs, cs)
    qs, cs = mk(); cs.remove(c(cs, 'SIG-T04')); out[2] = (qs, cs)
    qs, cs = mk(); b = c(cs, 'SIG-C08', 'run')['basis']; b['inputs']['r19']['value'] = 4.7; b['result']['max'] = round(0.1 / 4.7, 6)
    out[3] = (qs, cs)
    qs, cs = mk(); c(cs, 'SIG-T04')['basis']['clauses'] = ['K-NOPE']; out[4] = (qs, cs)
    qs, cs = mk(); c(cs, 'SIG-C09')['basis']['result']['max'] = 300; out[5] = (qs, cs)
    qs, cs = mk(); x = c(cs, 'SIG-C09')
    x.update(outcome='UNDECIDED', loose_input='c_node', missing={'what': 'U1 RXD 输入电容', 'from': 'VENDOR', 'closes_when': '节点电容 ≤ 50 pF'},
             severity={'level': 'P3', 'class': 'OPTIMIZATION', 'consequence': '高波特率误码'}); out[6] = (qs, cs)
    qs, cs = mk(); x = c(cs, 'SIG-C09'); x.pop('basis')
    x.update(outcome='UNDECIDED', searched=[{'source': 'evidence/ds/ch340ds1-v3c.txt', 'locator': 'p8 §6'}],
             missing={'what': 'U1 RXD 输入电容'}, severity={'level': 'P3', 'class': 'OPTIMIZATION', 'consequence': '高波特率误码'})
    out[7] = (qs, cs)
    qs, cs = mk(); q = next(x for x in qs['questions'] if x['id'] == qid['SIG-C09'])
    q['observations'] = [{'id': 'O-1', 'kind': 'SUSPECT', 'says': SUSPECT, 'input': False}]; out[8] = (qs, cs)
    qs, cs = mk(); c(cs, 'SIG-C07', 'esp-reset')['fix'] = {'readiness': 'READY'}; out[9] = (qs, cs)
    qs, cs = mk(); f = c(cs, 'SIG-T04')['basis']['facts']
    f[1] = {'node': 'D6.2', 'net_same_as': 'U6.35', 'means': 'D6 阳极接 U6 U0TXD'}
    f[2] = {'node': 'U6.34', 'net_same_as': 'D7.1', 'means': 'U6 U0RXD 接 D7 阴极'}; out[10] = (qs, cs)
    qs, cs = mk(); b = c(cs, 'SIG-C07', 'esp-reset')['basis']
    b['inputs']['vf']['max'] = 1.5; b['result']['min'] = 2.9; out[11] = (qs, cs)
    qs, cs = mk(); x = c(cs, 'SIG-C08', 'esp-reset')
    x['basis'] = {'kind': 'NUMERIC', 'criterion': {'limit': 0, 'unit': 'mA', 'direction': 'value_below_limit', 'clause': 'K-ASSUME'},
                  'calc': '(v5 - v_pin) / r18', 'inputs': {
                      'v5': {'min': 4.4, 'max': 5.25, 'unit': 'V', 'from': {'clause': 'K-RAIL'}},
                      'v_pin': {'min': 3.5, 'max': 3.7, 'unit': 'V', 'from': {'clause': 'K-ESP-IO'}},
                      'r18': {'value': 10, 'unit': 'kΩ', 'from': {'db': {'ref': 'R18', 'parse': 'resistance'}}}},
                  'result': {'min': 0.07, 'max': 0.175}}
    out[12] = (qs, cs)
    qs, cs = mk(); c(cs, 'SIG-C07', 'esp-reset')['severity']['level'] = 'P0'; out[13] = (qs, cs)
    qs, cs = mk(); c(cs, 'SIG-C08', 'esp-reset')['fix'] = copy.deepcopy(c(cs0, 'SIG-C07', 'esp-reset')['fix']); out[14] = (qs, cs)
    qs, cs = mk(); c(cs, 'SIG-C07', 'run')['missing']['from'] = 'REQUIREMENT'; out[15] = (qs, cs)
    # 16 a prefix dropped: the limit means mA but the criterion says A, the result is raw V/kΩ arithmetic
    qs, cs = mk(); c(cs, 'SIG-C08', 'run')['basis']['criterion']['unit'] = 'A'; out[16] = (qs, cs)
    # 17 a wrong formula whose stated result follows its own raw arithmetic (Ω/F is not a time)
    qs, cs = mk(); b = c(cs, 'SIG-C09')['basis']
    b['calc'] = '2.2 * r19 / c_node'; b['result'] = {'min': 0.44, 'max': 2.2}; out[17] = (qs, cs)
    # 18 an expression that turns inside the ranges: the corners agree, the middle does not
    qs, cs = mk(); b = c(cs, 'SIG-C09')['basis']
    b['calc'] = '2.2 * r19 * c_node * (2 - c_node / c_ref)'
    b['inputs']['c_ref'] = {'value': 30, 'unit': 'pF', 'from': {'clause': 'K-ASSUME'}}
    b['result'] = {'min': 2.2 * 10e3 * 10e-12 * (2 - 10 / 30) / 1e-9, 'max': 2.2 * 10e3 * 10e-12 * (2 - 10 / 30) / 1e-9}
    out[18] = (qs, cs)
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
         9: '不通过没有改法', 10: '事实结论与网表不符（交叉写反）',
         11: '有利角点会通过却判不通过', 12: '按审查者自定限值判不通过', 13: '等级高于后果类上限',
         14: '同一改法记成两个缺陷', 15: '没定的需求被评级',
         16: '单位前缀写错（mA 写成 A）', 17: '算式量纲不对', 18: '算式在范围内不单调'}
A_NOT_APPLICABLE = (16, 17, 18)   # arm A keeps no formula or units to check

def main():
    rr0, plan0 = load(W / 'a/review-results.json'), load(W / 'a/plan.json')
    qs0, cs0 = load(B / 'questions.json'), load(B / 'conclusions.json')
    base_a, base_b = run_a(rr0, plan0, 'base'), run_b(qs0, cs0, 'base')
    assert not base_a['errors'] and not base_a['derive_exit'], base_a
    assert not base_b['errors'], base_b
    res = []
    ai, bi = a_injections(rr0, plan0), b_injections(qs0, cs0)
    for n in range(1, 19):
        b = run_b(*bi[n], 'i%02d' % n)
        a = {'derive_errors': [], 'errors': base_a['errors'], 'derive_exit': None} if n in A_NOT_APPLICABLE else run_a(*ai[n], 'i%02d' % n)
        na = [e for e in a['derive_errors'] + a['errors'] if e not in base_a['errors']]
        nb = [e for e in b['errors'] if e not in base_b['errors']]
        res.append({'n': n, 'error': NAMES[n], 'A': {'caught': None if n in A_NOT_APPLICABLE else bool(na), 'by': na,
                                                     'derive_exit': a['derive_exit']},
                    'B': {'caught': bool(nb), 'by': nb}})
    dump(res, W / ('injections-%s.json' % B.name))
    for r in res:
        print('%2d %-22s A=%s B=%s' % (r['n'], r['error'], {True: 'Y', False: '-', None: 'n/a'}[r['A']['caught']],
                                       'Y' if r['B']['caught'] else '-'))
        for e in r['A']['by'][:2]: print('     A:', e[:200])
        for e in r['B']['by'][:2]: print('     B:', e[:200])
    print('A', sum(bool(r['A']['caught']) for r in res), 'B', sum(r['B']['caught'] for r in res))

main()
