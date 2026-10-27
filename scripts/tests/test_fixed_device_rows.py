"""Device rows (identity, pin disposition, operating conditions) do not depend on what the reviewer declares.

On one board one reviewer declared 13 devices and another 34: the transistors' and diodes' identity rows, 57 rows in
all, existed only in the second plan. Transistors, optocouplers, zeners, TVS/ESD parts, bridge rectifiers,
transformers and custom inductors now get them from the netlist; a plain diode or an ordinary inductor is a commodity
part and gets them only when declared.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plan_review import build_review_plan
from test_inductive_load import add
from test_optocoupler import opto_board


def board():
    db = opto_board()
    for ref, value, kind in (('Q1', 'AO3400', 'mosfet'), ('D1', 'BZT52-C5V1', 'zener'), ('D2', 'PESD5V0', 'tvs'),
                             ('D3', '1N4148', 'diode'), ('T1', 'TX-1', 'transformer'), ('BR1', 'GBU4M', None),
                             ('L1', 'CUSTOM-PFC-1', None), ('L2', '10uH', None)):
        add(db, ref, value, [('1', '1', 'N_' + ref), ('2', '2', 'GND')] + ([('3', '3', 'N3_' + ref)] if ref in ('Q1', 'BR1') else []))
        if kind:
            db.setdefault('device_kinds', {})[ref] = {'kind': kind, 'citation': 'synthetic'}
    return db


def device_rows(db, rule):
    return {c['object']['ref'] for c in build_review_plan(db)['checks'] if c['rule'] == rule}


class FixedDeviceRowTests(unittest.TestCase):
    def test_non_commodity_semiconductors_and_magnetics_get_device_rows_undeclared(self):
        for rule in ('DEV-D01', 'DEV-D05', 'DEV-C05'):
            with self.subTest(rule=rule):
                refs = device_rows(board(), rule)
                # D1 and D2 clamp a net to ground: their working voltage and temperature grade are the PRO-E02 row
                # (2026-10-26, user: 按照你的建议来改方案), so they get identity and pin rows but no DEV-C05
                clamps = {'D1', 'D2'} if rule != 'DEV-C05' else set()
                self.assertTrue({'Q1', 'T1', 'BR1', 'L1', 'OK1'} | clamps <= refs, refs)
                self.assertFalse({'D3', 'L2'} & refs, refs)
                if rule == 'DEV-C05':
                    self.assertFalse({'D1', 'D2'} & refs, refs)


if __name__ == '__main__':
    unittest.main()
