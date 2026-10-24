# 方案：需求行的 owners 由计划推荐、有候选时必填（SR 审查框架分析之一）

状态：用户 2026-10-24 已定："三条都做；一个候选时也要手写 owners（A）；计划行加字段不升版本。开工。"

实施记录：三条于 2026-10-24 落地（提交 3a78547）。第一版实现把系统功能和接口一律算作可承接，结果 SYS-POWER 经 PWR-C01 成了"电流与功率限制"的可承接电路、与本表不符；用户选修法 A（"系统功能和接口也按方面白名单过滤，表按提案里那张候选表写"），`catalog.ASPECT_OWNER_TYPES` 每格改为电路类型、系统功能、接口种类三栏。中文文案按用户建议改为"承接电路 / 可承接的电路"。

按 SKILL.md"改架构先问人"：这条改变需求行**由谁判**（绑定派生还是审查员手判），属于"改变谁做判断"，所以先出方案。
格式版本不动（见"待你决定"第 3 条）。

## 现状

`intent.requirements[].owners` 是可选字段，写落实这条需求的电路、接口或系统功能的 id。它决定需求行（REQ-D01.<需求>.<方面>）的判法：

| owners | 方面有树上规则承担（`ASPECT_RULES`） | 需求行怎么判 |
|---|---|---|
| 写了 | 是 | 绑到 owners 拥有的这些规则的行，结论由 `derive_rows.py` 取最差者派生，不另判、不拆条款 |
| 没写 | 是，且是全板方面（温度等级、降额、寿命、隔离、测试点） | 绑到全板**所有**这些规则的行，同样派生 |
| 没写 | 是，不是全板方面 | **不绑任何行**，需求行自己手判、拆条款 |
| 任意 | 否 | 需求行自己手判、拆条款 |

现有校验只查"合法"：owners 是非空字符串数组，点名的 id 必须拥有计划里的行，`bound_checks` 由校验重算。
没有任何规则说**什么时候该写** owners，也没有工具告诉审查员**可以写谁**。

后果：

- 同一块板，审查员 A 给"输出 12 V ± 5 %"写了 `owners: [C2]`，需求行由 C2 的 PWR-E01、PWR-C15 行派生；审查员 B 没写，
  需求行自己拆条款手判。两份记录的 REQ-D01 行同名不同源，结论和措辞都可能不同，`compare_reviews` 配得上但对不上，
  也报不出原因（R5 验收里 163 条"经需求条款挡行的边"有一部分出在这里：需求行手判时把需求条款当了判据来源）。
- 不写 owners 的那条路违背了需求分解的目的之一："需求的结论和电路的结论是同一个"——它恰恰生成了第二套判断。
- 审查员要自己翻计划找电路 id，才知道能写什么。

## 建议

三件事，都是机器能数的：

### 1. 计划算出每个需求方面的候选 owners

规则总表加一张 `ASPECT_OWNER_TYPES`：每个有树上规则承担的方面，列出通常落实它的电路类型。候选 = 拥有该方面规则的
**适用**行的所属（电路、接口、系统功能）里，电路类型在表内的电路，加上拥有这些行的系统功能和接口（它们不按类型过滤）。

| 方面 | 承担规则（已有） | 电路类型（新） | 系统功能 / 接口（由行推出） |
|---|---|---|---|
| INPUT_STAGE_RATING、INPUT_THRESHOLDS、CONVERTER_INPUT_RANGE | DEV-C01、PWR-C02、PWR-C06、PWR-C13、PRO-C02、DEV-C05 | POWER_PROTECTION、POWER_CONVERTER | SYS-POWER |
| OUTPUT_LEVELS、OUTPUT_LIMITS、OUTPUT_ACCURACY | PWR-E01、PWR-C15、PWR-C01、PWR-C03、PWR-C06、PWR-C14、DEV-C03、ANA-C01 | POWER_CONVERTER | SUPPLY 接口 |
| PROTOCOL_ROLE、PORT_DETECTION | SIG-T04、SIG-D04、SIG-C05 | USB、CAN、RS485、UART、SPI、I2C、ETHERNET、HSSERIAL、AV、STORAGE、DDR | CIRCUIT_PAIR、LINK 接口 |
| EXTERNAL_PINOUT | DEV-D03 | — | EXTERNAL 接口 |
| FAULT_DETECTION、FAULT_THRESHOLD、FAULT_RESPONSE | ANA-T01、ANA-C04、PWR-T04、PWR-C06、PRO-C02、PRO-C01、PRO-D03、RST-T03 | POWER_PROTECTION、POWER_CONVERTER、ANALOG | SYS-MONITOR、SYS-SEQUENCE |
| MEASUREMENT_CHAIN、MEASUREMENT_ACCURACY | ANA-T01、ANA-C01 | ANALOG | SYS-MONITOR |
| POWER_SEQUENCE、STARTUP_TIMING | RST-T03、RST-C02 | STARTUP | SYS-SEQUENCE |
| CLOCK_ACCURACY | CLK-C01 | CLOCK | — |
| 全板方面（温度、寿命、隔离、测试点） | 已绑全板行 | 不推荐、不必填（现状不变） | — |

计划把候选写在需求行上：`owner_candidates: [{id, kind, type}]`（不进检查标识）。

### 2. 有候选而没写 owners：计划拒绝，并打印候选

和"intent 写了 `circuit_decisions` 却没带 `--candidates`"同级：出计划时报错

    requirement.R3.owners 缺：方面 OUTPUT_LEVELS/OUTPUT_LIMITS 由 C2（POWER_CONVERTER +12V）、C5（POWER_CONVERTER +5V）拥有的行承担；
    写 owners 后需求行由这些行派生。不属于任何候选的，写 owners: [] 并给 no_owner_reason

- 候选为空（板上没有对应类型的电路拥有这些行）：owners 不必填，需求行自己手判（现状），行上记 `self_judged: NO_OWNER_CANDIDATE`。
- 审查员认为需求不落在任何候选上：写 `owners: []` 加 `no_owner_reason`（可定位引用），需求行手判，行上记 `self_judged: DECLARED`。
  `[]` 与"没写"分开：没写是漏，`[]` 是决定。
- 写了候选以外的 id：允许（审查员可能比类型表更清楚），现有"必须拥有行"的校验不变；计划打一条诊断 `REQUIREMENT_OWNER_OUTSIDE_CANDIDATES` 供复核。
- 只有一个候选时：见"待你决定"第 2 条。

### 3. 对比工具按需求报 owners 差异

`compare_reviews.py` 现在按 `check_key` 配对需求行，owners 不在标识里，所以两份记录一份派生一份手判也算"配对且一致/不一致"。
加一节：逐需求列两份记录的 owners 集合和判法（派生 / 手判），不同的单列。这样 owners 差异从配对率里分出来，能数。

## 动哪些文件

| 步骤 | 文件 | 改什么 |
|---|---|---|
| ② 出计划 | `scripts/catalog.py` | `ASPECT_OWNER_TYPES` 表；文档渲染的方面表加"候选所属"列 |
| ② 出计划 | `scripts/requirement_bindings.py` | `candidates(checks, row, owners_table)`；`attach()` 写 `owner_candidates`、`self_judged` |
| ② 出计划 | `scripts/plan_board.py` | 需求行上调用候选；有候选没 owners → 加进计划错误；候选外 owners → 诊断 |
| ② 出计划 | `scripts/plan_review.py` | `validate_intent`：`owners: []` 须带 `no_owner_reason`（可定位）；`diagnostic_lines` 打印候选 |
| ④ 校验 | `scripts/requirement_bindings.py errors()` | 重算候选，与计划写的一致；`self_judged` 与 owners 状态一致 |
| 维护 | `scripts/compare_reviews.py` | 逐需求的 owners / 判法差异一节 |
| 文档 | `references/plan-and-results.md`、`references/check-catalog.md`（重生成）、SKILL.md 1.1 一句 | owners 规则：有候选必填，`[]` 要理由 |
| 测试 | `scripts/tests/test_requirement_bindings.py` | 候选推导、拒绝、`[]` 路径、候选外诊断、校验重算；对比工具一例 |
| 变异 | `evals/mutation/mutations.json`、README | 没候选也拒绝 / 有候选放行 / `[]` 不要理由 / 候选不按类型过滤 / 对比不报差异 |

不动：intent、计划、结果的格式版本（见下）；`ASPECT_RULES`；绑定派生逻辑；全板方面的处理。

## 不改的话有什么替代

- **只做第 1 条（推荐，不必填）**：审查员看到候选，差异会减少，但"没写"仍然合法，两条判法并存，一致性问题留着。
- **自动绑全部候选，不要 owners**：多路输出的板子会把"+12 V 精度"绑到 +5 V 变换器的行上，错绑出假 FAIL。否决。
- **维持现状**：owners 继续可选。需求行由谁判取决于审查员有没有想到写这个字段。

## 验证

- 单元：候选推导按类型过滤、系统功能和接口不过滤；有候选没 owners 被拒；`owners: []` 无理由被拒；候选外 id 出诊断不拒；校验重算一致。
- 回放：KiCad 回放 195 字段、典型电路 42 块板——这两套夹具的 intent 多数没有需求或没写 owners，预期部分用例因"有候选没 owners"被拒：
  逐个补 owners 或 `[]` + 理由，这本身就是对候选表的一次校准，结果写进本提案的实施记录。
- 变异门：改动文件上全部杀死。

## 待你决定

1. **做不做**，以及是否三条都做（第 3 条对比工具可以后做）。
2. **只有一个候选时**：A 仍要求审查员手写 owners；B 计划自动填上并在行上记 `owners_source: PLANNED`，审查员可改。
   我倾向 A：owners 是"这条需求落在哪"的判断，一个候选时自动填会把"没想过"和"确认过"混在一起；代价是多写一行。
3. **计划行加 `owner_candidates`、`self_judged` 两个字段，不升计划格式版本**（旧计划照读，缺字段按"无候选"处理）；
   还是按惯例升到 8、旧计划不读。我倾向不升：字段是计划自己算出来的，不是审查员写的，旧记录不会因此读错。
