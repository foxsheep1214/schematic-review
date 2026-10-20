# 变异门结果

由 `python3 evals/mutation/run.py` 生成；门槛是单元层全部 KILLED。

| 变异 | 说明 | 文件 | unit | 首个失败的测试（单元层） |
|---|---|---|---|---|
| M1 | NET-A01 silent on single-pin nets | `scripts/lint.py` | KILLED | FAILED scripts/tests/test_board_scans.py::TypicalBoardPowerTest::test_open_datasheet_nc_pin_is_not_reported |
| M2 | opto CTR derating ignored | `scripts/checkers/optocoupler.py` | KILLED | FAILED scripts/tests/test_optocoupler.py::HotRuleTest::test_derated_ctr_below_requirement_fails |
| M3 | DAMAGE_OR_HAZARD graded P1 | `scripts/review_summary.py` | KILLED | FAILED scripts/tests/test_ledger_replay.py::LedgerReplayTests::test_every_record_matches_its_frozen_answer |
| M4 | DEV-E02 low margin ignored | `scripts/lint.py` | KILLED | FAILED scripts/tests/test_electrical_safety.py::ElectricalSafetyTests::test_operating_range_fails_when_the_rail_minimum_is_below_the_recommended_minimum |
| M5 | DRV-A03 floating gate never reported | `scripts/checkers/power_switch.py` | KILLED | FAILED scripts/tests/test_power_switch.py::RecognitionTest::test_floating_gate_reports_ps01 |
| M6 | opto LED-off check removed | `scripts/checkers/optocoupler.py` | KILLED | FAILED scripts/tests/test_optocoupler.py::HotRuleTest::test_led_not_conducting_fails |
| M7 | pin map mismatch never reported | `scripts/lint.py` | KILLED | FAILED scripts/tests/test_hot_bench.py::HotBenchTest::test_every_case_and_mutation_matches_its_classified_answer |
| M8 | report says 0 P0 always | `scripts/render_report.py` | KILLED | FAILED scripts/tests/test_ledger_replay.py::LedgerReplayTests::test_every_record_matches_its_frozen_answer |
| M9 | NET-A03 passive-only auto net never reported | `scripts/lint.py` | KILLED | FAILED scripts/tests/test_rule_contracts.py::RuleContractTests::test_NET_A03 |
| M10 | PWR-A04 same-base rails never reported | `scripts/lint.py` | KILLED | FAILED scripts/tests/test_rule_contracts.py::RuleContractTests::test_PWR_A04 |
| M11 | RST-A01 EN pull candidates never reported | `scripts/lint.py` | KILLED | FAILED scripts/tests/test_rule_contracts.py::RuleContractTests::test_RST_A01 |
| M12 | REQ-A01 key-part count mismatch never reported | `scripts/lint.py` | KILLED | FAILED scripts/tests/test_rule_contracts.py::RuleContractTests::test_REQ_A01 |

全部杀死。
