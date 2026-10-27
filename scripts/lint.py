#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动扫描（方式 A）——规则编号见 scripts/catalog.py

用法:
    python3 lint.py db.json [--log netlist.log] [--intent intent.json]
    python3 lint.py db.json --datasheet-audit datasheet-audit.json \
        [--merge-plan review-plan-cold.json] [--plan-json review-plan.json] [--json out.json]

第二趟带资料审计，按核实的器件类型重扫并合并成最终计划。E 规则的检查项由审查者按手册保证值判定。
**扫描输出是疑似清单，不是判决。** 合法结构（Bob-Smith 终端、补偿网络、
DNP 选项、被删外设的引出脚、工具伪网络）由执行 agent 逐条排除。
规则依赖命名和已知图结构；零命中不表示检查完整或电气通过。

电源追踪只把实际输出脚或已声明的外部供电节点当作来源候选。
电感/磁珠/保险丝/0R 是导通边；二极管和 MOS 需要对应状态的有向模型。
网表扫描路径和网络名均不是电压、载流能力或上电时序的 PASS 证据。
"""
import argparse
import board_scans
import catalog
import difflib
import io
import json
import os
import re
import requirement_parameters
import sys
from collections import defaultdict

from audit_datasheets import validate_datasheet_audit
from checkers import PowerTree, REGISTRY, REGISTRY_BY_ID
from checkers.powertree import declared_supply_nets
from checkers import netgraph as ng, passive_stress
import part_words as pw
import protective_clamps
from checkers.netgraph import NetGraph, rail_voltage as _volt
from part_words import CONNECTOR, FERRITE, IC, INDUCTOR, OPTO, PASSIVE_LINKS, TRANSFORMER, TVS, TWO_TERMINAL
from electrical_contract import db_fingerprint, load_json
import board_intent
from plan_review import build_review_plan, diagnostic_lines, validate_intent
from solve_dividers import parse_resistor

# 导出日志分级（英文与中文界面）：导出错误/中止、批注错误、其他告警。退出码 0 不等于没有告警。
EXPORT_ERROR_RE = re.compile(r'ERROR\s*\(|Aborting Netlisting|错误\s*[（(]|中止|已终止', re.I)
EXPORT_ANNOTATION_RE = re.compile(r'annotation error|not (?:fully )?annotated|批注错误|标注错误|未(?:完全)?标注', re.I)
EXPORT_WARNING_RE = re.compile(r'\b(?:warning|error)\b|警告|错误', re.I)
NO_CONNECT_IGNORED_RE = re.compile(r'"No_connect" property on Pin', re.I)
# kicad-cli on macOS always prints Fontconfig cache chatter; it is host font noise, not an export warning.
HOST_FONT_NOISE_RE = re.compile(r'^\s*Fontconfig (?:warning|error):', re.I)


def export_log_kind(line):
    if NO_CONNECT_IGNORED_RE.search(line) or HOST_FONT_NOISE_RE.match(line):
        return None  # DOC-A02 parses these separately; Fontconfig lines are skipped outright
    if EXPORT_ANNOTATION_RE.search(line):
        return 'CANDIDATE'
    if EXPORT_ERROR_RE.search(line):
        return 'FINDING'
    if EXPORT_WARNING_RE.search(line):
        return 'INFO'
    return None


def _fmt_v(value):
    return '无' if value is None else '%gV' % value


BOOTSTRAP_PIN_RE = re.compile(r'^(BOOT|BST|CBOOT|BTST|CB)\w*$', re.I)
STARTUP_PIN_RE = pw.STARTUP_PIN_RE
THERMAL_PAD_PIN_RE = re.compile(r'^(E?PAD\w*|EP|TAB|EXPOSED\w*|THERMAL\w*)$', re.I)
NEGATIVE_SUPPLY_PIN_RE = re.compile(r'^(-\w+|\w+-|V-|VEE|VNEG|V_?NEG|VSS\w*|V_?MINUS|\w+[_-](NEG|RTN|RET|MINUS)|COM|0V)$', re.I)
SUPPLY_PIN_RE = re.compile(r'^(VDD|VCC|AVDD|DVDD|VBAT|VDDA|VDDIO|VCCA|VCCIO)\w*$'
                           r'(?<![_-]DET)(?<![_-]SENSE)(?<![_-]SNS)(?<![_-]EN)(?<![_-]PG)(?<![_-]MON)', re.I)
RAIL_RE = ng.RAIL_RE   # one rail-name test: excludes _FB/_SENSE lines and _N/_RTN returns
OUTPIN_RE = re.compile(r'^(VOUT|SW|OUT|VO|LX|\+VO)', re.I)
EN_RE = re.compile(r'(^|_)(EN|ENABLE|SHDN|SHUTDOWN|PWREN)(_|\d|$)', re.I)
# EN 脚耐压绝大多数 <=6V；超过此值的上拉优先查 Abs Max（提示，非判定）
EN_PULL_ALERT_V = 6.0
KICAD_UNCONNECTED_RE = re.compile(r'^unconnected-\(', re.I)
DATASHEET_NC_PIN_RE = re.compile(r'^(N\.?C\.?|DNC|NIC|RSVD|RESERVED)(?:$|[_\-\d])', re.I)
BIDIR_PINTYPES = {'BI', 'BIDI', 'BIDIR', 'BIDIRECTIONAL', 'IO', 'I/O', 'TRISTATE', '3STATE'}
KICAD_AUTO_NET_RE = re.compile(r'(^|/)(Net|unconnected)-\(')   # 工具按引脚生成的网名，不是手写拼写
NET_TIE_RE = re.compile(r'NET_?TIE', re.I)
ISOLATOR_RE = re.compile(r'ISOLAT|\bISO\d|ISOW|ADUM|SI8[46]\d|NSI\d|CA-IS|隔离', re.I)


# NET-A02：命名惯例里成对/成组出现的网名不是拼写分裂。
NET_PAIR_TOKENS = [frozenset(p) for p in (
    ('RX', 'TX'), ('RXD', 'TXD'), ('RXP', 'TXP'), ('RXN', 'TXN'), ('MISO', 'MOSI'),
    ('SDI', 'SDO'), ('DIN', 'DOUT'), ('SCL', 'SDA'), ('SCLK', 'SDATA'), ('CANH', 'CANL'),
    # one transistor's terminals (VLDO_EN_G / VLDO_EN_S on a load switch, typical circuits 2026-10-26)
    ('G', 'S'), ('G', 'D'), ('D', 'S'), ('B', 'E'), ('B', 'C'), ('C', 'E'))]
NET_VOLTAGE_TOKEN_RE = re.compile(r'^(\d+V\d*|V\d+|\d+\.\d+V)$', re.I)


def _token_difference(a, b):
    """两名按分隔符切词后只差一个词时返回该词对，否则 None。"""
    ta, tb = re.split(r'[^A-Za-z0-9+-]+', a), re.split(r'[^A-Za-z0-9+-]+', b)
    if len(ta) != len(tb):
        return None
    diff = [(x, y) for x, y in zip(ta, tb) if x != y]
    return diff[0] if len(diff) == 1 else None


def net_name_split(a, b):
    """相邻排序的两张网是否疑似同一名字的拼写分裂。

    只比较叶名（层次路径是同页所有网共享的，不构成相似证据）；豁免末位序号、_N/_P 与 +/- 差分对、
    只差一个字母且字母相邻的兄弟（GHA/GHB、AUX1_A/AUX1_B）、收发对（RX/TX、MISO/MOSI、SCL/SDA）、
    同一只晶体管的端子（EN_G/EN_S、Q1_B/Q1_E）和同名双路（FB_12V/FB_5V）。
    """
    la, lb = a.rsplit('/', 1)[-1], b.rsplit('/', 1)[-1]
    if la == lb or difflib.SequenceMatcher(None, la, lb).ratio() <= 0.90:
        return False
    if re.sub(r'\d+$', '', la) == re.sub(r'\d+$', '', lb):
        return False          # 仅差末位序号 -> 同族
    if re.sub(r'(_?[NP]|[+-])$', '', la) == re.sub(r'(_?[NP]|[+-])$', '', lb):
        return False          # 差分对
    if len(la) == len(lb):
        diff = [(x, y) for x, y in zip(la, lb) if x != y]
        if len(diff) == 1 and (all(c.isdigit() for c in diff[0]) or (
                all(c.isalpha() for c in diff[0])
                and abs(ord(diff[0][0].upper()) - ord(diff[0][1].upper())) == 1)):
            return False      # 序号/字母序兄弟（AUX1_X/AUX2_X、GHA/GHB）
    pair = _token_difference(la, lb)
    if pair and (frozenset(t.upper() for t in pair) in NET_PAIR_TOKENS
                 or all(NET_VOLTAGE_TOKEN_RE.match(t) for t in pair)):
        return False          # 收发对 / 同名双路
    if _embedded_pair(la, lb):
        return False          # 收发对写在一个词里（PRI_DCAN1RX / PRI_DCAN1TX）
    return True


def _embedded_pair(a, b):
    """One name becomes the other by swapping a multi-letter pair token inside a word (DCAN1RX -> DCAN1TX)."""
    ua, ub = a.upper(), b.upper()
    for pair in NET_PAIR_TOKENS:
        for x in pair:
            y = next(iter(pair - {x}))
            if len(x) < 2 or len(y) < 2:
                continue
            start = ua.find(x)
            while start != -1:
                if ua[:start] + y + ua[start + len(x):] == ub:
                    return True
                start = ua.find(x, start + 1)
    return False


def _ground_like(net):
    """网名含地记号（GND、GNDA、AGND、PGND_ISO、Net-(U1-GND)、VSS…），只作孤岛扫描的候选范围。"""
    return any(ng.is_ground(t) for t in re.split(r'[^A-Z0-9]+', str(net).upper()) if t)


BRIDGED_JUMPER_RE = re.compile(r'SolderJumper_(\d)_Bridged(\d*)')


def pin_name_tokens(name):
    """Names a symbol pin answers to: the whole name and each '/'-separated alternate function,
    with KiCad's active-low overbar ~{...} removed. 'IO2/GPIO2/ADC1_CH2' answers to IO2."""
    text = re.sub(r'~\{([^}]*)\}', r'\1', str(name)).strip().upper()
    return {text} | {part.strip() for part in text.split('/') if part.strip()}


def _pin_class(value):
    value = str(value or '').strip().upper()
    if value in {'OUT', 'OUTPUT', 'TRISTATE', '3STATE'}:
        return 'OUT'
    if value in {'IN', 'INPUT'}:
        return 'IN'
    if value in {'BI', 'BIDI', 'BIDIR', 'BIDIRECTIONAL', 'IO', 'I/O'}:
        return 'BIDI'
    if value in {'GROUND', 'GND'}:
        return 'GROUND'
    if value in {'POWER', 'PWR'}:
        return 'POWER'
    return value or 'UNSPEC'



clamp_volt = ng.clamp_voltage   # 钳位器件的 Vz/Vrwm：先试 TVS 型号规则，再退回通用电压推断


class Lint:
    def __init__(self, db, log_text=None, intent=None, datasheet_audit=None):
        self.db = db
        self.db_sha256 = db_fingerprint(db)
        self.datasheet_audit = datasheet_audit
        self.intent = requirement_parameters.resolve(intent or {})
        self.nets = db['nets']
        self.parts = db['parts']
        self.pinname = db['pinname']
        self.pin2net = db['pin2net']
        self.pintype = db.get('pintype', {})
        self.page = db.get('ref2page', {})
        self.pseudo = set(db.get('pseudo_nets', []))
        self.log = log_text
        self.F = []
        self.skipped = []      # 未执行的规则及原因——绝不静默跳过
        self._ends_cache = {}
        analysis = board_intent.with_verified_kinds(self.intent, datasheet_audit)   # datasheet-verified kinds
        analysis_db = board_intent.graph_db(db, analysis)
        self.graph = NetGraph(analysis_db)
        self.powertree = PowerTree(self.graph, self.intent)
        self.inventories = {checker.id: checker.build(analysis_db, analysis) for checker in REGISTRY}

    # -- helpers ---------------------------------------------------------
    def ends(self, ref):
        if ref not in self._ends_cache:
            self._ends_cache[ref] = sorted(
                {v for k, v in self.pin2net.items() if k.startswith(ref + '.')})
        return self._ends_cache[ref]

    def refs_of(self, net):
        return {x.split('.')[0] for x in self.nets.get(net, [])}

    def resistor_links(self, net):
        links = []
        seen = set()
        for node in self.nets.get(net, []):
            ref = node.split('.')[0]
            if not ref.startswith('R') or ref in seen:
                continue
            seen.add(ref)
            part = self.parts.get(ref, {})
            if part.get('nc'):
                continue
            ends = self.ends(ref)
            if len(ends) != 2 or net not in ends:
                continue
            parsed = parse_resistor(part.get('value'))
            other = ends[0] if ends[1] == net else ends[1]
            link = {
                'ref': ref,
                'other': other,
                'ohm': parsed['kohm'] * 1000.0 if parsed else None,
                'tol': parsed['tol'] if parsed else None,
            }
            far, via = self.bridged_jumper_peer(other)
            if far:
                link.update(other=far, via=via)
            links.append(link)
        return links

    def bridged_jumper_peer(self, net):
        """The net a factory-closed solder jumper ties `net` to. KiCad's Jumper:SolderJumper_2_Bridged,
        _3_Bridged12 and _3_Bridged123 ship with the named pads joined by copper, so a pull-up drawn
        through one is present unless someone cuts it. Returns (net, jumper ref) or (None, None)."""
        peers = set()
        for node in self.nets.get(net, []):
            ref, pad = node.split('.', 1)
            match = BRIDGED_JUMPER_RE.search(str(self.parts.get(ref, {}).get('prim') or ''))
            if not match:
                continue
            joined = match.group(2) or '12'
            if pad not in joined:
                continue
            peers |= {(self.pin2net.get('%s.%s' % (ref, other)), ref) for other in joined if other != pad}
        peers = {(n, r) for n, r in peers if n and n != net}
        if len(peers) > 1:
            # A three-pad Bridged123 also joins the other pull-up's top; the rail is the one that counts.
            peers = {(n, r) for n, r in peers if RAIL_RE.match(n) or ng.is_ground(n)}
        return next(iter(peers)) if len(peers) == 1 else (None, None)

    def pulls(self, net):
        pulls = []
        for link in self.resistor_links(net):
            other = link['other']
            if ng.is_ground(other):
                pulls.append(dict(link, state='low', voltage=0.0))
            elif RAIL_RE.match(other) or _volt(other) is not None:
                pulls.append(dict(link, state='high', voltage=_volt(other)))
        return pulls

    def add(self, rid, name, detail, ref=None, kind='FINDING', **extra):
        """kind: FINDING=疑似缺陷，逐条排除；CANDIDATE=待资料取证定夺的优先级清单；INFO=提示，不计入疑点"""
        item = {'rule': rid, 'name': name, 'detail': detail, 'kind': kind,
                'page': self.page.get(ref, 0) if ref else 0}
        if ref:
            item['ref'] = ref
        item.update(extra)
        self.F.append(item)

    def power_path(self, net):
        """Return a source-to-load candidate path, never a rail signoff."""
        return self.powertree.source_of(net)

    def driven(self, net):
        return self.power_path(net) is not None

    def _external_entry(self, net):
        """Off-board contacts (connector or battery) that feed the net, directly or through
        fuses, diodes, switches, protection MOSFETs or supply-filter resistors."""
        if not hasattr(self, '_feed_tree'):
            self._feed_tree = PowerTree(self.graph, self.intent, feed=True)
        found = self._feed_tree.source_of(net)
        if not found:
            return []
        if found['basis'].startswith('off-board'):
            return [found['source']] + found['path']
        return ['via:' + found['source']]

    def _protected_pins_text(self, net, clamp=None):
        """The IC pins the clamp protects: on the clamp's own net (no series impedance between them) or one resistor away
        (R7 acceptance 2026-10-25, user: B3 a — the clamp voltage is compared with these pins' absolute maximum); and
        the other parts on the net, each against its own rating (2026-10-26, user: 按方案 B 改 — the lowest limit on the
        net decides, so no reviewer picks one capacitor or switch and leaves the rest)."""
        direct, behind, others = [], [], set()
        for node in self.graph.nodes_on(net):
            ref = node.partition('.')[0]
            kind = self.graph.kind(ref)
            if (ref != clamp and self.graph.is_fitted(ref)
                    and kind not in (IC, pw.RESISTOR, CONNECTOR, pw.TESTPOINT, pw.ZENER, TVS)):   # clamps protect, not protected
                others.add(ref)
            if self.graph.kind(ref) == IC and self.graph.is_fitted(ref):
                direct.append(f'{node}({self.graph.pinname.get(node) or "?"})')
            elif self.graph.kind(ref) == pw.RESISTOR and len(self.graph.nets_of(ref)) == 2 and net in self.graph.nets_of(ref):
                other = next(n for n in self.graph.nets_of(ref) if n != net)
                for far in self.graph.nodes_on(other):
                    if self.graph.kind(far.partition('.')[0]) == IC and self.graph.is_fitted(far.partition('.')[0]):
                        behind.append(f'{far}({self.graph.pinname.get(far) or "?"}) 经 {ref}')
        rest = f'同网其他器件 {"、".join(sorted(others))} 各按自身耐压比较；' if others else ''
        if direct:
            return f'同网 IC 脚 {"、".join(sorted(direct))} 直接并在钳位上（无串联阻抗，钳位电压对脚绝限比较）；' + rest
        if behind:
            return f'IC 脚 {"、".join(sorted(behind))}（有串联阻抗，可按注入电流核）；' + rest
        return '同网没有 IC 脚；' + rest

    def _resistor_fed(self, net):
        """A two-terminal resistor on the net whose other end is driven or fed from off board (R6 acceptance
        2026-10-24: a controller's HV pin fed from the rectified bus through its start-up resistor)."""
        for node in self.graph.nodes_on(net):
            ref = node.partition('.')[0]
            ends = self.graph.nets_of(ref)
            if self.graph.kind(ref) != pw.RESISTOR or len(ends) != 2 or net not in ends:
                continue
            other = ends[0] if ends[1] == net else ends[1]
            if self.driven(other) or self._external_entry(other):
                return True
        return False

    def _local_regulator_node(self, node, net):
        """A supply pin whose net holds only its own IC's pins and capacitors (VDDCR, VCAP):
        the IC's internal regulator output, not an undriven rail."""
        ref = node.partition('.')[0]
        others = [n for n in self.graph.nodes_on(net) if n.partition('.')[0] != ref]
        return bool(others) and all(self.graph.kind(n.partition('.')[0]) == pw.CAPACITOR for n in others)

    # -- rules -----------------------------------------------------------
    def _relay_nc_contact(self, net, nodes):
        """NC can name a normally-closed contact, without proving its ratings."""
        relay_seen = False
        for node in nodes:
            ref = node.partition('.')[0]
            if not self.graph.is_fitted(ref):
                return False
            if self.graph.basis(ref) not in {'datasheet', 'part-keyword'}:
                return False
            kind = self.graph.kind(ref)
            if kind == 'connector':
                continue
            # Contact roles come from pin names; a symbol without pin names may carry them in its
            # three distinct net names (COM/NC/NO), as hand-drawn relay libraries do.
            unnamed = not any(str(self.pinname.get(ref + '.' + p, '')).strip() for p in self.graph.pins_of(ref))

            def contact(pin_node, pin_net):
                name = str(self.pinname.get(pin_node, '')).strip().upper()
                if name or not unnamed:
                    return name
                return str(pin_net).rsplit('/', 1)[-1].strip().upper()
            if kind != 'relay' or contact(node, net) != 'NC':
                return False
            roles = defaultdict(list)
            for pin, pin_net in self.graph.pins_of(ref).items():
                name = contact(ref + '.' + pin, pin_net)
                if name in {'NC', 'COM', 'NO'}:
                    roles[name].append(pin_net)
            if any(len(roles[name]) != 1 for name in ('NC', 'COM', 'NO')):
                return False
            contact_nets = [roles[name][0] for name in ('NC', 'COM', 'NO')]
            if (contact_nets[0] != net or len(set(contact_nets)) != 3
                    or any(not n or n in self.pseudo for n in contact_nets)):
                return False
            relay_seen = True
        return relay_seen

    def _ground_islands(self):
        """PWR-A03 地名网孤岛：IC 地脚所在的地名网经已装配的直流连接件到不了主地（节点最多的地名网组）。

        直流连接件：电阻/电感/磁珠/跳线/保险（可经至多两个只有两节点的中间网串联）、NetTie、多绕组电感/共模扼流；
        电容不算。孤岛上有连接器（外部回流）、已知隔离器件（光耦、变压器、隔离器）或地名含 SENSE/SNS/KELVIN
        的遥测线时不报。其他多端器件同时挂在孤岛和主地上（如同一颗 IC 的 AGND 在孤岛、PGND 在主地）
        降为候选：须按手册确认片内是否连通、外部是否必须连接。疑点按图面与手册排除。"""
        g = self.graph
        grounds = sorted(n for n in self.nets if n not in self.pseudo and _ground_like(n))
        if len(grounds) < 2:
            return
        parent = {n: n for n in grounds}

        def root(n):
            while parent[n] != n:
                parent[n] = parent[parent[n]]
                n = parent[n]
            return n

        def join(a, b):
            parent[root(a)] = root(b)

        def blob(ref):
            part = self.parts.get(ref, {})
            return ' '.join(str(part.get(k, '')) for k in ('part', 'value', 'prim'))
        for n in grounds:
            frontier, seen = [(n, 0)], {n}
            while frontier:
                net, hops = frontier.pop()
                for _, other in g.neighbors(net, kinds=PASSIVE_LINKS):
                    if other in seen:
                        continue
                    seen.add(other)
                    if other in parent:
                        join(n, other)
                    elif hops < 2 and len(self.nets.get(other, [])) == 2:
                        frontier.append((other, hops + 1))
        for ref in sorted(self.parts):
            if not g.is_fitted(ref):
                continue
            if NET_TIE_RE.search(blob(ref)) or (g.kind(ref) in (INDUCTOR, FERRITE) and len(g.nets_of(ref)) > 2):
                tied = [n for n in g.nets_of(ref) if n in parent]
                for other in tied[1:]:
                    join(tied[0], other)
        groups = defaultdict(set)
        for n in grounds:
            groups[root(n)].add(n)
        main = max(groups.values(), key=lambda nets: (sum(len(self.nets[n]) for n in nets), sorted(nets)))
        main_refs = {ref for n in main for ref in g.refs_on(n)}

        def is_ic(ref):
            return g.kind(ref) == IC or bool(re.match(r'^(IC|A)\d', ref))

        def ground_pin(node):
            return _ground_like(self.pinname.get(node, '')) or _pin_class(self.pintype.get(node)) == 'GROUND'
        for island in sorted(groups.values(), key=sorted):
            if island is main:
                continue
            nodes = sorted(x for n in island for x in self.nets[n])
            refs = {ref for n in island for ref in g.refs_on(n)}
            pins = [x for x in nodes if x.split('.')[0] in refs and is_ic(x.split('.')[0]) and ground_pin(x)]
            words = {t for x in list(island) + [self.pinname.get(x, '') for x in pins]
                     for t in re.split(r'[^A-Z0-9]+', str(x).upper())}
            cross = sorted(ref for ref in refs & main_refs if g.kind(ref) not in TWO_TERMINAL)
            isolators = [ref for ref in refs
                         if g.kind(ref) in (OPTO, TRANSFORMER) or ISOLATOR_RE.search(blob(ref))]
            if (not pins or isolators or words & {'SENSE', 'SNS', 'KELVIN'}
                    or any(g.kind(ref) == CONNECTOR for ref in refs)):
                continue
            detail = (f'{"/".join(sorted(island))} {nodes[:8]} 经已装配直流连接件到不了主地 '
                      f'{"/".join(sorted(main))}；孤岛上 IC 地脚 {pins[:6]}，无连接器、无已知隔离器件')
            if cross:
                self.add('PWR-A03', '地名网孤岛（经多端器件跨接，待核片内连通）',
                         detail + f'；{cross} 另有脚在主地，按手册核片内是否连通、外部是否必须相连',
                         pins[0].split('.')[0], kind='CANDIDATE')
            else:
                self.add('PWR-A03', '地名网孤岛（IC 地脚到不了主地）', detail, pins[0].split('.')[0])

    def run(self):
        nets, parts, pinname, pin2net = (
            self.nets, self.parts, self.pinname, self.pin2net)

        # NET-A01 单节点悬空网
        for n, nds in nets.items():
            if n in self.pseudo:
                continue
            if len(nds) == 1:
                ref = nds[0].split('.')[0]
                if KICAD_UNCONNECTED_RE.match(n):
                    # KiCad names a pin left open without an NC flag; datasheet NC/DNC pins are meant to be open.
                    if DATASHEET_NC_PIN_RE.match(pinname.get(nds[0], '')):
                        continue
                    self.add('NET-A01', '单节点悬空网',
                             f'{n} <- {nds[0]} ({parts.get(ref, {}).get("value", "")}，脚名 {pinname.get(nds[0], "?")}) '
                             '未连接且没有 NC 标记：确认有意悬空（未用输出、连接器备用脚）后补 NC 标记，'
                             '输入脚另按 NET-A07 核', ref, kind='CANDIDATE')
                    continue
                detail = f'{n} <- {nds[0]} ({parts.get(ref, {}).get("value", "")})'
                if (self.graph.kind(ref) == IC
                        and pw.normalize(self.pintype.get(nds[0])) in BIDIR_PINTYPES):
                    # 2026-10-20 第 1 轮裁决：双向（兼 GPIO）脚只挂一个标签多是未用的调制解调/GPIO 线，
                    # 不是标签分裂；输入、输出与电源脚仍按 FINDING 报。
                    self.add('NET-A01', '单节点悬空网',
                             detail + '：双向脚只挂标签，未用的调制解调/GPIO 线常见；确认有意不用后补 NC 或接出',
                             ref, kind='CANDIDATE')
                    continue
                self.add('NET-A01', '单节点悬空网', detail, ref)

        # NET-A02 疑似网络名分裂（剔除同族总线/差分对/序号兄弟/收发对/同名双路）
        names = sorted(nets)
        for a, b in zip(names, names[1:]):
            if a == b or not net_name_split(a, b):
                continue
            if re.fullmatch(r'N\d{6,}', a) or re.fullmatch(r'N\d{6,}', b):
                continue
            if KICAD_AUTO_NET_RE.search(a) or KICAD_AUTO_NET_RE.search(b):
                continue
            self.add('NET-A02', '疑似网络名分裂',
                     f'{a}({len(nets[a])}节点) <-> {b}({len(nets[b])}节点)')

        # NET-A03 自动命名网仅含无源件
        for n, nds in nets.items():
            if not re.fullmatch(r'N\d{6,}', n):
                continue
            rs = self.refs_of(n)
            if not any(r[0] in 'UJMY' for r in rs):
                self.add('NET-A03', '自动命名网仅含无源件', f'{n}: {sorted(rs)}')

        # PWR-A01 电源轨无驱动；只经连接器触点进板的轨是外部供电，记候选而不是疑似缺陷
        # intent.power_rails 声明的轨不论名字都扫；PWR_FLAG 不是来源。
        declared_rails = declared_supply_nets(self.graph, self.intent)
        for n, nds in nets.items():
            if ng.is_ground(n) or n in self.pseudo or not (RAIL_RE.match(n) or n in declared_rails):
                continue
            if not self.driven(n):
                entry = self._external_entry(n)
                if entry and entry[0].startswith('via:'):
                    continue   # fed from a driven rail through a filter resistor, switch or protection FET
                if entry:
                    self.add('PWR-A01', '电源轨只经连接器进板',
                             f'{n}: 板上无来源，经 {entry[:4]} 由外部供电；输入保护按 PRO 规则另核', kind='INFO')
                else:
                    self.add('PWR-A01', '电源轨疑似无驱动',
                             f'{n} ({len(nds)}节点): {sorted(self.refs_of(n))[:6]}')

        # PWR-A02 电源脚无驱动 / 无网络：器件自己的供电脚（原生 power_in 或供电脚名），连接器触点不算
        native = self.db.get('native_pintype') or {}
        for node in sorted(set(pinname) | {k for k, t in native.items() if t == 'power_in'}):
            pn = pinname.get(node, '')
            ref = node.split('.')[0]
            if self.graph.kind(ref) in (CONNECTOR, pw.TESTPOINT):
                continue
            if not (SUPPLY_PIN_RE.match(pn) or native.get(node) == 'power_in') or BOOTSTRAP_PIN_RE.match(pn):
                continue
            n = pin2net.get(node)
            if n is None:
                self.add('PWR-A02', '电源球无网络', f'{node} ({pn})', ref)
            elif (ng.is_ground(n) and native.get(node) == 'power_in' and pn
                  and not _ground_like(plain := re.sub(r'[{}]|_(?=\{)', '', pn))
                  and not NEGATIVE_SUPPLY_PIN_RE.match(plain) and not THERMAL_PAD_PIN_RE.match(plain)):
                # VIPer22A VDD tied to the source ground: the device's own supply pin is shorted to its return.
                # Other power_in names (REGIN of an unused internal LDO) may be grounded by the datasheet.
                supply = bool(SUPPLY_PIN_RE.match(plain) or re.match(r'^V', plain, re.I))
                if not supply and not re.search(r'IN|REG|PWR|SUPPLY|BAT|BUS', plain, re.I):
                    continue   # opaque pin names (TC78H660 "A") carry no supply claim to check
                self.add('PWR-A02', '电源脚落在地网',
                         f'{node} ({pn}，原生 power_in) <- {n}：供电脚直接接地，'
                         + ('器件无供电或供电被短路' if supply else '按手册确认该脚允许接地（如未用的内部 LDO 输入）'),
                         ref, kind='FINDING' if supply else 'CANDIDATE')
            elif (n not in self.pseudo and not ng.is_ground(n) and not self.driven(n)
                  and not self._local_regulator_node(node, n)):
                if _ground_like(pn) or THERMAL_PAD_PIN_RE.match(pn or ''):
                    continue   # a return pin (GND, EP) on a return net that is not named as ground: not a supply
                entry = self._external_entry(n)
                jumpers = [r for r in self._feed_tree.source_of(n)['path']
                           if self.graph.kind(r) == pw.JUMPER] if entry else []
                if jumpers:
                    self.add('PWR-A02', '电源脚经跳线供电',
                             f'{node} ({pn}) <- {n}：经跳线 {"、".join(jumpers)} 才接到供电，核该装配下跳线是否闭合',
                             ref, kind='CANDIDATE')
                elif not entry and not (STARTUP_PIN_RE.match(pn or '') and self._resistor_fed(n)):
                    # a high-voltage start-up pin is fed through its start-up resistor by design, whatever its value
                    self.add('PWR-A02', '电源球所在轨无驱动', f'{node} ({pn}) <- {n}', ref)

        # PWR-A03 地脚未入地
        for node, pn in pinname.items():
            if re.match(r'^(VSS|AVSS|DVSS)', pn, re.I):
                n = pin2net.get(node)
                if not ng.is_ground(n):
                    self.add('PWR-A03', 'VSS 球未入地',
                             f'{node} ({pn}) <- {n}', node.split('.')[0])
        self._ground_islands()

        # NET-A06 引脚类型冲突（PINUSE/ERC）：只自动定判无歧义冲突；输入-only 作为候选
        if not self.pintype:
            self.skipped.append(
                ('NET-A06', catalog.title('NET-A06'), '网表未提供 pintype'))
        else:
            coverage = len(self.pintype) / max(len(self.pin2net), 1)
            if coverage < 1.0:
                self.skipped.append((
                    'NET-A06', catalog.title('NET-A06'),
                    f'仅部分执行：pintype 覆盖 {len(self.pintype)}/'
                    f'{len(self.pin2net)} = {coverage:.1%}'))
            for net, nodes in nets.items():
                if net in self.pseudo:
                    continue
                typed = [(node, _pin_class(self.pintype.get(node)))
                         for node in nodes if node in self.pintype]
                outputs = [node for node, kind in typed if kind == 'OUT']
                if len(outputs) > 1:
                    self.add(
                        'NET-A06', '多个输出引脚直连',
                        f'{net}: {outputs}；开漏/三态等合法结构须逐条排除')
                if nodes and len(typed) == len(nodes) and typed and all(
                        kind == 'IN' for _, kind in typed) and not any(
                        self.graph.kind(node.partition('.')[0]) in {CONNECTOR} | PASSIVE_LINKS
                        or DATASHEET_NC_PIN_RE.match(self.pinname.get(node, '')) for node in nodes):
                    # A connector contact typed input (some header libraries) is driven off-board; a series
                    # resistor, inductor or ferrite typed input (an RF choke feeding a PA's VCC) passes the other net.
                    self.add(
                        'NET-A06', '网络仅含输入引脚（确认外部源/漏驱动）',
                        f'{net}: {[node for node, _ in typed]}',
                        kind='CANDIDATE')
                for node, kind in typed:
                    if kind == 'GROUND' and not ng.is_ground(net):
                        self.add(
                            'NET-A06', 'GROUND 类型引脚未接已知地网',
                            f'{node} -> {net}', node.split('.')[0],
                            kind='CANDIDATE')

        # PRO-A01 ESD/TVS 挂残网
        for ref, v in parts.items():
            blob = (v.get('part', '') + ' ' + v.get('prim', '')).upper()
            if not re.search(r'ESD|TVS', blob) and self.graph.kind(ref) != TVS:
                continue
            for node, n in ((k, x) for k, x in pin2net.items()
                            if k.startswith(ref + '.')):
                if n and n not in self.pseudo and len(nets.get(n, [])) < 2:
                    self.add('PRO-A01', 'ESD/TVS 挂残网',
                             f'{ref} {node} -> {n} (仅{len(nets.get(n, []))}节点)', ref)

        # NET-A04 "NC" 网络 —— 先判别是真短路还是工具伪网络；伪网络只作提示
        for n, nds in nets.items():
            if not re.fullmatch(r'NC[_\-\d]*', n, re.I) or len(nds) <= 1:
                continue
            if n in self.pseudo:
                self.add('NET-A04', '"NC" 为工具伪网络（提示，非缺陷）',
                         f'{n}: {len(nds)} 个引脚。C_SIGNAL 为裸字面量、无层次路径 '
                         '-> PSTWRITER 的 No-Connect 汇集网，不构成电气短路', kind='INFO')
            elif self._relay_nc_contact(n, nds):
                continue
            else:
                self.add('NET-A04', '"NC" 被当作网络名导致短接',
                         f'{n}: {len(nds)} 个引脚被电气短接（该网带层次路径，'
                         '系设计者所画，非工具伪网络）')

        # PWR-A04 同基名多轨
        rails = defaultdict(list)
        for n in nets:
            m = re.match(r'((?:VCC|VDD|V)[A-Z0-9]*_?\d+V\d*)', n, re.I)
            if m:
                rails[m.group(1).upper()].append(n)
        for base, grp in rails.items():
            if len(grp) > 1:
                self.add('PWR-A04', '同基名多轨（确认非张冠李戴）',
                         f'{base}: {sorted(grp)}')

        # DOC-A03 BOM/库字段卫生；REQ-H01 改版闭环由 diff_netlists.py 负责
        for ref, v in parts.items():
            for field in ('part', 'value', 'jedec', 'prim'):
                value = v.get(field, '')
                if isinstance(value, str) and value != value.strip():
                    self.add(
                        'DOC-A03', 'BOM/库字段含首尾空白（影响比对）',
                        f'{ref}.{field}: {value!r}', ref)

        # REQ-A01 关键器件计数（网表扫描·参数化：需 1.1 的意图清单）
        expect = (self.intent or {}).get('expect') or {}
        if expect:
            for key, want in expect.items():
                got = sorted(r for r, v in parts.items() if not v.get('nc') and key.upper()
                             in (v.get('part', '') + ' ' + v.get('value', '') + ' '
                                 + v.get('prim', '')).upper())
                if len(got) != want:
                    self.add('REQ-A01', '关键器件计数不符',
                             f'{key}: 意图 {want} 实为 {len(got)}'
                             + (f' {got}' if got else ''))
        else:
            self.skipped.append(('REQ-A01', catalog.title('REQ-A01'), '意图中缺少器件计数目标 intent.expect'))

        # RST-A01 使能脚上下拉：网络名或引脚功能名命中
        for n, nds in nets.items():
            pin_hit = any(EN_RE.search(pinname.get(node, '')) for node in nds)
            if n in self.pseudo or not (
                    EN_RE.search(n) or pin_hit):
                continue
            pulls = []
            for pull in self.pulls(n):
                label = '上拉' if pull['state'] == 'high' else '下拉'
                voltage = pull['voltage']
                pulls.append(
                    f"{pull['ref']} {label}->{pull['other']}"
                    + (f'({voltage}V)' if voltage is not None else '')
                    + (' [优先]' if voltage and voltage >= EN_PULL_ALERT_V else ''))
            if pulls:
                self.add('RST-A01', 'EN 脚上拉/下拉待复核（极性+Abs Max）',
                         f'{n}: {"; ".join(sorted(set(pulls)))}',
                         kind='CANDIDATE')

        # PRO-E02: model/name-derived voltage is a retrieval hint, not breakdown data.
        for ref, value in parts.items():
            if value.get('nc'):
                continue
            blob = protective_clamps.part_text(value)
            rail = protective_clamps.protected_net(ref, value, self.pin2net, self.graph, self.intent)
            if rail is None:
                continue   # not a clamp, not across a net and ground, or a reference/level zener (DEV-C05 and the verdict)
            self.add('PRO-E02', '防护器件工作/击穿/钳位窗口待复核',
                     f'{ref} ({blob.strip()}) 跨 {rail}；轨名提示={_fmt_v(_volt(rail))}，'
                     f'型号提示={_fmt_v(clamp_volt(blob))}。{self._protected_pins_text(rail, ref)}'
                     'VRWM（齐纳取 VZ 下限）对该网正常最高电压（含瞬态与公差）；按需求的浪涌或 ESD 波形取钳位电流，'
                     '该电流下的钳位电压对同网最低耐受，高于 IC 脚绝限即 FAIL，除非串联阻抗下注入电流在芯片允许范围内；'
                     '该波形的脉冲能量对器件额定（按本板环境温度降额），温度等级覆盖本板环境；型号不能证明导通或烧毁。',
                     ref, kind='CANDIDATE')

        # DOC-A01/DOC-A02 导出日志：错误中止与 No_connect 被忽略 —— 免费证据，别丢。
        # 提供了日志即执行扫描；kicad-cli 导出成功时日志本来就是空的，空日志表示零命中而不是未提供。
        if self.log is not None:
            for line in self.log.splitlines():
                kind = export_log_kind(line)
                if kind == 'FINDING':
                    self.add('DOC-A01', '网表导出错误/中止，核实是否为本次有效导出', line)
                elif kind == 'CANDIDATE':
                    self.add('DOC-A01', '导出时报批注（位号）错误，网表已写出但位号可能重复或未定',
                             line, kind='CANDIDATE')
                elif kind == 'INFO':
                    self.add('DOC-A01', '导出日志中的其他告警，逐条确认不影响本次网表', line, kind='INFO')
            ig = re.findall(
                r'"No_connect" property on Pin "([^"]+)" ignored.*?net "([^"]+)"',
                self.log)
            for pin, net in ig:
                actual = pin2net.get(pin)
                tag = '' if actual == net else f'（网表实为 {actual}）'
                self.add('DOC-A02', 'No_connect 属性被忽略并强行连线',
                         f'{pin} -> {net}{tag}', pin.split('.')[0])
        else:
            for rule in ('DOC-A01', 'DOC-A02'):
                self.skipped.append((rule, catalog.title(rule), '未提供导出日志（--log）'))
        board_scans.run(self)
        for checker in REGISTRY:
            inventory = self.inventories.get(checker.id)
            if inventory is not None:
                checker.cold_findings(self, inventory)
        return self.F

def _table(by, keys):
    for k in keys:
        print(f'  {k[0]:12s} {by[k][0]["name"]:32s} {len(by[k]):5d} 条')


def main():
    ap = argparse.ArgumentParser(description='自动扫描（扫描输出为疑似清单）')
    ap.add_argument('db', help='parse_netlist.py 产出的 db.json')
    ap.add_argument('--log', help='netlist.log（导出日志，含 No_connect 等免费证据）')
    ap.add_argument('--intent',
                    help='1.1 的意图清单 JSON（适用性发现与 REQ-A01 所需）')
    ap.add_argument(
        '--datasheet-audit',
        help='audit_datasheets.py 产出的逐物料覆盖审计 JSON')
    ap.add_argument('--review-mode', choices=('first', 'revision'),
                    help='首审或复审；缺省取 intent.review_mode/first')
    ap.add_argument('--old-db', help='实际读取复审旧版 db.json 并生成变化清单')
    ap.add_argument('--old-plan', help='上一设计版本最终计划；与本版 merge-plan 分开')
    ap.add_argument('--revision-impact-json', help='另存改版影响与必需复验清单')
    ap.add_argument('--claims', help='历史评审断言 JSON（用于执行计划准备度）')
    ap.add_argument('--plan-json', help='单独写出逐项检查计划 JSON')
    ap.add_argument('--candidates', help='circuit_candidates.py 生成的 record/circuit-candidates.json；intent 声明电路时必需')
    ap.add_argument('--i2c-topology-json', help='另存本次计划中的 I2C 连接覆盖清单；不是电气判决')
    ap.add_argument('--decoupling-json', help='另存本次计划中的去耦清单；不是电气判决')
    ap.add_argument('--checker-json', action='append', default=[], metavar='ID=PATH',
                    help='另存指定检查器的清单，可重复；不是电气判决')
    ap.add_argument('--merge-plan', help='合入同版旧计划的补查项；结果仍在独立台账中复核')
    ap.add_argument('--json', help='把完整命中写入 JSON')
    a = ap.parse_args()

    try:
        db = load_json(a.db)
        log = io.open(a.log, encoding='utf-8', errors='replace').read() if a.log else None
        intent = load_json(a.intent) if a.intent else None
        datasheet_audit = load_json(a.datasheet_audit) if a.datasheet_audit else None
        previous_plan = load_json(a.merge_plan) if a.merge_plan else None
        old_db = load_json(a.old_db) if a.old_db else None
        old_plan = load_json(a.old_plan) if a.old_plan else None
        candidates = load_json(a.candidates) if a.candidates else None
    except (OSError, ValueError) as error:
        ap.error(str(error))
    if a.intent and not isinstance(intent, dict):
        ap.error('explicit intent.json root must be an object')
    for supplied, value, label in ((a.old_db, old_db, '--old-db'), (a.old_plan, old_plan, '--old-plan')):
        if supplied and not isinstance(value, dict):
            ap.error(label + ' JSON root must be an object')
    intent_errors = validate_intent(intent, db, candidates=candidates, require_candidates=True)
    if intent_errors:
        sys.exit('[FATAL] intent.json 无效:\n  - ' + '\n  - '.join(intent_errors))
    if datasheet_audit is not None:
        errors = validate_datasheet_audit(datasheet_audit, db)
        if errors:
            sys.exit('[FATAL] datasheet-audit.json 无效:\n  - '
                     + '\n  - '.join(errors))
    for label, path in (('--old-db', a.old_db), ('--claims', a.claims)):
        if path and not os.path.isfile(path):
            sys.exit(f'[FATAL] {label} 文件不存在: {path}')

    lint = Lint(db, log, intent, datasheet_audit)
    F = lint.run()
    try:
        # Each automatic-scan finding is answered in the ledger like any other check.
        review_plan = build_review_plan(
            db, intent, a.review_mode,
            old_db_available=bool(a.old_db),
            claims_available=bool(a.claims),
            datasheet_audit=datasheet_audit, previous_plan=previous_plan,
            old_db=old_db, old_plan=old_plan, lint_findings=F, candidates=candidates)
    except ValueError as error:
        sys.exit(f'[FATAL] {error}')
    if a.revision_impact_json:
        if 'revision_impact' not in review_plan:
            ap.error('--revision-impact-json requires revision mode')
        with open(a.revision_impact_json, 'w', encoding='utf-8') as stream:
            json.dump(review_plan['revision_impact'], stream, ensure_ascii=False, indent=2, allow_nan=False)
    summary = review_plan['summary']
    print('=== 检查计划（规则总表展开） ===')
    print(f"  checks={summary['checks_total']}  "
          f"applicability={summary['applicability']}")
    print(f"  readiness={summary['readiness']}  "
          f"handoff_required={summary['handoff_required']}")
    for line in diagnostic_lines(review_plan, db, intent):
        print(line)
    if a.plan_json:
        json.dump(review_plan, io.open(a.plan_json, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=2)
        print(f'  -> {a.plan_json}')
    # 两个旧开关是通用导出的别名，走同一条路径，不另写一份导出代码
    exports = (['i2c_topology=' + a.i2c_topology_json] if a.i2c_topology_json else []) \
        + (['decoupling=' + a.decoupling_json] if a.decoupling_json else []) + a.checker_json
    for spec in exports:
        checker_id, _, path = spec.partition('=')
        checker = REGISTRY_BY_ID.get(checker_id)
        if checker is None or checker.plan_key not in review_plan or not path:
            raise SystemExit('未知检查器或缺少输出路径: ' + spec)
        with open(path, 'w', encoding='utf-8') as stream:
            json.dump(review_plan[checker.plan_key], stream, ensure_ascii=False,
                      indent=2, allow_nan=False)

    # 分组键含 kind——同一条规则可同时产出 FINDING 与 CANDIDATE
    by = defaultdict(list)
    for f in F:
        by[(f['rule'], f['kind'])].append(f)
    # 按规则总表顺序（内容域 → 方式 → 序号）
    order = sorted(by, key=lambda k: catalog.order(k[0]))
    find = [k for k in order if k[1] == 'FINDING']
    cand = [k for k in order if k[1] == 'CANDIDATE']
    info = [k for k in order if k[1] == 'INFO']

    print('=== 自动扫描汇总（疑似清单，非判决）===')
    _table(by, find)
    n_find = sum(len(by[k]) for k in find)
    print(f'  {"合计":45s} {n_find:5d} 条')
    print('\n  逐条排除后才是发现项——由执行 agent 完成，排除依据须留痕。合法结构举例：'
          'Bob-Smith 终端、补偿网络、DNP 选项、\n  被删外设的 SoC 引出脚、工具伪网络。')

    if cand:
        print('\n=== CANDIDATE：待资料取证定夺（决定优先读哪几份 datasheet）===')
        _table(by, cand)

    if info:
        print('\n=== INFO：提示（非缺陷，准出前仍需图面或属性证据）===')
        _table(by, info)

    # 未执行的规则必须报出来——扫出 0 条与根本没扫，绝不能长得一样
    print('\n=== 本趟未执行（0 条 ≠ 通过）===')
    for rid, name, why in lint.skipped:
        print(f'  {rid:12s} {name:32s} {why}')

    if a.json:
        json.dump({'findings': F,
                   'skipped': [list(s) for s in lint.skipped],
                   'review_plan': review_plan,
                   'coverage': {
                       'pintype_available': bool(db.get('pintype')),
                       'pintype_nodes': len(db.get('pintype', {})),
                       'pin_nodes': len(db.get('pin2net', {})),
                       'pintype_ratio': (
                           len(db.get('pintype', {}))
                           / max(len(db.get('pin2net', {})), 1)),
                       'finding_count': len([x for x in F
                                             if x['kind'] == 'FINDING']),
                       'candidate_count': len([x for x in F
                                               if x['kind'] == 'CANDIDATE']),
                       'info_count': len([x for x in F if x['kind'] == 'INFO']),
                   }},
                  io.open(a.json, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print(f'\n  -> {a.json}')


if __name__ == '__main__':
    main()
