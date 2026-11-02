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
import part_words as pw  # noqa: E402

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
    baseline: dict = field(default=None, repr=False)
    intent: dict = field(default=None, repr=False)
    contract: dict = field(default_factory=dict)

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
    return pw.normalize(db.get('pinname', {}).get(node)).upper()


# --- operators --------------------------------------------------------------

def gnd_pin(db):
    """D-GND-PIN: move one IC ground pin onto a ground-named island."""
    g = graph(db)
    for ref in sorted(db['parts']):
        if g.kind(ref) != pw.IC or not fitted(db, ref):
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
        ic = [n for n in nodes if g.kind(n.split('.', 1)[0]) == pw.IC and fitted(db, n.split('.', 1)[0])]
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
        if g.kind(ref) != pw.CAPACITOR or not pins or not POLAR_RE.search(blob) or not fitted(db, ref):
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
        if g.kind(ref) != pw.CAPACITOR or not pins or not fitted(db, ref):
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
            if g.kind(rref) != pw.RESISTOR or not rpins:
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
        if g.kind(ref) != pw.TVS or not fitted(db, ref):
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
        if g.kind(ref) not in (pw.RELAY, pw.INDUCTOR) or not fitted(db, ref):
            continue
        coil = set(g.pins_of(ref).values())
        for dref in sorted(db['parts']):
            pins = two_pins(g, dref)
            if g.kind(dref) not in (pw.DIODE, pw.ZENER) or not pins or not fitted(db, dref):
                continue
            if {n for _, n in pins} <= coil and len({n for _, n in pins}) == 2:
                a, b = (dref + '.' + p for p, _ in pins)
                yield Mutation('D-FLY-MISS', ('DRV-A01',), (ref, dref), (), dref + ' removed', removed(db, dref))
                yield Mutation('D-FLY-REV', ('DRV-A02',), (ref, dref), (), 'swap ' + a + '/' + b, swapped(db, a, b))


def opto(db):
    """D-OPTO-R / D-OPTO-PU: drop the LED series resistor or the output pull-up."""
    g = graph(db)
    for ref in sorted(db['parts']):
        if g.kind(ref) != pw.OPTO or not fitted(db, ref):
            continue
        for pin, net in sorted(g.pins_of(ref).items()):
            pname = name(db, ref + '.' + pin)
            res = [n.split('.', 1)[0] for n in db['nets'].get(net, [])
                   if g.kind(n.split('.', 1)[0]) == pw.RESISTOR and fitted(db, n.split('.', 1)[0])]
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
            if (g.kind(ref) == pw.RESISTOR and pins and fitted(db, ref)
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


def i2c_value(db):
    """G04-017/018: retain real pull-up topology, violate its resistance window.

    10 Mohm cannot charge even 10 pF in the Standard-mode 1 us window;
    1 ohm requires amperes at normal logic rails. Board budgets still need review.
    """
    for m in i2c_pu(db):
        for defect, value in (('D-I2C-PU-HIGH', '10Meg'), ('D-I2C-PU-LOW', '1R')):
            out = copy.deepcopy(db)
            for ref in m.refs:
                out['parts'][ref]['value'] = value
            yield Mutation(defect, ('SIG-C01',), m.refs, m.nets,
                           ','.join(m.refs) + ' -> ' + value, out)


def usb_bulk(db):
    """G01-029: enlarge a capacitor directly on a USB VBUS/VUSB net.

    Deliberately does not mutate a capacitor behind an inrush limiter. Role and
    external limiting are not in the cold db: each site remains a hypothesis.
    """
    g = graph(db)
    for ref in sorted(db['parts']):
        pins = two_pins(g, ref)
        if g.kind(ref) != pw.CAPACITOR or not pins or not fitted(db, ref):
            continue
        if (any(re.search(r'(^|[/_])(VBUS|VUSB)($|[_/])', n, re.I) for _, n in pins)
                and any(ng.is_ground(n) for _, n in pins)):
            out = copy.deepcopy(db)
            out['parts'][ref]['value'] = '1000uF 50V'
            yield Mutation('D-USB-BULK', ('SIG-C05',), (ref,), (), ref + ' -> 1000uF', out)


def isolation_bridge(db):
    """G04-040: bridge two distinct ground domains of a real isolator/opto.

    Only optos or explicitly named digital isolator families with two ground
    domains are eligible; a generic multi-ground IC is not an isolator.
    """
    g = graph(db)
    for ref in sorted(db['parts']):
        part = db['parts'][ref]
        identity = ' '.join(str(part.get(k, '')) for k in ('prim', 'part', 'value'))
        isolator = g.kind(ref) == pw.OPTO or re.search(r'ADuM|ADM2483|ADM3251|CA-IS37', identity, re.I)
        if not isolator or not fitted(db, ref):
            continue
        grounds = sorted({n for n in g.pins_of(ref).values() if ng.is_ground(n)})
        if len(grounds) != 2:
            continue
        out = copy.deepcopy(db)
        for node, net in list(out['pin2net'].items()):
            if net == grounds[1]:
                out['pin2net'][node] = grounds[0]
        yield Mutation('D-ISO-BRIDGE', ('PRO-D02',), (ref,), tuple(grounds),
                       'short ' + ' / '.join(grounds), rebuild(out))


def crystal_load(db):
    """G04-078: load a real passive crystal with 1 uF to ground.

    Preserve the existing crystal and its oscillator wiring; only change the
    existing load capacitors, never invent a clock source from its net name.
    """
    g = graph(db)
    for ref in sorted(db['parts']):
        if g.kind(ref) != pw.CRYSTAL or not fitted(db, ref):
            continue
        nets = set(g.pins_of(ref).values())
        caps = []
        for cref in sorted(db['parts']):
            pins = two_pins(g, cref)
            if (g.kind(cref) == pw.CAPACITOR and pins and fitted(db, cref)
                    and any(n in nets and not ng.is_ground(n) for _, n in pins)
                    and any(ng.is_ground(n) for _, n in pins)):
                caps.append(cref)
        if caps:
            out = copy.deepcopy(db)
            for cref in caps:
                out['parts'][cref]['value'] = '1uF'
            yield Mutation('D-XTAL-LOAD', ('CLK-C01',), (ref, *caps), (),
                           ','.join(caps) + ' -> 1uF', out)


def regulator_cout(db):
    """G03-003: remove all direct output capacitors of an identified LDO family.

    Source pin name and family must both match. Remote/external capacitance and
    the exact variant's minimum Cout remain human evidence, not cold-db facts.
    """
    g = graph(db)
    for ref, part in sorted(db['parts'].items()):
        identity = ' '.join(str(part.get(k, '')) for k in ('prim', 'part', 'value'))
        if not fitted(db, ref) or not re.search(r'AMS1117|LM1117|AP2112|MCP1700|XC6206', identity, re.I):
            continue
        for pin, net in sorted(g.pins_of(ref).items()):
            if not re.fullmatch(r'V?OUT', name(db, ref + '.' + pin), re.I):
                continue
            caps = []
            for cref in sorted(db['parts']):
                pins = two_pins(g, cref)
                if (g.kind(cref) == pw.CAPACITOR and pins and fitted(db, cref)
                        and net in {n for _, n in pins}
                        and any(ng.is_ground(n) for _, n in pins)):
                    caps.append(cref)
            if caps:
                out = db
                for cref in caps:
                    out = removed(out, cref)
                yield Mutation('D-LDO-COUT', ('PWR-C04',), (ref, *caps), (net,),
                               'remove output capacitors ' + ','.join(caps), out)


def can_termination(db):
    """G04-032: bridge actual transceiver CAN H/L pins, bypassing termination.

    Corpus end resistors are switchable, so matching only a resistor directly
    across named H/L nets would produce no sites. A wire short across the
    transceiver's physical bus pins is unambiguous regardless of jumper state.
    """
    g = graph(db)
    for ref in sorted(db['parts']):
        if g.kind(ref) != pw.IC or not fitted(db, ref):
            continue
        by_name = {name(db, ref + '.' + p).upper(): n for p, n in g.pins_of(ref).items()}
        if not {'CANH', 'CANL'} <= set(by_name):
            continue
        high, low = by_name['CANH'], by_name['CANL']
        if high == low:
            continue
        out = copy.deepcopy(db)
        for node, net in list(out['pin2net'].items()):
            if net == low:
                out['pin2net'][node] = high
        yield Mutation('D-CAN-TERM-SHORT', ('SIG-C03',), (ref,), (high, low),
                       'wire short CAN H/L, bypass termination', rebuild(out))


def crystal_shared(db):
    """G04-082: duplicate a real oscillator IC, sharing the same passive crystal.

    Clone all pins/metadata, so the extra oscillator is supplied and configured
    as the original. Other shared outputs may also need review; the intended
    counterexample is two active oscillator stages on one crystal.
    """
    g = graph(db)
    for ref in sorted(db['parts']):
        if g.kind(ref) != pw.CRYSTAL or not fitted(db, ref):
            continue
        oscillator_nets = {n for n in g.pins_of(ref).values() if not ng.is_ground(n)}
        if len(oscillator_nets) != 2:
            continue
        for ic in sorted(db['parts']):
            if g.kind(ic) != pw.IC or not fitted(db, ic):
                continue
            clock_pins = {n for p, n in g.pins_of(ic).items()
                          if re.fullmatch(r'XI|XO|XIN|XOUT|XTAL[12]|OSC_IN|OSC_OUT', name(db, ic + '.' + p), re.I)}
            if not oscillator_nets <= clock_pins:
                continue
            new = ic + '_SEED'
            if new in db['parts']:
                continue
            out = copy.deepcopy(db)
            out['parts'][new] = copy.deepcopy(db['parts'][ic])
            for key in ('pin2net', 'pinname', 'pintype', 'declared_pintype'):
                for node, value in list(db.get(key, {}).items()):
                    if node.split('.', 1)[0] == ic:
                        out[key][new + '.' + node.split('.', 1)[1]] = value
            if ic in out.get('ref2page', {}):
                out['ref2page'][new] = out['ref2page'][ic]
            out['no_connect_nodes'] = list(out.get('no_connect_nodes', [])) + [
                new + '.' + node.split('.', 1)[1] for node in db.get('no_connect_nodes', [])
                if node.split('.', 1)[0] == ic]
            yield Mutation('D-XTAL-SHARED', ('CLK-C01',), (ref, ic, new), tuple(sorted(oscillator_nets)),
                           'clone ' + ic + ' as ' + new + ' on the same crystal', rebuild(out))
            break


OPERATORS = (gnd_pin, rail_split, cap_pol, cap_vr, led_r, tvs_stub, en_float, flyback, opto, i2c_pu,
             ref_anno, bom_ws, i2c_value, usb_bulk, isolation_bridge, crystal_load,
             regulator_cout, can_termination, crystal_shared)


def mutations(db, per_operator=4):
    """At most per_operator sites per operator per board keeps one run under a minute."""
    for op in OPERATORS:
        seen = {}
        for mutation in op(db):
            if seen.get(mutation.defect, 0) < per_operator:
                seen[mutation.defect] = seen.get(mutation.defect, 0) + 1
                yield mutation


# Controlled pairs from the four adjudicated boards. Corrected baselines are
# synthetic parameter contracts, never a claim that the source board was clean.
def board_mutations(db):
    g = ng.NetGraph(db)
    from solve_dividers import parse_resistor

    def present(ref):
        return ref in db.get('parts', {}) and fitted(db, ref)

    def model(ref):
        return str(db.get('parts', {}).get(ref, {}).get('part', ''))

    def rail_intent(net, voltage, citation):
        return {'schema_version': 5, 'power_rails': {net: {
            'voltage_v': {'min': voltage, 'max': voltage}, 'citation': citation}}}

    for ref, pattern, voltage, rating, source in (
            ('D54', r'TPD1E0B04DPYR', 5.0, 3.6, 'TI TPD1E0B04 datasheet recommended working range, adjudication lane-1 F058'),
            ('D22', r'PTVS9V0S1UR,115', 15.0, 9.0, 'Nexperia PTVS9V0S1UR VRWM=9V, adjudication lane-2 F49')):
        if not present(ref) or not re.fullmatch(pattern, model(ref)):
            continue
        nets = g.nets_of(ref)
        rails = [n for n in nets if not ng.is_ground(n)]
        if len(rails) != 1 or not any(ng.is_ground(n) for n in nets):
            continue
        base = copy.deepcopy(db)
        # Explicit synthetic compliant TVS, without inventing an orderable MPN.
        base['parts'][ref].update(part='SEED_PARAMETER_CONTRACT_TVS', prim='Device:D_TVS',
                                  value='TVS VRWM=%gV' % (voltage + 3))
        contract = {'normal_v': voltage, 'mutant_vrwm_v': rating, 'source': source,
                    'baseline': 'synthetic TVS working-voltage contract, not an orderable MPN'}
        yield Mutation('D-TVS-VRWM', ('PRO-E02',), (ref,), tuple(rails),
                       'replace compliant working-voltage contract with ' + model(ref), copy.deepcopy(db),
                       baseline=base, intent=rail_intent(rails[0], voltage, 'SEED contract: source schematic operating mode p1'),
                       contract=contract)

    caps = ('C139', 'C140')
    if all(present(r) and model(r) == 'C1005X6S1A105K050BC' for r in caps):
        common = set(g.nets_of(caps[0])) & set(g.nets_of(caps[1]))
        rails = [n for n in common if not ng.is_ground(n)]
        if len(rails) == 1 and any(ng.is_ground(n) for n in common):
            base, out = copy.deepcopy(db), copy.deepcopy(db)
            for ref in caps:
                base['parts'][ref].update(part='SEED_PARAMETER_CONTRACT_MLCC_25V', value='1u/25V')
                # Rating is bound by the exact manufacturer record below, not inferred from the model digits.
                out['parts'][ref]['value'] = '1u/10V'
            yield Mutation('D-MLCC-RATING-BELOW-PD', ('DEV-A01', 'DEV-C01'), caps, tuple(rails),
                           '25V synthetic contract -> exact TDK 10V MLCC under controlled 15V mode', out,
                           baseline=base, intent=rail_intent(rails[0], 15, 'SEED contract: source schematic 15V3A p8'),
                           contract={'normal_v': 15, 'rating_v': 10, 'mpn': 'C1005X6S1A105K050BC',
                                     'source': 'https://product.tdk.com/en/search/capacitor/ceramic/mlcc/info?part_no=C1005X6S1A105K050BC'})

    if (present('R199') and model('R199') == 'CR1206-J/-000ELF' and len(g.nets_of('R199')) == 2
            and (parse_resistor(db['parts']['R199'].get('value')) or {}).get('kohm') == .000005):
        base = copy.deepcopy(db)
        base['parts']['R199']['part'] = 'SEED_PARAMETER_CONTRACT_5mOhm'
        yield Mutation('D-SHUNT-MPN-CONFLICT', ('DEV-D04',), ('R199',), tuple(g.nets_of('R199')),
                       'keep 5mOhm value and Kelvin topology, replace MPN with 0Ohm CR1206-J/-000ELF', copy.deepcopy(db),
                       baseline=base, contract={'value_ohm': .005, 'mpn_ohm': 0,
                                               'source': 'Bourns CR1206-J/-000ELF qualification; lane-3 F146'})

    if (all(present(r) and model(r) == 'PAC1954T-E/4MX' for r in ('U19', 'U20'))
            and db['pin2net'].get('U19.6') == db['pin2net'].get('U20.6') == '3V3_SYS'
            and all(db.get('pinname', {}).get(r + '.6') == 'ADDRSEL' for r in ('U19','U20'))
            and all(db['pin2net'].get('U19.' + pin) == db['pin2net'].get('U20.' + pin)
                    and db['pin2net'].get('U19.' + pin) not in (None, 'GND')
                    for pin in ('4','5'))):
        base = moved(db, 'U20.6', 'GND')
        yield Mutation('D-I2C-ADDRESS-COLLISION', ('SIG-D01',), ('U19', 'U20'), ('3V3_SYS',),
                       'U20 ADDRSEL GND (0x10) -> VDD (0x1F), matching U19', copy.deepcopy(db), baseline=base,
                       contract={'pin': 'ADDRSEL.6', 'baseline_addresses': [31, 16], 'mutant_addresses': [31, 31],
                                 'source': 'Microchip PAC1954 DS20006539D address selection; lane-3 F147'})

    if (present('U36') and model('U36') == '74LCX07BQX'
            and 'U36.13' in db.get('no_connect_nodes', [])):
        base = moved(db, 'U36.13', 'GND')
        base['no_connect_nodes'] = [n for n in base.get('no_connect_nodes', []) if n != 'U36.13']
        yield Mutation('D-CMOS-UNUSED-IN-FLOAT', ('NET-A07', 'DEV-D05'), ('U36',), (),
                       'disconnect unused input A5.13; retain output O5.12 and DAP NC markers', copy.deepcopy(db), baseline=base,
                       contract={'input': 'U36.13', 'source': 'onsemi 74LCX07/D Rev2 p3 note4, lane-4 F219'})

    if present('Y2') and model('Y2') == 'ABM8G-12.000MHZ-18-D2Y-T':
        for mutation in crystal_load(db):
            if 'Y2' in mutation.refs and {'C190', 'C193'} <= set(mutation.refs):
                mutation.contract = {'cl_pf': 18, 'capacitors': ['C190', 'C193'],
                                     'source': 'Abracon ABM8G ordering code CL=18pF, lane-3 M01'}
                yield mutation
                break
