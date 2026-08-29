#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AC0 Automated Check（自动检查）——机械、可穷举的规则全量扫描

用法:
    python3 lint.py db.json [--log netlist.log] [--json out.json]

**输出是疑似清单，不是判决。** 合法结构（Bob-Smith 终端、补偿网络、
DNP 选项、被删外设的引出脚、工具伪网络）必须人工排除。实践中命中
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


class Lint:
    def __init__(self, db, log_text=''):
        self.db = db
        self.nets = db['nets']
        self.parts = db['parts']
        self.pinname = db['pinname']
        self.pin2net = db['pin2net']
        self.page = db.get('ref2page', {})
        self.pseudo = set(db.get('pseudo_nets', []))
        self.log = log_text
        self.F = []
        self._ends_cache = {}

    # -- helpers ---------------------------------------------------------
    def ends(self, ref):
        if ref not in self._ends_cache:
            self._ends_cache[ref] = sorted(
                {v for k, v in self.pin2net.items() if k.startswith(ref + '.')})
        return self._ends_cache[ref]

    def refs_of(self, net):
        return {x.split('.')[0] for x in self.nets.get(net, [])}

    def add(self, rid, name, detail, ref=None):
        self.F.append({'rule': rid, 'name': name, 'detail': detail,
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


def main():
    ap = argparse.ArgumentParser(description='AC0 Automated Check（输出为疑似清单）')
    ap.add_argument('db', help='parse_netlist.py 产出的 db.json')
    ap.add_argument('--log', help='netlist.log（导出日志，含 No_connect 等免费证据）')
    ap.add_argument('--json', help='把完整命中写入 JSON')
    a = ap.parse_args()

    db = json.load(io.open(a.db, encoding='utf-8'))
    log = io.open(a.log, encoding='utf-8', errors='replace').read() if a.log else ''
    F = Lint(db, log).run()

    by = defaultdict(list)
    for f in F:
        by[f['rule']].append(f)

    print('=== AC0 Automated Check 汇总（疑似清单，非判决）===')
    # Rule-* 在前、其余（导出日志等）在后
    for rid in sorted(by, key=lambda r: (not r.startswith('Rule-'), r)):
        print(f'  {rid:12s} {by[rid][0]["name"]:32s} {len(by[rid]):5d} 条')
    print(f'  {"合计":45s} {len(F):5d} 条')
    print('\n  逐条人工排除后才是发现项。合法结构举例：Bob-Smith 终端、补偿网络、'
          'DNP 选项、\n  被删外设的 SoC 引出脚、工具伪网络。')

    if a.json:
        json.dump(F, io.open(a.json, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print(f'\n  -> {a.json}')


if __name__ == '__main__':
    main()
