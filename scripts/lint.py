#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AC0 Automated Check（自动检查）——机械、可穷举的规则全量扫描

用法:
    python3 lint.py db.json [--log netlist.log] [--json out.json]

**输出是疑似清单，不是判决。** 合法结构（Bob-Smith 终端、补偿网络、
DNP 选项、被删外设的引出脚、工具伪网络）由执行 agent 逐条排除。实践中命中
数百条而真问题为零是常态——AC0 的职责是保证"没漏看"，不是"看对了"。

驱动源自动识别
--------------
Rule-04/05 判断"电源轨有无驱动"时，以下**全部**算驱动源，漏掉任何一类
都会产生大批假"无驱动轨"：
  - 稳压器/DCDC/LDO 的输出脚（VOUT/SW/OUT）
  - 电感、磁珠、保险丝、二极管
  - **0R 跳线**（配置用的直连，最容易漏）
  - **模组自身输出的电源**（4G/WiFi 模组给出的 1.8V 电平参考等）
  - 连接器（外部供入）
"""
import argparse
import difflib
import io
import json
import re
import sys
from collections import defaultdict

GNDS = {'GND', 'PGND', 'AGND', 'DGND', 'EGND'}
RAIL_RE = re.compile(r'^(VCC|VDD|VDDA|VCCA|VOUT|VBAT|AVDD|DVDD|VIN|VBUS|V\d)', re.I)
OUTPIN_RE = re.compile(r'^(VOUT|SW|OUT|VO|LX|\+VO)', re.I)
EN_RE = re.compile(r'(^|_)(EN|ENABLE|SHDN|SHUTDOWN|PWREN)(_|\d|$)', re.I)
CLAMP_RE = re.compile(r'ZENER|TVS|BZT|SMBJ|SMAJ|SMCJ|MMSZ|1SMB|ESDA|PESD', re.I)
# EN 脚耐压绝大多数 <=6V；超过此值的上拉优先送 ER1 查 Abs Max（提示，非判定）
EN_PULL_ALERT_V = 6.0


def _volt(s):
    """从名字里推电压：3V3->3.3, 24V->24, 5.0V->5.0, V5P0->5.0；推不出返回 None"""
    if not s:
        return None
    u = s.upper()
    m = re.search(r'(\d{1,3})V(\d)(?![\dA-Z])', u)      # 3V3 / 24V0
    if m:
        return float(m.group(1)) + float(m.group(2)) / 10
    m = re.search(r'(\d{1,3}\.\d)V', u)                 # 5.0V
    if m:
        return float(m.group(1))
    m = re.search(r'(\d{1,3})V(?![\dA-Z])', u)           # 24V / _5V
    if m:
        return float(m.group(1))
    m = re.search(r'V(\d{1,2})P(\d)(?![\d])', u)        # V5P0
    if m:
        return float(m.group(1)) + float(m.group(2)) / 10
    return None


def clamp_volt(blob):
    """钳位器件的 Vz/Vrwm：先试 TVS 型号规则，再退回通用电压推断"""
    m = re.search(r'SM[ABCF]J(\d{1,3}(?:\.\d)?)', blob.upper())   # SMBJ5.0A
    if m:
        return float(m.group(1))
    return _volt(blob)


class Lint:
    def __init__(self, db, log_text='', intent=None):
        self.db = db
        self.intent = intent or {}
        self.nets = db['nets']
        self.parts = db['parts']
        self.pinname = db['pinname']
        self.pin2net = db['pin2net']
        self.page = db.get('ref2page', {})
        self.pseudo = set(db.get('pseudo_nets', []))
        self.log = log_text
        self.F = []
        self.skipped = []      # 未执行的规则及原因——绝不静默跳过
        self._ends_cache = {}

    # -- helpers ---------------------------------------------------------
    def ends(self, ref):
        if ref not in self._ends_cache:
            self._ends_cache[ref] = sorted(
                {v for k, v in self.pin2net.items() if k.startswith(ref + '.')})
        return self._ends_cache[ref]

    def refs_of(self, net):
        return {x.split('.')[0] for x in self.nets.get(net, [])}

    def add(self, rid, name, detail, ref=None, kind='FINDING'):
        """kind: FINDING=疑似缺陷，逐条排除；CANDIDATE=待 ER1 定夺的优先级清单"""
        self.F.append({'rule': rid, 'name': name, 'detail': detail, 'kind': kind,
                       'page': self.page.get(ref, 0) if ref else 0})

    def driven(self, net):
        """这条轨是否有驱动源（见模块 docstring 的五类）"""
        for x in self.nets.get(net, []):
            ref = x.split('.')[0]
            v = self.parts.get(ref, {})
            if v.get('nc'):
                continue
            head = re.match(r'[A-Za-z]+', ref)
            head = head.group() if head else ''
            if head in ('L', 'FB', 'F', 'D', 'J'):
                return True
            if head in ('U', 'M'):
                # 稳压器输出脚，或模组自身输出的电源脚
                if OUTPIN_RE.match(self.pinname.get(x, '')):
                    return True
                if re.match(r'^(VDD_EXT|VREG|VOUT)', self.pinname.get(x, ''), re.I):
                    return True
            if head == 'Q':
                return True
            if head == 'R' and str(v.get('value', '')).upper().startswith('0R'):
                return True   # 0R 跳线：最容易漏的一类驱动
        return False

    # -- rules -----------------------------------------------------------
    def run(self):
        nets, parts, pinname, pin2net = (
            self.nets, self.parts, self.pinname, self.pin2net)

        # Rule-01 单节点悬空网
        for n, nds in nets.items():
            if n in self.pseudo:
                continue
            if len(nds) == 1:
                ref = nds[0].split('.')[0]
                self.add('Rule-01', '单节点悬空网',
                         f'{n} <- {nds[0]} ({parts.get(ref, {}).get("value", "")})', ref)

        # Rule-02 双胞胎网络名（剔除同族总线/差分对/序号兄弟）
        names = sorted(nets)
        for a, b in zip(names, names[1:]):
            if a == b or difflib.SequenceMatcher(None, a, b).ratio() <= 0.90:
                continue
            if re.sub(r'\d+$', '', a) == re.sub(r'\d+$', '', b):
                continue          # 仅差末位序号 -> 同族
            if re.sub(r'_?[NP]$', '', a) == re.sub(r'_?[NP]$', '', b):
                continue          # 差分对
            if re.fullmatch(r'N\d{6,}', a) or re.fullmatch(r'N\d{6,}', b):
                continue
            self.add('Rule-02', '疑似网络名分裂',
                     f'{a}({len(nets[a])}节点) <-> {b}({len(nets[b])}节点)')

        # Rule-03 自动命名网仅含无源件
        for n, nds in nets.items():
            if not re.fullmatch(r'N\d{6,}', n):
                continue
            rs = self.refs_of(n)
            if not any(r[0] in 'UJMY' for r in rs):
                self.add('Rule-03', '自动命名网仅含无源件', f'{n}: {sorted(rs)}')

        # Rule-04 电源轨无驱动
        for n, nds in nets.items():
            if n in GNDS or n in self.pseudo or not RAIL_RE.match(n):
                continue
            if not self.driven(n):
                self.add('Rule-04', '电源轨疑似无驱动',
                         f'{n} ({len(nds)}节点): {sorted(self.refs_of(n))[:6]}')

        # Rule-05 电源球无驱动 / 无网络
        for node, pn in pinname.items():
            if not re.search(r'(VDD|VCC|AVDD|DVDD|VBAT)', pn, re.I):
                continue
            n = pin2net.get(node)
            ref = node.split('.')[0]
            if n is None:
                self.add('Rule-05', '电源球无网络', f'{node} ({pn})', ref)
            elif n not in self.pseudo and not self.driven(n):
                self.add('Rule-05', '电源球所在轨无驱动', f'{node} ({pn}) <- {n}', ref)

        # Rule-06 VSS 球未入地
        for node, pn in pinname.items():
            if re.match(r'^(VSS|AVSS|DVSS)', pn, re.I):
                n = pin2net.get(node)
                if n not in GNDS:
                    self.add('Rule-06', 'VSS 球未入地',
                             f'{node} ({pn}) <- {n}', node.split('.')[0])

        # Rule-10 ESD/TVS 挂残网
        for ref, v in parts.items():
            blob = (v.get('part', '') + ' ' + v.get('prim', '')).upper()
            if not re.search(r'ESD|TVS', blob):
                continue
            for node, n in ((k, x) for k, x in pin2net.items()
                            if k.startswith(ref + '.')):
                if n and n not in self.pseudo and len(nets.get(n, [])) < 2:
                    self.add('Rule-10', 'ESD/TVS 挂残网',
                             f'{ref} {node} -> {n} (仅{len(nets.get(n, []))}节点)', ref)

        # Rule-15 "NC" 网络 —— 必须先判别是真短路还是工具伪网络
        for n, nds in nets.items():
            if not re.fullmatch(r'NC[_\-\d]*', n, re.I) or len(nds) <= 1:
                continue
            if n in self.pseudo:
                self.add('Rule-15-INFO', '"NC" 为工具伪网络（非缺陷）',
                         f'{n}: {len(nds)} 个引脚。C_SIGNAL 为裸字面量、无层次路径 '
                         '-> PSTWRITER 的 No-Connect 汇集网，不构成电气短路')
            else:
                self.add('Rule-15', '"NC" 被当作网络名导致短接',
                         f'{n}: {len(nds)} 个引脚被电气短接（该网带层次路径，'
                         '系设计者所画，非工具伪网络）')

        # Rule-18 同基名多轨
        rails = defaultdict(list)
        for n in nets:
            m = re.match(r'((?:VCC|VDD|V)[A-Z0-9]*_?\d+V\d*)', n, re.I)
            if m:
                rails[m.group(1).upper()].append(n)
        for base, grp in rails.items():
            if len(grp) > 1:
                self.add('Rule-18', '同基名多轨（确认非张冠李戴）',
                         f'{base}: {sorted(grp)}')

        # Rule-17 假闭环线索：VALUE 字段异常（前导空白等）
        for ref, v in parts.items():
            val = v.get('value', '')
            if val != val.strip():
                self.add('Rule-17', 'VALUE 字段含首尾空白（影响 BOM 比对）',
                         f'{ref}: {val!r}', ref)

        # Rule-07 关键器件计数（冷跑·参数化：需第 0 步意图清单）
        expect = (self.intent or {}).get('expect') or {}
        if expect:
            for key, want in expect.items():
                got = sorted(r for r, v in parts.items() if not v.get('nc') and key.upper()
                             in (v.get('part', '') + ' ' + v.get('value', '') + ' '
                                 + v.get('prim', '')).upper())
                if len(got) != want:
                    self.add('Rule-07', '关键器件计数不符',
                             f'{key}: 意图 {want} 实为 {len(got)}'
                             + (f' {got}' if got else ''))
        else:
            self.skipped.append(('Rule-07', '关键器件计数', '未提供 --intent 意图清单'))

        # Rule-12 EN 极性/耐压 —— 冷跑只出候选，极性与耐压须 ER1 查 datasheet 定判
        for n, nds in nets.items():
            if n in self.pseudo or not EN_RE.search(n):
                continue
            pulls = []
            for x in nds:
                ref = x.split('.')[0]
                if not ref.startswith('R') or parts.get(ref, {}).get('nc'):
                    continue
                for other in self.ends(ref):
                    if other == n:
                        continue
                    if other in GNDS:
                        pulls.append(f'{ref} 下拉->{other}')
                    elif RAIL_RE.match(other) or _volt(other):
                        v = _volt(other)
                        pulls.append(f'{ref} 上拉->{other}'
                                     + (f'({v}V)' if v else '')
                                     + (' [优先]' if v and v >= EN_PULL_ALERT_V else ''))
            if pulls:
                self.add('Rule-12', 'EN 脚上拉/下拉待核（极性+Abs Max）',
                         f'{n}: {"; ".join(sorted(set(pulls)))}',
                         kind='CANDIDATE')

        # Rule-13 钳位器件直连电源（Vz 可从型号推出即冷跑定判，推不出转候选）
        for ref, v in parts.items():
            if v.get('nc'):
                continue
            blob = (v.get('part', '') + ' ' + v.get('value', '') + ' '
                    + v.get('prim', ''))
            if not CLAMP_RE.search(blob):
                continue
            ends = self.ends(ref)
            if len(ends) != 2 or not any(e in GNDS for e in ends):
                continue
            rail = [e for e in ends if e not in GNDS][0]
            vr = _volt(rail)
            if vr is None:
                continue                      # 轨电压未知，交 ER2 电源树处理
            vz = clamp_volt(blob)
            if vz is None:
                self.add('Rule-13', '钳位器件跨接电源轨（Vz 待查）',
                         f'{ref} ({blob.strip()}) 跨 {rail}({vr}V)-GND，'
                         f'型号推不出 Vz/Vrwm', ref, kind='CANDIDATE')
            elif vz < vr:
                self.add('Rule-13', '钳位器件 Vz 低于所跨电源轨',
                         f'{ref} ({blob.strip()}) Vz/Vrwm≈{vz}V < {rail} 的 {vr}V'
                         f' —— 上电即导通/烧毁', ref)

        # 导出日志：No_connect 被忽略 —— 免费证据，别丢
        if self.log:
            ig = re.findall(
                r'"No_connect" property on Pin "([^"]+)" ignored.*?net "([^"]+)"',
                self.log)
            for pin, net in ig:
                actual = pin2net.get(pin)
                tag = '' if actual == net else f'（网表实为 {actual}）'
                self.add('LOG-36038', 'No_connect 属性被忽略并强行连线',
                         f'{pin} -> {net}{tag}', pin.split('.')[0])
        return self.F


# 热跑项：判据来自 datasheet，冷跑阶段无法执行，须 ER1 完成后回补
HOT_RULES = [('Rule-08', '参数验算不符'), ('Rule-09', '必需上拉/串阻缺失'),
             ('Rule-14', '新增符号引脚映射'), ('Rule-16', 'strap 违反强制条款')]


def _table(by, keys):
    for k in keys:
        print(f'  {k[0]:12s} {by[k][0]["name"]:32s} {len(by[k]):5d} 条')


def main():
    ap = argparse.ArgumentParser(description='AC0 Automated Check（输出为疑似清单）')
    ap.add_argument('db', help='parse_netlist.py 产出的 db.json')
    ap.add_argument('--log', help='netlist.log（导出日志，含 No_connect 等免费证据）')
    ap.add_argument('--intent', help='第 0 步意图清单 JSON（Rule-07 关键器件计数所需）')
    ap.add_argument('--json', help='把完整命中写入 JSON')
    a = ap.parse_args()

    db = json.load(io.open(a.db, encoding='utf-8'))
    log = io.open(a.log, encoding='utf-8', errors='replace').read() if a.log else ''
    intent = json.load(io.open(a.intent, encoding='utf-8')) if a.intent else None

    lint = Lint(db, log, intent)
    F = lint.run()

    # 分组键含 kind——同一条规则可同时产出 FINDING 与 CANDIDATE（如 Rule-13）
    by = defaultdict(list)
    for f in F:
        by[(f['rule'], f['kind'])].append(f)
    # Rule-* 在前、其余（导出日志等）在后
    order = sorted(by, key=lambda k: (not k[0].startswith('Rule-'), k[0]))
    find = [k for k in order if k[1] == 'FINDING']
    cand = [k for k in order if k[1] == 'CANDIDATE']

    print('=== AC0 Automated Check 汇总（疑似清单，非判决）===')
    _table(by, find)
    n_find = sum(len(by[k]) for k in find)
    print(f'  {"合计":45s} {n_find:5d} 条')
    print('\n  逐条排除后才是发现项——由执行 agent 完成，排除依据须留痕。合法结构举例：'
          'Bob-Smith 终端、补偿网络、DNP 选项、\n  被删外设的 SoC 引出脚、工具伪网络。')

    if cand:
        print('\n=== CANDIDATE：待 ER1 定夺（决定优先读哪几份 datasheet）===')
        _table(by, cand)

    # 未执行的规则必须报出来——扫出 0 条与根本没扫，绝不能长得一样
    print('\n=== 本趟未执行（0 条 ≠ 通过）===')
    for rid, name, why in lint.skipped:
        print(f'  {rid:12s} {name:32s} {why}')
    for rid, name in HOT_RULES:
        print(f'  {rid:12s} {name:32s} 热跑项，须 ER1 完成 datasheet 核实后回补')

    if a.json:
        json.dump({'findings': F,
                   'skipped': [list(s) for s in lint.skipped],
                   'hot_pending': [list(h) for h in HOT_RULES]},
                  io.open(a.json, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print(f'\n  -> {a.json}')


if __name__ == '__main__':
    main()
