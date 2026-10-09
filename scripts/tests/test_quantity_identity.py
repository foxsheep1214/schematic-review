"""Choose retrieval identities without treating component quantities as MPNs."""
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from audit_datasheets import _identity_for, _alternate_identities, build_datasheet_audit


class QuantityIdentityTests(unittest.TestCase):
    def test_explicit_part_beats_parameter_value(self):
        for ref, value, part in (("C1", "22uF / 10V", "CAP-ORDER-X"),
                                 ("L1", "2.2uH", "12345678901"),
                                 ("R1", "10K / 1%", "RES-ORDER-X"),
                                 ("R2", "4K7", "RES-ORDER-Y"),
                                 ("C2", "100 nF, 50 V", "CAP-ORDER-Y")):
            with self.subTest(value=value):
                self.assertEqual(_identity_for(ref, {"value": value, "part": part}), (part, "part"))

    def test_numeric_mpn_value_is_not_mistaken_for_a_quantity(self):
        self.assertEqual(_identity_for("L1", {"value": "12345678901", "part": "OTHER-ORDER"}),
                         ("12345678901", "value"))

    def test_conflicting_identity_value_is_preserved(self):
        part = {"value": "IC-ORDER-A", "part": "IC-ORDER-B"}
        self.assertEqual(_identity_for("U1", part), ("IC-ORDER-A", "value"))
        self.assertIn({"field": "part", "value": "IC-ORDER-B"}, _alternate_identities(part, "IC-ORDER-A"))

    def test_unknown_or_generic_part_cannot_invent_exact_identity(self):
        for part in (None, "UNKNOWN", "TBD", "C", "CAPACITOR", "22uF"):
            with self.subTest(part=part):
                self.assertEqual(_identity_for("C1", {"value": "22uF", "part": part}), ("22uF", "value"))

    def test_package_symbol_alias_is_not_an_exact_ordering_identity(self):
        for ref, value, alias in (("X1", "16MHz", "CRYSTAL_3225_4_PAD"),
                                  ("C1", "22uF", "C_0603"),
                                  ("R1", "10K", "RESISTOR_0402"),
                                  ("L1", "2.2uH", "INDUCTOR_1210")):
            with self.subTest(alias=alias):
                self.assertEqual(_identity_for(ref, {"value": value, "part": alias,
                                                     "prim": "Generic:" + alias}), (value, "value"))

    def test_selected_part_does_not_erase_value_evidence(self):
        part = {"value": "22uF / 10V", "part": "CAP-ORDER-X"}
        identity, _ = _identity_for("C1", part)
        self.assertIn({"field": "value", "value": "22uF / 10V"}, _alternate_identities(part, identity))

    def test_filename_match_only_generates_candidate(self):
        db = {"parts": {"L1": {"value": "2.2uH", "part": "12345678901", "nc": False}}}
        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / "12345678901.pdf").write_bytes(b"%PDF-1.4\n")
            audit = build_datasheet_audit(db, [tmp], required_refs=["L1"])
        material = audit["materials"][0]
        self.assertEqual(material["identity"], "12345678901")
        self.assertEqual(material["status"], "NEEDS_VERIFICATION")


if __name__ == "__main__":
    unittest.main()
