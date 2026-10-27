# review-results.json 格式

> 读者：审查员。

审查数据分四份文档：[intent 格式](intent-format.md)（`intent.json`，按需求和设计结果写，不抄设计方的意图文件）、[计划格式](plan-format.md)（`review-plan.json`）、[结果格式](results-format.md)（`review-results.json`）、[校验与重新审查](gate-and-rerun.md)（门禁输出与规则指纹）。计划只决定每项的规则、适用性和准备度，不提前制造 PASS/FAIL；结果另存，由 `validate_review.py` 对账。常规命令见 [SKILL.md](../SKILL.md)。

台账有三层，只有第一层是审查员写的判断：
- **功能判定**（`functions[]`）是判断单位。一个功能回答一块电路的一个问题（“偏置路径能否让 VCC 保持在 9.5 V 以上”），
  带手册条款、计算、余量、结论和开放项/失败项。计划按 intent 电路生成框架；框架外的功能审查员自己加。
- **逐项检查**是审计明细。一项对应一条规则、一个实际对象、一个状态，编号为“规则.对象[.状态]”，跨轮次保持不变，
  供改版复审、训练裁决和复核引用。绑定了功能的检查项由功能派生，不手填，也不写进台账：门禁、报告、打包、对比读取时派生（`results_model.materialize`），
  `derive_rows.py` 只是审查员的检查；审查员自己绑定的检查项写 `{id, function_id, aspect}`，给派生检查项补注记只写 `{id, 注记}`；
  事实性检查（目检、脚表、身份、需求条款）手填。一个器件挂很多条规则是正常的，不合并成一项。
- **待办**是交付单位，由开放项和失败项派生（编号 `W-<key>`，见 [结论与准出](verdicts-and-release.md#待办由开放项派生)），
  不手写。设计者、ASG 和报告都按待办处理；PASS 和 NA 不进待办。

“资料不足”只有一个入口：先有功能判定的开放项，才有 INSUFFICIENT 的检查项。

## 三、review-results.json（schema_version 8）

### 顶层字段

- `plan_digest` / `db_digest`：`validate_review.fingerprint()` 对 JSON 对象排序序列化后的 SHA-256（不是文件字节哈希）。
- `functions`：功能判定，见下节；没有时写空数组。
- `checks`：与最终计划 ID 集合完全一致的逐项结果。
- `findings`：唯一已确认缺陷/改善，一个根因可被多个检查引用。
- `scope_checks`：六个覆盖维度 `input_consistency`、`requirements`、`chains`、`states`、`datasheets`、`history`
  各指向对应覆盖审计项。表示覆盖审计完成，不是该域全部电气通过。
- `coverage`：各维度“对象→检查 ID 数组”的完整映射。有 `--db` 时机械检查 components、pins、nets、pages
  及 requirements 是否都关联至少一条检查；仅 PDF 时由页面/手工对象清单另审，不制作伪网表。
- 不写 `requirement_clarifications`：需求问题在第①步当场问用户，问题和答复写 `intent.clarifications`（见 [需求澄清](requirement-clarifications.md)），结果里没有待决需求。`work_items` 不再写：待办由开放项派生（见 [结论与准出](verdicts-and-release.md#待办由开放项派生)）。
- `review_scope`（只在局部热审时写）：`{"functions": [计划框架 id…], "reason": "…"}`。声明后校验只要求这些框架的检查项有结果，
  不要求 `scope_checks` 与 `coverage`；gate 的 `valid` 可为真，但带阻断“不是整板结论”，`release` 恒为 NO_GO，`pack_review.py` 不打包。
  用于训练语料的单电路热审与试点，不用于交付。
- 没有分版本号：`binding_version`、`remediation_version`、`workflow_version`、`impact_class_version`、
  `requirement_clauses_version`、`requirement_clarification_version` 写了会被拒绝，各项一律按最新规则校验。
  绑定由 `validate_review.py` 总是要求，修改说明由 `--require-actionable` 要求。
  schema 2/3/4 的旧台账不再读取，按本版 SR 重新审查。
- 复审另有 `revision_impact_version`、`revision_digest` 和必需项的 `reverification`，见 [改版复审](revision-review.md)。
- `summary` / `release` 可省略，由校验器计算；填了必须一致。

### 功能判定（functions）

计划框架的问题可以改得更具体，但改后的问题仍要点名这块电路、它的器件或网络，不能换成“本节保留的已核方面”这类范围说明。
框架的成员检查项转给别的功能（`function_id` 指向别的功能）后仍是这块电路的检查项：成员检查项里有证据不足或不符合时，报告把这块电路
计为未定或不符合，并列出那一项所在的待办，不随转出变成“通过”。

以一个合成例子说明：反激控制器 U1 的 VCC 由辅助绕组经整流、源跟随管 Q2 供电，数字全部是编的，只为展示字段：

```json
{
  "id": "FN-BIAS", "circuit": "BIAS",
  "question": "最低输出档 5 V、−10..105 °C、辅助绕组取最低电压时，Q2 偏置路径能否让 U1 VCC 保持在 8.8 V 以上",
  "objects": {"refs": ["Q2", "D2", "D3", "D4", "C3"], "nets": ["AUX", "BIAS", "VCC"]},
  "states": ["STARTUP", "RUN", "LATCH"],
  "conditions": [
    {"id": "c1", "kind": "NUMERIC_LIMIT", "source": "evidence/ds/D2.txt", "locator": "p3 Table 7", "refs": ["D2"],
     "says": "VF ≤ 0.35 V @10 mA，≤ 0.45 V @100 mA（25 °C）", "limit": {"max": 0.45, "unit": "V"},
     "regime": "25 °C，10–100 mA", "use": "20 mA 在两点之间，VF 单调，取 0.45 V 作上界"},
    {"id": "c2", "kind": "NUMERIC_LIMIT", "source": "evidence/ds/Q2.txt", "locator": "p4 Table 4", "refs": ["Q2"],
     "says": "VGS(th) 1.0–2.0 V @250 µA", "limit": {"min": 1.0, "max": 2.0, "unit": "V"},
     "regime": "25 °C，250 µA", "use": "20 mA 取 2.0 V + 0.5 V 工程余量"},
    {"id": "c3", "kind": "NUMERIC_LIMIT", "source": "evidence/ds/U1.txt", "locator": "p7 Table 7", "refs": ["U1"],
     "says": "VCC(off) max 8.8 V", "limit": {"max": 8.8, "unit": "V"}, "regime": "−10..105 °C", "use": "判据"},
    {"id": "c4", "kind": "MANDATORY_CLAUSE", "source": "evidence/ds/U1.txt", "locator": "p9 §7.3", "refs": ["U1"],
     "says": "VCC 引脚必须经外部电容去耦，UVLO 释放前不得由 HV 脚以外的路径反灌",
     "applies": "U1 由外部偏置供电时", "use": "偏置路径的连接要求"},
    {"id": "c5", "kind": "NETLIST_FACT", "source": "db.json", "locator": "net AUX", "nets": ["AUX"],
     "says": "AUX 网把辅助绕组整流接到 Q2 栅极", "use": "路径"},
    {"id": "c6", "kind": "DESIGN_CONSTRAINT", "source": "evidence/engineering.md", "locator": "claim BIAS-VCCMIN",
     "says": "T1 辅助绕组 5 V 空载最低峰值 ≥ 13.5 V（= 8.8 + 2.5 + 0.45 + 1.5 + 0.25 V 余量）", "limit": {"min": 13.5, "unit": "V"},
     "regime": "5 V 空载、−10..105 °C", "owner": "磁件设计", "handoff": 0, "use": "辅助绕组最低峰值取约束下限"}
  ],
  "calculation": {"claim_ids": ["BIAS-VCCMIN"], "inputs": ["v_aux_min", "vf_d2", "vgs_q2"], "result": "VCC_min = 9.6 V",
                  "margin": {"value": 0.8, "unit": "V", "against": "VCC(off) max 8.8 V", "states": ["STARTUP", "RUN", "LATCH"],
                             "basis": {"kind": "GUARANTEED_BOUND", "comparison": "GT", "limit": "c3", "conditions": ["c1", "c2", "c6"],
                                       "scope": "−10..105 °C，VF 与 VGS(th) 取保证上界", "regime": "−10..105 °C",
                                       "derivation": "GUARANTEED_LIMIT", "cell": "NONE",
                                       "corners": [{"input": "vf_d2", "condition": "c1", "picked": "max", "why": "VF 越大 VCC 越低"},
                                                   {"input": "vgs_q2", "condition": "c2", "picked": "max", "why": "VGS(th) 越大 VCC 越低"},
                                                   {"input": "v_aux_min", "condition": "c6", "picked": "min", "why": "辅助电压越低 VCC 越低"}]}},
                  "assumptions": ["辅助绕组 −10%", "Na/Ns = 3"], "aspect": "变换器电压裕量"},
  "judgements": [{"aspect": "偏置路径连接", "conditions": ["c4", "c5"], "states": ["STARTUP", "RUN", "LATCH"],
                  "says": "C3 跨接 VCC 与地，AUX 只经 Q2 进入 VCC，无 HV 脚以外的反灌路径"}],
  "verdict": "PASS",
  "open": [],
  "fails": [],
  "handoffs": [{"receivers": ["磁件设计"], "constraint": "T1 辅助绕组 5 V 空载最低峰值 ≥ 13.5 V",
                "verification": "磁件规格写明 5 V 空载最低峰值电压且 ≥ 13.5 V"},
               {"receivers": ["样机试验"], "constraint": "5 V 空载、−10 °C 时 VCC ≥ 8.8 V", "verification": "实测 C3 电压"}],
  "evidence": [{"source": "evidence/ds/U1.txt", "locator": "p7 Table 7"}]
}
```

三个状态都由 0.8 V 的保证最坏值余量判 PASS。辅助绕组最低峰值归磁件规格定，原理图上不写：SR 按 VCC(off) 反推出
≥ 13.5 V 的设计约束（c6），余量按约束下限算，派生检查项带上 `handoffs[0]` 交给磁件设计（乙）。
如果缺的是原理图或 BOM 本该写明的值（电容耐压、分压电阻阻值、料号），就是失败项，发现项的改法写反推出的值（甲）。

字段：

| 字段 | 含义 |
|---|---|
| `id` / `circuit` / `question` / `objects` / `states` | 计划框架给出；框架外的功能自己写，`id` 以 `FN-` 开头。框架的 `members` 列出要在这个功能里答的全部检查项：电路检查项和电路拥有的器件检查项 |
| `conditions[]` | [判“证据不足”之前先定界](evidence-proportionality.md#判证据不足之前先定界)第 1 步“先用手册里已有的界限”：每条 `id`/`kind`/`source`/`locator`/`says`/`use`；只在可编程器件某个设置下成立的条件写 `setting{ref, group, value}`（配置项、设置值），门禁汇总成 `configuration_settings` 交给配置表编写方，配置表本身不审；`use` 写怎么用（相邻测试点夹出界限、门限上限、温度系数）。`kind` 是下表六种之一。`refs` 写这条条款说的是板上哪几只器件：手册来源（`source` 在 `ds/`、`datasheets/`、`manuals/` 下，或是资料审计里某位号的那份文件）和 BOM 行来源的条款必填且至少一个，带 `setting` 的要含 `setting.ref`，NETLIST_FACT 可不写、写了要含 `pins` 所属的位号；需求、标准、`commodity-floors.md`、工程假定选填。每个位号是网表或 BOM 的器件，不重复；位号在资料审计里对应另一份资料而条款的 `source` 不是它时拒收（张冠李戴）；位号不在本功能 `objects.refs` 和成员检查项对象里只提示 CONDITION_REF_OUTSIDE_FUNCTION。余量不写位号，经 `basis.limit` / `basis.conditions` 指向条款 |
| `calculation` | 同节第 2 步“算出了余量就下结论”：`result`（一句结论；比较过的量不写在这里，超 300 字或游离数字超 8 个出 RESULT_NARRATIVE）、`margin{value,unit,against,basis[,aspect,states,check_ids]}`（多个方面写成列表，各带 `aspect`；`against` 写含项目降额的限值；`unit` 按 `scripts/units.py` 的拼法）、`claim_ids`、`inputs`（计算的输入量名，影响条目的 `via.input` 从这里取）、`assumptions`；只针对一个方面时写 `aspect`。同一功能里 `value`、`unit`、`against` 都相同的余量只能有一条：一个缺陷落在证明它的那个方面，要落到别的方面须是另一个量、另一条余量。没有数值的功能写 `no_calculation_reason` |
| `judgements[]` | 没有数值的方面各写一条：`{aspect, conditions: [条件 id], says[, states, check_ids]}`，`says` 写这几条条件对本方面说明了什么（例如“无外置补偿网络，按拓扑无独立电压环”）。厂家参考电路也可以撑起判断：该 TYPICAL_REFERENCE 条件写 `reference_circuit{figure, connection, load}`——参考电路的图号或页、本板与它相同的接法、它的元件值与本板负载的对照（本板不重于它），报告依据写“厂家参考电路 + 图号”。检查项要判 PASS，本方面本状态必须有证明通过的余量或一条 judgement，不能借别的方面或别的状态的结论 |
| `verdict` | PASS / FAIL / OPEN，且与 `open`/`fails` 一致（有失败项即 FAIL，否则有开放项即 OPEN） |
| `open[]` | 开放项：`key`（全文件唯一）、`kind`、`what`、`scope`、`decides[影响条目]`、`severity{level,class,affects,consequence[,hazard_path,exclusion]}`、`closure`、`due_stage`（默认 design_iteration）、`design_option`，`title`/`why` 可选；各种 `kind` 另要的字段见下面“开放项的三种” |
| `fails[]` | 失败项：`key`、`finding_id`（指向 findings）、`what`、`decides`，可带 `conditions`（被违反的强制条款）、`title`/`why`/`due_stage`/`design_option`；依据三选一：余量证明不够（REACHABLE_CASE/EXACT_ENVELOPE）、违反强制条款、或 `outside_specified{condition, operating_point, curves_checked}`——器件工作在手册没规定的区域：`condition` 是本功能里给出手册规定区的条款，`operating_point` 写本机工作点，`curves_checked` 列查过的曲线和表，其中须有推荐工作条件或电气特性节，工作点是某个引脚的还须有引脚说明节；不要把“没规定”写成限值 0 去比较 |
| `handoffs[]` | 功能级移交，派生检查项时填进计划要求移交的检查项 |
| `verdict_history[]` | 改过结论时写 `{from, to, basis: [条件或 claim id], note}`，basis 不能为空 |
| `evidence` | 可定位的证据 |

**设计没定不是开放项**（2026-10-26，用户：按甲乙分开改：甲判不合格并给改法，乙判合格并附设计约束）。
判断要用到设计者还没定的值时，先看这个值归谁定：
- **甲：原理图或 BOM 本该写明**（器件值、额定、耐压、料号写成 TBD 或没写）：记失败项，发现项的改法写反推出的值（“C12 耐压定为 ≥ 25 V”）；
- **乙：归另一份设计文件**（磁件规格、固件配置、PCB）：反推出的界写成 DESIGN_CONSTRAINT 条件（`limit`、`regime`、`owner`、`handoff`），
  余量按约束的不利端算，满足就判 PASS，派生检查项带上 `handoffs[handoff]` 交给 `owner`；`owner` 写原理图或 BOM 的拒收（那是甲）。
  门禁 `design_constraints` 汇总，报告结论段带一句。`kind: DESIGN_VALUE` 写了会被拒绝（结果格式 10）。
- **另一环节欠的交付物同样并入乙**（2026-10-26，用户：并入乙）：定制件图纸（绝缘结构、三重线、爬电、耐压）、固件或 OTP
  能否实现所需的控制与恢复策略，都写成 DESIGN_CONSTRAINT 交给负责方；没有单一数值的写成条款（不写 `limit`，`says` 写必须满足什么），
  由 `judgements` 引用，定制件自己的身份与脚检查项、SIG-* 检查项也这样判。交付物已经到了而不满足约束的，记失败项。
  `kind: DELIVERABLE_PENDING` 写了会被拒绝，不再有“等交付物”，也不再把准出压到有条件定稿（结果格式 11）。

**开放项的三种。** 归类看欠的是什么，不看向谁要：

| `kind` | 必写 | 不写 | 说明 |
|---|---|---|---|
| VENDOR_DATUM（只有厂家知道） | `checked`（条件 id）、`why_insufficient`、`acquisition`、`worst_case` | — | 先按公开资料界限算：`worst_case{bound{condition, value, basis: GUARANTEED_LIMIT/ADJACENT_TEST_POINT/TYPICAL_CURVE/PUBLISHED_TABLE/APPLICATION_NOTE}, result, margin{value,unit,against,basis}}`，这个余量按它的依据决定结论。确实没有公开界限时写 `worst_case{not_boundable_reason, curves_checked[{source, locator}], operating_point_specified}`：`true` 是手册写了这种用法只缺数值，另写 `specified_by` 指向写了这种用法的条件（不能是 `monotonic_tried.test_points` 里没覆盖工作点的测试点；可以是条款、应用说明或 `regime` 覆盖工作点的典型曲线），引典型曲线（`curve: true`）时另写 `typical_estimate{value, unit, against, basis: ESTIMATE 并引这条曲线}`，估算已经不够就是失败项（余量记 REACHABLE_CASE），资料不足按后果定级；`false` 是设计依赖手册未规定的工作区，记失败项，发现项给出回到规定区的改法，不向厂家要。目录器件的参数是这一种，不是交付物 |
| USER_DEFERRED（用户暂缓） | `instruction` | — | — |
| REVIEW_INCOMPLETE（审查没做完） | — | — | 本轮自己读算完；有这种开项时不打包 |

**每类开放项能挡哪些检查项**（`catalog.OPEN_ITEM_RULES`）：
`decides` 边的 `aspect` 是规则标题，那个标题的规则不在本类能挡的集合里就拒绝。VENDOR_DATUM 能挡计算检查项（C）、电气窗口检查项（E）和需求检查项 REQ-D01；
配置表不是缺口。文档/身份检查项（D）、拓扑检查项（T）、提示（A）和覆盖检查项不等任何开放项：
按已知的判，或换对的缺口种类。不是规则标题的 aspect（需求方面、自由文字）不在此查。

**条件的六种。** 每条条件先要能定位：`locator` 给页码、表号、图号、章节、手册的节名（电气特性、绝对最大、引脚说明……）、
需求或记录编号、位号，或点名的网络/引脚（“nets PGND/SGND”）；“相关位号所有物理脚”“## BIAS”不定位任何东西。再按它是什么写 `kind`：

| `kind` | 另要的字段 | 能用来做什么 |
|---|---|---|
| NUMERIC_LIMIT | `limit{min 和/或 max（有限数）, unit}`，`says` 引出这个数，`regime`（温度、波形或脉宽、模式、型号——限值成立的条件） | 余量比较的限值；不能写进判断句 |
| MANDATORY_CLAUSE | `says` 引出规范句（必须/不得/须/shall/must…），`applies`（本设计受它约束的前提）；不要数字；位置是典型应用、应用电路、参考设计的不算 | 判断、失败项的依据 |
| NETLIST_FACT | `nets` 和/或 `pins`（REF.PIN）；有网表时每个名字要在网表里，只写叶名而网表里有两个同叶名网络的要写全路径 | 判断的依据 |
| TYPICAL_REFERENCE | 能定位；典型曲线或特性图写 `curve: true`，应用说明的文字不写 | 参考，不能撑起保证最坏值 |
| ENGINEERING_ASSUMPTION | 无 | 估算，不能撑起保证最坏值或确会出现的工况 |
| DESIGN_CONSTRAINT | `limit{min 和/或 max, unit}`（没有单一数值的条款不写，`says` 写必须满足什么）、`regime`、`owner`（定这个值的设计文件或团队，不是原理图/BOM）、`handoff`（本功能 `handoffs` 的序号）；`source`/`locator` 指向反推它的计算 | 乙：另一份设计文件要满足的界，余量按它算，派生检查项带上移交 |

条款指能定位的 NUMERIC_LIMIT 或 MANDATORY_CLAUSE。

**余量的依据（`margin.basis`）。** 每个余量写 `basis{kind, comparison GE/GT, scope, conditions[, limit, regime, conversion]}`，说明这个数证明了什么：

| `basis.kind` | 证明什么 | 另要 |
|---|---|---|
| GUARANTEED_BOUND | 在要求范围内余量的下界：满足则 PASS，不满足只说明没证明（OPEN） | 不依赖 TYPICAL_REFERENCE 或 ENGINEERING_ASSUMPTION |
| REACHABLE_CASE | 一个确会出现的工况：不满足则 FAIL，满足不证明整个范围（OPEN） | `joint` 说明这些参数为什么会同时出现；不依赖 ENGINEERING_ASSUMPTION |
| EXACT_ENVELOPE | 完整的最坏包络：满足 PASS，不满足 FAIL | `model`、`domain`、`extremum`；同 GUARANTEED_BOUND 不依赖典型值或假设 |
| ESTIMATE | 什么都不决定；按定界表那一格的判决边界允许的后果类、经倍数打折后仍满足且移交样机实测时，判 PASS（见下） | 判 PASS 时写 `cell`、`method`（G7–G9）、`consequence_class`、`estimate_factor`、`handoff` 与 `risk` |

估算判通过：估算能不能判 PASS 由 `basis.cell` 那一格的[判决边界](bounding-table.md#判决边界)按
`consequence_class`（沿用开放项 `severity.class` 的词：REQUIRED_FUNCTION、PERFORMANCE_OR_LIFE、COMPONENT_DAMAGE……）决定，与检查项的规则 id 无关：
格允许这个后果类时，`basis` 写 `method`（该格的估算推法 G7–G9，保证推法 G1–G6 得到的是 GUARANTEED_BOUND 不是估算）、`consequence_class`、
`estimate_factor`（等于格给该后果类的倍数，余量按估算值再按不利方向打这个折之后算；格另给余量下限的，余量用那个单位且不低于它，如 MOS-RDS-HOT 判损坏要结温余量 ≥ 20 °C）
和 `handoff`（本功能 `handoffs` 里样机实测那一条的序号，那一条写全 receivers、constraint、verification），满足就判 PASS，派生检查项带上这条移交（`required: true`，OPEN）。
DAMAGE_OR_HAZARD、CORE_LINK_LOSS 在任何格都不估算。`cell: NONE`（表里没有这个参数）走默认：只许 REQUIRED_FUNCTION / PERFORMANCE_OR_LIFE，
损坏、过热和保护类规则（DEV-C01、DEV-C04、PWR-C03、PWR-C06、PWR-C10、DRV-C01、全部 PRO）不走这条路；同时门禁记 NEW_BOUND_CELL 待扩项。
估算判 PASS 的检查项是 C 级证据（派生时写 `evidence_confidence: C`，门禁拒绝别的等级），结论是“合格，但有风险”（2026-10-26 定）：
`basis.risk{types, corner, improvement}` 必写，`types` 取那一格“估算对应的风险”（ENVIRONMENT / LIFETIME / CONSISTENCY；`NONE` 任选），
`corner` 写只靠估算的角点，`improvement` 写消除风险的改法。决定性余量在额定内但没满足假定降额时可写 `risk{types: [STRESS], …}`，仍判 PASS。
门禁 `risks` 逐条列出（`source` ESTIMATE / LIFE / STRESS），不限制 `release`，报告按类型单列“风险清单”。
寿命检查项另有自己的估算路径（见 DEV-C02/DEV-C06），凭估算判通过时门禁自动列为寿命风险，改法取它的 `bom_constraint`。

`comparison` 为 GE 时零余量算满足，GT 时不算。除 ESTIMATE 外，`limit` 指向被比较的 NUMERIC_LIMIT，`regime` 写算出量成立的条件；
与限值的 `regime` 不同时，`conversion` 要指向一条条件或 claim（换算或包络），否则跨条件比较被拒绝。

除 ESTIMATE 外，`basis` 还写这个界怎么来的：
- `derivation`：GUARANTEED_LIMIT（手册限值就在本工况成立）、ADJACENT_TEST_POINT 或 MONOTONIC（从测试点推过来，另写 `monotonic{curve: 本功能里说明单调形状的条件 id, side: FAVORABLE}`，实际工况须在有利一侧，不利一侧的测试点什么都定不了）、TEMPCO（经温度系数推，`tempco` 指向给出温度系数 min/max 的 NUMERIC_LIMIT）、PUBLISHED_TABLE（公开数表）；TYPICAL_CURVE 只能用于 REACHABLE_CASE（典型件已经不够）；按典型曲线读出的估算记 ESTIMATE，不写 `derivation`。
- `cell`（决定性余量必写）：按[工作点定界表](bounding-table.md)写限值所在的格，表里没有这个参数的写 `NONE`；
  写了格就写 `method`（须是这一格允许的推法），推法带公式时写 `formula{name: bound_formulas 里的函数, inputs, value}`，门禁用同样的输入重算，差超过 0.5% 拒收；
  `NONE` 不带 `method`（`formula` 仍可写、仍被复算）。ESTIMATE 可不写。
- `corners[{input, condition, picked: min|max, why}]`：每个带公差的输入取了哪条 NUMERIC_LIMIT 的哪一端，以及为什么那一端不利；取的那一端必须是该条件给出的数。
  `basis.conditions` 里（除 `limit` 本身）每条给了 min 和 max 的 NUMERIC_LIMIT 都算带公差的输入，都要有角点，否则拒收；
  不进这条余量计算的条款不要列进 `basis.conditions`。没有带公差的输入时写空列表加 `no_corners_reason`。

开放项判“定不出界”（`worst_case.not_boundable_reason`）时，先用数写 `monotonic_tried`（结果格式 6）：
- `side`：开着的是上界还是下界（UPPER 或 LOWER）；`quantity`：哪个量的界。
- `cell`：[工作点定界表](bounding-table.md)里这个参数的格（表里没有写 `NONE`）。格有开着的一侧时须与 `side` 相同；
  格落到 `BOUNDED`（总能定界）或 `OUTSIDE_SPECIFIED`（记失败项）时拒收；参数单调时，有利一侧给了这一侧限值的测试点就定了界，拒收。
- `operating_point{min, max, unit}`：本板上测试点所在那个变量的范围（如齐纳电流 0.06–1.3 mA）。
- `test_points[{condition, at{value, unit}}]`：手册给这个量或它斜率的测试点，条件须在 `checked` 里，单位与工作点相同（u、μ 按 µ 算）；
  手册对这个量一个数值点都没有时写 `[]` 并加 `no_test_points_reason`（查过的页码或表），整段范围都开着。
- `why_not`：这些测试点为什么给不出开着的那个界，不得照抄 `not_boundable_reason`。
- `other_side`：另一个界 DECIDED（本功能有同一方面的余量）或 NOT_DECISIVE（写 `other_side_reason`）。

工作点整段落在两个测试点之间时，门禁拒收“定不出界”，按相邻测试点定界（ADJACENT_TEST_POINT）；只有一部分在测试点之外时，
`open_range{min, max}` 写开着的那段（在工作点之内、不跨进测试点之间），测试点之间那段写成本功能同一方面的余量。
开放项的每条边写 `side`，与 `monotonic_tried.side` 相同。

厂家数据开放项的格（`monotonic_tried.cell` 或 `margin.basis.cell`）兜底为 `OUTSIDE_SPECIFIED`（脚超绝限、超 SOA、无浪涌额定、超灌拉电流、无 IFSM）时拒收，记失败项；
格为 `NONE` 或没写而 `what`/`why_insufficient`/`not_boundable_reason`/`quantity`/`against` 点到某格参数词，或点到 `OUTSIDE_SPECIFIED` 格却写别格，也拒收：写那一格，或写 `cell_reason` 说明。

计算类（规则方法 C）的方面判 PASS 必须有证明它的余量；一句判断只能收掉连接追踪（T）和条款核对（D）类方面，写明 `reference_circuit` 的厂家参考电路例外。

**影响条目（`decides[]`）。** 开放项和失败项的每个 `decides` 条目是一条边：`{aspect, states?, check_ids?, effect, via, rationale}`。
`effect` 默认 BLOCKS_PROOF（挡住该范围的证明），INFORMATION_ONLY 只登记不挡；`check_ids` 把边收窄到点名的检查项。
经需求文档条款的边（条件来自需求目录里的文档，`requirement_source` 及其同目录文件）只能挡绑定到该需求的检查项：该需求的 REQ-D01 项及其 `bound_checks`；挡别的检查项要经缺的数进入的那个比较——数值限值、计算输入，或手册、标准里的条款。
VENDOR_DATUM 的每条边都写 `via`——缺的量进到哪里：`{condition: 本功能的条件 id}` 或
`{claim: 计算的 claim id[, input: calculation.inputs 里的输入名]}`——和 `rationale`（现有的界为什么决定不了这一项）。
一个缺口挡几个方面不限数，超过 3 个只出 WIDE_GAP 提示，供复看是否该拆开。

**范围要写明。** 余量、判断和边不写 `states` 时只覆盖不带状态的检查项（STATELESS），不覆盖所有状态；要覆盖几个状态就把它们列出来。

**退役字段。** `margin_not_decisive_reason`、`loose_bound`、`decides_reason` 写了会被拒绝：余量决不决定由余量依据说明，挡住什么由影响条目说明。

校验 F1–F11：F1 每个功能有问题、对象、结论，电路功能至少引用一条条款（被判断、余量依据、开放项、失败项或影响条目实际引用；只含 DOC 检查项的功能不要求）；
F2 设计没定不开项（见上）；F3 VENDOR_DATUM 写查过什么、为什么不够，以及公开资料界限下的最坏情况（界的条件、取值、依据和带余量依据的余量；没有界就列查过的曲线表），
公开资料界限下证明通过的余量说明这个量不缺，开放项要撤掉，证明不满足的要记失败项，ESTIMATE 可以保留开放；
F4 结论跟着余量的依据走：证明通过的余量与挡住同一范围的边并存被拒绝，证明不满足的余量要有失败项，同一范围既有通过又有失败的证据是 EVIDENCE_CONFLICT，
没被任何东西决定的 OPEN 余量要有开放项；失败项要么落在证明不满足的余量上，要么在 `conditions` 里引被违反的强制条款，指向的发现项带 `remediation`；
F5 项跟随功能（见下）；F6 改结论要引条款或数字；F7 缺口的每条影响条目写 `via` 和 `rationale`，`via` 指向本功能的条件或计算的 claim 与输入；
F9 判 PASS 的每个方面在该状态有证明通过的余量或 `judgements` 条目，每条 judgement 至少引一条 MANDATORY_CLAUSE、NETLIST_FACT 或写明 `reference_circuit` 的厂家参考电路，不引 NUMERIC_LIMIT
（数字限值在余量里比较，不在判断句里宣布满足），只说“不适用 / 无此问题 / 按拓扑无… / 不涉及”而不引 NETLIST_FACT 的判断被拒绝（改记 NA），
判断与挡住同一范围的边冲突，没人判过的方面不会默认通过；
F10 同一条不能定位的条件出现在两个以上功能里被拒绝（能定位的条款可以被几个功能共同引用；同一句 `assumptions` 抄进几个功能的计算同样拒绝，共用工况写进 intent 一次）；
同一句 `why_insufficient`/`closure`/`acquisition` 出现在几个开放项上只出 TEMPLATE_REASON 提示（同一方法套几个对象是一件待办、多个位号）；
F11 框架功能的 `objects` 不超出 intent 电路声明的位号与网络（要扩大先改 intent 再重生成计划，不在判定里放宽），审查员自己绑定的检查项要是该功能对象上的检查项
（位号检查项的位号、网络检查项的网络在功能 `objects` 里，网络名不计图纸路径；感性负载检查项只看电感本身和它的开关节点，续流回路里别的器件只是上下文；需求检查项、全板检查项没有对应的器件或网络，不受此限）——一块电路的缺口不借绑定伸进另一块电路；

**检查项标识。** `plan_review.py` 给每个检查项写 `check_key`：规则、规则版本（目录条目与问题模板）、去掉 `circuit` 名称后的对象、判据四项的摘要。
装配状态按内容命名：计划的 `assemblies` 给 intent.assemblies 的每个名字一个由贴装表和跳线算出的键（`ASSEMBLY-…`），检查器检查项的 `state`/`states`
和装配检查的 `assembly` 用这个键进标识，所以两人给同一装配起不同的名字仍是同一项检查；电路检查项的 `state` 是工作态，不换。
检查器清单的摘要（`*_digest`）和句柄（`decoupling_group`、`power_switch`、`supervision` 等，见 `check_key.INVENTORY_FIELDS`）只是指回清单，不进标识。
校验器总是重算这个键，不信记录里存的值；同一项检查在计划里问了两次被拒绝。改电路名不改检查项，换规则模板或判据才改。
`scripts/compare_reviews.py` 先按这个键严格配对两份记录，再给出按电路的建议配对（见 [自动检查](scans-and-tools.md#脚本分类)），
并读两边的 `intent.circuit_decisions` 与 `record/circuit-candidates.json`，逐候选、逐对齐电路的成员、逐未归属器件列电路决定的差异。
电路级检查项的对象带 `circuit_key`（电路来自的候选编号，合并的用 `+` 连接）：有它时成员表、核心器件和网络不进标识，
两份记录接受了同一批候选，即使画法（成员、网络写法）不同，电路检查项也是同一项。

**所属对象。** 计划给每个检查项写 `owner`：电路级检查项归它的电路（`{"kind": "CIRCUIT", "id": …}`）；
`catalog.SYSTEM_FUNCTIONS` 里的系统规则检查项归系统功能（`SYSTEM`，如 SYS-POWER）；关于器件的检查项归拥有这颗器件的电路
（多颗器件须同属一块）；其余归全板（`BOARD`）。计划的 `owners` 列出每块电路拥有的器件，`summary.owners` 是按所属的检查项数。
校验器按 `owners` 重算每个检查项的所属，拒绝写错的检查项；审查员后加的拆分检查项可以不写。

**接口。** 计划的 `interfaces`（`scripts/interfaces.py`）列出所属对象之间的接口：一条网络连着两个所属对象的器件脚就是它们之间的接口网络，
同一对之间的网络合成一个接口；地网不是接口网络。四种：电路对 `IF-<A>~<B>`、链路 `LINK-<跨电路候选>`（带它自有的器件 `parts`）、
供电 `RAIL-<轨>`（带 `source` 与 `basis`）、对外 `EXT-<连接器>`（连接器全部脚）。编号用电路的候选编号，改电路名不改接口。
每个端点 `{owner, pin, role, basis, domain, supply}`：角色 DRIVER / RECEIVER / BIDIRECTIONAL / PASSIVE 按库引脚类型、器件类别、电源树和引脚名推，
推不出的进 `gaps`（`reason: role`），轨推不出源的也进 `gaps`（`reason: source`）。

**接口检查项。** 计划按 `catalog.INTERFACE_SUBJECTS` 逐接口生成检查项，对象带 `interface`：电路对问 SIG-T04 方向语义与 SIG-C07 电平，
链路问 SIG-C07（两端电平），轨、开关节点、变压器绕组和整流桥上的网络（`power_node`）不问这两项，只剩这种网络的电路对不出检查项、不建框架；两端 IC 供电轨或参考地分区不同的接口网络（`cross_supply`）另问 SIG-C08；连接器问 DEV-D03 对端定义、
DEV-C04 载流、PRO-D03 对外防护（对象 `{interface: EXT-<连接器>, ref}`）；供电轨在敏感电路（ANALOG、CLOCK、RF）取电时问 PWR-C14
（对象带 `loads`）。检查项的缺口取接口的角色缺口（`interface-role:<脚>`）、轨源缺口（`rail-source:<接口>`）和端点 IC 的资料。
电路对、链路和连接器各一个接口框架（`functions[]` 里带 `interface`、`interface_kind`，没有 `circuit`），成员是该接口的检查项；
供电接口只有检查项，不建框架。按声明的总线电路展开的同名规则仍问电路内部的链路。

**系统功能。** 有对象才生成：两个以上地网问 PWR-T06（`{system: SYS-GROUND, nets}`），两条以上电源轨问 RST-T03
（`{system: SYS-SEQUENCE, rails}`，全板一项），有可能是主控的 IC 问 SIG-D13（`{system: SYS-PINMAP, refs}`）；电源树与监控的检查项
（PWR-T01/C01/A01/A04、PWR-T04/A06）照旧生成。每个有检查项的系统功能一个框架（`functions[]` 里带 `system`），成员是归它的检查项。
**自有器件。** DEV-C01 应力、DEV-C02 电容、DEV-C03 精度每块电路对它拥有的器件一项（`{circuit, circuit_key, refs}`，
按器件类别取），没有电路拥有的器件全板一项（`{board: BOARD, refs}`）。
**覆盖审计。** 校验器另查两条：电路来自候选时，每颗贴装器件恰归一块电路（`row_owner.coverage_errors`），
或列在 REQ-Q08 的 `unassigned` 上（计划把没有电路拥有的贴装器件都列进去）；每个接口都有它该问的检查项（`interfaces.coverage_errors`），电路对、链路（有网络时）和连接器另有框架。
**报告分组。** 计划有树框架时，报告的功能表分系统功能、功能电路、接口和审查员另建的功能四组；每个发现项多一行“所属”，写它的检查项归哪个系统功能、电路、接口或全板。

**文档检查不是功能电路。** 功能回答一块电路的问题；DOC-* 检查项（输入版本、图纸卫生）不是电路。
文档错误直接在检查项上判 FAIL 并写 finding，不绑定功能（校验拒绝绑定了功能的 DOC FAIL 检查项）；这件待办由 finding 生成（`W-<finding id>`，含指向它的全部 DOC FAIL 检查项），不要改记证据不足。DOC 检查项证据不足时仍需一个开放项作入口，这种只含 DOC 检查项的功能不计入
“功能判定”计数，也不进报告的功能表。

隔离器件的工作资格（PRO-C03）和反馈稳定（PWR-C15）是功能的方面，不另设约定：
PRO-C03 在隔离功能里逐个列出变压器、光耦/数字隔离器、跨接电容的实际工作电压、重复峰值/频率和厂家资格条件
（短时耐压、目标绝缘类别、无直流跨接都不能独自关闭）；PWR-C15 在变换器功能里写反馈模型、补偿配置和角点稳定性
（无反馈环按拓扑 NA；内部补偿用厂家适用条件证明；Bode 实测是移交，不是开放项）。

**检查项跟随功能。** 绑定了功能的检查项（计划检查项，或审查员写了 `function_id` 的检查项——这样的检查项要是该功能对象上的检查项（F11）；同一组对象声明了两个功能电路时，
一个框架的检查项可以绑到另一框架的功能，条件是该功能的 `objects` 覆盖这一项的位号与网络，这样共用的检查项只判一次、不复制开放项；
框架检查项不能挂到审查员自建的功能上，也不能从自建功能取 `open_ref`/`fail_ref`：计划电路的缺口写成该电路功能（或拥有该器件的计划功能）的开放项或失败项，
缺口只写一次——跨电路的缺口写在拥有缺失量的框架里，开放项的 `decides` 另加影响条目，用 `check_ids` 点名另一电路受它挡住的检查项，
那些检查项的 `open_ref` 就指向这个开放项（没点名的检查项不能指向别的功能的开放项；失败项不跨功能）；自建功能只装不属于任何框架的检查项，如器件、检查器和全板检查项，
它的位号若全在某个电路框架里，校验拒收并提示写进那个框架；计划漏了电路时在 `intent.circuit_decisions` 登记 add 决定后重生成计划）：功能 PASS → 检查项 PASS；
功能 FAIL → `fails[].decides` 命中的（方面，状态）FAIL 并带 `fail_ref`/`finding_id`；功能 OPEN →
`open[].decides` 命中的检查项 INSUFFICIENT 并带 `open_ref: "FN-ID/KEY"`；其余的检查项只有本方面本状态有证明通过的余量或 `judgements` 条目才 PASS，
否则派生报“judges no …”而不生成该检查项（门禁同样报）。`rationale` 写“见功能判定 FN-X（方面，状态）：”加本方面自己的结论和余量，或 judgement 的内容和条款。
读取时派生这些检查项（`results_model.materialize`），台账里不写；手填的检查项只对账不覆盖。校验强制：INSUFFICIENT 必有 `open_ref` 且其 `decides` 覆盖本检查项的方面和状态；
绑定的检查项的 `aspect` 等于计划的方面；每个有已审成员的框架都有功能判定。

### 每项检查的盲区与关闭条件

计划顶层的 `check_explanations` 按规则编号各存一份说明（由 `scripts/catalog.py` 生成，计划中出现的每条规则都要有），
计划项本身不重复携带；`check_explanations_version` 记录说明版本（当前为 2）。字段：

| 字段 | 必填 | 要回答的问题 |
|---|---|---|
| `risk_if_omitted` | 是 | 朴素检查会漏掉什么？（盲区，不是本次已发现的问题） |
| `closes_when` | 是 | 证据到什么程度可以关闭本项？哪些事不归本项？ |
| `inputs` | 否 | 复用哪个上游检查的哪个已核事实？ |
| `false_alarms` | 自动扫描（A）必填 | 哪些合法结构会触发本规则？ |

逐项执行时先读盲区和常见误报，再用真实器件、物理路径、状态和需求确认适用范围；达到关闭条件即停止，
不因没有实测或全温曲线继续索取参数。通用说明不再准确时（拓扑专用、部分范围、NA 等），在结果检查项
`check_explanation` 里只写需要改的字段，例如只改 `closes_when`；不能改绑定的原判据。
NA 写明本机为什么不暴露于该风险；纯下游项写明本阶段可做什么及后续由谁负责。

实际证据依赖在 `rationale/evidence` 中写准确检查实例 ID、所用数值/事实、适用状态和边界；
只列规则编号或“详见其他检查”不构成依赖证据。`inputs` 只是复用方向，不要求把列出的规则全部执行。
互相引用时注明各自产出的不同事实，不让两个尚未证明的结论相互担保。
“漏查可能损坏器件”不自动生成 P0；实际工况、保护协调及允许的永久安全失效仍按需求分别判断。

例如反激：DRV-T01 确认储能/送能及漏感吸收路径（无 RCD 时跨开关的 TVS 也算）；DRV-C01 复用该路径
计算吸收器件应力；PRO-C02 给保护门限，PRO-C01 联合输入能量与耐受计算停能窗口；DRV-C02 复用峰压、
驱动与工况核功率管。同一停能缺口共用一份计算并分别引用，不报成多个独立严重故障。

说明版本不是当前版本的计划不读，要重新生成；第 1 版字段 `purpose/connections` 当作未知字段拒收。

### 对象上下文录入

结论录入前，在审查证据中记录实际物理脚、装配/工作状态、逐跳路径及出处、已核范围和未知边界，
由现有 `evidence` 定位引用，无需新 JSON 字段。供电、返回及旁路电容按实际节点重新配对，不能从邻近位号
或另一器件的记录猜对象；额定补证消费 `qualification_refs` 并核实际电容轨窗口，分组端身份不能代替资格。

同一 IC 有多个隔离电源/地域时，组按官方脚表逐供电网推出（`intent.decoupling` schema 4），
返回脚由官方脚表推出，返回脚跨网时在该组（ref，net）的条目里用 `return_net` 选定本组的返回网；不要仅按芯片位号把两域返回脚池化。声明须有官方脚义与当前
归网依据，不能为避开候选而改地网、作用域或保证条件。
手册没有去耦条款（没写外接电容值、也没有"每个供电脚接 xx µF"之类的话）时，条款照样要写：`citation` 引该脚的引脚说明页，`requirements` 写明"手册未给条款"，
容量按功能判定里的估算余量判——这是审查员从手册读出的事实，不是工具限制，所以不开 `manual_verification`。

去耦逐组先列“实际供电脚→直接网络→已贴电容→直接返回网络→实际返回脚”，并列出本段电容为空、
容量不可解析与串联边界的事实。磁珠、0Ω、跳线或开关另一侧的电容只进入独立的供电/滤波分析，
不能计入本段普通旁路容量，也不能用普通旁路说明覆盖专用滤波/飞跨组。PWR-T03 可通过完整的零电容
清单核对；PWR-D02/C09 是否合格须另对本器件、本脚组、工况的条款判断。有适用替代接法/阻抗证明才可
据此放行；资料尚不能证明替代合规时记具体 INSUFFICIENT，不从“没有直接电容”统一判实物失效。

审查者旁路补查（登记在 `intent.rule_gaps`）必须保留自动生成项。`object` 用独立 `manual_group`，准确 `ref`、`nodes`、`return_nodes` 与
已声明 `state`；官方角色未在清单设备声明时，补 `manual_pin_roles`（物理节点→`power/return`）
与 `manual_pin_citation` 的独立官方脚表出处；`manual_pin_source` 用绝对 `path`、文件 `sha256` 和
`locator` 绑定原文。节点必须在当前原生输入存在；已有官方映射的冲突角色不能以审查者声明覆盖。
不能以名称候选代替核验。确认非供电脚的候选
用 `manual_group_role: "excluded_candidate"` 与实际 `other` 脚角色记录；D/C 判 NA 仍须独立用途依据。不得带任何 `decoupling_*` 生成绑定字段。审查者结论仅证明该独立判据，不恢复自动条款/资格
缺口，也不能解除输入完整性失败带来的全板 NO_GO。输入资格缺口只影响确实依赖该事实的检查项：
某器件缺功能名只影响该器件自身引脚角色，不改变网络连通，其他器件去耦组的电容、回流与边界照常审结；
不能把同一缺口复制成每个去耦检查项的 INS（见 [执行一致性](execution-consistency.md#2-局部-pass-不扩展为路径或系统-pass)）。
受影响的检查项引用原生导出逐端点比对；局部电气结论还须具体用途、原厂条款、状态及参数证明，不能仅从 XML 推断合格。
逐项证据记录取证来源、实际端点、装配及已核范围；工具验证绑定一致性，不代替手册条款核实。

接口按当前协议列实际端点、官方信号角色、各段串联/转换/隔离/保护器件、状态与外接/电缆边界。
USB 的 D+/D−、Host/Device 与供电 Source/Sink、CC/Rp/Rd 分别核相应条款，UART/SPI 按自身角色核。
窄的标准脚义/方向项可用标准及器件手册闭合；准确机械/焊盘视图与已指定对端的兼容保证另审，
未指定外卡/主机按 [本体与系统范围](evidence-proportionality.md#模块本体完整系统与制造核准) 处理。

`rationale` 和开放项的每个字段（what、scope、severity、decides）与派生待办分别核同一实际对象/状态/因果。
任务的 prerequisite、steps、impact_review、verification、avoids 不能借另一个根问题填充；输入取得方法与
验收须能关闭所关联的具体判据，不以“执行发现项说明”等通用指令替代。计算修订同步所有引用该值的结果与
结构化任务，核单位、公差及不利方向；正确理由、绑定或 locator 不证明其余字段正确。
物理脚说明同时核“位号、物理脚号、官方脚名、网络”；别名与符号编号差异注明映射依据，不把另一脚的
名称带入 locator/rationale。最终结果修改后，从最终子项 ID 与状态重新核父项的理由、缺口和汇总，
不得保留旧草稿的“子项证据不足”文字。已完成连接或计算子项不承担未解决的其他条款。
功能电路汇总引用检查项结果与现有任务，不重复收集同一材料；汇总等级注明最高可信后果对应的成员与条件，
不统一压低成员风险，也不将其复制给所有成员。

### 阵列与多单元器件的内部通道

追踪信号跨越电阻/电容阵列、分体或多单元器件前，先从完整原生缓存的各 unit 引脚定义与
原厂内部连接图确认物理 pin 的配对、元件类型和该装配的导通条件，再与每个外部 pin/net
逐端对账。保存各通道的两端物理 pin、所属 unit、数值/公差、实际源端与接收端和引用位置。
网表只列各引脚的外部网络，网络邻居不证明器件内部通道；编号相邻或图上排布也不证明配对。
缺内部映射时保留具体路径 INSUFFICIENT，不凭编号顺序推断跨阵列的端到端连接。

按确认的通道核正常态、启动与单域掉电的源/接收端供电和应力；整改方案、影响分析、条件
计算及下游移交必须指向同一真实通道。发现配对错误时保留旧记录，逐条修正受影响路径与
任务，重新对账父子结果；不把记录修正当作硬件已改动或新增已发生故障。硬件可实现某个
方向/PIO功能不证明实际固件 pinmux 或模式，配置与默认高阻/恢复顺序仍需独立受控证据。

### 功能复核

录入与最终校验前，先逐个功能核：问题是不是这块电路真正要回答的；`conditions` 是否列全了手册里有关的条款，
`use` 的推导是否成立（测试条件不是使用范围，相邻测试点夹出界限要有单调性依据）；`calculation` 的假设是否写明；
算出余量的方面是否已下结论；每个开放项的 `kind` 是否对（本设计要定的量不是厂家资料）、`decides` 是否只覆盖它真正决定的方面与状态、
`severity.consequence` 是否写了这个缺口在什么工况下导致什么后果。然后逐项用实际对象上下文对照手填检查项的 `rationale` 及关联待办：

这一步有七个机器信号（`quality_screening` 的疑点）；它们点出的是最常漏的几种，不是复核的全部：

- `UNIT_GLYPH_SUSPECT`：条款引的资料文本层丢了符号字体（kΩ 印成 kW、全文没有 µ，1.3 的审计给该资料记 `unit_glyphs: SYMBOL_FALLBACK`），
  这条 NUMERIC_LIMIT 的单位又是 ms、mA、mH、W、kW、MW——它可能是 µs、µA、µH、Ω。对照渲染页，在 `says` 写明核过（含“核过原图”“误码”“实为”或 µ 字样的 says 不再提示），或改单位。
  R7 的一份记录把 22.5–37.5 "ms" 的 OVP 检测延时当真，算出反馈断开后 VRAW 冲到 38 V 判了 P1；同一条款另一份记录注明误码按 µs 算，结论相反。
  校验器按结果文件所在目录解析条款的 `source`（相对路径或绝对路径，PDF 原件也读文本层）。
- `RATING_AT_TEST_TEMP`：余量的 `limit` 是功率或电流额定（W、mW、A、mA），`regime` 只给一个 ≤ 25 °C 的温度点，`derivation` 却写 GUARANTEED_LIMIT：
  额定在这个温度成立，本板环温更高时要经降额曲线或数表（PUBLISHED_TABLE、TYPICAL_CURVE 或 `conversion` 指向的换算条件）带过来，或在 `regime` 写明为什么不降额。
- `BOUNDING_CELL_AVAILABLE`：决定性余量写了 `cell: NONE`，但它的 `against`/`aspect` 或限值条款的 `says`/`use` 里有某个格的参数词（VZ、VF、RDS(on)、CTR、Isat、ESR……，`catalog.CELL_WORDS`）：
  如果这个限值就是那个参数，写格和推法，带公式的推法让门禁复算。
- `TEMPLATE_REASON`：同一句理由、关闭条件或取得方式出现在几个开放项上（`why_insufficient`、`closure`、`acquisition`）。
- `UNIT_UNKNOWN`：余量的 `unit` 或条款 `limit.unit` 不在单位表（`scripts/units.py`：SI 前缀 × 电学基本单位，µ/u、Ω/ohm、²/2 同义，Vac/Arms/°C/%/ratio/x/A²s/mV/K/°C/W 等专名）里。
  按表的拼法写；真是新单位就加进表。表外单位既换算不了也核不了量级。
- `QUANTITY_IMPLAUSIBLE`：限值的 `min`/`max`（两端）或余量的 `value`（只看上端：余量可以很小）换算到基本单位后超出该量纲在板级可能的范围
  （电压 1 µV–1 MV、电流 1 pA–100 kA、电阻 1 µΩ–100 TΩ、电容 1 fF–10 kF、时间 1 ps–1 Gs、温度 −273–3000 °C……，`units.SPANS`）：多半是前缀写错或文本层丢了 µ，对照渲染页改。
- `RESULT_NARRATIVE`：`calculation.result` 超过 300 字，或带超过 8 个余量 `value`、限值 `min`/`max` 都没承载的“数字 + 单位”。结构化字段是主路径：每个比较过的量写成
  `margin{value, unit, against, basis}` 或条款的 `limit`，`result` 只留结论句（报告只印第一句）。R7 两份 Codex 记录把 514/561 个量写在 result 里（10/13 个 result 超 300 字），余量只有 111/96 条；两份 Claude 记录 117/107 个量对 151/181 条余量。

4.2 证据不足的分类另有自己的提示：`DOWNSTREAM_RECORDED_AS_DESIGN_GAP` 除了读检查项的缺口文字，还读 VENDOR_DATUM 开放项的
`closure`、`acquisition`、`why_insufficient`——写了实测、样机、样品、仿真作为关闭路径的（“随后/留给……”分句已分出下游部分，不算），厂家保证值和样机才能测是两档，
实测的部分拆成阶段 NA 检查项加移交，开放项只写真正能关它的数据或规格。R7 的四份记录里这样的开放项有 2 / 0 / 6 / 2 条（三只光耦的 CTR“保证或高低温实测”、端口短路“实测峰流”、BULK 浪涌“实测或仿真上界”）。
`FIRMWARE_IMAGE_RECORDED_AS_DESIGN_GAP` 与 `CALCULATION_RECORDED_AS_DATA_GAP` 同样读开放项（`what`、`acquisition`、`closure`、`why_insufficient`、`deliverable`、`spec`，“随后/留给……”分句不算）：
VENDOR_DATUM 项写了烧录镜像、读回、编程模式、量产校准而 `what`/`acquisition` 里没有编程口、上拉、GPIO 这类原理图前提的是前者；
VENDOR_DATUM 项的取得方式写了已读某页、只剩复算，又没有一句说缺哪个数据的是后者。手填检查项仍按检查项的 `missing_inputs` 判，派生检查项不逐项点。

筛查的层级：派生检查项（`derived: true`，`open_ref` 指向开放项；读取时派生，台账里没有）的措辞、对象、后果与缺口都是工具按开放项写的，所以对象越界、后果引外部位号、引用本记录、下游误记、时序窗口、定级整批同级这些疑点在派生检查项上读开放项一次——
定级按缺口数（一条开放项和它挡住的检查项算一个）、时序窗口看开放项的 `scenario`/`allowed_window`/`response_bound`、`check_ids` 列该项挡住的检查项。
R7 上这些疑点原来点到的派生检查项（codex1 对象/后果越界 18 项、同规则整批同级 92 项，codex2 时序窗口 13 项——都指向一条已写好窗口的开放项）全部收回；codex2 13 条开放项 12 条同级，仍提示。

门禁拒收的两件：决定性余量（GUARANTEED_BOUND、REACHABLE_CASE、EXACT_ENVELOPE）没写 `basis.cell`；`basis.conditions` 里有 min≠max 的 NUMERIC_LIMIT（除 `limit` 本身）却没有对应角点，
`no_corners_reason` 不能代替。

- 对每条需求，将原文与本检查项 criterion 中并列的功能、工况前提、交付和范围排除分别列为分项要求，
  在现有 evidence 定位每项实际证据、相关检查 ID 与状态。明确排除认证、实测或某种使用状态，
  只证明该排除分项要求；不能据此让同条需求中的电气实现或保证前提一起 PASS。必要时按上文
  “拆分实例的命名”补查分项要求，保留自动原项及完整覆盖关系。
- 需求整项只有全部适用分项要求已 PASS（或有来源证明 NA）时才能 PASS。分项要求有确认 FAIL 时
  整项按真实违反给 FAIL；没有确认 FAIL 但仍有必需证据不足时整项为 INSUFFICIENT，写明具体
  开放项、未知和关闭条件，是否写 `"blocking": false` 按该要求现有准出依赖判断。最高潜在级仅引用实际相关
  分项要求的可信物理后果与条件，确认缺陷和潜在风险分开；复用既有唯一根因任务，不重复计缺陷。
  纯范围排除项可独立 PASS，不能因为全板其他项未闭就自动传染 INSUFFICIENT；相反，复合项不能
  用范围 PASS 掩盖它明确依赖的器件自身的要求。资料缺口不是需求待决，不改成问用户。

- 将文字中的每个位号、物理脚、网络与本检查项对象/状态核对。额外对象只能作为有定位的供电、返回、保护或
  共同证明路径出现，说明其与本检查项的关系；从其他检查项继承而无因果关系的前缀、脚名、数值须删除或重写。
  旁路、储能等器件清单按本检查项所核电源脚及实际贴装变体的连接路径列出，避免把全板清单带入局部判据。
- 用“本检查项要判断的内容→已核路径/条款→剩余未知→补证或修改→复验判据”核闭环。接口防护的缺口须对应
  该接口的实际外接边界；另一个接口的浪涌、旁路或源许可不能独自关闭本检查项。无源触点的候选排除说明须
  引用其真实角色，不能借相邻 IC 的旁路说明代替。
- 共享的是可定位的证明，不是整段结论。确实共用同一路径/工况的对象可引用同一证据，分别说明它覆盖的
  范围；状态、对端、故障路径或关闭资料不同的项分别写。不要以禁止共享文字的机械规则制造重复工作。
- 修改理由或关联关系后重新核父项、澄清项和任务；已完成的板级窄判据与真实外部未知分别留记录。
- 运行态与掉电态分别核取证。正常运行接口项引用运行供电、输入电平/共模和对端边界；Ioff、掉电泄漏、
  UVLO/关断条件只支持其实际适用的状态与判据。某个字段写错状态时修正该字段及关联任务，仍保留
  本检查项真实未闭合的外部共模等缺口，不用掉电补证替代运行态证明，也不把整项自动改为 NA。
  原生绑定只核记录一致性，`quality_screening` 只提示疑点，两者都不能证明文字中的工程主张正确。

### 预交付的范围与必要性复核

最终台账与报告交付前，按 [交付前的必要性复核](evidence-proportionality.md#交付前的必要性复核) 逐条反查补证、澄清及移交的关闭条件。

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
  "evidence": [{"source": "db.json", "locator": "nets.SENSE_A; nets.SENSE_B"}],
  "rationale": "要求的检测端点不连通，见路径表 PATH-01。",
  "severity": "P1",
  "finding_id": "F-001",
  "handoff": {"required": false}
}
```

证据不足的检查项只指向功能判定里决定它的开放项（缺口文字写在开放项上，检查项不重复）：

```json
{
  "id": "ANA-C01.CURRENT-RUN.RS1",
  "binding": {"object": {"circuit": "CURRENT", "ref": "RS1", "state": "RUN"},
              "criterion": "……"},
  "applicability": "APPLICABLE",
  "review_result": "INSUFFICIENT",
  "function_id": "FN-CURRENT", "aspect": "直流范围与误差", "open_ref": "FN-CURRENT/ADC-CAL",
  "evidence": [{"source": "evidence/engineering.md", "locator": "## CURRENT"}],
  "rationale": "见功能判定 FN-CURRENT（直流范围与误差，RUN）：开放项 ADC-CAL——RS1 校准与误差预算未定",
  "handoff": {"required": false}
}
```

`gap_cause`、`missing_inputs`、`input_requests`、`potential_severity`、`impact_assessment` 由开放项推出
（VENDOR_DATUM→EXTERNAL_DATA，其余同名），写了会被拒绝。

由校验器推出、不写进台账的字段（写了会被拒绝）：
- `blocking`：FAIL/INSUFFICIENT 默认阻塞。只有阶段允许暂留的 P2/P3 才写 `"blocking": false`。
- `evidence_confidence`：PASS/FAIL 默认 B，INSUFFICIENT 为 C。只有声称 A 级证据时才写 `"A"`。
- `disposition`：默认 OPEN。只写 FIXED_VERIFIED、ACCEPTED、RETRACTED。
- 检查项级潜在等级是 `open_ref` 指向的开放项的 `severity.level`；一项只指向一个开放项。

- `binding.object`/`binding.criterion` 是实际已审范围，与同 ID 计划的 object/criterion 完全一致；
  `evidence` 和 `rationale` 只支持这个对象、配置、工况和判据。复用结论前核对物理脚、网络及要求，
  不能因 ID 相似、同一 IC 或同一功能组就移用。
- 所有结果含非空 `rationale` 与可定位 `evidence`。INSUFFICIENT 必须有 `open_ref`（REQ-H02 历史处置除外）；非 FAIL 不填 `severity`（检查项级字段只属于 FAIL）。
- 每个开放项给 `scope` 和完整的 `severity`（`level`、`class`、`affects`、`consequence`），校验始终强制；
  内容按 [危险度分类原则](verdicts-and-release.md#证据不足的危险度分类原则) 逐项判定；非空字段不等于危险度可靠。
  `consequence` 同时是定级理由：写清这个缺口在什么工况下导致什么后果，不写跨开放项通用的套话（`TEMPLATED_SEVERITY_REASON`）。
- **独立审查**：结果顶层写 `history_inputs`（本轮能看到的旧审查目录或文件路径，没有就写空数组）。除 REQ-H02 上一版问题复验检查项外，任何检查的 evidence 引用这些路径都会被 `validate_review.py` 拒绝；未声明却引用某次审查的结论/校验/报告文件（`review-results.json`、`review-gate.json`、`审查报告.md`）会进质量筛查候选。报告结论里写明本轮可见的旧审查材料（只显示目录名）。首审（`review_mode: first`）可以看到旧材料，但结论按当前资料重新得出、不引用旧结论，也不逐条登记上一版问题的处理结果，报告照此说明；要逐条登记（已修、保留、撤回），用改版复审（REQ-H02）。
- `severity.class` 是后果类别，类别决定潜在等级（见[后果类别](verdicts-and-release.md#后果类别severityclass)）；
  P0 类别另给 `severity.hazard_path`，只会坏一个器件而不打开危险路径的写 `COMPONENT_DAMAGE`（P1）；
  P0 类别降为 P1 时给 `severity.exclusion` 写出独立保护。
- 每个 REQ-D01（需求状态 DEFERRED 与 NA 除外）给 `requirement_clauses`，
  把需求原文按顺序完整拆成条款（拼接后等于原文），逐条标类别：

  | 条款形式 | kind | 结论 |
  |---|---|---|
  | 规定本设计应达到的量值、功能或状态（=、≤、≥、±、须、不得、支持、保持、可靠进入） | OBLIGATION | `result` 取 PASS/FAIL/INSUFFICIENT/NA，可附 `check_ids` |
  | 工况与前提（允许…、输入…范围、给定的器件参数）、审查方法与输入取值（按…审查、公差取…、先读…再登记、移交下游）、范围说明 | PREMISE | 不带结论；作用于所有相关检查项 |

  格式：`[{"text": "原文片段", "kind": "OBLIGATION", "result": "PASS", "check_ids": [...]}, {"text": "原文片段", "kind": "PREMISE"}]`。
  检查项结论 = 要求条款中最差的结论（FAIL > INSUFFICIENT > PASS > NA），校验强制。前提条款里的要求由相关器件/电路检查项执行，
  其他检查项发现的缺陷不连带本检查项；需求原文把该缺陷写成要求（如“各连续受电元件不得超出持续功率额定”）时才在本检查项判。
- 证据不足的原因是开放项的 `kind`：VENDOR_DATUM、REVIEW_INCOMPLETE、USER_DEFERRED，
  含义见 [复核每条证据不足](evidence-proportionality.md#复核每条证据不足)。纯下游项不是 INSUFFICIENT，用阶段 NA。
  `scope` 写缺口要覆盖的电压/负载/状态/温度范围，不是标题或 `what` 的复述（`REQUEST_SCOPE_ECHOES_TASK` 提示，报告也不显示只复述的范围）；
  `acquisition` 以“已读 X 第 N 页，缺 Y”开头时，报告把“已读”部分单列为“已查过”。
  `closure` 写设计者能核的边界和条件（手册限值、标准条款、工况），不写审查员算例的中间值；
  位号与数值之间留空格或标点（“R12 100°C”，不写“R12100°C”）。
- 计划检查项带 `proposal.result = PASS` 而结论为 FAIL/INSUFFICIENT 时，须给 `proposal_override`（code 与 reason），
  code 的封闭清单见 [通用件最弱档基准](commodity-floors.md#计划预判dev-c01-逐颗检查项)。
- `bom_constraint`：常规器件（电阻、电容、电感、二极管）超出最弱档、或需求的特殊要求（寿命、精度、宽温等）落到这颗器件时，
  在 PASS 检查项上写 BOM 必须写明的要求，不建开放项、不记证据不足（规则见 [通用件最弱档基准](commodity-floors.md#常规器件只排查风险)）：
  `{refs, requirement, basis, consequence_class, level, status, hazard_path?, written_at?}`。`requirement` 写最低值（“额定功率 ≥ 0.09 W”
  “耐久 ≥ 10000 h @105 ℃”）；`basis` 写算出它的计算或需求编号；`consequence_class`/`level` 按
  [BOM 约束怎么定级](commodity-floors.md#bom-约束怎么定级)，等级由类别决定；`status` 为 TO_WRITE（冻结阶段阻断）或
  WRITTEN（`written_at` 指向 BOM 上写明它的那一行）。报告单列“BOM 要写明的额定与规格”一节。
  校验拒收：VENDOR_DATUM 开放项挡住的检查项全是常规器件的 DEV-C01/DEV-C02 项，或挡住全板 BOM 行（DEV-D04）而文字只点名常规器件时，应改写成 `bom_constraint`。
  需求有寿命参数（`lifetime`）时，计划按 `mission_profile` 给每颗电解、固态或超级电容一项 `DEV-C02.LIFE.<位号>`（带移交热设计；
  判据只写剖面的数字，相位名放在检查项的 `mission_profile` 字段），
  给每颗耗损件一项 `DEV-C06.<类别>.<位号>`（按次数核而次数没给的直接 NA）；寿命检查项可凭估算余量（`ESTIMATE`）判 PASS，
  这时须写 `bom_constraint` 且 `requirement` 写明“估算”和所设热点；寿命检查项不开 VENDOR_DATUM，见
  [寿命与耗损件](commodity-floors.md#寿命与耗损件)。
- 光耦输出接在控制器的反馈脚（FB/VFB/COMP）上时，计划给这个脚一项 `PRO-C01.FEEDBACK-OPEN.<位号-脚>`：反馈断开（光耦或串阻开路、副边控制失效）后控制器按开环送能，按手册的保护检测延时算到保护动作为止输出侧电压的上界，对照输出侧器件耐压；这一单一故障不看审查员是否想到。
- 其他常见单一故障也按网表特征派固定检查项，检查项只问问题、不预设结论，没有特征就不派：
  - 开关管一端接连接器、该端不给任何 IC 供电，另一端是变换器或稳压器输出（声明的电源轨，或能追到来源且有对地大电容）、本身不接连接器：`DRV-C02.PORT-SHORT`，端口硬短路时储能经开关释放，按写明的最小回路阻抗核 SOA、I²t 与关断尖峰，该阻抗交给后续环节；
  - NTC 两端都不接 IC、旁边有整流桥、二极管、保险或连接器（限浪涌用）：`PWR-C13.NTC-HOT`，热态重接入时整流桥、保险与输入电容承受的浪涌，源阻抗按 IEC 60725 参考阻抗；这两种外部阻抗都不记设计没定；
  - 开关节点（有 MOS 漏极和变压器或电感）经二极管到一个没有对地大电容的节点，该节点上的电阻和电容另一端接同一网：每颗电阻一项 `DRV-C01.RCD`，钳位电阻功率与耐压；
  - IC 的信号脚和 LED 或光耦 LED 的一端在同一网（不经晶体管、不是地网）：`DEV-C05.PIN-LED`，按第 5 条四档核该脚的电流；
  - 光耦输出接到 IC 的使能或关断脚（EN、SHDN、DIS、INH、STBY、ON/OFF、RUN 等）：`SIG-C09.ENABLE-LINK`，上电先后、使能门限与光耦延时、掉电后能否恢复。
- 器件检查项（DEV-D01 身份、DEV-D05 引脚处置、DEV-C05 工况）只跟核验过的器件类别走：集成电路（U/M 位号或原生电源脚识别的有源器件）、晶体管、光耦、稳压/TVS 二极管、整流桥、变压器和 part/value 写明 CUSTOM 的电感固定生成（跨网与地的防护钳位不出 DEV-C05，归 PRO-E02）；普通二极管、普通电感和阻容是常规件，声明了 `intent.devices` 也不生成器件检查项（声明只供脚表与输出档位用），它们的应力在所属电路的 DEV-C01 预判里按最弱档算，超了才逐颗出 DEV-C01 项；要让一颗二极管进器件检查项，路径是 `device_kinds` 核验为 zener/tvs/整流桥（[通用件定界](commodity-floors.md#哪些器件有自己的检查项)）。
- 脚电流行（`DEV-C01.PIN.*`）的串阻读不出阻值、计划没算出脚电流时，判 PASS 须附 `manual_verification`，在 `method` 里写出自己的脚电流计算。
- 阶段 NA：`review_result: NA` + `na_reason: OUTSIDE_SCHEMATIC_STAGE`，`applicability` 保持 APPLICABLE，
  `handoff.product_requirement_status: PENDING_VERIFICATION`，不建开放项；完整写法见 [纯下游验证项](verdicts-and-release.md#纯下游验证项)。
  复合要求不能整体 NA（只有 `catalog.STAGE_ASPECTS` 的方面检查项——DOWNSTREAM_HANDOFF——整项阶段 NA）；测试要求条款写 `result: NA`、`na_reason: OUTSIDE_SCHEMATIC_STAGE`，
  `check_ids` 链接独立阶段 NA 检查，不得只改条款结果让测试消失。
- 普通 NA 必须 NOT_APPLICABLE；修改自动计划的适用性需 `applicability_evidence`。计划检查项带 `requires`（网表上找到了它问的机制）
  时，NA 的 `applicability_evidence` 里至少一条写 `nets` 和/或 `pins`（`REF.PIN`），名字须在网表里，说明是哪条网表事实排除了它；
  只写一句能定位的话不够。UNDETERMINED 只能落 INSUFFICIENT。
- `disposition`（默认 OPEN，不写）：FIXED_VERIFIED / RETRACTED 只用于当前 PASS/NA 并须 `closure_evidence`；ACCEPTED 保留
  FAIL/INSUFFICIENT，附 `acceptance`（by/date/scope/reason/record，来自真实授权记录）。P0/P1 潜在未知默认阻断。
- 必需 handoff 的 receivers/constraint/verification 不可空；ACCEPTED/VERIFIED 须有 evidence；
  取消计划中的必需 handoff 须 `handoff_evidence` 留据。handoff 随图交出，OPEN 不阻断冻结。
- `manual_verification`：自动工具因自身限制（映射不全、模型不支持等）不让某项判 PASS，而审查时已不靠该工具、
  逐项对照网表和原厂资料核对完时，按核对结论判 PASS/FAIL，附
  `manual_verification: {tool_limitation, sr_improvement, method, evidence}`：
  SR 为什么做不到（哪个检查器、缺什么映射或模型）、建议怎么改进 SR（具体到规则、别名或模型）、这次怎么核对的。
  这是审查者（通常是 AI）自己的核对，不写成“人工核对”，除非确实有人参与并留有记录。可用 `reviewer_kind: "AI"` 或 `"HUMAN"` 明示实际核对者；未记录时不得推断为人员核对。
  同一对象（只差状态）的几项可写相同文字，报告会合并显示；不同对象写同一段 `method` 会被拒绝，每个检查项写清核对了哪些位号、节点和数值。只能用在工具确实拦了的检查项上；
  这类检查项不算 REVIEW_INCOMPLETE、不建开放项，gate 把工具限制列入 `sr_improvements`，不影响准出。
  资料或设计本身没给出的数值不是工具限制，仍按 EXTERNAL_DATA 处理，设计没定的按甲乙判。
  工具提示的 `required_inputs` 指向 `intent:` 字段（如 `supervision.rail_requirements` 逐轨 `required=false` / `internal_monitor`，
  `optocouplers[].internal_pullup`）时，是声明缺失不是工具限制：先补 intent、重生成计划再判，不写 `manual_verification`。
  校验按阻断的缺口代码强制这一条：`intent`、`evidence`、`requirements`、`firmware`、`population`、`datasheet*`、`unverified-device-pinout`、
  `official-full-pinout`、`rail-requirement`、`level-standard` 开头的缺口是审查者可补的输入，`manual_verification` 覆盖不了；
  其余（拓扑或模型识别不了，如 `pin-role-or-model:`）才算工具限制，报告“对 SR 的反馈”按缺口代码列出。

### 示例：设计约束和开放项各决定一项

合成例子：反激变换器的 T1 是定制件，图纸还没出：SR 把它要满足的条件写成设计约束（DESIGN_CONSTRAINT 条款，交给磁件设计），
环路模型（PWR-C15）按这条约束判合格；输出电容的低温 ESR（厂家才知道，VENDOR_DATUM）挡住最小关断时间（PWR-C04）。两项都由 `derive_rows.py` 从功能派生。

```json
{
  "functions": [{
    "id": "FN-QR", "circuit": "QR", "question": "90–264 Vac、5–12 V、空载至 3 A 时反激各输出档是否稳定且关断时间不低于 tOFF(min)",
    "objects": {"refs": ["U1", "Q1", "T1", "C5"], "nets": ["BULK", "VOUT"]}, "states": ["RUN"],
    "conditions": [
      {"id": "c1", "kind": "MANDATORY_CLAUSE", "source": "evidence/ds/U1.txt", "locator": "p13 Feedback, p21 补偿网络", "refs": ["U1"],
       "says": "使用内部补偿时，功率级增益和输出电容零点须在规定范围内", "applies": "FB 不外接补偿时", "use": "FB 外接与条件一致"},
      {"id": "c2", "kind": "NUMERIC_LIMIT", "source": "evidence/ds/U1.txt", "locator": "p8 Table 6", "refs": ["U1"],
       "says": "tOFF(min) ≤ 1.2 µs（−40..125 °C）", "limit": {"max": 1.2, "unit": "µs"}, "regime": "−40..125 °C",
       "use": "判据：关断时间不小于 1.2 µs"},
      {"id": "c3", "kind": "NUMERIC_LIMIT", "source": "evidence/ds/C5.txt", "locator": "p1 特性表", "refs": ["C5"],
       "says": "ESR ≤ 50 mΩ @20 °C、100 kHz", "limit": {"max": 50, "unit": "mΩ"}, "regime": "20 °C，100 kHz",
       "use": "低温 ESR 未给"},
      {"id": "c4", "kind": "NUMERIC_LIMIT", "source": "evidence/ds/C5.txt", "locator": "p1 规格表", "refs": ["C5"],
       "says": "使用温度范围 −40..+105 °C", "limit": {"min": -40, "max": 105, "unit": "°C"}, "regime": "全系列",
       "use": "−20 °C 在规定使用范围内"},
      {"id": "c5", "kind": "DESIGN_CONSTRAINT", "source": "evidence/engineering.md", "locator": "## QR 补偿适用范围",
       "says": "T1 的 Lp 公差、匝比与漏感使各输出档功率级增益和输出电容零点落在 U1 内部补偿适用范围内，且 264 Vac/12 V/0.3 A 下关断时间 ≥ 1.2 µs",
       "regime": "90–264 Vac、5–12 V 输出、空载至 3 A", "owner": "磁件设计", "handoff": 0, "use": "定制变压器图纸要满足的条件"}
    ],
    "no_calculation_reason": "功率级增益和关断时间由 T1 参数决定，按交给磁件设计的约束判，不在这里另算",
    "judgements": [{"aspect": "反馈模型与补偿资格", "conditions": ["c1", "c5"],
                    "says": "FB 不外接补偿，与内部补偿的前提一致；T1 按约束 c5 使功率级增益与零点在适用范围内"}],
    "handoffs": [{"receivers": ["磁件设计"], "constraint": "T1 的 Lp、匝比与漏感满足 c5",
                  "verification": "磁件规格书给出 Lp 下限、匝比与漏感上限，按它算出的增益、零点和关断时间满足 c5"}],
    "verdict": "OPEN",
    "open": [
      {"key": "C5-ESR", "kind": "VENDOR_DATUM", "what": "C5–C8 在 −20 °C 的 ESR 上限",
       "scope": "−20–40 °C 环境，5–12 V 输出", "checked": ["c3", "c4"], "why_insufficient": "c3 只给 20 °C ESR，c4 只给使用温度范围",
       "acquisition": "向电容厂家索取低温 ESR，或改用手册给出该值的系列",
       "worst_case": {"not_boundable_reason": "手册和厂家系列特性表都没有低温倍率，无法取上界",
                      "curves_checked": [{"source": "evidence/ds/C5.txt", "locator": "p1 特性表、p3 阻抗–频率曲线（仅 20 °C）"}],
                      "operating_point_specified": true, "specified_by": "c4",
                      "monotonic_tried": {"side": "UPPER", "cell": "ECAP-ESR-RIPPLE", "quantity": "C5 的 ESR 上限",
                                          "operating_point": {"min": -20, "max": 40, "unit": "°C"},
                                          "test_points": [{"condition": "c3", "at": {"value": 20, "unit": "°C"}}],
                                          "why_not": "只有 20 °C 一个测试点，ESR 随温度降低而升高，升多少没给",
                                          "other_side": "NOT_DECISIVE",
                                          "other_side_reason": "ESR 偏低只让零点频率升高，在适用范围的另一侧还有余量"}},
       "closure": "低温 ESR 满足控制器对输出电容零点的适用条件",
       "decides": [{"aspect": "变换器时序与输出电容条件", "via": {"condition": "c3"}, "side": "UPPER",
                    "rationale": "低温 ESR 决定输出电容零点的位置，20 °C 的上限给不出 −20 °C 的界"}],
       "severity": {"level": "P1", "class": "PERFORMANCE_OR_LIFE", "affects": "低温输出纹波",
                    "consequence": "低温 ESR 升高使输出电容零点移出适用范围，纹波超出规格"},
       "design_option": {"status": "NONE", "reason": "先查现有型号的低温 ESR；换型号同样需要该值",
                         "evidence": [{"source": "evidence/ds/C5.txt", "locator": "p1 特性表"}]}}
    ],
    "fails": [], "evidence": [{"source": "evidence/engineering.md", "locator": "## QR"}]
  }],
  "checks": [
    {"id": "PWR-C15.QR-RUN.U1", "review_result": "PASS", "function_id": "FN-QR",
     "aspect": "反馈模型与补偿资格", "handoff": {"required": true, "state": "OPEN", "receivers": ["磁件设计"], "…": "…"}},
    {"id": "PWR-C04.QR-RUN.U1", "review_result": "INSUFFICIENT", "function_id": "FN-QR",
     "aspect": "变换器时序与输出电容条件", "open_ref": "FN-QR/C5-ESR", "…": "…"}
  ]
}
```

- 一项只指向一个开放项：同时受几个开放项影响时，`derive_rows.py` 取 `open[]` 里先写的那个；
  开放项派生一件待办（W-C5-ESR），待办的 `check_ids` 是指向它的检查项。设计约束不派生待办，只随检查项移交。
- 共享的是开放项，不是结论：各项的方面写在 `decides` 里，等级和 `scope` 写在开放项上。
- 不再有 `obligations`、`request_keys`、`closure_domain`：隔离资格与环路稳定是功能的方面（见上）。

### 发现项

每个 `findings[]` 含 id、kind（DEFECT / IMPROVEMENT）、severity、check_ids 及非空的 `title`、`observed`、
`criterion`、`impact`、`scenario`、`root_cause`、`recommendation`、`verification`、`severity_reason`、`remediation`；
`location` 含 pages/refs/nets 字符串数组，缺图面时写“未定位：缺某版本 PDF”，不编造页码。
`--require-actionable` 下 P0/P1 的 DEFECT 另带 `figures`（kind/source/locator/caption），至少一张 ACTUAL；修改方案含 CONNECT/COMPONENT/DESIGN 步骤时再加 AFTER 或 REFERENCE，见 [用图说话](report-and-remediation.md#用图说话)。`root_cause` 写电路为什么失效（哪个量越过哪个限值），不写缺哪个器件。

- DEFECT 与其 FAIL 检查双向引用；一个根因一个 ID。严格绑定下，DEFECT 的 check_ids 都必须是该 finding 的 FAIL。
- location 覆盖各被检查的主对象（计划 object.ref、object.node 所属位号、object.net），不用共同电源或宽泛功能组代替。
- IMPROVEMENT 仅 P3，关联判据必须已 PASS。
- 例：STRAP 缺陷不能挂到已满足的 EN 判据；装配/等效值与低电平/上升时间是独立判据，不能互相代判。
