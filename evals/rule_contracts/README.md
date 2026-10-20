# 规则合同：每条自动规则一块触发板、一块近似板

`scripts/catalog.py` 里方式为 A、E、T、V、H 的 70 条规则，每条在 `boards/<规则>.json` 里有：

- **触发板**：最小合成板，规则必须触发；
- **近似板**：只差一处的板，规则必须不触发（且规则确实执行过，不能靠“被跳过”过关）。

`note` 字段写两块板差在哪。运行器与板格式见 [contracts.py](contracts.py)；
单元测试 [test_rule_contracts.py](../../scripts/tests/test_rule_contracts.py) 每条规则生成一个测试，
并检查“每条自动规则都有合同”。新增 A/E/T/V/H 规则必须同时加合同，否则该测试失败。

```sh
python3 evals/rule_contracts/contracts.py            # 逐条运行
python3 evals/rule_contracts/contracts.py --gaps     # 缺合同的自动规则
python3 evals/rule_contracts/contracts.py NET-A03    # 只跑某几条
```

## 什么算“触发”

| runner | 适用 | 触发板 | 近似板 |
|---|---|---|---|
| `cold` | Lint 内置与检查器的 A 规则 | 冷跑出现该规则的 FINDING/CANDIDATE（INFO 不算） | 没有，且该规则不在 `skipped` 里 |
| `hot` | E 规则 | 热跑证据算出 FAIL | 只有 PASS |
| `plan` | T、V 规则与 REQ-A02 | 计划里有该规则的 APPLICABLE 检查项 | 没有 APPLICABLE 项（NA/UNDETERMINED 不算） |
| `rule_plan` | REQ-H01 | 计划 `rule_plan` 行为 APPLICABLE | 不是 APPLICABLE |

热跑证据按 `scripts/tests/electrical_fixtures.bind_evidence` 绑定合成资料；`intent.bound=true`
表示套用共享装配绑定（`bound_intent`）。计划规则的近似板多数是“同一结构只有名称线索、没有意图声明”，
用来锁住适用性门槛：名称命中只能是 UNDETERMINED，不能直接排程为 APPLICABLE。

## 没有近似板的规则

DOC-T01、DOC-V02、PWR-T06 是全板通用规则，计划对每块板（含空板）都生成一项，不存在“不生成”的板；
合同里 `near_miss` 为 `null` 并写明 `always` 原因，只验证触发。

## 建立前的覆盖缺口（2026-10-19 扫描）

建合同前，以下自动规则在 `scripts/tests` 里从未被任何测试点名：

| 规则 | 方式 | 来源 |
|---|---|---|
| NET-A03 自动命名无源孤岛 | A | Lint 内置 |
| PWR-A04 同基名多轨 | A | Lint 内置 |
| RST-A01 使能脚上下拉待复核 | A | Lint 内置 |
| REQ-A01 关键器件计数 | A | Lint 内置 |
| PWR-T05 防反接与理想二极管 | T | 功能电路 POWER_PROTECTION |
| PWR-T06 地网划分与连接 | T | 全板通用 |
| RST-T03 上电顺序与恢复 | T | 功能电路 STARTUP |
| RST-T04 复位期间 IO 默认态 | T | 功能电路 STARTUP |

另有很多规则只被一两个测试点名（DOC-A03、DOC-V02、PRO-A02、ANA-T01、RST-T02 各 1 次）。
现在 70 条全部有合同，`--gaps` 输出 `none`。变异门里 M9–M12 专门删掉前四条 A 规则的报出，验证合同能杀死。

## 不在代码合同范围内

方式 C（工程计算，36 条）、D（条款核对，34 条）、Q（覆盖审计，9 条）由审查者逐项判定，代码只负责排程，
判据靠审查者对资料和需求，不存在“必触发/必不触发”的确定性合成板。它们的计划排程由
`test_catalog.py` 的可达性测试覆盖（每条 plan/package/board 规则都能被计划生成），审查质量由
`evals/training/` 的真值闭环衡量。
