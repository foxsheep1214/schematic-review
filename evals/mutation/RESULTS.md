# 变异门结果

由 `python3 evals/mutation/run.py` 生成；门槛是单元层全部 KILLED。

| 变异 | 说明 | 文件 | unit | 首个失败的测试（单元层） |
|---|---|---|---|---|
| M1 | NET-A01 silent on single-pin nets | `scripts/lint.py` | KILLED | FAILED scripts/tests/test_board_scans.py::TypicalBoardPowerTest::test_open_datasheet_nc_pin_is_not_reported |
| M2 | opto CTR derating ignored | `scripts/checkers/optocoupler.py` | KILLED | FAILED scripts/tests/test_ledger.py::LedgerTests::test_real_ledger_latest_entry_passes |
| M3 | DAMAGE_OR_HAZARD graded P1 | `scripts/review_summary.py` | KILLED | FAILED scripts/tests/test_ledger.py::LedgerTests::test_real_ledger_latest_entry_passes |
| M4 | DEV-E02 low margin ignored | `scripts/lint.py` | KILLED | FAILED scripts/tests/test_electrical_safety.py::ElectricalSafetyTests::test_operating_range_fails_when_the_rail_minimum_is_below_the_recommended_minimum |
| M5 | DRV-A03 floating gate never reported | `scripts/checkers/power_switch.py` | KILLED | FAILED scripts/tests/test_ledger.py::LedgerTests::test_real_ledger_latest_entry_passes |
| M6 | opto LED-off check removed | `scripts/checkers/optocoupler.py` | KILLED | FAILED scripts/tests/test_ledger.py::LedgerTests::test_real_ledger_latest_entry_passes |
| M7 | pin map mismatch never reported | `scripts/lint.py` | KILLED | FAILED scripts/tests/test_hot_bench.py::HotBenchTest::test_every_case_and_mutation_matches_its_classified_answer |
| M8 | report says 0 P0 always | `scripts/render_report.py` | KILLED | FAILED scripts/tests/test_ledger.py::LedgerTests::test_real_ledger_latest_entry_passes |
| M9 | NET-A03 passive-only auto net never reported | `scripts/lint.py` | KILLED | FAILED scripts/tests/test_ledger.py::LedgerTests::test_real_ledger_latest_entry_passes |
| M10 | PWR-A04 same-base rails never reported | `scripts/lint.py` | KILLED | FAILED scripts/tests/test_ledger.py::LedgerTests::test_real_ledger_latest_entry_passes |
| M11 | RST-A01 EN pull candidates never reported | `scripts/lint.py` | KILLED | FAILED scripts/tests/test_ledger.py::LedgerTests::test_real_ledger_latest_entry_passes |
| M12 | REQ-A01 key-part count mismatch never reported | `scripts/lint.py` | KILLED | FAILED scripts/tests/test_ledger.py::LedgerTests::test_real_ledger_latest_entry_passes |
| M13 | F2 design value asked of a vendor accepted | `scripts/review_functions.py` | KILLED | FAILED scripts/tests/test_ledger.py::LedgerTests::test_real_ledger_latest_entry_passes |
| M14 | F4 positive margin never decides | `scripts/review_functions.py` | KILLED | FAILED scripts/tests/test_derive_rows.py::DeriveTests::test_deriving_twice_changes_nothing_and_follows_a_changed_verdict |
| M15 | frame member bound to another function accepted | `scripts/review_functions.py` | KILLED | FAILED scripts/tests/test_ledger.py::LedgerTests::test_real_ledger_latest_entry_passes |
| M16 | derive_rows ignores open items | `scripts/derive_rows.py` | KILLED | FAILED scripts/tests/test_derive_rows.py::DeriveTests::test_a_hand_filled_row_is_kept_and_a_disagreement_is_named |
| M17 | question prohibition ban never fires on rows | `scripts/catalog.py` | KILLED | FAILED scripts/tests/test_catalog.py::QuestionTemplateTest::test_question_errors_reject_prohibition_phrasing_in_rows_and_frames |
| M18 | plan emits no function frames | `scripts/plan_review.py` | KILLED | FAILED scripts/tests/test_ledger.py::LedgerTests::test_real_ledger_latest_entry_passes |
| M19 | state-invariant rules expanded per state again | `scripts/plan_review.py` | KILLED | FAILED scripts/tests/test_ledger.py::LedgerTests::test_real_ledger_latest_entry_passes |
| M20 | F4 shortfall kept open accepted | `scripts/review_functions.py` | KILLED | FAILED scripts/tests/test_ledger.py::LedgerTests::test_real_ledger_latest_entry_passes |
| M21 | F8 design value without margin accepted | `scripts/review_functions.py` | KILLED | FAILED scripts/tests/test_ledger.py::LedgerTests::test_real_ledger_latest_entry_passes |
| M22 | document defect bound to a function accepted | `scripts/review_functions.py` | KILLED | FAILED scripts/tests/test_ledger.py::LedgerTests::test_real_ledger_latest_entry_passes |
| M23 | bidirectional single-node net reported as FINDING again | `scripts/lint.py` | KILLED | FAILED scripts/tests/test_board_scans.py::SingleNodeNetTest::test_bidirectional_ic_pin_with_only_a_label_is_a_candidate |
| M24 | driver behind a resistor chain ignored | `scripts/checkers/power_switch.py` | KILLED | FAILED scripts/tests/test_ledger.py::LedgerTests::test_real_ledger_latest_entry_passes |
| M25 | delegated frame row accepted without object coverage | `scripts/review_functions.py` | KILLED | FAILED scripts/tests/test_ledger.py::LedgerTests::test_real_ledger_latest_entry_passes |
| M26 | review_scope ignored: scoped ledger owes every plan row | `scripts/validate_review.py` | KILLED | FAILED scripts/tests/test_ledger.py::LedgerTests::test_real_ledger_latest_entry_passes |

全部杀死。
