"""Seeded-defect operators on a parsed db.json (parse_kicad / parse_netlist output).

Each operator enumerates every applicable site on a board and yields Mutation
records. Operators mirror the blind-calibration defect library (D-* types) but
only those expressible as a netlist edit; datasheet-dependent defects stay in
the human loop. A mutation is a hypothesis about a real defect, not proof that
every site is electrically wrong: the bench measures whether SR *notices*.
"""
import copy
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from checkers import netgraph as ng  # noqa: E402

EN_RE = re.compile(r'^~?\{?(EN|ENABLE|CE|SHDN|ON|RUN)\}?$', re.I)
I2C_RE = re.compile(r'(^|[/:_-])(SDA|SCL)\d*($|[:_-])', re.I)
POLAR_RE = re.compile(r'C_?POL|\bCP\b|CP_|ELEC|TANT|POLARI[SZ]ED', re.I)
ISO_PREFIX = 'SEED_ISO_'
# Site selection must not inherit SR's own rail heuristics, or a gap there hides
# whole defect classes from the bench. KiCad power symbols are +5V, +3V3, VUSB...
RAIL_LIKE_RE = re.compile(r'^\+|^(VCC|VDD|VBUS|VUSB|VIN|VBAT|VSYS|VOUT|V\d)|\d+V\d*$', re.I)
LED_PIN_RE = re.compile(r'^(A|ANODE|ANOD\w*|K|CATHODE|CATHOD\w*|KATOD\w*)$', re.I)
COLLECTOR_RE = re.compile(r'^(C|COLLECTOR|COLL\w*|KOLEK\w*)$', re.I)


def rail_like(net):
    return bool(net) and not ng.is_ground(net) and bool(RAIL_LIKE_RE.search(str(net).lstrip('/')))


@dataclass
class Mutation:
    defect: str
    targets: tuple
    refs: tuple
    nets: tuple
    note: str
    db: dict = field(repr=False)

    @property
    def site(self):
        return '+'.join(self.refs + self.nets)


def rebuild(db):
    nets = {}
    for node, net in db['pin2net'].items():
        nets.setdefault(net, []).append(node)
    db['nets'] = {net: sorted(nodes) for net, nodes in sorted(nets.items())}
    db['pseudo_nets'] = [n for n in db.get('pseudo_nets', []) if n in db['nets']]
    return db


def moved(db, node, net):
    out = copy.deepcopy(db)
    out['pin2net'][node] = net
    return rebuild(out)


def removed(db, ref):
    out = copy.deepcopy(db)
    del out['parts'][ref]
    for key in ('pin2net', 'pinname', 'pintype', 'declared_pintype'):
        for node in [n for n in out.get(key, {}) if n.split('.', 1)[0] == ref]:
            del out[key][node]
    out.get('ref2page', {}).pop(ref, None)
    out['no_connect_nodes'] = [n for n in out.get('no_connect_nodes', []) if n.split('.', 1)[0] != ref]
    return rebuild(out)


def swapped(db, a, b):
    out = copy.deepcopy(db)
    out['pin2net'][a], out['pin2net'][b] = db['pin2net'][b], db['pin2net'][a]
    return rebuild(out)


def graph(db):
    return ng.NetGraph(db)


def fitted(db, ref):
    return not db['parts'][ref].get('nc')


def two_pins(g, ref):
    pins = g.pins_of(ref)
    return sorted(pins.items()) if len(pins) == 2 else None


def name(db, node):
    return ng.normalize(db.get('pinname', {}).get(node)).upper()


# --- operators --------------------------------------------------------------

def gnd_pin(db):
    """D-GND-PIN: move one IC ground pin onto a ground-named island."""
    g = graph(db)
    for ref in sorted(db['parts']):
        if g.kind(ref) != ng.IC or not fitted(db, ref):
            continue
        gnd = sorted(n for n, net in db['pin2net'].items() if n.split('.', 1)[0] == ref and ng.is_ground(net))
        if len(gnd) >= 2:
            yield Mutation('D-GND-PIN', ('PWR-A03',), (ref,), ('GNDA',), gnd[-1] + ' -> GNDA', moved(db, gnd[-1], 'GNDA'))


def rail_split(db):
    """D-RAIL-SPLIT: one IC supply pin moves to a near-identical rail name."""
    g = graph(db)
    for net, nodes in sorted(db['nets'].items()):
        if not ng.is_rail(net) or len(nodes) < 3:
            continue
        ic = [n for n in nodes if g.kind(n.split('.', 1)[0]) == ng.IC and fitted(db, n.split('.', 1)[0])]
        if ic:
            twin = net + '_1' if not net.endswith('_1') else net + 'A'
            yield Mutation('D-RAIL-SPLIT', ('PWR-A04', 'NET-A02', 'PWR-A01', 'PWR-A02'),
                           (ic[0].split('.', 1)[0],), (twin,), ic[0] + ' -> ' + twin, moved(db, ic[0], twin))


def cap_pol(db):
    """D-CAP-POL: swap the two nets of a polarized capacitor across rail/ground."""
    g = graph(db)
    for ref, part in sorted(db['parts'].items()):
        pins = two_pins(g, ref)
        blob = ' '.join(str(part.get(k, '')) for k in ('prim', 'part', 'value'))
        if g.kind(ref) != ng.CAPACITOR or not pins or not POLAR_RE.search(blob) or not fitted(db, ref):
            continue
        nets = [net for _, net in pins]
        if any(ng.is_ground(n) for n in nets):
            a, b = (ref + '.' + p for p, _ in pins)
            yield Mutation('D-CAP-POL', ('DEV-A02',), (ref,), (), 'swap ' + a + '/' + b, swapped(db, a, b))


def cap_vr(db):
    """D-CAP-VR: state a voltage rating below the rail the capacitor sits on."""
    g = graph(db)
    for ref, part in sorted(db['parts'].items()):
        pins = two_pins(g, ref)
        if g.kind(ref) != ng.CAPACITOR or not pins or not fitted(db, ref):
            continue
        volts = [ng.rail_voltage(net) for _, net in pins if rail_like(net)]
        volts = [v for v in volts if v and v >= 5]
        if volts and any(ng.is_ground(net) for _, net in pins):
            low = '6.3V' if max(volts) > 6.3 else '4V'
            out = copy.deepcopy(db)
            out['parts'][ref]['value'] = str(part.get('value', '')).strip() + ' ' + low
            yield Mutation('D-CAP-VR', ('DEV-A01',), (ref,), (), 'value + ' + low + ' on ' + str(max(volts)) + 'V', out)


def led_r(db):
    """D-LED-R: short the series resistor of an LED that sits between a rail and ground."""
    g = graph(db)
    for ref in sorted(db['parts']):
        pins = two_pins(g, ref)
        blob = ' '.join(str(db['parts'][ref].get(k, '')) for k in ('prim', 'part', 'value'))
        if not pins or not re.search(r'LED', blob, re.I) or not fitted(db, ref):
            continue
        for pin, net in pins:
            other = [n for n in db['nets'].get(net, []) if n.split('.', 1)[0] != ref]
            if len(other) != 1:
                continue
            rref = other[0].split('.', 1)[0]
            rpins = two_pins(g, rref)
            if g.kind(rref) != ng.RESISTOR or not rpins:
                continue
            far = [n for p, n in rpins if rref + '.' + p != other[0]][0]
            mine = [n for p, n in pins if p != pin][0]
            if (rail_like(far) and ng.is_ground(mine)) or (ng.is_ground(far) and rail_like(mine)):
                out = copy.deepcopy(db)
                # A 0R in series is a short: merge the LED node onto the far net.
                out['pin2net'][ref + '.' + pin] = far
                out = removed(rebuild(out), rref)
                yield Mutation('D-LED-R', ('DEV-A03',), (ref, rref), (), rref + ' shorted', out)


def tvs_stub(db):
    """D-TVS-STUB: the protected-line end of a TVS/ESD part goes to an isolated label."""
    g = graph(db)
    for ref in sorted(db['parts']):
        if g.kind(ref) != ng.TVS or not fitted(db, ref):
            continue
        for pin, net in sorted(g.pins_of(ref).items()):
            if not ng.is_ground(net) and len(db['nets'].get(net, [])) >= 2:
                iso = ISO_PREFIX + ref
                yield Mutation('D-TVS-STUB', ('PRO-A01',), (ref,), (iso,), ref + '.' + pin + ' -> ' + iso,
                               moved(db, ref + '.' + pin, iso))
                break


def en_float(db):
    """D-EN-FLOAT: an IC enable pin goes to an isolated label (floating)."""
    for node in sorted(db['pin2net']):
        ref = node.split('.', 1)[0]
        if ref.startswith(('U', 'IC')) and EN_RE.match(name(db, node)) and fitted(db, ref):
            iso = ISO_PREFIX + ref + '_EN'
            yield Mutation('D-EN-FLOAT', ('RST-A01', 'RST-A03', 'RST-A04', 'NET-A07'), (ref,), (iso,),
                           node + ' -> ' + iso, moved(db, node, iso))


def flyback(db):
    """D-FLY-MISS / D-FLY-REV on diodes directly across a relay coil or inductor."""
    g = graph(db)
    for ref in sorted(db['parts']):
        if g.kind(ref) not in (ng.RELAY, ng.INDUCTOR) or not fitted(db, ref):
            continue
        coil = set(g.pins_of(ref).values())
        for dref in sorted(db['parts']):
            pins = two_pins(g, dref)
            if g.kind(dref) not in (ng.DIODE, ng.ZENER) or not pins or not fitted(db, dref):
                continue
            if {n for _, n in pins} <= coil and len({n for _, n in pins}) == 2:
                a, b = (dref + '.' + p for p, _ in pins)
                yield Mutation('D-FLY-MISS', ('DRV-A01',), (ref, dref), (), dref + ' removed', removed(db, dref))
                yield Mutation('D-FLY-REV', ('DRV-A02',), (ref, dref), (), 'swap ' + a + '/' + b, swapped(db, a, b))


def opto(db):
    """D-OPTO-R / D-OPTO-PU: drop the LED series resistor or the output pull-up."""
    g = graph(db)
    for ref in sorted(db['parts']):
        if g.kind(ref) != ng.OPTO or not fitted(db, ref):
            continue
        for pin, net in sorted(g.pins_of(ref).items()):
            pname = name(db, ref + '.' + pin)
            res = [n.split('.', 1)[0] for n in db['nets'].get(net, [])
                   if g.kind(n.split('.', 1)[0]) == ng.RESISTOR and fitted(db, n.split('.', 1)[0])]
            if len(res) != 1:
                continue
            if LED_PIN_RE.match(pname):
                yield Mutation('D-OPTO-R', ('PRO-A03',), (ref, res[0]), (), res[0] + ' removed', removed(db, res[0]))
            elif COLLECTOR_RE.match(pname):
                yield Mutation('D-OPTO-PU', ('PRO-A04',), (ref, res[0]), (), res[0] + ' removed', removed(db, res[0]))


def i2c_pu(db):
    """D-I2C-PU: remove every pull-up resistor from an SDA/SCL net."""
    g = graph(db)
    for net, nodes in sorted(db['nets'].items()):
        if not I2C_RE.search(net):
            continue
        pulls = []
        for node in nodes:
            ref = node.split('.', 1)[0]
            pins = two_pins(g, ref)
            # Pull-up: the far end is not a bus line and not ground (it may reach the
            # rail through a solder jumper, so do not require a rail name there).
            if (g.kind(ref) == ng.RESISTOR and pins and fitted(db, ref)
                    and not any(ng.is_ground(n) or (n != net and I2C_RE.search(n)) for _, n in pins)):
                pulls.append(ref)
        if pulls:
            out = db
            for ref in pulls:
                out = removed(out, ref)
            yield Mutation('D-I2C-PU', ('SIG-A03', 'SIG-E01', 'SIG-C01'), tuple(pulls), (net,),
                           'removed ' + ','.join(pulls), out)


def ref_anno(db):
    """D-REF-ANNO: one designator becomes unannotated (R?)."""
    for ref in sorted(db['parts'])[:1]:
        new = re.sub(r'\d+$', '', ref) + '?'
        out = copy.deepcopy(db)
        out['parts'][new] = out['parts'].pop(ref)
        for key in ('pin2net', 'pinname', 'pintype', 'declared_pintype'):
            for node in [n for n in out.get(key, {}) if n.split('.', 1)[0] == ref]:
                out[key][new + '.' + node.split('.', 1)[1]] = out[key].pop(node)
        if ref in out.get('ref2page', {}):
            out['ref2page'][new] = out['ref2page'].pop(ref)
        yield Mutation('D-REF-ANNO', ('DOC-A04',), (new,), (), ref + ' -> ' + new, rebuild(out))


def bom_ws(db):
    """D-BOM-WS: trailing whitespace in one VALUE field."""
    for ref in sorted(db['parts'])[:1]:
        out = copy.deepcopy(db)
        out['parts'][ref]['value'] = str(out['parts'][ref].get('value', '')) + ' '
        yield Mutation('D-BOM-WS', ('DOC-A03',), (ref,), (), 'value + trailing space', out)


OPERATORS = (gnd_pin, rail_split, cap_pol, cap_vr, led_r, tvs_stub, en_float, flyback, opto, i2c_pu,
             ref_anno, bom_ws)


def mutations(db, per_operator=4):
    """At most per_operator sites per operator per board keeps one run under a minute."""
    for op in OPERATORS:
        seen = {}
        for mutation in op(db):
            if seen.get(mutation.defect, 0) < per_operator:
                seen[mutation.defect] = seen.get(mutation.defect, 0) + 1
                yield mutation
