# ③ 判断

> 读者：审查员。

做本步前读 SKILL.md 和本文件；五个步骤的总览见 [SKILL.md 的执行流程](../SKILL.md#执行流程)。

判断的单位是**功能**，不是检查项。分三个任务：先逐个功能写判定（3.1），再由工具派生绑定的检查项（3.2），最后手填框架外的检查项（3.3）。

## 3.1 功能判定

按计划 `functions[]` 的框架逐个填写 `review-results.json` 的 `functions[]`；字段、条件的五种、余量依据和开放项
都按 [功能判定](results-format.md#功能判定functions)。框架自带问题、检查项、每条规则的盲区和五步核对单，审查员读手册、自己算，不翻规则书。要点：

- 条件（`conditions`）先能定位，再写种类；判断（`judgements`）引强制条款或网表事实，数字限值只在余量里比较。
  手册和 BOM 来源的条款写 `refs`——这条说的是板上哪几只器件（至少一个；带 `setting` 的含 `setting.ref`），需求、标准、工程假定可不写；
  门禁核位号在网表或 BOM 里、手册是不是该位号在资料审计里的那份资料；位号不在本功能对象里只提示（CONDITION_REF_OUTSIDE_FUNCTION），共享器件的条款看一眼即可。
  门禁按 `refs` 汇总器件参数表（`--detail full` 的报告才显示）。
- `objects` 就是电路（候选经决定）的成员；要扩大或漏了电路，改 `intent.circuit_decisions` 后重生成。框架的 `members` 既有电路检查项，也有这块电路拥有的器件检查项（身份、引脚、应力、工况、它器件上的扫描发现）：
  都在这个功能里判，同一方面的几颗器件一条 judgement 可以合答，差别用 `check_ids` 分开。一个电路的缺口和失败写在它自己的功能里；
  跨电路的缺口只写一次，影响条目用 `check_ids` 点名另一电路的检查项。自建功能只装不属于任何框架的检查项；文档检查（DOC-*）在检查项上判，不包成功能。
- 先从器件关键参数判断：每颗器件在本板用到的关键参数就是[工作点定界表](bounding-table.md)里它那一类的格，逐个参数比本板工作点和保证值，
  比完再下功能结论；功能结论只有三档——合格、不合格（给改法）、合格但有风险（检查项状态仍是 PASS/FAIL/INSUFFICIENT/NA，INSUFFICIENT 只剩缺厂家资料；只靠估算过关的角点标风险）。
- 余量按 `margin.basis.kind` 下结论（GUARANTEED_BOUND 满足才 PASS、REACHABLE_CASE 不满足才 FAIL、EXACT_ENVELOPE 两头都判、ESTIMATE 不判），器件参数按[工作点定界表](bounding-table.md)定界，门禁重算。
  典型值估算能否判 PASS 由那一格的[判决边界](bounding-table.md#判决边界)按后果类定，字段写法见[余量的依据](results-format.md#功能判定functions)；
  一条余量判合格、合格但有风险（含估算过关与额定内超降额的应力风险）还是不合格按[余量判定规则](margin-verdicts.md)。风险不限制定稿，报告单列“风险清单”。
- 缺口先按[判“证据不足”之前先定界](evidence-proportionality.md#判证据不足之前先定界)走完公开资料界限，真缺厂家数据的记 VENDOR_DATUM；
  设计没定不开项：原理图或 BOM 该写明而没写的值记失败项，改法写反推出的值；
  归另一份设计文件（磁件、固件、PCB）的值，以及另一环节欠的交付物（定制件图纸、固件能力），写 DESIGN_CONSTRAINT 条件（没有单一数值的写条款），按约束判 PASS 并移交给负责方；
  检查项只在本方面本状态有证明通过的余量或判断时 PASS，没人判过的方面不默认通过。

按计划 `functions[]` 的顺序推进：系统功能 → 功能电路 → 接口 → 全板；每个功能逐对象、逐状态给结果，全板项逐条给适用性和结果。
功能电路按实际 package/circuit/state/ref 归组并列必需检查项 ID，跨类型依赖说明真实路径；不能只按规则编号归组。
按 [功能电路依赖与状态核对](plan-format.md#功能电路依赖与状态核对) 核全部实际检查项、外围选值窗口与掉电路径。
遇到共享控制网、多供源/状态、功能父项或共享整改任务，先读 [执行一致性](execution-consistency.md)。
先按 [对象上下文录入](results-format.md#对象上下文录入) 保存实际物理对象、状态、路径及出处、
已核范围和未知边界，再形成结论；噪声 NA 先完成 [噪声路径资格](evidence-proportionality.md#噪声路径资格)。

- **电源与状态**：每轨追到真实电源脚或明确外部源，再到全部负载（PWR-T01）；0Ω/磁珠/二极管不是独立电源。
  按装配、开关/体二极管方向、EN/PG、时序和地参考分析，建立断电、启动/复位、运行、待机、掉电、热插拔和故障状态表。
  跨轨上拉先列候选再查 Ioff/注入/掉电容忍（SIG-C08）；检测点须匹配被测量（ANA-T01），查“采样→判断→使能→供电”循环依赖；
  地网逐个列出并核连接方式（PWR-T06）；复位期间和固件接管前的 IO 默认态不得误动作（RST-T04）。
- **连接追踪**：逐跳记录 起点物理脚→网络→已贴器件→网络→终点物理脚，同时核返回路径；端口、时钟、复位、启动、
  编程救援、反馈/检测、使能/故障上报都要追。TX/RX、P/N、Host/Device 按两端官方语义复述并查对端针序（SIG-T04）。
- **工程计算**：按 [WCA 公式](wca-formulas.md) 先确认模型，再代入实际串并联、输入/温度/负载和公差角点；
  原厂已覆盖工况的 Min/Max 直接使用。区分设定目标与物理可达输出（FB 公式不代表升压能力、RC 不等于复位脉宽、
  有 TVS 不等于防护通过）。阈值型保护（门限脚、门限链与基准齐纳、跨开关节点的能量钳位）两侧都算（PRO-C02）；跨网与地的防护钳位（电源轨 TVS、芯片脚对地齐纳、连接器信号线 ESD）逐器件核工作电压（只比持续最高电压）、能到达本节点的瞬态下钳位电压对同网最低耐受和脉冲能量（PRO-E02）。一次只取一个瞬态或故障事件，叠加在持续最坏工况上；瞬态比瞬态额定，持续比持续额定（[单一瞬态](wca-formulas.md#假设上界与实际故障的证据门槛)），连接器只核挂线与泄放（PRO-D03）；传感器开短路按控制器实际偏置档与环境全范围判别（ANA-C04）。连续可调输出在全范围扫描应力。判“缺保护”前计入 IC 自带保护（寄存器设定的门限归固件任务）；改频率/阻值/保护管时连带复算。
  某条准则要复算时，用知识框架的 `索引/准则支撑表.md` 从准则编号找到 `知识/计算方法/<知识域>/` 的条目，按它的取值步骤和输入取端复算；WCA 已有的公式不重抄（[关系](wca-formulas.md#公式与验收依据)）。
- **自己算关键数值**：决定结论的数值由 SR 按原理图、需求和原厂资料自己算，`circuit_bounds.*`（分压、RC 跨阈、线性稳压热、逻辑电平裕量、电容纹波折算、电阻功耗、串阻电流）与 `model_bounds.*` 自行枚举公差角点。不复算设计文档所称的数值，也不拿它当判据。
- **核对模型和原表**：CrM Boost 输出电容用 `model_bounds.crm_boost_capacitor_ripple` 独立核二极管导通相位，并按控制器实际母线模式分别算；不沿用设计脚本的公式证明自身。厂家参数引用用 `audit_parameter_claims.py` 对比独立摘录的原表，给料号/材料、文档哈希、页码、温度/激励条件、典型或保证值口径；工程设计限值另核裕量，不能当厂家额定值引用。工具不代替原表摘录核实，详见 [自动扫描与计算工具](scans-and-tools.md#厂家参数引用核对)。
- **动态数值证据**：需要有界 R/C 工作点或瞬态时按 [仿真证据](simulation-evidence.md)；样本在窗口内不直接等于规则 PASS。
- **条款核对**：每颗 IC/模组核推荐工作条件（DEV-C05）和逐脚处置（DEV-D05）；连接器核对端定义（DEV-D03）和对外防护（PRO-D03）；
  主控引脚复用对照平台约束与固件配置（SIG-D13）。由参考设计派生的电路列出全部偏离并按本设计条件复核。
- **知识框架对照**：查阅时先用 `python3 scripts/knowledge_checklist.py entries review-plan.json`（或 `entries <电路类型或器件类别名称 ...>`）按本板的电路类型、器件类别列出框架里头部声明了它们的条目（按组件分组），再按需读。
  跨块接口两端是否交代全、总线电气条件对照 `接口约定/`；器件失效方式、单故障与故障模式分析的步骤对照 `失效与故障分析/`；
  `典型电路/` 各实现方案的“已知坑”只作找问题的线索，发现仍落到具体准则和证据上，不因没用某种典型电路判缺陷。
- **知识必答清单**：计划里的每块电路对上知识框架典型电路的一个实现方案，该方案的必算项和已知坑逐项要有审查结论，记在 `review-results.json` 旁边的 `knowledge-checklist.json`：

      python3 scripts/knowledge_checklist.py find <关键词 ...>                                 # 检索典型电路与实现方案
      python3 scripts/knowledge_checklist.py build review-plan.json knowledge-checklist.json   # 按计划的电路列项，已写的保留
      python3 scripts/knowledge_checklist.py check review-plan.json knowledge-checklist.json
      python3 scripts/knowledge_checklist.py entries review-plan.json                          # 按本板电路类型、器件类别列出声明了它们的条目

  `circuits` 每块电路写 `typical`（`<典型电路文件名>#<实现方案名>`；知识框架里没有对应的写 `none`，并在 `reason` 写查过哪些、为什么都不对应），写完重跑 build 列出各项。
  `items` 每项只填处置：`checked` 在 `where` 列出核过它的检查项或功能编号（计划里的编号），`not_applicable` 在 `reason` 写本电路为什么没有这种情况。
  `entries` 记查阅过的其他条目：`entry` 写相对 `知识/` 的路径，`disposition` 写 `read`，或 `not_applicable` 并在 `reason` 写理由。本板的电路类型、器件类别记在计划 `knowledge_scope` 段；build、check 和 `validate_review.py`（输出的 `knowledge_hints`）对框架里声明了它们、却既不是所写典型电路也不在 `entries` 里的条目给“提示”，不判失败：查阅后补记，或写明不适用。
  清单只规定这些项都要看过，不是判据：结论仍写在功能判定和检查项里。条目文字变了，对应项作废，重跑 build 后补写。

做完的标志：`review-results.json` 的 `functions[]` 与计划的 `functions[]` 一一对应，每个功能有 verdict 与 evidence；
开放项、失败项每条有 `key`、`kind`、`decides`，每条边只挡这类开放项能挡的检查项（[每类开放项能挡哪些检查项](results-format.md#功能判定functions)）；要算数的功能有计算记录，不用算的写 `no_calculation_reason`；比较过的每个量在 `margin` 或条款 `limit` 里（`calculation.result` 只是结论句，单位按 `scripts/units.py` 的拼法；4.1 的 RESULT_NARRATIVE / UNIT_UNKNOWN / QUANTITY_IMPLAUSIBLE 零提示）；手册和 BOM 来源的条款都有 `refs`（门禁无 “refs names the part” 错误）；
框架里每个方面×状态都有判断或开放项（派生时 `derive_rows.py` 不报“未判”）。

## 3.2 检查项派生

绑定了功能的检查项由功能派生（结论、open_ref/fail_ref、rationale 都从功能来），不手填；绑定了树上检查的需求检查项（`bound_checks`）取绑定检查项中最差的结论，也不手填。
派生的检查项**不写进台账**：`review-results.json` 只装功能判定和手填的检查项，门禁、报告、打包、对比读取时从计划和功能派生（`results_model.materialize`），
所以台账里不可能有一份和功能判定不一致的副本。审查员自己把检查项绑到功能时只写 `{id, function_id, aspect}`；要给派生检查项补注记（`manual_verification`、`notes`、`handoff_evidence`、`applicability_evidence`、`settings`、`bom_constraint`、`requirement_clauses`、`proposal_override`）时只写 `{id, 注记}`，结论仍由功能派生。
功能判定写完后跑一次检查，看功能派生出什么、哪些方面没判、哪条手填检查项和功能不一致（它不写文件）：

    python3 scripts/derive_rows.py review-plan.json review-results.json

做完的标志：命令无 ERROR；打印的“手填保留”检查项都是框架外的检查项，没有一条“手填与功能不一致”；台账里没有 `derived: true` 的检查项。

## 3.3 手填剩余检查项与图面目检（V）

框架外的检查项手填：图面目检、全板拥有的器件检查项、需求条款等事实性检查；这些检查项要判资料不足，也必须先建一个功能判定。
审查员自己绑到功能的检查项必须是该功能对象上的检查项；需求检查项（REQ-D01.<需求 ID>）不整项记阶段 NA，
测试要求只在它的条款上记 NA 并链接单独的阶段 NA 检查项；成本、体积、取舍优先级这类优化目标或范围说明的需求检查项记 NOT_APPLICABLE 并引需求原文，不写 PASS。
所有页面留目检记录（DOC-V01），新页和变更区细读；极性、pin1/视图、选项表、同名端、NC 标记以图形为证据。
注释、遗留命名和图框版本按 DOC-V02，装配选项互斥与完整性按 DOC-T01。

做完的标志：计划里没有 `function_id` 的 APPLICABLE 检查项每条有结论与证据；每页有 DOC-V01 目检记录；需求检查项的条款逐条有判断或链接的阶段 NA 检查项；`knowledge_checklist.py check` 通过（每块电路对上了实现方案或写明没有，必算项和已知坑逐项有处置）。
