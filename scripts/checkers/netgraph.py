#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按连接关系识别电路的共享工具：器件分类、引脚角色、逐状态连接查询。

只回答"网表里连成了什么"，不回答"电气上是否合格"。分类和角色都带依据；
依据不足时返回未知并形成缺口，不猜测、不按名称下结论。
"""
import re

GNDS = {'GND', 'PGND', 'AGND', 'DGND', 'EGND'}
RAIL_RE = re.compile(
    r'^(VCC|VDD|VDDA|VCCA|VOUT|VBAT|AVDD|DVDD|VIN|VBUS|V\d|[0-9]+V)', re.I)

RESISTOR, CAPACITOR, INDUCTOR, FERRITE = 'resistor', 'capacitor', 'inductor', 'ferrite'
DIODE, TVS, ZENER, MOSFET, BJT = 'diode', 'tvs', 'zener', 'mosfet', 'bjt'
RELAY, OPTO, CRYSTAL, TRANSFORMER = 'relay', 'opto', 'crystal', 'transformer'
FUSE, JUMPER, TESTPOINT, SWITCH = 'fuse', 'jumper', 'testpoint', 'switch'
IC, CONNECTOR, UNKNOWN = 'ic', 'connector', 'unknown'

PREFIX_KINDS = (
    (r'^JP\d', JUMPER), (r'^TP\d', TESTPOINT), (r'^FB\d', FERRITE),
    (r'^R\d', RESISTOR), (r'^RN\d', RESISTOR), (r'^C\d', CAPACITOR),
    (r'^L\d', INDUCTOR), (r'^D\d', DIODE), (r'^Q\d', MOSFET),
    (r'^K\d', RELAY), (r'^Y\d', CRYSTAL), (r'^X\d', CRYSTAL),
    (r'^T\d', TRANSFORMER), (r'^F\d', FUSE), (r'^SW\d', SWITCH),
    (r'^S\d', SWITCH), (r'^[UM]\d', IC), (r'^(J|P|CN)\d', CONNECTOR),
)

KEYWORD_KINDS = (
    (r'RELAY|继电器', RELAY),
    (r'OPTO|PC81[07]|LTV\d|TLP\d|6N13[57]|HCPL|ACPL|FOD\d|CNY17|VO6\d|光耦', OPTO),
    (r'\bTVS\b|SMAJ|SMBJ|SMCJ|P6KE|1\.5KE|ESD\d|PESD|SM712', TVS),
    (r'ZENER|BZX|MMSZ|1N47\d|稳压二极管', ZENER),
    (r'MOSFET|\bFET\b|NMOS|PMOS|IRF|AO\d{4}|SI\d{4}|BSS\d|2N7002|IGBT', MOSFET),
    (r'\bNPN\b|\bPNP\b|BC\d{3}|2N\d{4}|MMBT|S8050|S8550|三极管', BJT),
    (r'SCHOTTKY|DIODE|SS\d{2}|BAT\d|1N4\d{3}|1N58\d|二极管', DIODE),
    (r'FERRITE|BEAD|BLM\d|MPZ\d|磁珠', FERRITE),
    (r'INDUCTOR|CHOKE|电感', INDUCTOR),
    (r'CRYSTAL|XTAL|OSC|晶振|晶体', CRYSTAL),
    (r'TRANSFORMER|变压器', TRANSFORMER),
    (r'FUSE|PTC|保险', FUSE),
)

TWO_TERMINAL = {RESISTOR, CAPACITOR, INDUCTOR, FERRITE, DIODE, TVS, ZENER,
                FUSE, JUMPER}
PASSIVE_LINKS = {RESISTOR, INDUCTOR, FERRITE, JUMPER, FUSE}

GATE_NAMES = {'G', 'GATE', 'GT'}
DRAIN_NAMES = {'D', 'DRAIN', 'C', 'COLLECTOR', 'COL'}
SOURCE_NAMES = {'S', 'SOURCE', 'SRC', 'E', 'EMITTER', 'EMIT'}
ANODE_NAMES = {'A', 'ANODE', 'AN', '+', 'P'}
CATHODE_NAMES = {'K', 'C', 'CATHODE', 'CATH', '-', 'N'}
COIL_NAMES = {'COIL', 'COIL1', 'COIL2', 'A1', 'A2', 'L1', 'L2', '+', '-'}
LED_ANODE_NAMES = {'A', 'ANODE', 'LED+', 'LEDA'}
LED_CATHODE_NAMES = {'K', 'CATHODE', 'LED-', 'LEDK'}


def normalize(value):
    return str(value).strip().upper() if value is not None else ''


def classify(ref, part, pin_count=None):
    """返回 (kind, basis)。basis 说明结论来自型号关键字还是位号前缀。"""
    blob = ' '.join(normalize(part.get(key)) for key in ('part', 'value', 'prim', 'jedec'))
    for pattern, kind in KEYWORD_KINDS:
        if re.search(pattern, blob, re.I):
            if kind in (MOSFET, BJT) and pin_count is not None and pin_count < 3:
                continue
            return kind, 'part-keyword'
    for pattern, kind in PREFIX_KINDS:
        if re.match(pattern, ref, re.I):
            if kind is MOSFET and pin_count is not None and pin_count < 3:
                return UNKNOWN, 'refdes-prefix conflicts with pin count'
            return kind, 'refdes-prefix'
    return UNKNOWN, 'no classification evidence'


def is_ground(net):
    return normalize(net) in GNDS


def is_rail(net):
    return bool(net) and not is_ground(net) and bool(RAIL_RE.match(str(net)))


class NetGraph:
    """按某一装配状态给出的网表视图；未贴器件不导通、不参与识别。"""

    def __init__(self, db, fitted=None):
        self.db = db
        self.nets = db.get('nets', {})
        self.parts = db.get('parts', {})
        self.pin2net = db.get('pin2net', {})
        self.pinname = db.get('pinname', {})
        self.pintype = db.get('pintype', {})
        self.pseudo = set(db.get('pseudo_nets', []))
        self._pins = {}
        for node, net in self.pin2net.items():
            ref, _, pin = node.partition('.')
            self._pins.setdefault(ref, {})[pin] = net
        if fitted is None:
            fitted = {ref for ref, part in self.parts.items() if not part.get('nc')}
        self.fitted = set(fitted)
        self._kinds = {}

    # -- 器件 ---------------------------------------------------------
    def pins_of(self, ref):
        return dict(self._pins.get(ref, {}))

    def kind(self, ref):
        if ref not in self._kinds:
            part = self.parts.get(ref, {})
            self._kinds[ref] = classify(ref, part, len(self._pins.get(ref, {})) or None)
        return self._kinds[ref][0]

    def basis(self, ref):
        self.kind(ref)
        return self._kinds[ref][1]

    def is_fitted(self, ref):
        return ref in self.fitted

    def role(self, node):
        """引脚角色；引脚名缺失时返回 None，调用方必须登记缺口。"""
        ref, _, _ = node.partition('.')
        name = normalize(self.pinname.get(node))
        if not name:
            return None
        kind = self.kind(ref)
        if kind in (MOSFET, BJT):
            if name in GATE_NAMES or name.startswith('GATE'):
                return 'gate'
            if name in DRAIN_NAMES:
                return 'drain'
            if name in SOURCE_NAMES:
                return 'source'
            return None
        if kind in (DIODE, TVS, ZENER):
            if name in ANODE_NAMES:
                return 'anode'
            if name in CATHODE_NAMES:
                return 'cathode'
            return None
        if kind is RELAY:
            if name in COIL_NAMES or name.startswith('COIL'):
                return 'coil'
            return 'contact'
        if kind is OPTO:
            if name in LED_ANODE_NAMES:
                return 'led_anode'
            if name in LED_CATHODE_NAMES:
                return 'led_cathode'
            if name in DRAIN_NAMES:
                return 'out_collector'
            if name in SOURCE_NAMES:
                return 'out_emitter'
            return None
        return None

    def node_named(self, ref, role):
        for pin in sorted(self._pins.get(ref, {})):
            node = ref + '.' + pin
            if self.role(node) == role:
                return node
        return None

    # -- 连接 ---------------------------------------------------------
    def nodes_on(self, net):
        return sorted(self.nets.get(net, []))

    def refs_on(self, net, fitted_only=True):
        refs = {node.partition('.')[0] for node in self.nets.get(net, [])}
        return sorted(ref for ref in refs if not fitted_only or ref in self.fitted)

    def terminals(self, ref):
        pins = self._pins.get(ref, {})
        nets = sorted(set(pins.values()))
        return nets if len(nets) == 2 else []

    def between(self, net_a, net_b, kinds=None, fitted_only=True):
        """两网之间的二端器件。"""
        found = []
        for ref in self.refs_on(net_a, fitted_only):
            ends = self.terminals(ref)
            if len(ends) != 2 or net_b not in ends or net_a not in ends:
                continue
            if kinds and self.kind(ref) not in kinds:
                continue
            found.append(ref)
        return sorted(found)

    def neighbors(self, net, kinds=None, fitted_only=True):
        """经二端器件可达的相邻网络：[(ref, other_net)]。"""
        out = []
        for ref in self.refs_on(net, fitted_only):
            ends = self.terminals(ref)
            if len(ends) != 2 or net not in ends:
                continue
            if kinds and self.kind(ref) not in kinds:
                continue
            other = ends[0] if ends[1] == net else ends[1]
            out.append((ref, other))
        return sorted(out)

    def series_path(self, net, kinds=PASSIVE_LINKS, max_hops=3, fitted_only=True):
        """沿串联无源件扩展出的等电位候选网络集合（含起点）。"""
        seen, frontier = {net}, [(net, 0)]
        while frontier:
            current, hops = frontier.pop()
            if hops >= max_hops:
                continue
            for _, other in self.neighbors(current, kinds, fitted_only):
                if other not in seen:
                    seen.add(other)
                    frontier.append((other, hops + 1))
        return seen
