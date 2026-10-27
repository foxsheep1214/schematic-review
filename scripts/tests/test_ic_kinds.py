"""Integrated circuits carry a datasheet-verified kind like discretes do, and the kind names their role.

An anchor for circuit candidates is an IC whose kind says what it does (PWM controller, gate driver,
synchronous-rectifier controller, PD controller, regulator, supervisor ...). The declaration mechanism is
the existing intent.device_kinds (page + verbatim quote, verified by the datasheet audit); only the
vocabulary and the obligation grow: every fitted U/M part needs one, a generic `ic` is accepted only when
its quote names no role kind, and the planner lists the missing declaration as a DEV-D02 gap.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import board_intent
import catalog
import datasheet_kinds as dk
from checkers import netgraph as ng
import part_words as pw
from plan_review import build_review_plan
import test_inductive_load as fixture

ROLE_QUOTES = {
    'pwm_controller': 'High Voltage Current Mode PWM Controller for flyback converters',
    'gate_driver': 'Dual Low-Side MOSFET Gate Driver',
    'sr_controller': 'Synchronous Rectifier Controller for Flyback Converters',
    'pd_controller': 'USB Type-C and Power Delivery (PD) controller',
    'regulator': 'Low Dropout Voltage Regulator, 300 mA',
    'supervisor': 'Microprocessor Supervisor with watchdog timer',
    'opamp_comparator': 'Dual Low-Power Operational Amplifier',
    'shunt_reference': 'Adjustable Precision Shunt Regulator',
    'mcu': '32-bit Arm Cortex-M0+ Microcontroller',
    'transceiver': 'High-Speed CAN Transceiver',
    'isolator': 'Dual-Channel Digital Isolator',
    'load_switch': 'Load Switch with Adjustable Current Limit',
    'charger': 'Switch-Mode Li-Ion Battery Charger with Buck Regulator',
    'adc_dac': '24-Bit Delta-Sigma ADC with PGA',
    'oscillator': 'Low-Jitter Crystal Oscillator',
    'memory': '128-Mbit Serial Flash Memory with Quad SPI',
    'level_shifter': 'Bidirectional Voltage-Level Translator',
    'motor_driver': 'H-Bridge Motor Driver with Current Regulation',
}


def board():
    db = {'nets': {}, 'parts': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {}, 'pseudo_nets': [], 'ref2page': {}}
    add = fixture.add
    add(db, 'U1', 'CTRL-8', [('1', 'VCC', 'VCC'), ('2', 'GND', 'GND'), ('3', 'DRV', 'GATE'), ('4', 'FB', 'FB')])
    add(db, 'Q1', 'MOSFET-N', [('1', 'G', 'GATE'), ('2', 'D', 'SW'), ('3', 'S', 'GND')])
    add(db, 'R1', '10R', [('1', '1', 'GATE'), ('2', '2', 'GND')])
    add(db, 'C1', '1uF', [('1', '1', 'VCC'), ('2', '2', 'GND')])
    return db


def verified(db, kinds):
    intent = {'schema_version': 5, 'input_sha256': board_intent.input_fingerprint(db), 'device_kinds': {}}
    audit = {'device_kinds': {}}
    for ref, kind in kinds.items():
        declaration = {'kind': kind, 'page': 1, 'quote': ROLE_QUOTES.get(kind, 'synthetic ' + kind)}
        intent['device_kinds'][ref] = declaration
        audit['device_kinds'][ref] = dict(declaration, status='VERIFIED', document='synthetic.pdf',
                                          document_sha256='a' * 64)
    return intent, audit


class VocabularyTests(unittest.TestCase):
    def test_every_ic_role_kind_is_a_declarable_device_kind(self):
        for kind in board_intent.IC_KINDS:
            self.assertIn(kind, board_intent.DEVICE_KINDS)
        self.assertIn('ic', board_intent.IC_KINDS)
        self.assertEqual(board_intent.device_kind_errors({'U1': {'kind': 'pwm_controller', 'page': 1, 'quote': 'x'}}, None), [])
        self.assertTrue(any('kind must be one of' in e for e in
                            board_intent.device_kind_errors({'U1': {'kind': 'controller', 'page': 1, 'quote': 'x'}}, None)))

    def test_anchor_kinds_are_the_registry_roles_with_circuit_types(self):
        self.assertEqual(set(board_intent.ANCHOR_KINDS),
                         {name for name, role in catalog.DEVICE_ROLES.items() if role.circuits})
        self.assertEqual(set(board_intent.ANCHOR_KINDS) & {'ic', 'isolator'}, set())
        for role in ('pwm_controller', 'regulator', 'mcu', 'transceiver', 'load_switch', 'memory', 'oscillator'):
            self.assertIn(role, board_intent.ANCHOR_KINDS)

    def test_every_role_list_reads_the_registry(self):
        """The five former copies of the role list are views of catalog.DEVICE_ROLES."""
        roles = tuple(catalog.DEVICE_ROLES)
        self.assertEqual(board_intent.IC_KINDS, roles)
        self.assertEqual(pw.IC_ROLES, frozenset(roles))
        self.assertEqual(pw.ANCHOR_ROLES, frozenset(board_intent.ANCHOR_KINDS))
        self.assertEqual(dk.IC_ROLE_CUES, set(roles) - {'ic'})
        self.assertEqual(dict(dk.KIND_CUES)['load_switch'], catalog.DEVICE_ROLES['load_switch'].cues)
        self.assertEqual(catalog.device_role_errors(), [])
        self.assertEqual(roles[-1], 'ic')
        self.assertEqual(catalog.DEVICE_ROLES['ic'].cues, ())


class QuoteVerificationTests(unittest.TestCase):
    def page(self, text):
        return lambda path, page: text if page == 1 else None

    def test_each_role_kind_is_named_by_its_own_quote(self):
        for kind, quote in ROLE_QUOTES.items():
            with self.subTest(kind=kind):
                self.assertEqual(dk.cues(quote), {kind}, quote)
                result = dk.verify({'kind': kind, 'page': 1, 'quote': quote}, 'u.pdf', self.page('HEADER\n' + quote))
                self.assertEqual(result['status'], 'VERIFIED', result)

    def test_generic_ic_is_accepted_only_when_the_quote_names_no_role(self):
        plain = 'Quad 2-input NAND gate'
        self.assertEqual(dk.verify({'kind': 'ic', 'page': 1, 'quote': plain}, 'u.pdf', self.page(plain))['status'], 'VERIFIED')
        role = ROLE_QUOTES['pwm_controller']
        result = dk.verify({'kind': 'ic', 'page': 1, 'quote': role}, 'u.pdf', self.page(role))
        self.assertEqual(result['status'], 'QUOTE_CONFLICT')
        self.assertIn('pwm_controller', result['detail'])

    def test_optoisolator_quote_is_an_opto_not_an_isolator(self):
        quote = 'Optoisolator with phototransistor output'
        self.assertEqual(dk.cues(quote), {'opto'})

    def test_physical_dimensions_do_not_make_a_transceiver(self):
        self.assertEqual(dk.cues('Physical dimensions of the package'), set())
        self.assertEqual(dk.cues('10/100 Ethernet PHY transceiver'), {'transceiver'})

    def test_registry_disambiguation_keeps_the_named_role(self):
        self.assertEqual(dk.cues('Three-Phase Smart Gate Driver'), {'gate_driver'})
        self.assertEqual(dk.cues('H-Bridge Driver for Brushed DC Motors'), {'motor_driver'})
        self.assertEqual(dk.cues('32-bit MCU with 2 MB Flash memory and internal oscillator'), {'mcu'})
        self.assertEqual(dk.cues('Low Dropout Voltage Regulator'), {'regulator'})
        # a load switch used to be a regulator cue; declaring it as regulator now lacks the type
        result = dk.verify({'kind': 'regulator', 'page': 1, 'quote': ROLE_QUOTES['load_switch']}, 'u.pdf',
                           self.page(ROLE_QUOTES['load_switch']))
        self.assertEqual(result['status'], 'QUOTE_LACKS_TYPE')

    def test_a_pd_controller_quote_is_not_a_pwm_controller(self):
        self.assertEqual(dk.cues('USB PD controller with integrated power switch'), {'pd_controller'})
        # a datasheet title that names the PFC role without the word "correction"
        self.assertEqual(dk.cues('Enhanced, High-Efficiency Power Factor Controller'), {'pwm_controller'})

    def test_audit_covers_integrated_circuits_and_suggests_their_role(self):
        materials = [{'status': 'AVAILABLE', 'refdes': ['U7', 'R1'], 'document': {'path': 'u.pdf'}}]
        orig = dk.page_text
        dk.page_text = lambda path, page: ROLE_QUOTES['sr_controller'] if page == 1 else None
        try:
            section = dk.audit_kinds(materials, {})
        finally:
            dk.page_text = orig
        self.assertEqual(list(section), ['U7'])
        self.assertEqual(section['U7']['status'], 'UNDECLARED')
        self.assertEqual(section['U7']['candidates'][0]['kind'], 'sr_controller')


class GraphRoleTests(unittest.TestCase):
    def test_declared_role_kind_classifies_as_ic_and_keeps_its_role(self):
        db = board()
        intent, audit = verified(db, {'U1': 'pwm_controller'})
        graph = ng.NetGraph(board_intent.graph_db(db, board_intent.with_verified_kinds(intent, audit)))
        self.assertEqual(graph.kind('U1'), pw.IC)
        self.assertEqual(graph.basis('U1'), 'datasheet')
        self.assertEqual(graph.role_kind('U1'), 'pwm_controller')
        self.assertTrue(graph.is_anchor('U1'))
        self.assertIsNone(graph.role_kind('Q1'))

    def test_undeclared_ic_has_no_role_and_is_not_an_anchor(self):
        graph = ng.NetGraph(board())
        self.assertEqual(graph.kind('U1'), pw.IC)
        self.assertIsNone(graph.role_kind('U1'))
        self.assertFalse(graph.is_anchor('U1'))

    def test_generic_ic_declaration_is_an_ic_without_a_role(self):
        db = board()
        intent, audit = verified(db, {'U1': 'ic'})
        graph = ng.NetGraph(board_intent.graph_db(db, board_intent.with_verified_kinds(intent, audit)))
        self.assertEqual((graph.kind('U1'), graph.role_kind('U1'), graph.is_anchor('U1')), (pw.IC, 'ic', False))


class PlannerGapTests(unittest.TestCase):
    def row(self, db, intent=None, audit=None):
        plan = build_review_plan(db, intent, datasheet_audit=audit)
        return next(x for x in plan['checks'] if x['id'] == 'DEV-D02.U1')

    def test_ic_without_a_verified_kind_is_a_device_kind_gap(self):
        row = self.row(board())
        self.assertEqual(row['readiness'], 'WAITING_EVIDENCE')
        self.assertTrue(any(g.startswith('intent.device_kinds.U1:') for g in row['required_inputs']), row['required_inputs'])

    def test_verified_role_kind_clears_the_gap(self):
        db = board()
        intent, audit = verified(db, {'U1': 'pwm_controller'})
        row = self.row(db, intent, audit)
        self.assertFalse(any(g.startswith('intent.device_kinds.U1') for g in row['required_inputs']), row['required_inputs'])

    def test_declared_but_unverified_kind_keeps_the_gap(self):
        db = board()
        intent, _ = verified(db, {'U1': 'pwm_controller'})
        row = self.row(db, intent, {'device_kinds': {'U1': {'status': 'QUOTE_NOT_FOUND'}}})
        self.assertTrue(any(g.startswith('intent.device_kinds.U1:') and 'QUOTE_NOT_FOUND' in g for g in row['required_inputs']))


def bus_board():
    """U2 is a bus transceiver on J1 with a termination resistor; U3 a serial memory on the MCU's SPI nets."""
    db = {'nets': {}, 'parts': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {}, 'pseudo_nets': [], 'ref2page': {}}
    add = fixture.add
    add(db, 'U2', 'XCVR-8', [('1', 'TXD', 'TXD'), ('2', 'GND', 'GND'), ('3', 'VCC', 'VCC'), ('4', 'RXD', 'RXD'),
                             ('6', 'CANL', 'CANL'), ('7', 'CANH', 'CANH')])
    add(db, 'R1', '120R', [('1', '1', 'CANH'), ('2', '2', 'CANL')])
    add(db, 'J1', 'CONN-3', [('1', 'H', 'CANH'), ('2', 'L', 'CANL'), ('3', 'G', 'GND')])
    add(db, 'C1', '100nF', [('1', '1', 'VCC'), ('2', '2', 'GND')])
    add(db, 'U3', 'MEM-8', [('1', 'CS', 'CS'), ('2', 'SO', 'MISO'), ('5', 'SI', 'MOSI'), ('6', 'SCK', 'SCK'),
                            ('4', 'GND', 'GND'), ('8', 'VCC', 'VCC')])
    add(db, 'R2', '10k', [('1', '1', 'CS'), ('2', '2', 'VCC')])
    return db


class InterfaceCandidateTests(unittest.TestCase):
    """A registry role that targets interface circuits anchors a candidate of the type its datasheet title names."""

    def candidates(self, kinds, quotes=None):
        import circuit_candidates
        db = bus_board()
        intent, audit = verified(db, kinds)
        for ref, quote in (quotes or {}).items():
            intent['device_kinds'][ref]['quote'] = quote
            audit['device_kinds'][ref]['quote'] = quote
        return circuit_candidates.build(db, intent, audit)

    def test_transceiver_title_picks_the_bus_and_the_connector_joins(self):
        result = self.candidates({'U2': 'transceiver'})
        cand = next(c for c in result['candidates'] if c['id'] == 'CAN-U2')
        self.assertEqual(cand['type'], 'CAN')
        roles = {m['ref']: m['role'] for m in cand['members']}
        self.assertEqual(roles['U2'], 'anchor')
        self.assertEqual(roles['R1'], 'resistor')
        self.assertEqual(roles['J1'], 'connector')
        self.assertIn('CAN', next(m['via'] for m in cand['members'] if m['ref'] == 'U2'))
        self.assertEqual([g for g in result['gaps'] if g['kind'] == 'role-bus'], [])

    def test_rs485_title_makes_an_rs485_candidate(self):
        result = self.candidates({'U2': 'transceiver'}, {'U2': 'Half-Duplex RS-485 Transceiver'})
        self.assertEqual([c['type'] for c in result['candidates'] if c['anchor'] == 'U2'], ['RS485'])

    def test_memory_title_picks_spi_and_a_title_without_a_bus_is_a_gap(self):
        result = self.candidates({'U3': 'memory'})
        self.assertEqual([c['id'] for c in result['candidates'] if c['anchor'] == 'U3'], ['SPI-U3'])
        self.assertIn('R2', [m['ref'] for c in result['candidates'] if c['id'] == 'SPI-U3' for m in c['members']])
        result = self.candidates({'U3': 'memory'}, {'U3': '1-Mbit EEPROM'})
        self.assertEqual([c for c in result['candidates'] if c['anchor'] == 'U3'], [])
        gap = next(g for g in result['gaps'] if g['kind'] == 'role-bus')
        self.assertEqual(gap['ref'], 'U3')
        self.assertIn('SPI/I2C/DDR/STORAGE', gap['need'])

    def test_single_type_role_needs_no_title_cue(self):
        result = self.candidates({'U3': 'level_shifter'}, {'U3': 'Bidirectional Voltage-Level Translator'})
        self.assertEqual([c['id'] for c in result['candidates'] if c['anchor'] == 'U3'], ['LEVEL_SHIFT-U3'])
        self.assertEqual(catalog.interface_type('level_shifter', None), 'LEVEL_SHIFT')

    def test_generic_ic_is_listed_as_a_planning_diagnostic(self):
        db = bus_board()
        intent, audit = verified(db, {'U2': 'ic', 'U3': 'memory'})
        intent['device_kinds']['U2']['quote'] = audit['device_kinds']['U2']['quote'] = 'Quad 2-input NAND gate'
        plan = build_review_plan(db, intent, datasheet_audit=audit)
        generic = [d for d in plan['diagnostics'] if d['code'] == 'DEVICE_KIND_GENERIC']
        self.assertEqual([d['ref'] for d in generic], ['U2'])
        self.assertIn('NAND gate', generic[0]['detail'])
        from plan_review import diagnostic_lines
        self.assertTrue(any('U2 声明为泛称 ic' in line for line in diagnostic_lines(plan, db, intent)))


if __name__ == '__main__':
    unittest.main()
