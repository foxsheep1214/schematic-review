# 变异门结果

由 `python3 evals/mutation/run.py` 生成；门槛是单元层全部 KILLED。

| 变异 | 说明 | 文件 | unit | 首个失败的测试（单元层） |
|---|---|---|---|---|
| M1 | NET-A01 silent on single-pin nets | `scripts/lint.py` | KILLED | FAILED scripts/tests/test_board_scans.py::TypicalBoardPowerTest::test_open_datasheet_nc_pin_is_not_reported |
| M2 | opto CTR derating ignored | `scripts/checkers/optocoupler.py` | KILLED | FAILED scripts/tests/test_optocoupler.py::HotRuleTest::test_derated_ctr_below_requirement_fails |
| M3 | DAMAGE_OR_HAZARD graded P1 | `scripts/review_summary.py` | KILLED | FAILED scripts/tests/test_review_functions.py::DerivedLevelsTests::test_report_counts_p0_and_p1_items_separately |
| M4 | DEV-E02 low margin ignored | `scripts/lint.py` | KILLED | FAILED scripts/tests/test_electrical_safety.py::ElectricalSafetyTests::test_operating_range_fails_when_the_rail_minimum_is_below_the_recommended_minimum |
| M5 | DRV-A03 floating gate never reported | `scripts/checkers/power_switch.py` | KILLED | FAILED scripts/tests/test_power_switch.py::RecognitionTest::test_floating_gate_reports_ps01 |
| M6 | opto LED-off check removed | `scripts/checkers/optocoupler.py` | KILLED | FAILED scripts/tests/test_optocoupler.py::HotRuleTest::test_led_not_conducting_fails |
| M7 | pin map mismatch never reported | `scripts/lint.py` | KILLED | FAILED scripts/tests/test_hot_bench.py::HotBenchTest::test_every_case_and_mutation_matches_its_classified_answer |
| M8 | report says 0 P0 always | `scripts/render_report.py` | KILLED | FAILED scripts/tests/test_render_and_pack.py::ReportWordingTests::test_root_gap_count_not_check_count_and_details_preserve_evidence |
| M9 | NET-A03 passive-only auto net never reported | `scripts/lint.py` | KILLED | FAILED scripts/tests/test_rule_contracts.py::RuleContractTests::test_NET_A03 |
| M10 | PWR-A04 same-base rails never reported | `scripts/lint.py` | KILLED | FAILED scripts/tests/test_rule_contracts.py::RuleContractTests::test_PWR_A04 |
| M11 | RST-A01 EN pull candidates never reported | `scripts/lint.py` | KILLED | FAILED scripts/tests/test_rule_contracts.py::RuleContractTests::test_RST_A01 |
| M12 | REQ-A01 key-part count mismatch never reported | `scripts/lint.py` | KILLED | FAILED scripts/tests/test_rule_contracts.py::RuleContractTests::test_REQ_A01 |
| M13 | F2 design value asked of a vendor accepted | `scripts/review_functions.py` | KILLED | FAILED scripts/tests/test_review_functions.py::FunctionShapeTests::test_f2_design_value_is_specified_not_requested |
| M14 | F4 positive margin never decides | `scripts/review_functions.py` | KILLED | FAILED scripts/tests/test_derive_rows.py::DeriveTests::test_deriving_twice_changes_nothing_and_follows_a_changed_verdict |
| M15 | frame member bound to another function accepted | `scripts/review_functions.py` | KILLED | FAILED scripts/tests/test_review_functions.py::FrameTests::test_a_member_row_bound_to_a_function_that_does_not_cover_it_is_named |
| M16 | derive_rows ignores open items | `scripts/derive_rows.py` | KILLED | FAILED scripts/tests/test_derive_rows.py::DeriveTests::test_a_hand_filled_row_is_kept_and_a_disagreement_is_named |
| M17 | question prohibition ban never fires on rows | `scripts/catalog.py` | KILLED | FAILED scripts/tests/test_catalog.py::QuestionTemplateTest::test_question_errors_reject_prohibition_phrasing_in_rows_and_frames |
| M18 | plan emits no function frames | `scripts/plan_review.py` | KILLED | FAILED scripts/tests/test_plan_review.py::FunctionFrameTests::test_a_declared_circuit_gets_a_frame_and_bound_member_rows |
| M19 | state-invariant rules expanded per state again | `scripts/plan_review.py` | KILLED | FAILED scripts/tests/test_plan_review.py::ReviewPlanTests::test_level_shift_name_hit_is_candidate_until_circuit_is_declared |
| M20 | F4 shortfall kept open accepted | `scripts/review_functions.py` | KILLED | FAILED scripts/tests/test_review_functions.py::FunctionShapeTests::test_f4_margins_per_aspect |
| M21 | F8 design value without margin accepted | `scripts/review_functions.py` | KILLED | FAILED scripts/tests/test_review_functions.py::FunctionShapeTests::test_f8_a_design_value_open_beside_a_calculation_states_its_margin |
| M22 | document defect bound to a function accepted | `scripts/review_functions.py` | KILLED | FAILED scripts/tests/test_review_functions.py::RowBindingTests::test_a_document_defect_is_not_bound_to_a_function |
| M23 | bidirectional single-node net reported as FINDING again | `scripts/lint.py` | KILLED | FAILED scripts/tests/test_board_scans.py::SingleNodeNetTest::test_bidirectional_ic_pin_with_only_a_label_is_a_candidate |
| M24 | driver behind a resistor chain ignored | `scripts/checkers/power_switch.py` | KILLED | FAILED scripts/tests/test_power_switch.py::ChainedDriverTest::test_driver_behind_a_resistor_chain_is_a_candidate |
| M25 | delegated frame row accepted without object coverage | `scripts/review_functions.py` | KILLED | FAILED scripts/tests/test_review_functions.py::FrameTests::test_a_member_row_bound_to_a_function_that_does_not_cover_it_is_named |
| M26 | review_scope ignored: scoped ledger owes every plan row | `scripts/validate_review.py` | KILLED | FAILED scripts/tests/test_review_functions.py::ScopedReviewTests::test_a_scoped_ledger_reconciles_only_its_frames_and_is_not_a_board_verdict |

全部杀死。
