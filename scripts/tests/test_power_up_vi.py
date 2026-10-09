"""VI aliases require directional native power evidence, not a name alone."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from checkers.power_up import build_inventory
from test_power_up import rail_board, regulators_of


class PowerUpViTests(unittest.TestCase):
    def board(self, native_type="power_in", name="VI"):
        db = rail_board(enable="tied")
        db["pinname"]["U1.1"] = name
        db["pintype"]["U1.1"] = "POWER"
        db["native_pintype"] = {"U1.1": native_type}
        return db

    def test_native_vi_supply_is_recognized(self):
        for name in ("VI", "vi"):
            with self.subTest(name=name):
                item = regulators_of(build_inventory(self.board(name=name)))["U1"]
                self.assertEqual(item["input_nets"], ["V12"])
                self.assertEqual(item["enable_source"], "tied-to-input")

    def test_video_input_or_power_output_name_is_not_a_supply(self):
        for kind in ("input", "power_out", "passive", None):
            with self.subTest(kind=kind):
                item = regulators_of(build_inventory(self.board(native_type=kind)))["U1"]
                self.assertEqual(item["input_nets"], [])
                self.assertEqual(item["enable_source"], "unknown")

    def test_switch_power_input_is_not_supply_input(self):
        item = regulators_of(build_inventory(self.board(name="SW")))["U1"]
        self.assertEqual(item["input_nets"], [])

    def test_existing_vin_name_behavior_is_preserved(self):
        item = regulators_of(build_inventory(self.board(name="VIN", native_type=None)))["U1"]
        self.assertEqual(item["enable_source"], "tied-to-input")


if __name__ == "__main__":
    unittest.main()
