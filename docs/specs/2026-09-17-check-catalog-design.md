# 规则总表：按检查方式与内容域重排编号

- 日期：2026-09-17；基线提交 `cd7b8e9`（502 项测试全绿，circuit_bench 166 例全部通过）
- 需求来源：用户要求直接放弃 ER、Rule 等现有编号，按检查方式和执行内容重新编排规则表，
  使整个检查过程清晰明确。

## 1. 问题

旧编号有三套，互相交叉：

- **ER1～ER7** 同时承担三种分类：取证/计算/目检是“方式”，电源/功能链是“内容”，平台条款是
  “判据来源”，ER7 还装了覆盖审计与改版影响项。分派规则也不统一，例如热跑项 Rule-08 进 ER4，
  Rule-09/12/16 进 ER1；电路检查包只有四类进 ER4，其余进 ER5；显式证据的兜底阶段写死为
  “Rule-08 进 ER4，其余 ER1”，同一条检查器规则会随识别结果落到两个阶段。
- **Rule-NN** 编号不含语义，名称在文档、Lint、计划三处各写一份，已有 15 条互不一致；
  Rule-12 同时产出冷跑候选与热跑判定。
- **检查器前缀**（IL/PS/IF/PU/SV/DL/OC）用 01–09/10+ 区分冷热，与 Rule-NN 约定不同。

内容分类另有检查清单 16 域、功能目录 13 项、电路检查包 9 域、检查器 9 个、边界矩阵 7 域，
计划项没有统一的内容字段；检查清单条目没有编号，人工补查项无法引用。

## 2. 方案

### 2.1 编号

规则编号为 `内容域-方式序号`，例如 `PWR-E01`。

| 内容域 | 名称 | 方式 | 名称 |
|---|---|---|---|
| DOC | 图纸与数据 | A | 自动扫描 |
| DEV | 器件与引脚 | E | 证据计算 |
| NET | 网络连接 | T | 连接追踪 |
| PWR | 电源 | C | 工程计算 |
| RST | 启动与复位 | D | 条款核对 |
| CLK | 时钟 | V | 图面目检 |
| SIG | 接口与信号 | Q | 覆盖审计 |
| ANA | 模拟与监测 | H | 版本比对 |
| PRO | 防护与隔离 | | |
| DRV | 功率驱动 | | |
| REQ | 需求与闭环 | | |

共 150 条规则。原检查清单的每个条目都已落到某条规则：能自动生成的沿用生成器，其余登记为
来源“人工补查”的规则（审查者按适用性加入计划），因此检查清单文件并入总表后删除。

### 2.2 单一来源

`scripts/catalog.py` 登记全部规则（编号、名称、判据要点、来源）以及电路类型展开表
（`CIRCUIT_TYPES`）和六个覆盖维度（`COVERAGE_RULES`）。计划、Lint、证据契约、检查器、改版比对
与结果校验都从这里取编号和判据；`references/check-catalog.md` 的表格由
`catalog.py --write-doc` 生成，测试保证两者一致，并保证：各组序号连续；代码与文档中出现的
编号都已登记；每条非人工规则都能在其来源模块中找到；人工规则不被脚本生成。

### 2.3 计划项与流程

- 计划项 ID 为 `规则编号[.实例键].锚点`；删除 `check`、`stage`、`executor` 字段，新增
  `method`，`domain` 改为内容域代码；由电路类型展开的项另带 `circuit_type`。
- 合并计划和最终校验都核对 `rule`/`method`/`domain` 与总表一致、ID 以规则编号开头；
  人工补查项同样适用。
- 流程阶段按方式排列：输入准备 → 解析 → 冷跑（A）→ 资料取证 → 热跑（A+E）→ 专家审查（T/C/D，
  按 PWR→RST→CLK→SIG→ANA→PRO→DRV）→ 图面目检（V）→ 覆盖审计与报告（Q）→ 改版复验（H）。
  “冷跑/热跑”保留为两次 Lint 运行的名称。

### 2.4 不兼容变更

| 对象 | 变化 |
|---|---|
| review-plan.json | `schema_version` 1 → 2；旧计划不能合并、校验或作改版基线，需重新生成 |
| evidence.json | `schema_version` 1 → 2；`rule` 使用总表编号 |
| intent.json | `schema_version`（可省略）1 → 2；`circuits[].domain` 改名为 `circuits[].type` |
| review-results.json | 结构不变（仍为 2），检查 ID 随计划变化 |
| circuit_bench 协议 | `stimulus.py`、`worker.py` 改用新编号与证据版本 2；数据、答案、评分不变 |
| 文档 | `lint-rules.md` 改为 `auto-checks.md`；`review-checklist.md`、`methodology-v1.0.md` 并入总表后删除 |

## 3. 有意的行为变化

- 冷跑的使能脚上下拉候选独立为 RST-A01；有证据时的判定仍是 RST-E01（原先两者同为 Rule-12）。
- 显式证据的兜底计划项按规则本身的方式归类，不再固定落入 ER1/ER4。
- 两条光耦规则名称加“光耦”前缀；`rule_plan` 的名称统一取自总表。
- I²C 清单的 scope 文字由 `Rule-09` 改为 `SIG-E01`，清单摘要随之变化。
- 新增人工规则 PWR-C13（热插拔浪涌与输入电容）、ANA-D02（运放未用通道），补齐原检查清单中
  未被生成规则覆盖的两项。

## 4. 验证

- 单元测试 512 项全绿（原 502 项按新编号更新，新增规则总表测试与旧计划/错配拒绝用例）。
- 等价对比：在改动前后分别运行全部单元测试并记录 302 份计划与 Lint 输出，把旧输出按下表翻译
  后逐项比较（计划项内容、准备度、缺口、触发依据、移交、父子关系、规则台账、依赖清单、改版路由、
  Lint 疑点/结果/通过记录）。除第 3 节所列变化外完全一致；唯一其余差异来自一个复制“首个计划项”
  作人工项的测试，首项随编号排序不同，属测试数据差异。
- circuit_bench：新协议 166 例全部通过，逐例记录、指标与验收结论与改动前一致；评测自带 19 项
  测试通过，三种故障注入全部被检出。

## 5. 旧编号对照

### 5.1 阶段

| 旧 | 新 |
|---|---|
| AC0（AC0-COLD） | 冷跑，方式 A |
| AC0-HOT | 热跑，方式 E |
| ER1 身份、官方条款与热跑 | 阶段 3 资料取证（DEV-D01、DEV-D02）+ 阶段 4 热跑 |
| ER2 电源树与状态 | 阶段 5 专家审查中的 PWR/RST 部分 |
| ER3 功能与控制链 | 阶段 5 连接追踪（方式 T） |
| ER4 参数、容差与改法复算 | 阶段 5 工程计算（方式 C） |
| ER5 平台条款 | 阶段 5 条款核对（方式 D）与功能覆盖项（方式 Q） |
| ER6 全页目检 | 阶段 6 图面目检（方式 V） |
| ER7 身份收口 | DEV-D01 与阶段 7 覆盖审计（方式 Q） |

### 5.2 规则

| 旧 | 新 | 旧 | 新 |
|---|---|---|---|
| Rule-01 | NET-A01 | Rule-11 | PWR-T02 |
| Rule-02 | NET-A02 | Rule-12（冷跑候选） | RST-A01 |
| Rule-03 | NET-A03 | Rule-12（热跑） | RST-E01 |
| Rule-04 | PWR-A01 | Rule-13 | PRO-A02 |
| Rule-05 | PWR-A02 | Rule-14 | DEV-E01 |
| Rule-06 | PWR-A03 | Rule-15 | NET-A04 |
| Rule-07 | REQ-A01 | Rule-15-INFO | NET-A05 |
| Rule-08 | PWR-E01 | Rule-16 | RST-E02 |
| Rule-09 | SIG-E01 | Rule-17 | REQ-H01 |
| Rule-10 | PRO-A01 | Rule-18 | PWR-A04 |
| INPUT-EXPORT | DOC-A01 | Rule-19 | NET-A06 |
| LOG-36038 | DOC-A02 | Rule-20 | DOC-A03 |

| 旧 | 新 | 旧 | 新 |
|---|---|---|---|
| IL-01 | DRV-A01 | PU-01 | RST-A02 |
| IL-02 | DRV-A02 | PU-02 | RST-A03 |
| PS-01 | DRV-A03 | PU-03 | RST-A04 |
| PS-02 | DRV-A04 | PU-10 | PWR-E02 |
| PS-10 | DRV-E01 | SV-01 | RST-A05 |
| IF-01 | PWR-A05 | SV-02 | RST-A06 |
| IF-10 | PWR-E03 | SV-03 | PWR-A06 |
| DL-01 | SIG-A01 | SV-10 | RST-E03 |
| DL-02 | SIG-A02 | OC-01 | PRO-A03 |
| DL-10 | SIG-E02 | OC-02 | PRO-A04 |
| | | OC-10 | PRO-E01 |

### 5.3 计划项（旧 `check` 键）

| 旧 | 新 | 旧 | 新 |
|---|---|---|---|
| coverage-input_consistency | DOC-Q01 | feedback-divider-wca | PWR-E01 |
| coverage-requirements | REQ-Q01 | enable-default-absmax | RST-E01 |
| coverage-chains | REQ-Q02 | strap-required-state | RST-E02 |
| coverage-states | REQ-Q03 | i2c-required-pull | SIG-E01 |
| coverage-datasheets | DEV-Q01 | connector-pin-map | DEV-E01 |
| coverage-history | REQ-Q04 | power-rail-topology | PWR-T01 |
| requirement | REQ-D01 | power-rail-budget | PWR-C01 |
| required-feature-presence | REQ-A02 | differential-pair-connectivity | SIG-T01 |
| physical-pin-inventory | DEV-D02 | schematic-page-graphic-review | DOC-V01 |
| component-identity-package | DEV-D01 | revision-impact-coverage | REQ-Q05 |
| provided-evidence | 证据所属规则（实例键 PROVIDED） | revision-removed-check | REQ-H02 |
| feature-ddr/usb/ethernet/can/rs485 | SIG-Q01～SIG-Q05 | feature-i2c/spi/uart/storage/rf | SIG-Q06～SIG-Q10 |
| feature-isolation | PRO-Q01 | feature-clock | CLK-Q01 |
| feature-reset | RST-Q01 | feature-（自定义） | REQ-Q06 |
| decoupling-discovery | PWR-D01 | decoupling-coverage-* | PWR-T03 |
| decoupling-*-connection | PWR-D02 | decoupling-*-capacitance / -rating | PWR-C09 / PWR-C10 |
| i2c-topology-* | SIG-T02 | i2c-region-*-sink-rise / -domain-off / -address-state | SIG-C01 / SIG-C02 / SIG-D01 |
| inductive-load-clamp-topology-* | DRV-T01 | inductive-load-clamp-rating-* | DRV-C01 |
| power-switch-gate-drive-* | DRV-E01 | power-switch-soa-* / -node-damping-* | DRV-C02 / DRV-D01 |
| input-filter-damping-* | PWR-E03 | input-filter-attenuation-* | PWR-C11 |
| power-up-enable-source-* | RST-T01 | power-up-dropout-* / -prebias-* | PWR-E02 / PWR-D03 |
| supervision-reset-path-* | RST-T02 | supervision-reset-pulse-* | RST-E03 |
| supervision-rail-coverage-* | PWR-T04 | optocoupler-transfer-* / -isolation-* | PRO-E01 / PRO-D01 |
| diff-level-compatibility-* | SIG-E02 | diff-level-termination-* | SIG-T03 |

电路检查包（原 `intent.circuits[].domain` 的 9 类）按规则总表“电路类型展开”对应：
POWER_CONVERTER 的 voltage-headroom/current-stress/timing-stability/loss-reverse 为 PWR-C02～PWR-C05；
POWER_PROTECTION 的 thresholds/soa/coordination 为 PWR-C06～PWR-C08；ANALOG 为 ANA-C01～ANA-C03；
I2C 为 SIG-C01、SIG-C02、SIG-D01；STARTUP 的 sampled-level/reset-timing/power-order 为 RST-C01、
RST-C02、RST-T03；DDR 为 SIG-D02、SIG-D03；USB_C 的 cc-role/vbus 为 SIG-D04、SIG-C05；
CAN_RS485 为 SIG-C03、SIG-C04；CLOCK 为 CLK-C01、CLK-D01。

## 6. 未在本轮处理

- 未提供导出日志时，DOC-A01/DOC-A02 不会出现在 Lint 的“本趟未执行”列表中（改动前即如此）。
- README 的输入说明只提到 Cadence/OrCAD 解析器，未提 KiCad（改动前即如此）。
- `evals/workflow_bench` 封存数据与 circuit_bench 历史记录保留旧编号，不改写。
