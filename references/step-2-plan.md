# ② 出计划

> 读者：审查员。

做本步前读 SKILL.md 和本文件；五个步骤的总览见 [SKILL.md 的执行流程](../SKILL.md#执行流程)。

## 2.1 冷扫、候选与决定

② 出计划的命令按这个顺序跑（b 是 1.3 的取证，g 是 2.2 的重审计，穿插在中间）：

    python3 scripts/lint.py db.json --log netlist.log --intent intent.json --plan-json review-plan-cold.json --json lint-cold.json       # a 冷扫：1.2 的命令，① 做完后带全部 intent 再跑；还没有电路决定
    python3 scripts/audit_datasheets.py db.json --datasheet-dir <资料目录> --intent intent.json --json datasheet-audit.json             # b 1.3 的取证命令，器件类别补全后再跑一次
    python3 scripts/circuit_candidates.py db.json --intent intent.json --datasheet-audit datasheet-audit.json --json record/circuit-candidates.json   # c 候选
    python3 scripts/circuit_decisions.py intent.json record/circuit-candidates.json --db db.json --write                               # d 决定，推出 intent.circuits
    python3 scripts/lint.py db.json --log netlist.log --intent intent.json --datasheet-audit datasheet-audit.json --candidates record/circuit-candidates.json --plan-json review-plan-cold.json --json lint-cold.json   # e 带候选重跑冷扫
    python3 scripts/gap_inventory.py review-plan-cold.json --datasheet-audit datasheet-audit.json --md 资料请求.md                      # f 资料请求
    python3 scripts/audit_datasheets.py db.json --datasheet-dir <资料目录> --resolution datasheet-resolution.json --intent intent.json --json datasheet-audit.json   # g 补齐资料后重审计（2.2）
    python3 scripts/lint.py db.json --log netlist.log --intent intent.json --datasheet-audit datasheet-audit.json --candidates record/circuit-candidates.json --merge-plan review-plan-cold.json --plan-json review-plan.json --json lint-hot.json   # h 合并扫描，出最终计划

intent 一旦写了 `circuit_decisions`，每次扫描都要带 `--candidates`，否则直接报错。每次扫描都会打印计划要你先处理的提示（阻值读不出、电路类型问不到规则、未声明电压的轨、无界节点/跨域），这些提示也写在计划的 `diagnostics` 里。

电路不手画：器件类别核验后生成候选，审查员只对候选做决定，再推出 `intent.circuits`。

候选 = 类型 + 核心器件（核验角色的 IC，或无人驱动 / 声明了角色的开关），成员带走到它的路径（`via`，是归属关系不是导通主张）；
决定每个候选恰一条：accept / merge / split / reject（OUTSIDE_SCOPE、NOT_A_CIRCUIT、DUPLICATE_OF）/ add（只收未归属器件），
merge、split、reject、add 和加工作态都要能定位的引用。每颗被持有的器件恰好归一块电路（`owned`），其余持有它的电路只引用它；
同一级打平的器件（候选的 `shared`）写 own 决定（`ref`、`candidate`、可定位引用）裁定归谁。
计划按功能树组织，每个检查项恰有一个所属 `owner`：系统功能（电源树、地、监控、上电时序、主控引脚，有对象才生成）→ 功能电路 → 接口 → 全板与文档。
电路级检查项归电路，按候选编号与工作态识别，不随画法变；器件检查项归拥有该器件的电路，器件应力、电容和精度每块电路对它拥有的器件问一项，没人拥有的器件归全板一项。
计划的 `interfaces` 列出电路之间、链路、供电轨和连接器四种接口及端点角色，推不出的角色和轨源列为缺口；
接口规则逐接口问（电路对的方向与电平、链路两端电平、供电不同的网络的跨域注入、连接器的对端定义/载流/防护、敏感电路取电轨的噪声）。
系统功能、电路对、链路和连接器各有一个框架，与电路框架一样下功能判定；报告的功能表按系统功能、功能电路、接口分组，每个发现项写所属。
校验覆盖两条：每颗贴装器件恰归一块电路或列在 REQ-Q08 待审清单上，每个接口都有它的检查项和框架。候选漏了器件不手加计划检查项：
属于某块电路的写 add 决定（`intent.circuit_decisions`，`id` 给已有电路即并入）后重生成；有源件（mosfet / bjt / opto / ic，以及类别读不出、三个以上网的器件）不属于任何电路的写器件级 reject（`ref`、`reason`、`citation`），
两端件留在 REQ-Q08 清单上写原因；候选规则该认出而没认出的，另记改进台账改规则。
`features` 的 NOT_APPLICABLE 声明不生成检查项：候选没检出的类型都在 REQ-Q08 那一项里逐个确认，声明只作它的依据；REQ-Q07 只给检出或声明适用的类型。
`unassigned` 与 `gaps`（没核验角色的 IC、缺引脚名）先清。
格式见 [intent 字段](intent-format.md#一intentjsonschema_version-5)，规则见 [自动检查](automation.md#二检查器)。

SR 只用“[不变的决定](pipeline-overview.md#不变的决定)”第 1 条的四类输入：设计方的报告、方案、计算书、选型记录、意图、追溯、自检记录和对前轮意见的回复都不作参考，审查意图的出处和证据引用它们时校验拒收（`independence.py`）。
原理图上看不出、只写在设计文档里的事实（固件门限、寄存器配置等）写成移交项请设计方确认，确认后作为需求或输入进入审查。

冷扫的 FINDING/CANDIDATE 已各成计划一项，与其他检查一样作答。补齐命名启发式漏掉的对象/工况，登记到 `intent.rule_gaps` 后重新生成计划。排除候选须有反证，无特征不等于 NA。
电路检查项只在网表上有它问的机制时生成（功能框架的 `not_asked` 列出没问的和原因）；扫描提示某电路类型问不到一半规则（`CIRCUIT_TYPE_MISFIT`）时换电路类型或不建该电路。
计划检查项带 `requires` 仍记 NA 的，`applicability_evidence` 写排除它的 `nets`/`pins`；只说“不适用”的通过被拒，改记 NA。
检查器（I²C、去耦、感性负载、功率开关、输入滤波、上电、监控、差分电平、光耦等）每趟都跑；
名称线索只生成待复核候选，清单绑定输入指纹，不能编辑清单消缺口。见 [检查器共用约定](checker-conventions.md)。
扫描提示“未声明电压的轨”或“无界节点/跨域”时，先在 `intent.power_rails` 补轨压、节点窗口和参考地分区 `domain`
（由审查者按需求和稳压器/钳位手册自行定界，逐条写 `citation`），网表上像电源而名字不像轨的网逐条声明成轨或写进 `rail_exclusions`，再合并扫描；空的 `power_rails` 会让全部阻容预判失效。扫描提示“阻值读不出的电阻”时当场告诉用户：列出位号和原值，请设计方改成 `阻值[/公差][/额定功率][/额定电压][/封装]` 的写法或确认阻值，不自行猜阻值；未改之前这些电阻的预判和脚电流不算。值后面多一个说不清的词（如 `47R/1%/2W/pulse`）时阻值照读，诊断 `RESISTOR_VALUE_WORD` 只列这个词：它说的要求（抗脉冲能量、额定电压）是特殊要求，写成 BOM 约束，不开“阻值读不出”的待办。见 [通用件定界](commodity-floors.md#计划预判dev-c01-逐颗检查项)。

做完的标志：候选文件已生成，`circuit_decisions.py --write` 无错误（每个候选恰一条决定、未归属有源件 0、加的工作态都有 `state_requirements` 点名的需求、`intent.circuits` 已推出）；
带候选的冷扫（e）不再提示未声明电压的轨、无界节点/跨域、`CIRCUIT_TYPE_MISFIT`、阻值读不出；候选文件的 `gaps` 清零，
`DEVICE_KIND_GENERIC` 列的 ic 逐颗看过；REQ-Q08 清单上只剩两端件。

## 2.2 资料请求与重审计

命令是 2.1 清单的 f、g。冷扫后先出资料请求（f），按装配资料、器件资料、需求、图纸分组，每项写涉及位号和能解开的检查条数。把前几项一次发给设计方补齐再进入逐项审查，不要审完才发现几十条检查缺同一份资料；“审查者自行追踪”一组是自己的工作，不向设计方索取：普通阻容（R、C 位号）的专属手册归在这一组的一项里，按
[通用件定界](commodity-floors.md) 的保守档算，不逐颗向设计方要。资料补齐后重审计（g）。

做完的标志：`资料请求.md` 已出并一次发给设计方（设计方组每项写了位号与能解开的检查条数）；补齐后 g 跑过，
`datasheet-audit.json` 里能取得的材料都 AVAILABLE；取不到的留给 ③ 作证据缺口，不在这里卡住。

## 2.3 合并扫描

命令是 2.1 清单的 h。`review-plan.json` 是唯一最终计划。保证值核对（E）检查项由网表定出对象，审查者按两端规格书的保证 Min/Max 判定；
资料未 AVAILABLE 时判资料不足，例外见 [保证值核对的例外](evidence-proportionality.md#保证值核对的例外)。

做完的标志：`review-plan.json` 由 h 写出；扫描提示为空（或每条处置后重跑过）；`diagnostics` 里只剩信息类（`LINT_INFO`、`PASSIVE_PACKAGE_UNKNOWN`、
`REQUIREMENT_OWNER_OUTSIDE_CANDIDATES` 这类提示）；计划 `summary` 的检查项数与功能数看过一遍，与板子规模相称。
