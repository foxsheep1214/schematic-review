# 以功能为判断单元：SR 审查方法改造方案（A–E）

状态：设计稿，待确认后实施。基线：SR main a8bebcb；案例：R5 新版复审（SR-20261019-R5-新版复审-2692b08）。

## 0. 一页摘要

现在的方法让审查员逐行填 407 条“规则 × 器件 × 状态”的检查，每行问“这个参数有没有保证值”。工程判断
本来是按功能做的（“偏置电路能不能让 U402 保持工作”），被拆到几十行之后，一个缺口被复制到所有沾边的行，
而真正的计算（写在 engineering.md 里，多半是对的）没有正式地位，校验只看行不看分析。

改造后：

1. **功能判定**是唯一的判断单元。每个功能电路一条记录：要回答的问题、手册里有关的全部条款、计算、余量、结论。
2. **行从功能派生**。行只是覆盖审计；PASS 行由脚本生成，只有功能判定里写明的“开放项”才让对应的行变成资料不足。
3. **计划把判据写成问题**，并为每个功能生成现成的框架（问题、成员行、核对单）。
4. **校验核功能判定**：条款列了没有、算出余量就必须下结论、设计值不许向厂家要、没保证值要算最坏情况、改结论必须引用条款或数字。
5. **审查员填行时不读规则书**，读功能框架。

预期：R5 的 142 条资料不足、18 件待办，变成约 10 条开放项；W-BIAS、W-HV、W-NTC 按手册判通过并交样机实测，
W-OVP、W-SR 给出数字结论（通过并写余量，或指出风险和改法）。

## 1. 现在的方法哪里出错（R5 的数字）

| 现象 | 数字 | 说明 |
|---|---|---|
| 一个判断被复制 | 142 条资料不足只有 18 种缺口文字 | 平均一个缺口贴到 8 行 |
| 一个问题问多遍 | Q401 有 23 行，“偏置能否撑住 VCC”在 5 条规则 × 3 个状态里问了 15 遍 | 规则 PWR-C02/C03/C04/C05/C15 × STARTUP/RUN/LATCH |
| 分析和判定脱钩 | engineering.md 算出 VCCmin 10.24 V > 9.5 V，行仍判资料不足 | 行的判据问“有没有全温保证值”，分析答的是“电路能不能工作” |
| 判据预设答案 | PWR-C02.U402-HV-START 的判据写着“不把 120 V 测试点外推” | 这一行是最后一轮“逐行语义复核”加的，也是它把正确判断推翻 |
| 成本倒挂 | 资料不足行中位数 1515 字，PASS 行 641 字；但资料不足可以复制 | PASS 要出处、页码、计算，资料不足只要填满缺口块 |
| 行的归属 | 129 行挂在 intent.circuits 的 12 个电路上，其余 278 行是器件/引脚/需求表 | 资料不足里 59 条在电路行，83 条在器件/需求行，但后者的缺口文字和电路行相同 |

规则书 5600 行，证据尺度一节 495 行，多数是禁止句。填行时审查员匹配到最醒目的禁止句就停；
允许句（单调外推、反算范围）要做计算才能用，很少用上。昨天加的“5 步”仍是规则，治标。

## 2. 目标与不变的部分

目标

- 一个功能只判一次；判定里有条款、计算、余量，校验能核。
- 资料不足只有在列完条款、算完余量、分清设计值、算过最坏情况之后才允许写。
- 改变结论必须引用条款或数字；只看措辞的复核不能改结论。
- 审查员在填行阶段读的材料压到一页以内。

不变

- 覆盖不变：规则目录、功能包、全部 407 行仍在计划和结果里，行仍是审计底账（纲要第七项“证据覆盖”）。
- 交付不变：`审查报告.md` + `record/`；ASG 交接合同里的文件角色（review_intent/db/review_plan/review_results/review_gate）不变。
  ASG 的 review-comments 用报告里的待办编号（W-…）回应，编号规则保留。
- 阶段 NA + HANDOFF、需求澄清、REQ-H02 复审机制不变。
- P0、器件损坏和保护类判据仍要求本器件保证值；放宽的只是必需功能和性能（a8bebcb 已改）。
- 不做旧台账兼容：结果 schema 升到 4，schema 3 台账拒读（与 2026-10-10 起的约定一致）。

## 3. 方案总览

```
现在   intent.circuits ─► 计划 407 行（通用判据）─► 审查员逐行填 ─► work_items 手写 ─► 校验行 ─► 报告
                                                   ▲ engineering.md（自由文本，无地位）

改后   intent.circuits ─► 计划：407 行（具体问题）+ 功能框架 ─► 审查员写功能判定（条款/计算/余量/结论/开放项）
                                                                      │
                                              derive_rows.py ◄────────┘  行由功能派生；功能外的行手填
                                                    │
                                           校验：功能判定 + 行一致性 ─► 报告（待办 = 开放项）
```

## 4. A：功能判定

### 4.1 放哪里

`review-results.json` 顶层新增 `functions`（schema 4）。不另开文件：交接合同的文件角色不变，
一份结果文件里“先有功能判定、后有行”的顺序由校验保证（行必须引用功能）。
engineering.md 继续作为自由文本证据，由 `evidence` 定位引用。

### 4.2 字段（以 R5 的偏置电路为例，数字取自原记录和手册）

```json
{
  "id": "FN-BIAS-VCC",
  "circuit": "BIAS",
  "question": "默认 5 V 输出、−10..105 °C、辅助绕组取最低电压时，Q401 偏置路径能否让 U402 VCC 保持在 9.5 V 以上",
  "objects": {"refs": ["Q401", "D401", "D402", "D404", "R401", "C403"], "nets": ["AUX_DC", "BIAS15", "VCC"]},
  "states": ["STARTUP", "RUN", "LATCH"],
  "conditions": [
    {"id": "c1", "source": "Nexperia-PMEG6010CEH.pdf", "locator": "p3 Table 7",
     "says": "VF ≤ 0.31 V @10 mA，≤ 0.40 V @100 mA（25 °C）",
     "use": "工作电流约 20 mA 在两点之间，VF 随电流单调上升，取 0.40 V 作上界；高温 VF 更低"},
    {"id": "c2", "source": "Infineon-ISC032N12LM6.pdf", "locator": "p4 Table 4",
     "says": "VGS(th) 1.2–2.2 V @110 µA",
     "use": "20 mA 下 VGS 略高于阈值，取 2.2 V + 0.5 V 工程余量 = 2.7 V（B 级推导）"},
    {"id": "c3", "source": "NCP1343.pdf", "locator": "p7 Table 7", "says": "VCC(off) 8.5/9.0/9.5 V", "use": "判据取最大值 9.5 V"},
    {"id": "c4", "source": "evidence/engineering.md", "locator": "## BIAS", "says": "US1M VF 取 1.7 V（1 A 最大值）", "use": "20 mA 实际约 1 V，1.7 V 偏保守"}
  ],
  "calculation": {"claim_ids": ["BIAS-VCCMIN"], "result": "VCC_min = 10.24 V", "margin": "+0.74 V 对 9.5 V",
                  "assumptions": ["辅助绕组 −10%", "Na/Ns = 21/6"]},
  "verdict": "OPEN",
  "fails": [],
  "open": [{
    "key": "AUX-5V-MIN",
    "kind": "DESIGN_VALUE",
    "what": "T301 辅助绕组在 5 V 空载时的最低峰值电压还没有定（磁件设计单列为待定）",
    "spec": "5 V 空载、全温下 AUX_AC 峰值 ≥ 14.5 V（= 9.5 + 2.7 + 0.4 + 1.7 + 0.2 V 余量）；相对标称值只允许下降 14%",
    "owner": "ASG 磁件设计",
    "decides": [{"aspect": "电压窗口", "states": ["STARTUP", "RUN"]}],
    "severity": {"level": "P1", "class": "REQUIRED_FUNCTION", "consequence": "辅助电压低于规格时 U402 在 5 V 待机掉电重启"},
    "design_option": {"status": "NONE", "reason": "先定磁件规格；定不下来再改为有保证压差的受控偏置"}
  }],
  "handoffs": [{"receivers": ["样机试验"], "constraint": "5 V 空载、−10 °C 时 VCC ≥ 9.5 V", "verification": "实测 C403 电压"}],
  "evidence": [{"source": "evidence/engineering.md", "locator": "## BIAS"}, {"source": "evidence/calc-claims.json", "locator": "BIAS-VCCMIN"}]
}
```

含义

- `conditions` 是第 1 步“先用手册已有的界限”：相邻测试点、工作条件下限、门限、温度系数都写在这里，`use` 写怎么用。
- `calculation.margin` 是第 2 步：有余量就必须有结论；`verdict` 只能是 PASS / FAIL / OPEN。
- `open[].kind` 分清第 3 步和第 5 步：`DESIGN_VALUE`（本设计要定的量，必须写 `spec` 和 `owner`，不许向厂家要）、
  `VENDOR_DATUM`（厂家才知道的参数，必须写 `checked`（查过的条款 id）、`why_insufficient` 和 `worst_case`）、
  `REQUIREMENT`、`REVIEW_INCOMPLETE`、`USER_DEFERRED`。
- `decides` 限定这个开放项让哪些“方面 × 状态”判不了；其余行照常 PASS。方面 = 规则目录里的规则标题（PWR-C02 = 电压窗口，PWR-C03 = 电流应力，…）。
- `severity` 和 `design_option` 一份写在开放项上；现在的 work_item 字段（title/root_cause/reason/next_action/design_option/request_keys）全部由此派生，不再手写。
- `fails[]` 结构同 `open[]`，带 `finding_id`，指向发现项。

### 4.3 功能从哪里来

- 计划按 `intent.circuits` 为每个电路生成一个功能框架（见第 6 节）。R5 有 12 个电路。
- 审查员可以增加框架外的功能（R5 的 OVP-FAULT、OPTO、SR 三节在 intent 里没有电路）；增加的功能同样校验。
- 隔离资格（PRO-C03）和环路稳定（PWR-C15）现在用 `closure_contract.obligations` 单独保证；改后它们是 BARRIER 和变换器功能的方面，
  `review_obligations.py` 退役，不保留平行机制。

## 5. B：行从功能派生

### 5.1 规则

- 计划的每一行带 `function_id` 和 `aspect`。电路成员行由计划直接绑定；非电路行（DEV-C05、PRO-C02、REQ-D01 等）计划按位号重叠建议绑定，审查员可改。
- 行的结论由功能决定：
  - 功能 PASS → 成员行全部 PASS，`rationale` 自动写“见功能判定 FN-X（方面，状态）：结论一句 + 余量”。
  - 功能 FAIL → `fails[].decides` 命中的行 FAIL（带 finding_id），其余 PASS。
  - 功能 OPEN → `open[].decides` 命中的行 INSUFFICIENT，`gap_cause` 由 `kind` 映射（DESIGN_VALUE→DESIGN_OPEN，VENDOR_DATUM→EXTERNAL_DATA，…），行上只写 `open_ref: "FN-X/KEY"`，不再重复 gaps 文字；其余 PASS。
- 校验强制：INSUFFICIENT 行必须有 `open_ref`，且该行的（aspect, state）在开放项的 `decides` 里；绑定到 PASS 功能的行不能是 INSUFFICIENT；FAIL 行必须对应 `fails[]`。
- 没有绑定功能的行（图面目检、引脚表核对、器件身份等事实性检查）照旧手填；但它们要判资料不足，也必须先建一个功能判定（哪怕只有一个条件、一句计算）。这条规则保证“资料不足”在全板只有一个入口。

### 5.2 脚本

`scripts/derive_rows.py review-plan.json review-results.json -o review-results.json`：读 `functions`，为每个已绑定的行生成或更新结果；
已手填的行不覆盖，只校验一致。审查员写完功能判定后跑一次，再手填剩余行。

### 5.3 R5 偏置电路的前后对比

| | 现在 | 改后 |
|---|---|---|
| Q401 相关行 | 15 行 INSUFFICIENT（EXTERNAL_DATA），缺口文字相同 | 2 行 INSUFFICIENT（PWR-C02 电压窗口，STARTUP/RUN，DESIGN_OPEN），13 行 PASS，rationale 引用 FN-BIAS-VCC |
| 待办 | W-BIAS“给出 5 V 默认态偏置的保证范围”，涉及 21 条检查，向厂家要全温曲线 | W-AUX-5V-MIN“T301 辅助绕组 5 V 空载峰值 ≥ 14.5 V”，交 ASG 磁件设计，涉及 2 条 |
| 器件参数 | “缺全温小电流保证” | 条款 c1/c2 写明用相邻测试点和阈值上限定界，B 级通过，样机实测 |

HV 启动（W-HV）按同样方法会变成 PASS：条款列出 VHV(MIN) ≤ 40 V、VBO(start) 107–116 V、R403 压降，计算 HV 脚电压对门限的余量。
剩下的“充电期间是否比较欠压门限”若手册图 6 读不出来，才是一个 VENDOR_DATUM，且 `worst_case` 要写按最大启动电流算的结果。

## 6. C：计划把判据写成问题，并生成功能框架

- `catalog.py` 为功能包成员规则增加 `question` 模板（约 40 条规则），用电路 id、位号、状态和需求窗口填空。
  例：PWR-C02 → “{state} 时 {circuit}（{refs}）的输出在要求的输入/负载/温度范围内是否落在负载要求的窗口 {window} 内”。
  `window` 来自 `intent.power_rails` 的节点窗口；没有就写“（需求未给窗口）”。通用 `criterion` 保留为提示，不再是行的问题。
- 计划新增 `functions` 框架：每个电路一条，含 `question`（由该电路所有成员问题归纳的一句，审查员可改）、成员行 id 与方面、
  状态、相关规则的盲区各一句、以及五步核对单（原文抄自 evidence-proportionality.md，5 行）。审查员照框架填写，不翻规则书。
- 判据里不允许出现禁止句（“不把…外推”“不得…”）：`catalog.plan_explanation_errors` 加一条检查，审查员补加的行同样受限。
- 计划 schema 升到 4；kicad_replay_bench 开新合同修订 `function-frames-v1`。

## 7. D：校验核功能判定

硬错误（`validate_review` 新增，放在 `review_functions.py`）：

| 编号 | 条件 | 为什么 |
|---|---|---|
| F1 | 每个功能有 question、objects、≥1 条 conditions（source/locator/says/use 齐全）、verdict | 没列条款就不能说资料不足 |
| F2 | DESIGN_VALUE 开放项有 spec、owner，文字里不含“向…索取/取得” | 设计值反算成规格，不问厂家 |
| F3 | VENDOR_DATUM 开放项有 checked（≥1 个 conditions id）、why_insufficient、worst_case（result 或 not_boundable_reason） | 第 5 步才允许，且要算过最坏情况 |
| F4 | calculation.margin 存在且为正，同一方面不得有开放项；要保留须写 margin_not_decisive_reason | 算出余量就下结论 |
| F5 | 行一致性（5.1 节）；每个框架都有判定；每个成员行都绑定 | 行不能脱离功能自行判资料不足 |
| F6 | `verdict_history` 每条改判引用 conditions 或 calculation 的 id | 改结论必须有条款或数字 |
| F7 | 开放项 decides 覆盖超过 3 个方面或全部状态时必须写 `decides_reason` | 防止一个开放项再次铺到整块电路 |

自检变化

- `MARGIN_COMPUTED_BUT_OPEN`、`DESIGN_VALUE_ASKED_OF_VENDOR` 升级为 F4/F2 硬错误，行级版本删除。
- `REUSED_RATIONALE_ACROSS_SCOPES`、`TEMPLATED_SEVERITY_REASON`、`REQUEST_SCOPE_ECHOES_TASK`、`TEMPLATED_WORK_ITEM_REASON`、
  `DUPLICATE_WORK_ITEMS`、`BOILERPLATE_ACQUISITION` 对派生行不再有意义，删除；保留对手填行的措辞类提示。
- 现在 SKILL 第 7 步的“逐行语义复核”改为“功能复核”：按功能重读条款和计算，改判走 `verdict_history`。
  措辞、粘连、字段整理不改任何 verdict。

## 8. E：审查员在填行阶段读什么

SKILL 第 5 步改成三小步：

1. **功能判定**：按计划的功能框架逐个填写。框架自带问题、成员、核对单和盲区，审查员读手册和自己的计算，不读参考文档。
   需要查规则细节时按框架里给的锚点跳转，不整篇读。
2. **行派生**：跑 `derive_rows.py`。
3. **手填剩余行**：图面目检、引脚表、器件身份、需求条款等事实性检查，照现有写法。

第 7 步删除“逐行语义复核”，改为“功能复核”（第 7 节）。evidence-proportionality.md 保留为维护者和框架模板的来源，不再要求审查员通读。

## 9. 报告变化

- 数字一览第一行改为“功能判定 通过 / 不通过 / 未定”；检查条数行保留在后面。
- 结论之后加一节“各功能的判断”，一表：功能 | 问题 | 结论 | 余量或依据 | 待办编号。这是读者真正要的信息（“偏置：能，余量 0.74 V”）。
- 待办由开放项派生，编号保持 W-… 风格（ASG review-comments 依赖），五行写法不变；“涉及 N 条检查”按 decides 计。
- 其余节不变。

## 10. 对现有部件的影响

| 部件 | 影响 | 处理 |
|---|---|---|
| results schema | 3 → 4：新增 functions；行新增 function_id/aspect/open_ref，去掉 gaps、work_items、request_keys、obligations | 旧台账拒读，不做转换 |
| plan schema | 3 → 4：行新增 question/function_id/aspect，新增 functions 框架 | 同上 |
| review_engine 指纹 | 变化，进行中的审查须重审 | R5 本来就要重审 |
| ledger_replay（3 份 R3 schema 3 台账） | 不能再读 | 退役；R5 按新方法重审后，把它冻结为第一份新基线；依赖它的变异 M2/M3/M5/M6/M8 改指向单元测试（RESULTS 表里已有替代杀手） |
| kicad_replay_bench | 计划合同变化 | 新修订 function-frames-v1 |
| golden 报告 | 措辞变化 | 重新生成并审读 |
| run_regression 登记的 R3/R4 记录 | 已因 schema 2 各报 1 个错，基线不变 | 不动 |
| typical_circuits / seeded_bench / hot_bench | 只测自动层 | 不受影响 |
| closure-obligations（PRO-C03/PWR-C15） | 并入功能方面 | review_obligations.py、task_scope.py 退役 |
| ASG 交接 | 文件角色不变；gate 仍输出 workflow.current_work_items（派生） | 在 ASG 侧核一次 review-comments 流程 |
| 文档 | SKILL 第 5/7 步、plan-and-results（新增功能判定一节，删 work_items/request_keys）、verdicts-and-release（待办一节改派生）、report-and-remediation、closure-obligations（并入）、evidence-proportionality（5 步保留，注明进框架） | 同步改 |

涉及脚本：results_model、validate_review、review_workflow、review_summary、review_quality、plan_review、catalog、
render_report、pack_review、新建 review_functions、derive_rows；退役 review_obligations、task_scope。
测试：9 个引用 work_items 的测试文件重写夹具（decisive()/downstream() 改为带 functions），新增功能判定合同测试。

## 11. 实施顺序与每步的验证

| 步 | 内容 | 验证 |
|---|---|---|
| 1 | results schema 4 + 功能判定校验 F1–F7 + 行一致性 | 合同层测试：合成夹具（偏置例子 + 一个 PASS 功能 + 一个 FAIL 功能）全部通过；反例逐条被拒 |
| 2 | 计划：question 模板、功能框架、禁止句检查、plan schema 4 | test_rule_contracts；kicad_replay 新修订；R5 的 intent 生成 12 个框架，成员行全部有 aspect |
| 3 | derive_rows.py | 用偏置例子派生：15 行中 2 行 INSUFFICIENT、13 行 PASS，校验通过 |
| 4 | 报告与打包：待办派生、功能表、计数 | golden 重生成；pack 白话检查通过 |
| 5 | 文档与 SKILL | catalog --write-doc；pack 的用词检查；人工读一遍第 5/7 步 |
| 6 | 基准：退役 ledger_replay，变异杀手重指，RESULTS 重跑 | 12/12 KILLED；全量测试通过 |
| 7 | **验收：用新 SR 重审 R5** | 目标：开放项 ≤ 12；资料不足行 ≤ 40；W-BIAS 变为 1 个 DESIGN_VALUE 开放项并带规格；W-HV、W-NTC 为 PASS；W-OVP、W-SR 给出数字结论；不出现 F1–F7 错误 |

第 7 步是真正的验收。前 6 步的测试只证明机制，不证明判断变准。

## 12. 已定的点（2026-10-20）

1. `functions` 放在 review-results.json 顶层，不另开文件。
2. 台账回放：退役 R3 三份；R5 按新方法重审后冻结为第一份基线。
3. 报告在结论之后加“各功能的判断”一表，一行一个功能。
4. work_items 不再手写，由开放项派生；编号保持 W-…。
5. 功能粒度：每个 intent 电路一个，状态在开放项的 decides 里限定。
6. 实施：按第 11 节 7 步分会话做，每步提交并跑门；第 7 步重审 R5 是验收。

## 13. 风险与对策

- **功能太粗，一个开放项又铺满整块电路。** `decides` 必填；超过 3 个方面要写理由（F7）。
- **278 行非电路行仍要手填。** 它们多数是事实核对（引脚表、身份、目检），本来就不是问题源；要判资料不足也必须先建功能，入口唯一。
- **question 模板要逐条写。** 只写功能包成员的约 40 条；其余规则保留 criterion。
- **审查员在功能判定里仍然偷懒写 OPEN。** F1–F4 让 OPEN 比 PASS 更费力：要列条款、算最坏情况、反算规格。成本结构反过来是本方案的要点。
- **工作量。** 约 11 个脚本、9 个测试文件、6 份文档、3 个基准；加上 R5 重审验收，估计 3–4 个会话。
