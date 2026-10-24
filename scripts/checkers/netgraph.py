#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按连接关系识别电路的共享工具：器件分类、引脚角色、逐状态连接查询。

只回答"网表里连成了什么"，不回答"电气上是否合格"。分类和角色都带依据；
依据不足时返回未知并形成缺口，不猜测、不按名称下结论。
"""
import re

from part_words import (ANCHOR_ROLES, ANODE_NAMES, BJT, CATHODE_NAMES, COIL_NAMES, CONNECTOR, CONNECTOR_CONTACT_RE,
                        DIODE, DRAIN_NAMES, GATE_NAMES, IC, IC_ROLES, LED_ANODE_NAMES, LED_CATHODE_NAMES, MOSFET, OPTO,
                        PASSIVE_LINKS, RELAY, SOURCE_NAMES, TVS, ZENER, classify, name_matches, normalize, pin_aliases,
                        pin_signature)

GNDS = {'GND', 'PGND', 'AGND', 'DGND', 'EGND'}
# 可带 RAIL_ 前缀（RAIL_3V3_PRI）；VSYS/VMOT/VLED/VM、P5V/P3V3 也是轨名；HV/HV80_IN/HV_BIAS 是高压轨（HVEN、HV_EN 是使能）；
# 含 _FB/_FBACK/_SENSE/_SNS/_DET/_PG/_MON 段的是反馈、检测或状态线（VCC_EN 可能是受控轨，不排除）；以 _N/_NEG/_RTN/_RET/- 结尾的是回流
# （如 VOUT_N、VIN-、VBAT_NEG），不是电源轨。
RAIL_RE = re.compile(
    r'^\+?(?:RAIL_)?(VCC|VDD|VDDA|VCCA|VOUT|VBAT|AVDD|DVDD|VIN|VBUS|VSYS|VMOT|VLED|VM(?=$|\d|_)|V\d|P\d+V\d*'
    r'|[0-9]+(?:\.[0-9]+)?V|HV(?=$|\d|[_+](?!EN)))'
    r'(?!.*(?:[_-](?:N|NEG|RTN|RET|MINUS)|-)$)(?!.*[_-](?:FB|FBACK|FEEDBACK|SENSE|SNS|DET|DETECT|PG|PGOOD|MON)(?:$|[_-]))', re.I)

# A ground by its name token: GND with up to a 3-character unseparated prefix (SGND, PGND, CHGND), or VSS with an
# A/D prefix (AVSS, DVSS), and a short domain suffix (GND_ISO, GNDA, GND2, VSSA), or 0V. Kelvin/sense/detect lines to
# ground are signals. Every module asks is_ground; none keeps its own ground pattern.
GROUND_NAME_RE = re.compile(r'^(?:[A-Z0-9]{0,3}GND|[AD]?VSS)(?:[_-]?([A-Z0-9]{1,6}))?$')
GROUND_SIGNAL_SUFFIXES = {'SENSE', 'SNS', 'KELVIN', 'DET', 'FB', 'EN', 'SW'}


def is_ground(net):
    name = normalize(net).rsplit('/', 1)[-1]
    if name in GNDS or name == '0V':
        return True
    match = GROUND_NAME_RE.match(name)
    return bool(match) and match.group(1) not in GROUND_SIGNAL_SUFFIXES


# _P/_N 命名的电流/电压采样对（CS_P/CS_N、ISENSE+/-、SNS_P 等）是模拟测量，不是差分数据链路。
ANALOG_PAIR_BASE_RE = re.compile(
    r'(^|[_/.-])(CS|CSP|CSN|ISENSE|ISENS|ISNS|ISEN|SENSE|SNS|IMON|VSENSE|VSNS|SHUNT|IS|CUR|CURRENT|ISET)$', re.I)


def is_analog_sense_pair(positive):
    """按正腿网名去掉 _P/-P/+/P 后缀判断是不是采样对。"""
    base = re.sub(r'(_P|-P|\+|_DP|P)$', '', str(positive).rsplit('/', 1)[-1], flags=re.I)
    return bool(ANALOG_PAIR_BASE_RE.search(base))


AUTO_NET_RE = re.compile(r'(^|/)(Net|unconnected)-\(')


def is_auto_named(net):
    """A net name the schematic tool generated from a pin (KiCad Net-(…)/unconnected-(…)): nobody named it a rail."""
    return bool(AUTO_NET_RE.search(str(net or '')))


def is_rail(net):
    return bool(net) and not is_ground(net) and bool(RAIL_RE.match(str(net)))


def rail_voltage(name):
    """从名字里推电压：3V3->3.3, 24V->24, 5.0V->5.0, V5P0->5.0；推不出返回 None。

    名字只是线索，不是轨压证据；判据仍取需求或资料保证值。
    """
    if not name:
        return None
    upper = str(name).upper()
    match = re.search(r'(\d{1,3})V(\d)(?![\dA-Z])', upper)      # 3V3 / 24V0
    if match:
        return float(match.group(1)) + float(match.group(2)) / 10
    match = re.search(r'(\d{1,3}\.\d)V', upper)                 # 5.0V
    if match:
        return float(match.group(1))
    match = re.search(r'(\d{1,3})V(?![\dA-Z])', upper)           # 24V / _5V
    if match:
        return float(match.group(1))
    match = re.search(r'V(\d{1,2})P(\d)(?![\d])', upper)        # V5P0
    if match:
        return float(match.group(1)) + float(match.group(2)) / 10
    return None


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
            pins = self._pins.get(ref, {})
            names = [(self.pinname.get(ref + '.' + pin), pin) for pin in pins]
            declared = (self.db.get('device_kinds') or {}).get(ref, {}).get('kind')
            self._kinds[ref] = classify(ref, part, len(pins) or None, names, declared)
        return self._kinds[ref][0]

    def basis(self, ref):
        self.kind(ref)
        return self._kinds[ref][1]

    def role_kind(self, ref):
        """The datasheet-verified IC role (board_intent.IC_KINDS), or None for an undeclared or non-IC part."""
        declared = (self.db.get('device_kinds') or {}).get(ref, {}).get('kind')
        return declared if declared in IC_ROLES and self.kind(ref) == IC else None

    def is_anchor(self, ref):
        """A fitted IC whose verified role can anchor a circuit candidate."""
        return self.is_fitted(ref) and self.role_kind(ref) in ANCHOR_ROLES

    def qualified_connector_contact(self, ref):
        """Whether part identity supports an intentionally unused passive contact.

        Classification of the combined part text is only a discovery hint.
        An NC exemption needs either a verified declaration or agreement of
        each populated identity field, including an actual symbol identity.
        """
        if self.kind(ref) != CONNECTOR:
            return False
        if self.basis(ref) == 'datasheet':
            return True
        if self.basis(ref) != 'part-keyword':
            return False
        pins = self._pins.get(ref, {})
        names = [(self.pinname.get(ref + '.' + pin), pin) for pin in pins]
        if pin_signature(names):
            return False
        part = self.parts.get(ref, {})
        package = normalize(part.get('jedec'))
        if (package and package.upper() != 'MODULE'
                and not re.fullmatch(r'Connector(?:_[A-Za-z0-9.]+)*:[^\s:]+', package, re.I)
                and not re.fullmatch(CONNECTOR_CONTACT_RE, package, re.I)):
            # JEDEC/footprint is not an MPN. An unresolved or conflicting
            # physical package still needs review; legacy MODULE is neutral.
            return False
        if not any(normalize(part.get(key)) for key in ('part', 'prim')):
            return False
        for key in ('part', 'prim', 'value'):
            identity = normalize(part.get(key))
            if not identity:
                continue
            # Free-form descriptions and unknown identities cannot establish
            # a passive role merely by containing a connector keyword.
            if not re.fullmatch(CONNECTOR_CONTACT_RE, identity, re.I):
                return False
            if classify('?', {'part': identity}) != (CONNECTOR, 'part-keyword'):
                return False
        return True

    def is_fitted(self, ref):
        return ref in self.fitted

    def role(self, node):
        """引脚角色；引脚名缺失时返回 None，调用方必须登记缺口。"""
        ref, _, pin = node.partition('.')
        for alias in pin_aliases(self.pinname.get(node), pin):
            found = self._role(ref, alias)
            if found:
                return found
        return None

    def named_pins(self, ref, pattern):
        """某器件上引脚名（任一等价写法）命中 pattern 的脚 -> 网络。"""
        found = {}
        for pin, net in self.pins_of(ref).items():
            node = ref + '.' + pin
            if name_matches(pattern, self.pinname.get(node), pin):
                found[node] = net
        return dict(sorted(found.items()))

    def _role(self, ref, name):
        kind = self.kind(ref)
        if kind in (MOSFET, BJT):
            # The shared graph uses gate/drain/source coordinates for B/C/E.
            # This alias enables tracing, not a MOS drive model for a BJT.
            if kind == BJT and name in {'B', 'BASE', 'BAZA'}:
                return 'gate'
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
        if kind == RELAY:
            if name in COIL_NAMES or name.startswith('COIL'):
                return 'coil'
            return 'contact'
        if kind == OPTO:
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

    def nets_of(self, ref):
        """该器件接触到的全部网络（去重排序）。"""
        return sorted(set(self._pins.get(ref, {}).values()))

    def terminals(self, ref):
        nets = self.nets_of(ref)
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
