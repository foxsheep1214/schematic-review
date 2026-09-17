# 规则总表编号基线验证记录

日期：2026-09-17。被测源码：07238d3181047977e0316060da2ac5e2faf3ea79（规则按规则总表重新编号）。

本基线对应改编号后的评测协议：`stimulus.py` 写入 PWR-E01/SIG-E01/RST-E02，`worker.py` 提交
evidence `schema_version` 2。数据、答案、生成器、参考计算与评分未改动，但协议指纹已变，
不能用 `--baseline` 与 [2aeaee5 基线](../2aeaee5/verification.md) 直接比较。

| 验证 | 实际结果 | 解释 |
|---|---|---|
| 全量电路基线 | 166 / 166 符合预期 | 错误 PASS 0、误报 0、错误数值 0、运行错误 0 |
| 与改编号前逐例比较 | 166 / 166 记录一致 | 改编号前（cd7b8e9）在原协议下运行；规则编号按对照表翻译、去除指纹与临时路径后，逐例记录、指标、分组与验收结论完全一致 |
| 原有脚本单元测试 | 512 / 512 通过 | Python 3.13.13，unittest discover |
| 评测程序测试 | 19 / 19 通过 | 独立解、标签污染、分区、缺证、评分与比较门 |
| 理想模型数值交叉验证 | 150 / 150 角点通过 | ngspice-47；只验证参考计算，本次未改动 |
| 实际源码故障注入 | 3 / 3 被识别 | 标称值代替角点、漏算并联上拉、直接放行；仅临时副本 |

数值及错误分布见 [完整结果](results.json)，电路范围见 [基线报告](report.md)；
[SPICE 记录](spice-results.json) 与 [故障注入记录](mutation-results.json) 为本次重新运行的结果。
编号对照与改动说明见 [设计记录](../../../../docs/specs/2026-09-17-check-catalog-design.md)。

## 可复验指纹

- 案例：`5addda6a8fc2f0cee5d78d96b06ea86354befa365ccc101ea782aaeba171bdbb`
- 答案：`43fdd3c63b3ef3f5d245e069b462ae42fcc04d4cb9116225915811fcf05fc697`
- 评测程序：`b490003c47c3c58e8d93a2d61131e5162f653fc55866c937fc943a3efb4ba2e6`
- 被测脚本集合：`6c6957b401f3cbfe7d4eafdc2c8272cfd506f46a5465ef38cafd663e8a6fff28`
- spice_check.py：`7088aba7d9ecca044e13600de4e3f8660dd1f3ef3913c855128a6d7e5874bff5`
- tests/test_benchmark.py：`6197b1c0f49dec977e09d8691fb74d6422b4e3c480aab5f5eac16fa62617fecc`

本基线只记录编号变化后的工具评测结果；真实项目、完整 Agent 行为、PCB 和实测均未评测。
