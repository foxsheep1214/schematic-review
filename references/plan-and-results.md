# 计划与结果台账

审查数据分三份：`intent.json`（设计意图与输入声明）、`review-plan.json`（逐项检查计划）、
`review-results.json`（逐项结果）。计划只决定每项的规则、适用性和准备度，不提前制造 PASS/FAIL；
结果另存，由 `validate_review.py` 对账。常规命令见 [SKILL.md](../SKILL.md)。

## 一、intent.json（schema_version 3）

合成示例（数值仅说明结构）：

```json
{
  "schema_version": 3,
  "review_mode": "first",
  "review_phase": "design_iteration",
  "input_sha256": "填写 decoupling.py 候选清单里的 input_sha256",
  "assemblies": [{
    "id": "run-option-A", "citation": "装配 BOM Rev.B 选项 A；跳线表 Rev.C 第 2 行",
    "population": {"U1": true, "C1": true, "C2": false}, "jumpers": {"JP1": "closed"}
  }],
  "devices": {
    "U1": {
      "mpn": "REG-X-ADJ", "package": "QFN-16",
      "identity_citation": "BOM 订货码与官方订货表对应行",
      "citation": "REG-X datasheet Rev.A 第 3 页完整脚表", "pinout_complete": true,
      "pins": {"1": {"name": "VIN", "role": "power"}, "2": {"name": "GND", "role": "return"}}
    }
  },
  "requirements": [{
    "id": "REQ-USB", "text": "提供一路 USB 设备接口", "status": "CONFIRMED",
    "citation": "Requirements v1.2 section 4.1",
    "criterion": "PHY 与连接器双向链路、供电及外部带电状态满足接口条件"
  }],
  "circuits": [{
    "id": "USB-PORT", "type": "USB",
    "refs": ["U1", "J1"], "nets": ["USB_DP", "USB_DM", "VBUS"],
    "states": ["startup", "run", "external-power-only"],
    "citation": "Requirements v1.2 section 4.1; schematic page 2"
  }],
  "expect": {"USB_PHY": 1},
  "features": {
    "USB": {"applicability": "APPLICABLE", "citation": "Requirements v1.2 section 4.1"},
    "DDR": {"applicability": "NOT_APPLICABLE", "citation": "Requirements v1.2 section 2.3"}
  },
  "materials": {
    "requirements": {"available": true, "citation": "Requirements v1.2"},
    "schematic_pdf": {"available": true, "citation": "SCH-100 rev.B.pdf"},
    "datasheets": {"available": true, "citation": "datasheet-manifest.json 2026-08-31"},
    "platform_checklist": {"available": false}
  },
  "power_rails": {
    "VCC_3V3": {
      "voltage_v": {"min": 3.2, "max": 3.4}, "load_a": {"min": 0, "max": 0.5}, "available_a_min": 1.0,
      "refs": ["U1", "L1", "F1"], "state": "BOM B; stated Vin/load/temperature corners",
      "citation": "Load budget Rev.B table 2 and component guaranteed ratings"
    }
  }
}
```

- `review_mode`：`first` 或 `revision`。`review_phase` 取值见 [结论与准出](verdicts-and-release.md#5-审查阶段)。
- `features` 的键与 `circuits[].type` 取 [规则总表](check-catalog.md)“功能包”中的包名，否则拒绝；
  `applicability` 为 APPLICABLE / NOT_APPLICABLE / UNDETERMINED，前两者必须带 `citation`。
- 名称命中只生成 UNDETERMINED 候选，不展开成员；由电路声明、features 出处或已确认拓扑确认后再展开。
  带出处的不适用声明可排除误命中；与已确认拓扑冲突则保留待核。没搜到关键字不能推出 NOT_APPLICABLE。
- `materials.<name>.available=true` 必须带 `citation`。逐物料审计（`--datasheet-audit`）优先于这些全局布尔值。
- `assemblies`（1–32 个，各带 `id` 与 `citation`）是全部检查器共用的装配状态；`devices` 是按位号的官方脚表。
  声明二者或任一检查器段时须带顶层 `input_sha256`，过期即拒绝。
- `requirements[].status`：已确认（CONFIRMED）、提案（PROPOSED）、未定（OPEN）、暂缓（DEFERRED）。
  按需求文档原样填写，不省略未定项。OPEN 的 REQ-D01 必须 INSUFFICIENT + REQUIREMENT_OPEN；
  DEFERRED 必须 INSUFFICIENT + USER_DEFERRED；PROPOSED 可判定，但结论以提案为前提。
- `power_rails` 支撑 PWR-C01 与 DEV-E02：给电压/最大负载、源端最弱保证可供电流和条件；READY 不等于 PASS。
- 条件导通另可声明 `power_sources`（某状态的供入节点）与 `power_paths`（某状态可导通的方向，不是理想短路或载流声明），
  不得把未上电的稳压器或端口标成 source 来消除告警。
- 各检查器的 intent 段（`i2c_topology`、`decoupling`、`device_kinds` 等）见 [自动检查](automation.md)。

## 二、review-plan.json（schema_version 3）

### 生成与合并

- 冷跑 `lint.py --plan-json review-plan-cold.json` 保存计划和候选；人工补查项加入该计划。
- 热跑 `--merge-plan review-plan-cold.json --plan-json review-plan.json` 产生**唯一最终计划**。
  合并要求 `db_sha256` 与当前输入一致且规则指纹相同，保留人工补查项；相同 ID 的对象/判据冲突时拒绝自动覆盖。
- 匹配证据后保留基础覆盖项，按 evidence ID 生成带 `parent_check_id` 的状态子项；基础项只汇总覆盖，不能代替子项结果。
- 计划合并不读取或迁移结果；后续补查先更新计划，再更新 digest 和逐项结果。
- 人工补查项从总表选规则，`id` 写成 `规则编号.自定义键`，并填与总表一致的 `rule`/`method`/`domain`、
  `object`、`criterion`、`applicability`、`readiness`、`handoff`。

### 检查项字段

| 字段 | 含义 |
|---|---|
| `id` | `规则编号[.实例键].锚点`，如 `RST-T02.U3.SYS-RST-N` |
| `rule` / `method` / `domain` | 规则编号、方式代码、内容域代码，须与总表一致 |
| `object` | 对象：覆盖维度、功能包、全板、网络、位号、引脚或页码 |
| `criterion` | 本项判据 |
| `applicability` | APPLICABLE / NOT_APPLICABLE / UNDETERMINED |
| `readiness` | READY / WAITING_EVIDENCE / NOT_SCHEDULED |
| `required_inputs` | 当前缺失的输入 |
| `trigger` | 实例化该项的可复现依据 |
| `handoff` | 独立下游动作，可与任一结果并存 |

`rule_plan[]` 回答“这类规则要不要跑”，`checks[]` 回答“具体审哪一项”。

- APPLICABLE + READY：本轮执行；READY 不代表 PASS。
- APPLICABLE + WAITING_EVIDENCE：必须执行但缺材料，未补齐时为 INSUFFICIENT。
- UNDETERMINED：先补意图或解决意图/网表冲突，不得偷换成 NA。
- NOT_APPLICABLE：须有范围依据，结果为 NA。
- 需求要求某功能但网表未检出特征时，计划新增 REQ-A02 并报告 `REQUIRED_FEATURE_NOT_DETECTED`。

### 展开规则

- **全板通用**规则每板一项（`{"board": "BOARD"}`）；准备度按该规则所需资料判定。
  DOC-T01 逐 `intent.assemblies` 声明的装配状态一项。
- **逐位号**：每颗 IC/模组生成 DEV-C05 与 DEV-D05；每个连接器生成 DEV-D03、DEV-D05 与 PRO-D03。
  声明了 `intent.devices` 的位号，DEV-D02 带官方/符号双向差集，DEV-D05 带待核引脚清单（不是结论）。
- **需求与覆盖**：每条需求实例化为 REQ-D01；另有六类覆盖审计项 DOC-Q01、REQ-Q01～Q04、DEV-Q01。
- **证据计算（E）**：READY 须当前网表指纹、文档指纹、准确型号/版本/定位、依赖物料 AVAILABLE 及必要模型输入齐全，
  否则 WAITING_EVIDENCE。每条匹配证据生成独立状态子项。
- **功能包**：汇总项 REQ-Q07 只汇总覆盖；功能包适用后生成成员规则，声明了电路时逐电路×工况，
  否则按功能包一次；各成员仍须按 [最小充分证据](evidence-proportionality.md) 核适用性。
  未检出也未声明的功能包汇总到一项 REQ-Q08，逐个确认不适用并给依据。
- **检查器**：清单写在同名顶层键并带 `<id>_version`，计划项 `object` 带 `<id>_digest` 绑定清单，
  `inventory_gaps` 保留缺口——有缺口不能判 PASS；最终校验会重建清单，不能编辑清单消缺口。

## 三、review-results.json（schema_version 2）

### 顶层字段

- `plan_digest` / `db_digest`：`validate_review.fingerprint()` 对 JSON 对象排序序列化后的 SHA-256（不是文件字节哈希）。
- `checks`：与最终计划 ID 集合完全一致的逐项结果。
- `findings`：唯一已确认缺陷/改善，一个根因可被多个检查引用。
- `scope_checks`：六个覆盖维度 `input_consistency`、`requirements`、`chains`、`states`、`datasheets`、`history`
  各指向对应覆盖审计项。表示覆盖审计完成，不是该域全部电气通过。
- `coverage`：各维度“对象→检查 ID 数组”的完整映射。有 `--db` 时机械检查 components、pins、nets、pages
  及 requirements 是否都关联至少一条检查；仅 PDF 时由页面/手工对象清单另审，不制作伪网表。
- `binding_version: 1`、`remediation_version: 2`（见 [报告与修改说明](report-and-remediation.md)）、
  `requirement_clarification_version: 1` 与 `requirement_clarifications`（无则 `[]`）、
  `workflow_version: 1` 与 `work_items`（见 [结论与准出](verdicts-and-release.md#共同根因归并为任务)）。
- 复审另有 `revision_impact_version`、`revision_digest` 和必需项的 `reverification`，见 [改版复审](revision-review.md)。
- `summary` / `release` 可省略，由校验器计算；填了必须一致。

### 单条检查

```json
{
  "id": "SIG-T04.PATH-U1-J1",
  "binding": {
    "object": {"refs": ["U1", "J1"], "nets": ["SENSE_A", "SENSE_B"], "state": "RUN"},
    "criterion": "RUN 时 U1.4 与 J1.1 必须导通"
  },
  "applicability": "APPLICABLE",
  "review_result": "FAIL",
  "evidence_confidence": "A",
  "evidence": [{"source": "db.json", "locator": "nets.SENSE_A; nets.SENSE_B"}],
  "rationale": "要求的检测端点不连通，见路径表 PATH-01。",
  "severity": "P1",
  "finding_id": "F-001",
  "blocking": true,
  "disposition": "OPEN",
  "handoff": {"required": false}
}
```

- `binding.object`/`binding.criterion` 是实际已审范围，与同 ID 计划的 object/criterion 完全一致；
  `evidence` 和 `rationale` 只支持这个对象、配置、工况和判据。复用结论前核对物理脚、网络及要求，
  不能因 ID 相似、同一 IC 或同一功能组就移用。
- 所有结果含非空 `rationale` 与可定位 `evidence`。PASS/FAIL 只能 A/B；INSUFFICIENT 必须 C 并给
  `missing_inputs` 和 `potential_severity`（REQUIREMENT_OPEN 除外）；非 FAIL 不填 severity。
- INSUFFICIENT 可加 `gap_cause`：REQUIREMENT_OPEN、EXTERNAL_DATA、DESIGN_OPEN、REVIEW_INCOMPLETE、
  DOWNSTREAM_VERIFICATION、USER_DEFERRED，含义见 [最小充分证据](evidence-proportionality.md#复核每条证据不足)。
- NA 必须 NOT_APPLICABLE；修改自动计划的适用性需 `applicability_evidence`。UNDETERMINED 只能落 INSUFFICIENT。
- `disposition`：FIXED_VERIFIED / RETRACTED 只用于当前 PASS/NA 并须 `closure_evidence`；ACCEPTED 保留
  FAIL/INSUFFICIENT，附 `acceptance`（by/date/scope/reason/record，来自真实授权记录）。P0/P1 潜在未知默认阻断。
- 必需 handoff 的 receivers/constraint/verification 不可空；ACCEPTED/VERIFIED 须有 evidence；
  取消计划中的必需 handoff 须 `handoff_evidence` 留据。

### 发现项

每个 `findings[]` 含 id、kind（DEFECT / IMPROVEMENT）、severity、check_ids 及非空的 `title`、`observed`、
`criterion`、`impact`、`scenario`、`root_cause`、`recommendation`、`verification`、`severity_reason`、`remediation`；
`location` 含 pages/refs/nets 字符串数组，缺图面时写“未定位：缺某版本 PDF”，不编造页码。

- DEFECT 与其 FAIL 检查双向引用；一个根因一个 ID。严格绑定下，DEFECT 的 check_ids 都必须是该 finding 的 FAIL。
- location 覆盖各被检查的主对象（计划 object.ref、object.node 所属位号、object.net），不用共同电源或宽泛功能组代替。
- IMPROVEMENT 仅 P3，关联判据必须已 PASS。
- 例：STRAP 缺陷不能挂到已满足的 EN 判据；装配/等效值与低电平/上升时间是独立判据，不能互相代判。

## 四、校验与门禁输出

    python3 scripts/validate_review.py review-plan.json review-results.json --db db.json --lint lint-cold.json --lint lint-hot.json --require-actionable --require-bindings --json review-gate.json

- 退出 0 表示台账有效（结论 NO_GO 也可正常交付）；2 表示台账有错。冻结门加 `--require-release`，NO_GO 也退出 2。
- 校验只证明记录一致，不验证来源文字真实、计算合理或判据穷尽。空计划、遗漏对象、C 写 PASS、NA 冲突、
  无位置/改法、虚假汇总、陈旧规则指纹均被拒绝。
- **自动扫描候选处置**：两次 `--lint` 提供冷/热 JSON；`lint_reviews` 每条含 `run_digest` 与
  `items`（finding 索引→结果检查 ID 数组），全部候选都要处置；证据计算候选须关联对应状态子项。
  无证据时也保存一次未带证据的热跑。仅 PDF 模式明确 NA 并留依据。
- **输出**：`summary`（检查结果计数、唯一缺陷及 P0–P3）、`categorized_summary`（当前/历史检查、唯一缺陷、
  唯一任务、必需移交及其状态）、`insufficient_by_cause`、`requirement_clarification_summary`、`workflow`、
  `release`/`blockers`、`remediation_validation`、`binding_validation`。
- **quality_screening** 提示两类疑点：跨对象/判据复用完全相同理由，及位号与声明范围不相交。
  仅作提示，不增添缺陷、不改变 release；共享证明可一次核实，零提示不证明审完。

## 五、规则指纹与重新审查

计划写入 `review_engine`：SKILL.md、`references/` 与 `scripts/` 的逐文件 SHA256 及总摘要（含未提交修改，
排除测试、缓存、隐藏文件、`.pyc` 和 `~` 备份）。任何规则文字修改都会改变指纹。

- 指纹变化后以当前输入重新生成计划并完整审查；旧 PASS、旧缺口列表不能代替本轮判断。
- 冷/热合并只接受同一指纹；CLI 校验要求当前指纹。
- 原始 datasheet、已验证模型和计算数据可复用，但先复核型号/版本、工况、保证条件和当前判据。
