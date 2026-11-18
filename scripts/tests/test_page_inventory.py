"""Original synthetic native XML and independent ledger boundary tests."""
import copy
import json
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from page_inventory import inventory, NATIVE, LIMITED
from parse_kicad import parse
from parse_netlist import self_check

XML = (Path(__file__).parent / 'fixtures/page_inventory/empty-root.xml').read_text()


def mutate(change):
    root = ET.fromstring(XML)
    change(root)
    return ET.tostring(root, encoding='unicode')


def bind(p, r, db):
    r['plan_digest'], r['db_digest'] = fingerprint(p), fingerprint(db)
    return p, r, db


class NativePageInventoryTests(unittest.TestCase):


    def test_ambiguous_native_declarations_are_rejected(self):
        for attr, value in [('number', '7'), ('number', '0'), ('number', 'x'), ('number', ''),
                            ('name', '/'), ('name', ''), ('name', '/a/../b/'), ('name', '/a//b/'),
                            ('tstamps', '/')]:
            with self.subTest(attr=attr, value=value):
                with self.assertRaises(ValueError):
                    parse(mutate(lambda root: root.findall('./design/sheet')[1].set(attr, value)))

    def test_component_must_resolve_exact_declared_scope(self):
        for value in ('/Other/', '/Power α/Invented/', '', 'Power α'):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, 'sheetpath'):
                    parse(mutate(lambda root: root.find('./components/comp/sheetpath').set('names', value)))
        with self.assertRaisesRegex(ValueError, 'tstamps conflicts'):
            parse(mutate(lambda root: root.find('./components/comp/sheetpath').set('tstamps', '/wrong-uuid/')))


if __name__ == '__main__':
    unittest.main()
