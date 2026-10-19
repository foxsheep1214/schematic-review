"""Rule contracts: every automated rule fires on its trigger board and stays silent on its near-miss.

Boards live in evals/rule_contracts/boards/<rule>.json; one test per rule is generated below.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'evals' / 'rule_contracts'))
import contracts  # noqa: E402
import catalog  # noqa: E402

CONTRACTS = contracts.load_contracts()


class RuleContractCoverageTests(unittest.TestCase):
    def test_every_automated_rule_has_a_contract(self):
        self.assertEqual(contracts.gaps(CONTRACTS), [])

    def test_contracts_name_only_automated_catalog_rules(self):
        for name, contract in CONTRACTS.items():
            self.assertEqual(contract['rule'], name)
            self.assertIn(catalog.method_of(name), contracts.AUTOMATED_METHODS, name)

    def test_reviewer_judged_methods_are_out_of_scope(self):
        methods = {catalog.method_of(r.id) for r in catalog.RULES}
        self.assertEqual(methods, set(contracts.AUTOMATED_METHODS) | set(contracts.OUT_OF_SCOPE_METHODS))


class RuleContractTests(unittest.TestCase):
    pass


def _case(contract):
    def test(self):
        self.assertEqual(contracts.check_contract(contract), [])
    test.__doc__ = '%s: %s' % (contract['rule'], contract['note'])
    return test


for _name, _contract in CONTRACTS.items():
    setattr(RuleContractTests, 'test_' + _name.replace('-', '_'), _case(_contract))


if __name__ == '__main__':
    unittest.main()
