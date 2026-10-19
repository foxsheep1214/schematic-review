# 变异门结果

由 `python3 evals/mutation/run.py` 生成；门槛是单元层全部 KILLED。

| 变异 | 说明 | 文件 | unit | 首个失败的测试（单元层） |
|---|---|---|---|---|
| M7 | pin map mismatch never reported | `scripts/lint.py` | KILLED | FAILED scripts/tests/test_hot_bench.py::HotBenchTest::test_every_case_and_mutation_matches_its_classified_answer |

全部杀死。
