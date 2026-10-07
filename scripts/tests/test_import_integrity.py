"""Import guards motivated by real legacy KiCad empty exports."""
import copy
import sys
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from parse_kicad import parse
from test_parse_kicad import board


class ImportIntegrity(unittest.TestCase):
    def assert_rejected(self, mutate):
        root = ET.fromstring(board()); mutate(root)
        with self.assertRaises(ValueError):
            parse(ET.tostring(root))

    def test_empty_export_cannot_be_clean_review_input(self):
        self.assert_rejected(lambda r: (r.find('components').clear(), r.find('nets').clear()))

    def test_components_without_any_physical_nodes_are_rejected(self):
        self.assert_rejected(lambda r: r.find('nets').clear())

    def test_duplicate_component_cannot_silently_overwrite_identity(self):
        self.assert_rejected(lambda r: r.find('components').append(copy.deepcopy(r.find('components/comp'))))

    def test_pin_in_same_or_different_net_is_rejected(self):
        for i in [0, 1]:
            with self.subTest(net=i):
                self.assert_rejected(lambda r: r.findall('nets/net')[i].append(copy.deepcopy(r.find('nets/net/node'))))

    def test_malformed_or_orphan_node_cannot_be_skipped(self):
        for field, value in [('ref', ''), ('pin', ''), ('ref', 'ABSENT')]:
            with self.subTest(field=field, value=value):
                self.assert_rejected(lambda r: r.find('nets/net/node').set(field, value))

    def test_duplicate_or_missing_network_name_is_rejected(self):
        for value in ['', 'VIN_5V']:
            self.assert_rejected(lambda r: r.findall('nets/net')[1].set('name', value))

    def test_missing_component_reference_is_rejected(self):
        self.assert_rejected(lambda r: r.find('components/comp').set('ref', ''))


if __name__ == '__main__':
    unittest.main()
