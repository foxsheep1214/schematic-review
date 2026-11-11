# -*- coding: utf-8 -*-
"""External latch criteria fed by protection-IC status pins: the cold scans PRO-A06 (normal actions, G05-098) and
PWR-A08 (hot insertion of an allowed load, G03-017) share one model (user 2026-11-04: 修改SR不足 2.1、2.2).

A latch is a flip-flop of an exactly known logic family whose asynchronous set/clear input is the output of a gate
tree. The tree is traced through gates of known function down to leaf nets; a leaf that is the PG/FLT/IMON pin of a
protection IC (eFuse, hot-swap controller, load switch) makes the latch a status-pin criterion. Each normal action
gives the leaves values (three-valued: 0, 1, unknown) from the protection IC's datasheet corners and the board's
RC networks, and the tree is evaluated: an asserted async input in a normal action is a FINDING, an undecided one a
CANDIDATE that names what is missing. Datasheet numbers come only from exact-identity tables below (the
protective_clamps precedent); a part not tabled keeps the structure line without numbers.
"""
import math
import re

import part_words as pw
from checkers import netgraph as ng
from decoupling import parse_capacitance
from solve_dividers import parse_resistor

# --- logic parts, by exact family ----------------------------------------------------------------------------
LOGIC_RE = re.compile(r'(?:SN)?74(?:HCS|HCT|HC|AHCT|AHC|LVC|LV|ACT|AC|ALVC|AUP)(?:[123]G)?(\d{2,3})[A-Z]?', re.I)
FUNCTIONS = {'00': 'NAND', '02': 'NOR', '08': 'AND', '32': 'OR', '04': 'NOT', '14': 'NOT', '10': 'NAND', '11': 'AND',
             '27': 'NOR', '07': 'BUF', '17': 'BUF', '74': 'DFF'}

# (identity regex, ((VCC, VT- min, VT- max, VT+ min, VT+ max), ...), citation): guaranteed input thresholds over
# temperature, interpolated linearly in VCC between the tabled supplies.
INPUT_THRESHOLDS = (
    (r'SN74HCS00\w*', ((2.0, .61, .66, 1.18, 1.30), (4.5, 1.31, 1.42, 2.39, 2.58), (6.0, 1.72, 1.87, 3.11, 3.32)),
     'TI SN74HCS00 SCLS775D p5 §5.5 VT−/VT+'),
    (r'SN74HCS02\w*', ((2.0, .55, .71, 1.13, 1.37), (4.5, 1.21, 1.50, 2.31, 2.66), (6.0, 1.56, 1.99, 2.99, 3.44)),
     'TI SN74HCS02 SCLS776D p4 §5.4 VT−/VT+'),
    (r'SN74HCS74\w*', ((2.0, .3, 1.0, .7, 1.5), (4.5, .9, 2.2, 1.7, 3.15), (6.0, 1.2, 3.0, 2.1, 4.2)),
     'TI SN74HCS74 SCLS782D p5 §6.5 VT−/VT+'),
)

# Protection ICs whose status-pin timing was read. Keys:
#   enable: pin-name regex of the shutdown/enable input; off: its falling turn-off threshold (min, max) [V]
#   off_note: where the bounds come from; t_off: enable crossing to FET off (min, max) [s]
#   pg: PG pin regex; pg_fall: PG falling deglitch (min, max) [s]; pg_rise: rising deglitch (min, max) [s]
#   flt: FLT pin regex; flt_on_enable: whether pulling the enable low asserts FLT
#   pgth: PGTH pin regex with falling/rising thresholds (min, max) [V] (PG follows the output through a divider)
#   ilim: (pin regex, A·kΩ constant, relative spread) for I_OL = k / R_ILIM; flt_cl: FLT delay in current limit [s]
#   dvdt: (pin regex, I(dVdT) min/max [A], gain min/max) for the output ramp time
PROTECTION_TIMING = (
    (r'TPS2663[0-7]\w*', {
        'enable': r'SHDN', 'off': (0.8, 2.0), 't_off': (0.8e-6, 1.5e-6),
        'off_note': 'V(SHUTF) 下限 0.8 V，手册不给上限，取上升门限 V(SHUTR) 最大 2 V',
        'pg': r'PGOOD', 'pg_fall': (1.3e-6, 4e-6), 'pg_rise': (1.07e-3, 1.6e-3),
        'flt': r'FLT', 'flt_on_enable': False,
        'pgth': (r'PGTH', (1.09, 1.15), (1.176, 1.224)),
        'ilim': (r'ILIM', 18.0, 0.08), 'flt_cl': (20e-3, 31e-3),
        'dvdt': (r'DVDT', (1.775e-6, 2.225e-6), (23.5, 26.0)),
        'citation': 'TI TPS2663x SLVSE94G p7 V(SHUTF)/V(SHUTR)、I(OL)=18/R(ILIM)（9 kΩ 时 1.84–2.16 A）、I(dVdT)、GAIN(dVdT)；'
                    'p8 V(PGTHF)/V(PGTHR)、tSD(dly)；p9 tPGOODF/tPGOODR、tCB(dly)；p28 Figure 8-23（SHDN 关断 PGOOD 随之变低，不置 FLT）'}),
    (r'TPS25981\w*', {
        'enable': r'EN', 'off': (1.073, 1.116), 't_off': None,
        'off_note': 'VUVLO(F) 1.073–1.116 V',
        'pg': r'PG', 'pg_fall': (14e-6, 14e-6), 'pg_rise': (14e-6, 14e-6),
        'flt': r'FLT', 'flt_on_enable': False,
        'citation': 'TI TPS25981x SLVSGG6D p7 VUVLO(F)、tPGA/tPGD（只给典型 14 µs）；§8.3 FET 关断即撤销 PG，EN 关断不置 FLT'}),
)

# Diode forward voltage, typical curves [(mA, V)] at 25 °C and at the hot end (the low bound used for verdicts).
DIODE_VF = (
    (r'BAS21\w*', ((1, .62), (10, .72), (100, .86), (200, .98)), ((1, .38), (10, .54), (100, .72)),
     'onsemi BAS21H p3 Figure 2（典型曲线，25 °C 与 155 °C）'),
)
STATUS_PIN_RE = re.compile(r'^(?:P(?:OWER)?_?G(?:OOD|D)?|PWRGD|FLT|FAULT|IMON)$', re.I)
EXAMPLE_LOAD_F = (10e-6, 47e-6, 100e-6)


def _identity(part):
    return [str(part.get(k) or '') for k in ('part', 'value')]


def _table(table, part):
    ids = _identity(part)
    return next((row for row in table if any(re.fullmatch(row[0], i, re.I) for i in ids)), None)


def logic_function(part):
    for ident in _identity(part):
        m = LOGIC_RE.fullmatch(ident.split('/')[0].strip()) or LOGIC_RE.match(ident)
        if m and m.group(1) in FUNCTIONS:
            return FUNCTIONS[m.group(1)]
    return None


def _interp(points, vcc, col):
    pts = sorted(points)
    if vcc <= pts[0][0]:
        lo, hi = pts[0], pts[1]
    elif vcc >= pts[-1][0]:
        lo, hi = pts[-2], pts[-1]
    else:
        lo, hi = next((a, b) for a, b in zip(pts, pts[1:]) if a[0] <= vcc <= b[0])
    return lo[col] + (hi[col] - lo[col]) * (vcc - lo[0]) / (hi[0] - lo[0])


def fmt_v(v):
    return '%.2f' % v if v < 10 else '%.1f' % v


def fmt_t(t):
    if t == math.inf:
        return '∞'
    if t >= 1:
        return '%.2f s' % t
    if t >= 1e-3:
        return '%.3g ms' % (t * 1e3)
    return '%.3g µs' % (t * 1e6)


def fmt_range(lo, hi):
    return fmt_t(lo) if lo == hi else '%s–%s' % (fmt_t(lo), fmt_t(hi))


def fmt_f(c):
    return '%.3g µF' % (c * 1e6)


class Model:
    """Gates, latches and protection status pins of one board view (a Lint)."""

    def __init__(self, lint):
        self.lint, self.graph, self.parts = lint, lint.graph, lint.parts
        self.intent = lint.intent or {}
        self.gates = {}      # output node -> (ref, function, [input nets])
        self.latches = []    # (ref, unit, {'PRE': node, 'CLR': node, 'Q': net, 'QN': net})
        for ref, part in sorted(self.parts.items()):
            if part.get('nc') or not self.graph.is_fitted(ref):
                continue
            function = logic_function(part)
            if not function:
                continue
            units = {}
            for pin, net in self.graph.pins_of(ref).items():
                node = ref + '.' + pin
                raw = str(self.graph.pinname.get(node) or '')
                name = pw.pin_aliases(raw, pin)[-1] if raw else ''
                low = raw.startswith('~') or raw.startswith('!')
                if function == 'DFF':
                    m = re.fullmatch(r'(\d*)(PRE|CLR|D|CLK|CK|Q)', name, re.I)
                    if m:
                        key = m.group(2).upper()
                        key = 'QN' if key == 'Q' and low else key
                        units.setdefault(m.group(1), {})[key] = node if key in ('PRE', 'CLR') else net
                    continue
                m = re.fullmatch(r'(\d*)([A-D])', name, re.I)
                if m:
                    units.setdefault(m.group(1), {'in': [], 'out': None})['in'].append((m.group(2).upper(), net))
                    continue
                m = re.fullmatch(r'(\d*)Y', name, re.I)
                if m:
                    units.setdefault(m.group(1), {'in': [], 'out': None})['out'] = node
            for unit, pins in sorted(units.items()):
                if function == 'DFF':
                    if 'PRE' in pins or 'CLR' in pins:
                        self.latches.append((ref, unit, pins))
                elif pins['out'] and pins['in']:
                    self.gates[pins['out']] = (ref, function, [net for _, net in sorted(pins['in'])])
        self.reset_nets = {self.graph.pin2net.get(p[k]) for _, _, p in self.latches for k in ('PRE', 'CLR') if k in p}

    # -- tree ------------------------------------------------------------------------------------------------
    def driver(self, net):
        return next((self.gates[n] + (n,) for n in self.graph.nodes_on(net) if n in self.gates), None)

    def tree(self, net, depth=0, seen=()):
        d = self.driver(net)
        if d is None or depth > 8 or net in seen:
            return ('LEAF', net)
        ref, function, inputs, node = d
        return (function, net, ref, [self.tree(i, depth + 1, seen + (net,)) for i in inputs])

    def leaves(self, tree, stop=()):
        """Leaf nets, unique, in order; a gate output listed in stop counts as a leaf (the enable driver)."""
        if tree[0] == 'LEAF' or tree[1] in stop:
            return [tree[1]]
        return list(dict.fromkeys(leaf for child in tree[3] for leaf in self.leaves(child, stop)))

    def entry_gate(self, tree, leaf):
        """The gate ref whose input is the leaf (for its threshold)."""
        if tree[0] == 'LEAF':
            return None
        for child in tree[3]:
            if child[0] == 'LEAF' and child[1] == leaf:
                return tree[2]
            found = self.entry_gate(child, leaf)
            if found:
                return found
        return None

    @staticmethod
    def evaluate(tree, values):
        if tree[0] == 'LEAF' or tree[1] in values:
            return values.get(tree[1])
        ins = [Model.evaluate(c, values) for c in tree[3]]
        function = tree[0]
        if function in ('NAND', 'AND'):
            out = 0 if 0 in ins else (1 if all(v == 1 for v in ins) else None)
        elif function in ('NOR', 'OR'):
            out = 1 if 1 in ins else (0 if all(v == 0 for v in ins) else None)
        else:
            out = ins[0]
        if out is not None and function in ('NAND', 'NOR', 'NOT'):
            out = 1 - out
        return out

    @staticmethod
    def text(tree):
        if tree[0] == 'LEAF':
            return tree[1].rsplit('/', 1)[-1]
        return '%s(%s)' % (tree[0], ', '.join(Model.text(c) for c in tree[3]))

    # -- board values ----------------------------------------------------------------------------------------
    def rail_window(self, net):
        rail = (self.intent.get('power_rails') or {}).get(net) or {}
        v = rail.get('voltage_v') if isinstance(rail, dict) else None
        if isinstance(v, dict) and isinstance(v.get('min'), (int, float)) and isinstance(v.get('max'), (int, float)):
            return float(v['min']), float(v['max']), 'intent.power_rails'
        nominal = ng.rail_voltage(net)
        return (nominal, nominal, '按网名推定') if nominal else None

    def thresholds(self, ref):
        """(VT- min, VT- max, VT+ min, VT+ max, text) of a tabled gate at its supply, else None."""
        row = _table(INPUT_THRESHOLDS, self.parts.get(ref, {}))
        if not row:
            return None
        supply = next((net for pin, net in self.graph.pins_of(ref).items()
                       if re.fullmatch(r'VCC|VDD', str(self.graph.pinname.get(ref + '.' + pin) or ''), re.I)), None)
        window = self.rail_window(supply) if supply else None
        if not window:
            return None
        lo, hi, _ = window
        vtm = (_interp(row[1], lo, 1), _interp(row[1], hi, 2))
        vtp = (_interp(row[1], lo, 3), _interp(row[1], hi, 4))
        return vtm + vtp + ('%s VCC %s V：VT− %s–%s V，VT+ %s–%s V（%s）' % (
            ref, fmt_v(lo) if lo == hi else fmt_v(lo) + '–' + fmt_v(hi), fmt_v(vtm[0]), fmt_v(vtm[1]), fmt_v(vtp[0]), fmt_v(vtp[1]), row[2]),)

    def ohm(self, ref):
        parsed = parse_resistor(self.parts.get(ref, {}).get('value'))
        return parsed['kohm'] * 1e3 if parsed else None

    def farad(self, ref):
        return parse_capacitance(self.parts.get(ref, {}).get('value'))

    def caps_to_ground(self, net):
        return [r for r, other in self.graph.neighbors(net, {pw.CAPACITOR}) if ng.is_ground(other)]

    def diode_vf(self, ref, amps):
        """(25 °C typical, hot-end typical) forward voltage at the current, else None."""
        row = _table(DIODE_VF, self.parts.get(ref, {}))
        if not row or amps <= 0:
            return None
        ma = amps * 1e3

        def at(curve):
            pts = sorted(curve)
            if ma <= pts[0][0]:
                a, b = pts[0], pts[1]
            elif ma >= pts[-1][0]:
                a, b = pts[-2], pts[-1]
            else:
                a, b = next((x, y) for x, y in zip(pts, pts[1:]) if x[0] <= ma <= y[0])
            slope = (b[1] - a[1]) / (math.log10(b[0]) - math.log10(a[0]))
            return a[1] + slope * (math.log10(ma) - math.log10(a[0]))
        return at(row[1]), at(row[2]), row[3]


class Device:
    """A protection IC with a status pin among the leaves of a latch input."""

    def __init__(self, model, ref):
        self.model, self.ref = model, ref
        graph = model.graph
        row = _table(PROTECTION_TIMING, model.parts.get(ref, {}))
        self.spec = row[1] if row else None
        self.pins = {}
        for pin, net in graph.pins_of(ref).items():
            node = ref + '.' + pin
            self.pins[node] = (pw.pin_aliases(graph.pinname.get(node), pin) or ('',)), net
        self.enable = self._net(self.spec['enable'] if self.spec else r'EN|SHDN|ON|EN/UVLO|UVLO')
        self.output = self._net(r'OUT|VOUT')
        self.driver_net, self.r_drive = self._drive()

    def _net(self, pattern):
        return next((net for names, net in self.pins.values()
                     if any(re.fullmatch(pattern, n, re.I) for n in names)), None)

    def status_kind(self, net):
        for names, pnet in self.pins.values():
            if pnet != net:
                continue
            for n in names:
                if self.spec and re.fullmatch(self.spec['pg'], n, re.I) or re.fullmatch(r'P(?:OWER)?_?G(?:OOD|D)?|PWRGD', n, re.I):
                    return 'PG'
                if re.fullmatch(r'FLT|FAULT', n, re.I):
                    return 'FLT'
                if re.fullmatch(r'IMON', n, re.I):
                    return 'IMON'
        return None

    def _drive(self):
        """The net that commands the enable through a series resistor, and that resistor."""
        if not self.enable:
            return None, None
        for ref, other in self.model.graph.neighbors(self.enable, {pw.RESISTOR}):
            if other in self.model.reset_nets or ng.is_ground(other) or self.model.rail_window(other):
                continue
            if self.model.driver(other):
                return other, ref
        return None, None


def _delay_leaf(model, device, leaf):
    """(diode, capacitor, charge resistor) when the leaf is an RC net that discharges into the device's enable
    through a forward diode, ('', None, None) when the leaf is the enable itself, else None."""
    if leaf == device.enable:
        return '', None, None
    graph = model.graph
    for ref, other in graph.neighbors(leaf, {pw.DIODE}):
        if other != device.enable:
            continue
        if graph.pin2net.get(graph.node_named(ref, 'anode') or '') != leaf:
            continue
        caps = model.caps_to_ground(leaf)
        charge = next((r for r in graph.between(leaf, device.enable, {pw.RESISTOR})), None)
        return ref, (caps[0] if caps else None), charge
    return None


def command_off(model, device, tree):
    """The normal shutdown row: leaf values when the enable is commanded low; returns (values, notes, missing)."""
    spec = device.spec
    values, notes, missing = {}, [], []
    for leaf in model.leaves(tree, (device.driver_net,)):
        kind = device.status_kind(leaf)
        if kind == 'PG':
            values[leaf] = 0
            notes.append('%s：关断后 PG 变低（%s）' % (_short(leaf), '消抖 ' + fmt_range(*spec['pg_fall']) if spec else '手册未入表'))
        elif kind == 'FLT':
            if spec and not spec['flt_on_enable']:
                values[leaf] = 1
                notes.append('%s：命令关断不置 FLT，保持高' % _short(leaf))
            else:
                missing.append('%s 关断时 FLT 是否置位（%s 手册）' % (_short(leaf), device.ref))
        elif leaf == device.driver_net:
            values[leaf] = 0
            notes.append('%s：关断命令为低' % _short(leaf))
        elif leaf in model.reset_nets:
            values[leaf] = 1
            notes.append('%s：复位网，正常运行时不有效' % _short(leaf))
        else:
            delay = _delay_leaf(model, device, leaf)
            if delay is None:
                missing.append('%s 在关断时的电平' % _short(leaf))
                continue
            value, text, need = _level_at_turnoff(model, device, tree, leaf, delay)
            values[leaf] = value
            notes.append(text)
            missing.extend(need)
    return values, notes, missing


def _level_at_turnoff(model, device, tree, leaf, delay):
    spec = device.spec
    gate = model.entry_gate(tree, leaf)
    th = model.thresholds(gate) if gate else None
    need = []
    if not spec:
        need.append('%s 关断门限（手册未入表）' % device.ref)
    if not th:
        need.append('%s 输入门限 VT−（手册未入表或供电轨电压未声明）' % (gate or '判据门'))
    if need:
        return None, '%s：判据输入网，关断时电平待算' % _short(leaf), need
    off_lo, off_hi = spec['off']
    diode, cap, charge = delay
    r = model.ohm(device.r_drive) if device.r_drive else 0.0
    if diode:
        i_lo, i_hi = (off_lo / r, off_hi / r) if r else (1.0, 1.0)
        vf = model.diode_vf(diode, i_lo)
        vf_hi = model.diode_vf(diode, i_hi)
        if vf and vf_hi:
            lvl = (off_lo + vf[0], off_hi + vf_hi[0])
            floor = off_lo + vf[1]
            vf_text = '%s 压降 %s–%s V（%s，%s）' % (diode, fmt_v(vf[0]), fmt_v(vf_hi[0]),
                                                   '放电电流 %.2g–%.2g mA' % (i_lo * 1e3, i_hi * 1e3), vf[2])
        else:
            lvl, floor = (off_lo, off_hi + 1.0), off_lo
            vf_text = '%s 压降未入表（下限按 0 V 计）' % diode
    else:
        lvl, floor, vf, vf_text = (off_lo, off_hi), off_lo, None, ''
    vtm_lo, vtm_hi = th[0], th[1]
    c = model.farad(cap) if cap else None
    tau = r * c if (r and c) else None
    t_pg = (spec['t_off'][1] if spec.get('t_off') else 0.0) + spec['pg_fall'][1]
    if floor > vtm_hi:
        # still above the gate threshold at turn-off; how long until it falls below, against PG going low
        vf_floor = vf[1] if vf else 0.0
        if tau is None:
            t_cross = None
        elif vtm_hi <= vf_floor:
            t_cross = math.inf
        else:
            t_cross = tau * math.log((floor - vf_floor) / (vtm_hi - vf_floor))
        # no series resistor: the driver pulls the enable and the net down at once, the level is not held
        value = 1 if r and (t_cross is None or t_cross > t_pg) else None
    elif lvl[1] < vtm_lo:
        value, t_cross = 0, 0.0
    else:
        value, t_cross = None, None
    text = ('%s：关管时 %s 在 %s（%s）%s，约 %s–%s V（高温曲线下限 %s V），对 %s 的 VT− %s–%s V%s' % (
        _short(leaf), device.enable.rsplit('/', 1)[-1], fmt_v(off_lo) + '–' + fmt_v(off_hi) + ' V', spec['off_note'],
        ('，加 ' + vf_text) if vf_text else '', fmt_v(lvl[0]), fmt_v(lvl[1]), fmt_v(floor), gate,
        fmt_v(vtm_lo), fmt_v(vtm_hi), {1: ' 仍判高', 0: ' 判低', None: ' 判不定'}[value]))
    if tau:
        text += '；放电时间常数 %s×%s = %s，降到 VT− 上限约需 %s，PG 在 %s 内变低' % (
            device.r_drive, cap, fmt_t(tau), fmt_t(t_cross) if t_cross is not None else '—', fmt_t(t_pg))
    return value, text + '（%s）' % th[4], []


def _short(net):
    return str(net).rsplit('/', 1)[-1]


def hot_insert(model, device, tree, requirement_cl):
    """PWR-A08 numbers: charge sharing on hot insertion of a load, the PG low time, against the PG deglitch.
    Returns (values, notes, missing, sums) or None when the device has no PGTH divider model."""
    spec = device.spec
    if not spec or 'pgth' not in spec or not device.output:
        return None
    graph = model.graph
    pgth_net = device._net(spec['pgth'][0])
    top = next((r for r in graph.between(device.output, pgth_net, {pw.RESISTOR})), None) if pgth_net else None
    bottom = next((r for r, o in graph.neighbors(pgth_net, {pw.RESISTOR}) if ng.is_ground(o)), None) if pgth_net else None
    ilim_net = device._net(spec['ilim'][0])
    r_ilim = next((r for r, o in graph.neighbors(ilim_net, {pw.RESISTOR}) if ng.is_ground(o)), None) if ilim_net else None
    window = model.rail_window(device.output)
    missing = []
    if not (top and bottom):
        missing.append('%s PGTH 分压读不出' % device.ref)
    if not r_ilim:
        missing.append('%s ILIM 电阻读不出' % device.ref)
    if not window:
        missing.append('%s 电压未声明' % device.output)
    caps = [c for c in model.caps_to_ground(device.output) if model.farad(c)]
    if missing:
        return {}, [], missing, None
    ratio = (model.ohm(top) + model.ohm(bottom)) / model.ohm(bottom)
    vth = (spec['pgth'][1][0] * ratio, spec['pgth'][1][1] * ratio)
    vout = window[1]
    cout = sum(model.farad(c) for c in caps)
    k, spread = spec['ilim'][1], spec['ilim'][2]
    i_nom = k / (model.ohm(r_ilim) / 1e3)
    ilim = (i_nom * (1 - spread), i_nom * (1 + spread))
    crit = (cout * (vout / vth[1] - 1), cout * (vout / vth[0] - 1)) if cout else (0.0, 0.0)
    loads = [requirement_cl] if requirement_cl else list(EXAMPLE_LOAD_F)
    rows = []
    for cl in loads:
        shared = vout * cout / (cout + cl)
        t = (cout + cl) * (vth[1] - shared) / ilim[1] if shared < vth[1] else 0.0
        rows.append((cl, shared, t))
    t_deg = spec['pg_fall'][1]
    worst = max(rows, key=lambda x: x[2])
    sums = {'vth': vth, 'crit': crit, 'ilim': ilim, 'rows': rows, 'deglitch': t_deg, 'cout': cout, 'vout': vout,
            'requirement': requirement_cl}
    notes = ['PG 门限：%s 经 %s/%s 分压，V(PGTHF) %s–%s V 对应输出 %s–%s V' % (
        _short(pgth_net), top, bottom, fmt_v(spec['pgth'][1][0]), fmt_v(spec['pgth'][1][1]), fmt_v(vth[0]), fmt_v(vth[1])),
        '输出电容 %s %s 与负载电容分电荷：负载电容大于约 %s–%s 就跌破 PG 门限（输出 %s V%s）' % (
            '+'.join(caps) or '无', fmt_f(cout), fmt_f(crit[0]), fmt_f(crit[1]), fmt_v(vout),
            '' if window[2] == 'intent.power_rails' else '，' + window[2]),
        '限流 %s %s：%s–%s A，充回门限：' % (r_ilim, model.parts[r_ilim].get('value'), '%.2f' % ilim[0], '%.2f' % ilim[1]) +
        '；'.join('%s%s 跌到 %s V，约 %s' % ('需求上限 ' if requirement_cl else '例 ', fmt_f(cl), fmt_v(sv), fmt_t(t))
                 for cl, sv, t in rows) +
        '，对 PG 下降消抖最大 %s' % fmt_t(t_deg)]
    if not requirement_cl:
        missing.append('需求没有允许热插入的负载电容上限（需求缺口，load_capacitance）')
    pg_drops = worst[2] > t_deg
    values = {}
    for leaf in model.leaves(tree, (device.driver_net,)):
        kind = device.status_kind(leaf)
        if kind == 'PG':
            values[leaf] = 0 if pg_drops else 1
        elif kind == 'FLT':
            values[leaf] = 1 if spec.get('flt_cl') and spec['flt_cl'][0] > worst[2] else None
        elif leaf == device.driver_net or leaf in model.reset_nets:
            values[leaf] = 1
        elif _delay_leaf(model, device, leaf) is not None:
            values[leaf] = 1
    if spec.get('flt_cl'):
        notes.append('限流期间 FLT 在 %s 后才置位，远长于充电时间' % fmt_t(spec['flt_cl'][0]))
    return values, notes, missing, sums


def requirement_load_capacitance(intent):
    best = None
    for req in (intent or {}).get('requirements') or []:
        for p in req.get('parameters') or []:
            if p.get('name') != 'load_capacitance':
                continue
            scale = {'F': 1, 'mF': 1e-3, 'µF': 1e-6, 'uF': 1e-6, 'nF': 1e-9}.get(p.get('unit'), None)
            value = p.get('max') if isinstance(p.get('max'), (int, float)) else p.get('value')
            if scale and isinstance(value, (int, float)):
                best = max(best or 0, value * scale)
    return best


def turn_on(model, device, tree, leaf, delay):
    """Retry: the delay net charges again while the output ramps; the delay must outlast PG assertion."""
    spec = device.spec
    diode, cap, charge = delay
    gate = model.entry_gate(tree, leaf)
    th = model.thresholds(gate) if gate else None
    if not (spec and spec.get('dvdt') and charge and cap and th and device.output and spec.get('pgth')):
        return None
    graph = model.graph
    dvdt_net = device._net(spec['dvdt'][0])
    c_dvdt = next((model.farad(r) for r, o in graph.neighbors(dvdt_net, {pw.CAPACITOR}) if ng.is_ground(o)), None) if dvdt_net else None
    pgth_net = device._net(spec['pgth'][0])
    top = next((r for r in graph.between(device.output, pgth_net, {pw.RESISTOR})), None) if pgth_net else None
    bottom = next((r for r, o in graph.neighbors(pgth_net, {pw.RESISTOR}) if ng.is_ground(o)), None) if pgth_net else None
    if not (c_dvdt and top and bottom):
        return None
    vrise = spec['pgth'][2][1] * (model.ohm(top) + model.ohm(bottom)) / model.ohm(bottom)
    t_pg = vrise * c_dvdt / (spec['dvdt'][1][0] * spec['dvdt'][2][0]) + spec['pg_rise'][1]
    supply = model.rail_window(next((n for p, n in graph.pins_of(gate).items()
                                     if re.fullmatch(r'VCC|VDD', str(graph.pinname.get(gate + '.' + p) or ''), re.I)), ''))
    vh = supply[1] if supply else 3.3
    tau = model.ohm(charge) * model.farad(cap)
    t_dly = tau * math.log(vh / (vh - th[2])) if vh > th[2] else math.inf
    ok = t_dly > t_pg
    return ok, '开启时 %s 经 %s×%s 充到 VT+ 下限约 %s，PG 置位最晚约 %s（dVdT 斜坡到 PG 门限加 tPGOODR，阻性负载）：%s' % (
        _short(leaf), charge, cap, fmt_t(t_dly), fmt_t(t_pg), '判据延时更长，开启不置锁' if ok else '判据先到期，开启过程置锁')


def scan(lint):
    """Run both scans on the lint's board: PRO-A06 per latch input per protection IC, PWR-A08 per hot-insert case."""
    model = Model(lint)
    load_cl = requirement_load_capacitance(model.intent)
    for ref, unit, pins in model.latches:
        for key in ('PRE', 'CLR'):
            node = pins.get(key)
            if not node:
                continue
            net = model.graph.pin2net.get(node)
            tree = model.tree(net)
            if tree[0] == 'LEAF':
                continue
            leaves = model.leaves(tree)
            devices = sorted({n.partition('.')[0] for leaf in leaves for n in model.graph.nodes_on(leaf)
                              if _protection_status(model, n)})
            latch_text = '%s.%s（%s，低有效）= %s' % (ref, key + unit, _short(net), Model.text(tree))
            for dref in devices:
                device = Device(model, dref)
                _report_normal(lint, model, device, tree, latch_text, ref)
                _report_hot_insert(lint, model, device, tree, latch_text, ref, load_cl)


def _protection_status(model, node):
    ref = node.partition('.')[0]
    if not model.graph.is_fitted(ref) or model.graph.kind(ref) != pw.IC:
        return False
    tabled = _table(PROTECTION_TIMING, model.parts.get(ref, {})) is not None
    if not (tabled or model.graph.role_kind(ref) == 'load_switch'):
        return False
    names = pw.pin_aliases(model.graph.pinname.get(node), node.partition('.')[2])
    return any(STATUS_PIN_RE.fullmatch(n) for n in names)


def _report_normal(lint, model, device, tree, latch_text, latch_ref):
    values, notes, missing = command_off(model, device, tree)
    state = Model.evaluate(tree, values)
    rows = ['命令关断：' + '；'.join(notes) + ' → 异步输入%s' % {0: '有效（锁存被置）', 1: '无效', None: '不定'}[state]]
    # MCU reset and power-up defaults
    if device.driver_net:
        reset_values = {}
        for leaf in model.leaves(model.tree(device.driver_net)):
            pull = _pull(model, leaf)
            if pull is not None:
                reset_values[leaf] = pull
            elif any(leaf == p.get('Q') for _, _, p in model.latches):
                reset_values[leaf] = 0
            elif any(leaf == p.get('QN') for _, _, p in model.latches):
                reset_values[leaf] = 1
        cmd = Model.evaluate(model.tree(device.driver_net), reset_values)
        rows.append('MCU 复位：命令输入取上下拉默认态、锁存未置，%s 为%s%s' % (
            _short(device.driver_net), {0: '低', 1: '高', None: '不定'}[cmd],
            '，等同命令关断（同上）' if cmd == 0 else ('，通道保持开' if cmd == 1 else '，按命令关断核')))
    power_up = {}
    for leaf in model.leaves(tree, (device.driver_net,)):
        kind = device.status_kind(leaf)
        if kind == 'PG':
            power_up[leaf] = 0
        elif leaf in model.reset_nets:
            power_up[leaf] = 0
        elif _delay_leaf(model, device, leaf) is not None and leaf != device.enable:
            power_up[leaf] = 0
    up = Model.evaluate(tree, power_up)
    rows.append('上电默认态：PG 低、延时电容未充、复位有效 → 异步输入%s' % {0: '有效（上电即置锁）', 1: '无效', None: '不定'}[up])
    retry = []
    for leaf in model.leaves(tree):
        delay = _delay_leaf(model, device, leaf)
        if delay and delay[0]:
            found = turn_on(model, device, tree, leaf, delay)
            if found:
                retry.append(found)
    rows.append('过流重试：先命令关断（同上）再开启' + ('；' + '；'.join(t for _, t in retry) if retry else '；开启时序读不出，审查员按启动时间核'))
    preset = state == 0 or up == 0 or any(not ok for ok, _ in retry)
    if not preset and state == 1 and up == 1:
        return   # every action leaves the async input inactive; what is not tabled cannot change that
    kind = 'FINDING' if preset else 'CANDIDATE'
    head = ('%s 的状态脚驱动外部锁存 %s：' % (device.ref, latch_text))
    tail = ('；缺：' + '；'.join(dict.fromkeys(missing))) if missing else ''
    lint.add('PRO-A06', '外部锁存判据在正常动作下成立' if preset else '外部锁存判据在正常动作下待核',
             head + '。'.join(rows) + tail + '。按 G05-098 逐动作核：把命令信号纳入判据或给判据输入网独立快速放电。',
             latch_ref, kind=kind, latch={'device': device.ref, 'actions': rows, 'missing': missing})


def _report_hot_insert(lint, model, device, tree, latch_text, latch_ref, load_cl):
    found = hot_insert(model, device, tree, load_cl)
    if found is None:
        return
    values, notes, missing, sums = found
    if sums is None:
        lint.add('PWR-A08', '热插入负载时状态脚触发外部锁存待核',
                 '%s 的 PG 驱动外部锁存 %s；缺：%s' % (device.ref, latch_text, '；'.join(missing)), latch_ref, kind='CANDIDATE')
        return
    state = Model.evaluate(tree, values)
    if state == 1:
        return
    pg_drops = values.get(next((l for l in model.leaves(tree) if device.status_kind(l) == 'PG'), ''), 1) == 0
    kind = 'FINDING' if state == 0 else 'CANDIDATE'
    lint.add('PWR-A08', '热插入负载时状态脚触发外部锁存' if state == 0 else '热插入负载时状态脚触发外部锁存待核',
             '%s 已开通道热插入负载：%s。%s → 异步输入%s%s。按 G03-017/G05-098：PG 低持续时间短于判据判定时间，或判据加时间限定。' % (
                 device.ref, '；'.join(notes), latch_text,
                 {0: '有效（锁存被置）', 1: '无效', None: '不定'}[state] if pg_drops else '无效（PG 不掉）',
                 ('；缺：' + '；'.join(missing)) if missing else ''),
             latch_ref, kind=kind, latch={'device': device.ref, 'hot_insert': {
                 'pg_threshold_out_v': [round(x, 3) for x in sums['vth']],
                 'critical_load_f': [round(x, 9) for x in sums['crit']],
                 'ilim_a': [round(x, 3) for x in sums['ilim']],
                 'recharge': [{'load_f': cl, 'shared_v': round(v, 3), 'time_s': t} for cl, v, t in sums['rows']],
                 'pg_deglitch_max_s': sums['deglitch']}, 'missing': missing})


def _pull(model, net):
    """1/0 when the net has a pull resistor to a rail/ground and no driver, else None."""
    if model.driver(net):
        return None
    for ref, other in model.graph.neighbors(net, {pw.RESISTOR}):
        if ng.is_ground(other):
            return 0
        if model.rail_window(other):
            return 1
    return None
