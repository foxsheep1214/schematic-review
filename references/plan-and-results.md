# 计划与结果台账

审查数据分三份：`intent.json`（审查意图与输入声明，按需求和设计结果写，不抄设计方的意图文件）、`review-plan.json`（逐项检查计划）、
`review-results.json`（逐项结果）。计划只决定每项的规则、适用性和准备度，不提前制造 PASS/FAIL；
结果另存，由 `validate_review.py` 对账。常规命令见 [SKILL.md](../SKILL.md)。

台账有三层，只有第一层是审查员写的判断：
- **功能判定**（`functions[]`）是判断单位。一个功能回答一块电路的一个问题（“偏置路径能否让 VCC 保持在 9.5 V 以上”），
  带手册条款、计算、余量、结论和开放项/失败项。计划按 intent 电路生成框架；框架外的功能审查员自己加。
- **逐项检查**是审计明细。一行对应一条规则、一个实际对象、一个状态，编号为“规则.对象[.状态]”，跨轮次保持不变，
  供改版复审、训练裁决和复核引用。绑定了功能的行由 `derive_rows.py` 从功能派生，不手填；
  事实性检查（目检、脚表、身份、需求条款）手填。一个器件挂很多条规则是正常的，不合并成一行。
- **待办**是交付单位，由开放项和失败项派生（编号 `W-<key>`，见 [结论与准出](verdicts-and-release.md#待办由开放项派生)），
  不手写。设计者、ASG 和报告都按待办处理；PASS 和 NA 不进待办。

“资料不足”只有一个入口：先有功能判定的开放项，才有 INSUFFICIENT 的行。

## 一、intent.json（schema_version 4）

合成示例（数值仅说明结构）：

```json
{
  "schema_version": 4,
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
  "requirement_source": {"path": "/绝对路径/需求.md", "sha256": "requirements_extract.py 输出的 sha256"},
  "requirements": [{
    "id": "REQ-USB", "status": "CONFIRMED", "categories": ["PROTOCOL"],
    "interpretation": "PHY 与连接器双向链路、供电及外部带电状态满足接口条件",
    "parameters": [{"name": "output_voltage", "min": 4.75, "max": 5.25, "unit": "V"}]
  }],
  "circuit_decisions": [
    {"candidate": "USB-J2", "decision": "accept", "id": "USB-PORT",
     "states_add": ["external-power-only"], "citation": "Requirements v1.2 section 4.1"},
    {"candidate": "DEBUG-BOARD", "decision": "reject", "reason": "OUTSIDE_SCOPE",
     "citation": "Requirements v1.2 section 2.3：调试口不在本轮范围"},
    {"decision": "add", "id": "V5-SENSE", "type": "ANALOG", "members": ["R99"], "via": {"R99": "V5"},
     "citation": "schematic page 3 V5 检测分压"}
  ],
  "expect": {"USB_PHY": 1},
  "features": {
    "DDR": {"applicability": "NOT_APPLICABLE", "citation": "Requirements v1.2 section 2.3"}
  },
  "materials": {
    "schematic_pdf": {"path": "/绝对路径/SCH-100 rev.B.pdf"},
    "datasheets": {"path": "/绝对路径/datasheets/"}
  },
  "rail_exclusions": {"VBAT_SNS": "电池电压检测分压点，不对任何器件供电"},
  "rule_gaps": [{"id": "Q7-REVERSE", "rule": "PWR-T05", "object": {"ref": "Q7"},
                 "criterion": "Q7 体二极管在反接时承受的反向电流与功耗在额定以内",
                 "missing": "反接保护 MOSFET 的反向导通应力没有生成规则",
                 "basis": "网表：Q7 串在输入正端，体二极管方向构成反接保护"}],
  "power_rails": {
    "VCC_3V3": {
      "voltage_v": {"min": 3.2, "max": 3.4}, "load_a": {"min": 0, "max": 0.5}, "available_a_min": 1.0,
      "refs": ["U1", "L1", "F1"], "state": "BOM B; stated Vin/load/temperature corners",
      "citation": "Requirements Rev.B load table 2 and component guaranteed ratings"
    }
  }
}
```

- `schema_version` 必写（4）；顶层只认本节列出的字段和各检查器的段（`plan_review.INTENT_FIELDS`），拼错或多写的字段被拒收并提示最接近的字段名。
- `circuit_decisions` 的写法见下文“电路不手画”；`circuits` 和 `circuit_candidates_sha256` 由 `circuit_decisions.py --write` 写入，不手写。
- `review_mode`：`first` 或 `revision`。`review_phase` 取值见 [结论与准出](verdicts-and-release.md#5-审查阶段)。
- `features` 的键与 `circuits[].type` 取 [规则总表](check-catalog.md)“功能电路”中的包名，否则拒绝；
  `applicability` 为 APPLICABLE / NOT_APPLICABLE / UNDETERMINED，前两者必须带 `citation`。
- 名称命中只生成 UNDETERMINED 候选，不展开成员；由电路声明、features 出处或已确认拓扑确认后再展开。
  带出处的不适用声明可排除误命中；与已确认拓扑冲突则保留证据不足。没搜到关键字不能推出 NOT_APPLICABLE。
  电路来自候选（有 `circuit_decisions`）时，电路类别由候选与决定推出：`features` 不写 `intent.circuits` 已有的类别，
  也不写 APPLICABLE（候选没检出却要审，就在 `circuit_decisions` 里补电路），只给规则总表有、候选没检出的类别写不适用依据。
- `materials.<name>` 只写 `path`（文件或目录），文件存在即可用，不写 `available`；路径不存在被拒收。
  需求由 `requirement_source` 推出（不必再写 `materials.requirements`），规格书由逐物料审计（`--datasheet-audit`）推出；
  没有的资料不写，依赖它的行等资料。
- `rail_exclusions`：网表上像电源（有 IC 从它取电，或 ≥1 µF 电容到地）而名字不像轨的网，每条都要在 `power_rails`
  声明成轨或在这里写它不是轨的依据，否则拒收；只能排除这类网，且不能同时声明。计划的 `rail_candidates` 列出每条这类网
  及其确认方式（`name` 名字像轨、`declared`、`excluded`）。名字像轨的网照旧按名字识别。
- `rule_gaps`：审查员认为该查、计划里没有的检查。每条写 `id`、`rule`（按总表哪条规则判，不能是 REQ-D01：需求行由需求文档生成）、
  `object`（非空；位号须在网表里）、`criterion`、`missing`（工具缺什么规则或推导）和 `basis`（依据）。计划工具写成一行
  `origin: REVIEWER_ADDED` 的检查（`rule_gap` 记缺口编号、`missing`、`basis`），照常判；计划 `summary.reviewer_added` 计数，
  两份记录比较时这些行单独列出、不计入配对率；门禁结果 `rule_gaps` 列出每条缺口与结论，报告在“对 SR 的反馈”里列出，
  每条记进改进台账，变成工具生成的规则。
- `assemblies`（1–32 个，各带 `id` 与 `citation`）是全部检查器共用的装配状态；`devices` 是按位号的官方脚表。
  声明二者或任一检查器段时须带顶层 `input_sha256`，过期即拒绝。
- `devices.<位号>.configurable`（intent 格式 4 起，一致性方案第 3 条）：可编程器件的配置组，每组
  `{group, citation, allowed, affects[, title, required, set_points]}`——`group` 是角色的固定组（`catalog.CONFIG_GROUPS`，
  pd_controller 为 CAPABILITY 能力发布、CABLE_VCONN 线缆与 VCONN、PROTECTION 保护门限与动作、SENSING 检测通道、GPIO 角色/默认态/
  对外控制时序、COMPENSATION 环路补偿、SEQUENCE 放电与上下电时序）或自定组（须写 `title`），`citation` 是手册寄存器或配置章节，
  `allowed` 是手册允许的范围，`affects` 是这组设置决定的方面，`required` 是需求要求的值，`set_points` 是这组选出的输出档位。
  计划给已核验角色的每个固定组和每个声明组一行 CFG-D01（`CFG-D01.<组>.<位号>`，不随工况重复；没声明的组 WAITING_EVIDENCE），
  mcu 这类没有固定组的可编程角色没声明任何组时给一行 `CFG-D01.DECLARE.<位号>` 要求声明或说明为什么没有；写了 `set_points`
  的组另加一行 `PWR-C02.SET-POINT-<组>.<位号>` 逐档核输出精度。某组对该器件不存在时，该行记 NA 并引手册条款。
- `mission_profile`（intent 格式 4，一致性方案第 6 条）：所有寿命行共用的一份任务剖面
  `{requirement, phases[{name, share, load, ambient_c, citation[, requirement]}], events[{event, count, citation[, refs, requirement]}]}`。
  `requirement` 是给出设计寿命（`lifetime` 参数）的需求；`share` 是这一段占设计寿命时间的比例，各段合计为 1；`load` 是负载占额定的
  比例（0–1）；`ambient_c` 是环境温度；`event` 取 `catalog.LIFE_EVENTS`（开关机、浪涌、故障动作、动作、插拔、充放电循环、擦写），
  `count` 是设计寿命内的总次数，`refs` 只给点名的器件；每个 `citation` 须是所引需求原文里的一段。规则见
  [寿命与耗损件](commodity-floors.md#寿命与耗损件)。
- 需求不手抄：`python3 scripts/requirements_extract.py 需求.md --json record/requirements.json` 逐字抄录需求表
  （首列为 ID/编号的表格行，或 `- <编号>：<文字>` 列表项），每条各列分开、带所在章节与 `文件:行号`，并给文件 sha256。
  `requirement_source` 写文件路径和这个 sha256，`requirements[]` 每项只写 `id`、`categories`、`interpretation`
  和 `status`，不写 `text`、`citation`、`criterion`。`categories` 从 [规则总表](check-catalog.md#需求类别与审查方面)
  的需求类别表选一个或几个（表有“怎么选”一列；拿不准就多选，少选是漏查）。分解的单位是需求里的量：带参数的方面由
  `parameters` 里有没有这个参数决定，有就问，不管选了哪些类别；不带参数的方面由类别决定；一个参数都没写的需求才按类别问全部方面，
  计划同时列出原文里没读进参数的带单位数字（`REQUIREMENT_NUMBERS_UNREAD`，扫描时打印）。计划按（需求，方面）各生成一行 REQ-D01，判据取方面模板。
  `interpretation` 写这条需求要在原理图上落实什么（不抄原文），挂在每一行上，不进检查标识；
  不适用的方面在结果里判 NA 并给依据，不从类别里删方面。需求文档里每个编号都要有一项（优化目标、明确排除也一样），
  文档里没有的编号被拒收；文档改了 sha256 就变，重新抄录并复看改过的需求。源不是表格时先整理成同格式的需求表并存档。
  计划的 REQ-D01 行带 `source_text`（出处、章节、各列原文），每个方面行结果的 `requirement_clauses` 按顺序拼接都须等于这段原文。
- `requirements[].parameters`：从原文读出的数字，每项 `{name, min, max, unit, condition}`；`name` 与 `unit` 取
  [规则总表](check-catalog.md#需求类别与审查方面)的需求参数表，至少给 `min`、`max` 之一，每个数字须在该条原文里出现
  （`±5%` 同时给出 −5 和 5；数字后紧跟的短横是范围，不是负号），`condition` 须是原文里的一段（如“3 A 线缆时”）。
  参数按规范单位换算后挂在该需求的每一行上（`parameters`，不进检查标识）。计划使用这些数字：
  `power_rails.<网>.voltage_v` 可以只写 `{"requirement": "<需求编号>"}`（该需求同时有输入和输出电压时加 `parameter`），
  窗口取那条需求电压参数的上下限；输入电压、频率写进 SYS-POWER 框架的 `requirement_windows` 和问题；
  工作环境温度（DEV-C01/C02/C05）和设计寿命（DEV-C02/C06）作为 `conditions` 挂在器件应力行上，计划顶层 `conditions` 列出各条来源。
- `requirements[].owners`，**承接电路**：落实这条需求的功能电路、系统功能或接口的 id。规则总表给每个审查方面列出承担它的检查和可承接的电路类型；
  计划替每个需求行找出**可承接的电路**，写在 `owner_candidates`（拥有承担该方面的行的所属里，类型在表内的电路，加上系统功能和接口）。
  **有可承接的电路的需求必须写 owners**（OPEN、DEFERRED 的除外），没写的计划拒绝生成并打印它们；审查员认定没有承接电路时写 `owners: []`
  加能定位的 `no_owner_reason`，需求行自判（行记 `self_judged: DECLARED`，“审查员认定没有承接电路”）；没有可承接的电路的不要求写，需求行自判
  （`self_judged: NO_OWNER_CANDIDATE`，“没有可承接的电路”）。写了可承接之外的 id 允许，计划打诊断 `REQUIREMENT_OWNER_OUTSIDE_CANDIDATES` 供复核。
  只有一个可承接的电路也要手写，不自动填。
  计划把需求行绑定到这些规则中 `owners` 拥有的行，没写 `owners` 时全板方面（器件温度等级、按温度降额、寿命）绑定全板这些规则的行，
  写在需求行的 `bound_checks`（不进检查标识，校验时重算，点名的 id 必须拥有计划里的行）。有绑定行判过（不算 NA）的需求行不再另判：
  `derive_rows.py` 取绑定行中最差的结论写出（`derived_from`；FAIL 带上该发现项并把需求行加进它的 `check_ids`，INSUFFICIENT 带上 `open_ref`），
  手填的需求行只对账不覆盖；校验要求结论等于绑定行中最差者，这种行不要求条款。没有绑定行、或绑定行全是 NA 的方面由需求行自己判，照常拆条款。
- `requirements[].status`：已确认（CONFIRMED）、提案（PROPOSED）、未定（OPEN）、暂缓（DEFERRED）。
  保留需求原文和源状态，先按 [需求原文到审查要求](requirement-clarifications.md#需求原文到审查要求)
  确定本次判据的实际确认状态，不省略真实未定项。OPEN 的 REQ-D01 必须 INSUFFICIENT + REQUIREMENT_OPEN；
  DEFERRED 必须 INSUFFICIENT + USER_DEFERRED；PROPOSED 可判定，但结论以提案为前提。
- `power_rails` 支撑 PWR-C01 与 DEV-C05：给电压/最大负载、源端最弱保证可供电流和条件；READY 不等于 PASS。
  片内稳压输出（如 MCU 的 1.1 V 内核轨）、仅板内使用的中间轨同样要声明电压：阻容预判按同簇器件的全部供电轨定界，缺一条就整簇不出预判。计划命令末尾会列出“未声明电压的轨”及受阻行数，能从稳压器手册或需求定出时补齐后重跑。
  隔离或多地设计给各轨与各地写 `domain`（如 PRI/SEC），地写 `voltage_v: {min: 0, max: 0}`；栅极/检测节点可按计算声明窗口。
  窗口由审查者独立定界：取需求输入范围、稳压器/钳位/保护门限的保证值和故障上限，逐条写 `citation`；不取设计方计算的数值。
  合并扫描前 `power_rails` 仍为空却有 DEV-C01/PWR-C10 行，属审查准备未完成，先补齐再录结论。
- 条件导通另可声明 `power_sources`（某状态的供入节点）与 `power_paths`（某状态可导通的方向，不是理想短路或载流声明），
  不得把未上电的稳压器或端口标成 source 来消除告警。
- 各检查器的 intent 段（`i2c_topology`、`decoupling`、`device_kinds` 等）见 [自动检查](automation.md)。
  `device_kinds` 也覆盖集成电路：每颗 U/M 位号声明手册标题给出的角色（pwm_controller、gate_driver、sr_controller、
  pd_controller、regulator、supervisor、opamp_comparator、shunt_reference、mcu、transceiver、isolator，或泛称 ic），
  没有核验过的角色是 DEV-D02 的缺口；角色决定电路候选的核心器件。
- 计划顶层 `domains`（参考地分区、跨域器件、核心器件、截止网络，由 `checkers/domains.py` 按地的直流连通推导）见同文。
- **电路不手画**：`circuits` 由 `record/circuit-candidates.json`（`scripts/circuit_candidates.py` 从网表、已核实的器件类别和检查器库存生成，见[自动检查](automation.md)）与 `circuit_decisions` 推出，
  `python3 scripts/circuit_decisions.py intent.json record/circuit-candidates.json --db db.json --write` 写入 `circuits` 和 `circuit_candidates_sha256`；
  lint/计划对声明电路的 intent 必须带 `--candidates`，手写的电路列表与决定推出的不相等即拒绝（类型、成员集合、工作态、候选编号逐个比较）。
  `circuit_decisions[]` 每条对一个候选做一种决定，每个候选恰有一条：
  - `accept`：原样接受，可给名称 `id`；按手册模式名加工作态写 `states_add` 并给可定位的 `citation`（页、表、节、记录号或位号/网名）。
  - `merge`：`candidate` 列几个候选，`id` 必填，`citation` 引一条把它们描述成一个流程的条款；电路候选不与跨电路候选（ISOLATION、STARTUP、保护链）合并。
  - `split`：`into: [{id, members}]`，每部分成员是该候选成员的子集，所有成员都要有去处，`citation` 可定位。
  - `reject`：`reason` 为 OUTSIDE_SCOPE / NOT_A_CIRCUIT / DUPLICATE_OF（后者带 `of: <已推出的电路>`，成员须都在它里面），`citation` 可定位；被拒候选的成员进 REQ-Q08 复核。
  - `add`：生成器没找到的功能，`id`、`type`（规则总表的包名）、`members` 只能收 `unassigned` 中的器件、`via` 为每颗写它所在的网，`citation` 可定位。
  - `own`：`ref`、`candidate`、`citation`（可定位）：同一级认领打平的器件归 `candidate` 所在的电路。只裁定打平，不改已有的归属；每颗至多一条。
  推出的电路带 `id`、`type`、`refs`、`owned`、`nets`、`states`、`citation`、`candidate_ids`、`cross_cutting`、`anchors`。
  `refs` 是电路持有的全部器件，`owned` 是其中归它所有的：每颗被持有的器件恰好在一块电路的 `owned` 里，其余持有它的电路只引用它
  （可在条件与计算里引用，计划不为它生成行）。归属在决定后保留的电路之间按认领强弱判定：电路的核心器件 > 电路成员 >
  电路里的端点类角色（端口的 PD 控制器）> 链路成员（启动链、保护链）> 隔离带 > 链路的核心器件与端点；被拒或判为重复的候选让出的器件
  由下一个认领者拥有，打平的要 own 决定。一颗非核心器件最多被两块电路持有。
  审查员认为候选漏了器件，不往电路里手加：那是规则或网表的缺口，记在 REQ-Q08（候选生成没有归属的器件逐颗列出）并改规则。

## 二、review-plan.json（schema_version 7）

行带 `owner`、`check_key` 和 `requires`，计划带所属表 `owners` 和接口 `interfaces`，功能框架带 `not_asked`；电路检查项只在网表上有它问的机制时生成
（见下文“电路规则的前提”）。更早格式的计划（含据它写的结果）不再读，
校验、合并（`--merge-plan`）和改版比对（`--old-plan`）都拒收，按当前规则重新生成计划、重新审。

### 生成与合并

- 网表扫描 `lint.py --plan-json review-plan-cold.json` 保存计划和候选；审查者要补的检查登记到 `intent.rule_gaps` 后重新生成，计划工具没写的行（自动扫描行与改版记录以外）在合并和校验时都被拒。
- intent 声明电路时两次扫描都带 `--candidates record/circuit-candidates.json`；计划顶层 `circuit_candidates` 记候选文件的 `db_sha256`、`rules_version`、候选编号、决定和未归属器件，
  功能框架的 objects 直接取电路（即候选经决定后的）成员；候选文件随计划一起打包（`pack_review.py --circuit-candidates`）。
- 合并扫描 `--merge-plan review-plan-cold.json --plan-json review-plan.json` 产生**唯一最终计划**。
  合并要求 `db_sha256` 与当前输入一致且规则指纹相同；相同 ID 的对象/判据冲突时拒绝自动覆盖。
- 匹配证据后保留基础覆盖项，按 evidence ID 生成带 `parent_check_id` 的状态子项；基础项只汇总覆盖，不能代替子项结果。
- 计划合并不读取或迁移结果；后续补查先更新计划，再更新 digest 和逐项结果。
- 补查项按 `intent.rule_gaps` 生成，`id` 为 `规则编号.GAP-<缺口编号>.锚点`，`rule`/`method`/`domain` 随总表。
- **拆分实例的命名**：一条规则需要逐对象或逐判据给出不同结果时，逐个登记规则缺口，缺口编号写成
  `<对象>[-<判据>]`，对象用位号、网络或电路 ID，判据用简短大写词。例如全板项 DEV-C01 逐颗判定时登记
  `C12`、`Q3`，IC 脚经串联电阻接高轨的脚工具已逐脚生成（`DEV-C01.PIN.<位号>-<脚号>`，见 [阻容应力](commodity-floors.md#计划预判dev-c01-逐颗行)），工具没覆盖的（如经齐纳链或多颗电阻）才登记，如 `U2-FAULT`（行 `DEV-C01.GAP-U2-FAULT.U2`）；PWR-C02 拆窗口与调节能力时登记 `U1-WINDOW`、`U1-REGULATION`。
  自动生成的原计划项（如 `DEV-C01.BOARD`）保持不变（校验会按保存的输入重建它），在结果行写
  `split_out: [拆分实例 ID…]`：原项的结论只覆盖拆出实例**以外**的对象，拆出的对象各自给结论。
  这样一颗 C201 缺规格只让 `DEV-C01.GAP-C201.C201` 资料不足，其余已核对象仍可让 `DEV-C01.BOARD` 通过，
  不会被一个对象拖成整板资料不足。拆出实例须同规则、只属于一个原项，且不再嵌套拆分（`validate_review.py` 检查）；
  原项 rationale 写清其余对象核到了哪些、依据是什么。报告在拆出实例下注明所属原项。
  对 DEV-C01/02/03/04 的整板待核项先定位实际器件、额定/寿命/精度判据，保留与原检查的显式映射。
  不另造同一对象/工况/判据的重复行；启动与运行只有检查内容不同才分开。不同控制器的功率级即使同级风险，
  仍按独立关闭条件分任务。筛查 `BROAD_CHECK_NEEDS_LOCALIZATION` 只提示定位，不自动把汇总项变PASS。

### 检查项字段

| 字段 | 含义 |
|---|---|
| `id` | `规则编号[.实例键].对象`，如 `RST-T02.U3.SYS-RST-N` |
| `rule` / `method` / `domain` | 规则编号、方式代码、内容域代码，须与总表一致 |
| `object` | 对象：覆盖维度、功能电路、全板、网络、位号、引脚或页码 |
| `criterion` | 本项判据 |
| `applicability` | APPLICABLE / NOT_APPLICABLE / UNDETERMINED |
| `readiness` | READY / WAITING_EVIDENCE / NOT_SCHEDULED |
| `required_inputs` | 当前缺失的输入 |
| `trigger` | 实例化该项的可复现依据 |
| `handoff` | 独立下游动作，可与任一结果并存；`constraint`/`verification` 逐条写接收方要做和要测的事，不写“执行 X 原文及其全部工况”这类只换编号的套话（`TEMPLATED_HANDOFF` 提示） |
| `question` / `function_id` / `aspect` | 电路检查行才有：按规则模板填了电路、位号、状态和需求窗口的问题；所属功能框架；方面（= 规则标题）。问题里不许有禁止句（“不得…”“不把…外推”），校验 `question_errors` 拒绝，审查员补加的行同样受限 |
| `requires` | 带前提的电路检查行才有：`{id, found[, unread]}`，前提名（`catalog.SUBJECT_REQUIRES`）、网表上满足前提的器件、网表说不清的器件；行 `object.ref` 取 `found`（没有时取 `unread`）的第一个 |

`rule_plan[]` 回答“这类规则要不要跑”，`checks[]` 回答“具体审哪一项”，`functions[]` 是功能框架：
每个 intent 电路一条，含 `id`（`FN-<电路 id>`）、`question`（由成员问题归纳，审查员可改）、`objects`、`states`、
`members[]`（检查行 id、规则、方面、状态）、`blind_spots`（每条问了的电路检查项的盲区一句）、`not_asked[]`
（前提不成立、没有问的规则：`rule`、`aspect`、`requires`、`why`）、`checklist`
（判“证据不足”之前的五步原文）和 `bounds[]`（框架里器件对应的[工作点定界表](bounding-table.md)的格：`cell`、`refs`、`parameter`、
`side`、`methods`（按顺序）、`formulas`、`fallback`；NTC 按 NTC、电解按电解、IC 另按核实过的角色取格）。审查员照框架写功能判定，不翻规则书。

- APPLICABLE + READY：本轮执行；READY 不代表 PASS。
- APPLICABLE + WAITING_EVIDENCE：必须执行但缺材料，未补齐时为 INSUFFICIENT。
- UNDETERMINED：先补意图或解决意图/网表冲突，不得偷换成 NA。
- NOT_APPLICABLE：须有范围依据，结果为 NA。
- 需求要求某功能但网表未检出特征时，计划新增 REQ-A02 并报告 `REQUIRED_FEATURE_NOT_DETECTED`。

### 展开规则

- **全板通用**规则每板一项（`{"board": "BOARD"}`）；准备度按该规则所需资料判定。
  DOC-T01 逐 `intent.assemblies` 声明的装配状态一项。
- **逐位号**：每颗 IC/模组生成 DEV-C05 与 DEV-D05（位号不是 U/M、但有原生 power_in/out 脚、三脚以上且未归为
  分立器件或连接器的，如 Reg1 稳压器，也按有源器件生成）；每个连接器生成 DEV-D03、DEV-D05 与 PRO-D03。
  每颗齐纳、电源轨或板内 TVS 与每个保护门限脚（FAULT/OVP/UVLO/OCP/OTP 等）生成 PRO-C02 不误动作（NOTRIP）、动作有效（TRIP）两项；
  非地端全是信号网且直达连接器的 ESD/TVS 不另生成，记入该连接器 PRO-D03 的 `clamp_refs` 一并核对；
  热敏等传感器每个接到 IC 的检测脚生成 ANA-C04（开短路判别）；传感器接电源轨的一端和轨上 IC 的供电脚不算检测脚。
  声明了 `intent.devices` 的位号，DEV-D02 带官方/符号双向差集，DEV-D05 带待复核引脚清单（不是结论）。
- **需求与覆盖**：每条需求实例化为 REQ-D01；另有六类覆盖审计项 DOC-Q01、REQ-Q01～Q04、DEV-Q01。
- **保证值核对（E）**：网表或检查器定出对象，计划行一律 WAITING_EVIDENCE，审查者按两端规格书保证值经功能判定作答。
- **功能电路**：汇总项 REQ-Q07 只汇总覆盖，由工具写出：计划把它绑定到同类电路的全部适用行（`bound_checks`），各行都有结论且至少一行不是 NA 时 `derive_rows.py` 写它为 PASS（绑定行全为 NA 时脚本不写，由审查员填并写依据），不复制任何子项的结论；手填结论不同被拒绝；功能电路适用后生成电路检查项，声明了电路时逐电路×工况（答案不随工作态变化的电路检查项
  每电路一行，行的 `object` 不带 `state`，见 `catalog.STATE_INVARIANT`），否则按功能电路一次；各检查项仍须按 [最小充分证据](evidence-proportionality.md) 核适用性。
  未检出也未声明的功能电路汇总到一项 REQ-Q08，逐个确认不适用并给依据。
- **电路规则的前提**（一致性方案第 2 条）：`catalog.SUBJECT_REQUIRES` 给部分“类型 × 规则”一个由网表判断的前提，
  如 DRV-C02 要电路里有 MOSFET/BJT，PWR-C15 要电路或与它相接的 IC（经电路里的电阻接到开关栅极、或脚在电路网上）有
  反馈/补偿脚、电路里的 IC 有稳压输出脚，或有分压/光耦把输出送到 IC，RST-* 要有带复位、使能或启动配置脚的 IC；全表见
  [规则总表](check-catalog.md#功能电路)。前提不成立就不生成这一行，框架记 `not_asked`，报告在“各功能的判断”下列
  “FN-… 未问：方面（电路里没有…）”。地按网名和各域的参考地（`_RTN` 一类回流）认。网表说不清时照问：器件不在网表、
  类别未知（两脚件不算晶体管或 IC，整流桥和符号名出热敏/压敏的件不算未知）、IC 没有脚名。漏问的经 `intent.rule_gaps` 补回。
  一种类型对某电路问到的规则不到一半时，计划诊断 `CIRCUIT_TYPE_MISFIT` 并在计划命令输出里提示换类型，或不建这块电路、
  让器件走器件行。
- **电平转换（LEVEL_SHIFT）**：用于独立转换模块和通用 GPIO 跨电压域互连。转换器位于已声明的 I²C/SPI/UART 等
  总线上时，把转换器列入该总线电路的 refs，不另声明 LEVEL_SHIFT，避免同一链路重复检查；此时 REQ-Q08 中的
  LEVEL_SHIFT 以“已并入 <电路 ID>”为依据关闭，不写成“不适用”。分立 MOSFET 转换器没有名称线索，须在 `intent.circuits`
  中声明；计算与规则归属见 [WCA 公式](wca-formulas.md#mosfet-双向开漏电平转换)。分立转换管会被功率开关检查器识别，
  它不是功率开关：在 `intent.power_switches` 中把它声明为 `role: "level_shifter"`（带出处），计划就不再生成
  DRV-E01、DRV-C02、DRV-D01 及 DRV-A03/A04 候选，其 VGS/RDS 改由电平转换电路的规则核对。
- **检查器**：清单写在同名顶层键并带 `<id>_version`，计划项 `object` 带 `<id>_digest` 绑定清单，
  `inventory_gaps` 保留缺口——有缺口不能判 PASS；最终校验会重建清单，不能编辑清单消缺口。

### 功能电路依赖与状态核对

专家执行与 REQ-Q07 汇总先按最终计划的实际 `circuit_type`、`circuit`、`state`、`ref/refs` 核检查项归属，
在现有 evidence/rationale 列出全部必需检查项的准确 ID、所支持分项要求和结果。规则编号相同不证明是同一电路；
未列 `circuit_type` 的计算或补查项按实际端点和判据判断是否必需，不机械纳入所有未归类的项，也不因未归类而遗漏。
跨类型检查项只有在同一供电、信号、控制或保护路径构成真实依赖时才引用，并写逐跳路径及适用状态；
另一接口同名规则不能代替本接口电气检查。连接类检查项完成不代表电平、端接、供电或掉电检查项已完成。

汇总先核检查项适用性及实际违反：任一必需检查项已确认 FAIL，父项不得因其他检查项 INSUFFICIENT 改成
INSUFFICIENT；保留确认根因与其等级，再单列其余未知。没有确认 FAIL 而必需检查项未闭合时才按具体
缺口给 INSUFFICIENT。纯覆盖审计项按自身覆盖判据评判，不能直接复制整类电路的电气结论。

每颗关键器件从适用官方章节、表头及脚注逐脚列外围选值窗口，包括检测/配置电阻、时序、反馈、
电容、电感等实际使用项；按真实型号/档位、供电、模式、温度及容差角点验算 Min/Max。
外围器件自身耐压/功率通过不证明它满足 IC 的推荐选值窗口，标称值在窗内不证明全工况在窗内。
现有资料已证明越窗就按适用判据 FAIL；漏读适用参数属于执行覆盖缺失，不把正确计算器归为算术故障。

启动、运行和 OFF 分别画实际供能/信号路径，列独立外部来源是否仍在、默认脚态、非 failsafe 输入、
钳位/体二极管及受影响掉电域。启动时 Hi-Z、同一 3V3 供电、dead-battery 某脚行为不能证明全部
OFF 输入安全；反之，纯电池状态不能借不存在的外 5V 传播持续注入风险。每条排除依据限于其已证
工况，未证路径留具体缺口，不添加需求未承诺的零待机电流门槛。结果、父项、发现项和任务同步核
实际页码、型号、物理脚/网络与状态，避免把封装/文档错误误写为实体错连。

## 三、review-results.json（schema_version 6）

### 顶层字段

- `plan_digest` / `db_digest`：`validate_review.fingerprint()` 对 JSON 对象排序序列化后的 SHA-256（不是文件字节哈希）。
- `functions`：功能判定，见下节；没有时写空数组。
- `checks`：与最终计划 ID 集合完全一致的逐项结果。
- `findings`：唯一已确认缺陷/改善，一个根因可被多个检查引用。
- `scope_checks`：六个覆盖维度 `input_consistency`、`requirements`、`chains`、`states`、`datasheets`、`history`
  各指向对应覆盖审计项。表示覆盖审计完成，不是该域全部电气通过。
- `coverage`：各维度“对象→检查 ID 数组”的完整映射。有 `--db` 时机械检查 components、pins、nets、pages
  及 requirements 是否都关联至少一条检查；仅 PDF 时由页面/手工对象清单另审，不制作伪网表。
- `requirement_clarifications`（无则可省略）。`work_items` 不再写：待办由开放项派生（见 [结论与准出](verdicts-and-release.md#待办由开放项派生)）。
- `review_scope`（只在局部热审时写）：`{"functions": [计划框架 id…], "reason": "…"}`。声明后校验只要求这些框架的检查行有结果，
  不要求 `scope_checks` 与 `coverage`；gate 的 `valid` 可为真，但带阻断“不是整板结论”，`release` 恒为 NO_GO，`pack_review.py` 不打包。
  用于训练语料的单电路热审与试点，不用于交付。
- schema 5（2026-10-23，在 4 的基础上给决定结论的余量加推界方式与公差端，给“定不出界”加单调定界尝试）没有分版本号：`binding_version`、`remediation_version`、`workflow_version`、`impact_class_version`、
  `requirement_clauses_version`、`requirement_clarification_version` 写了会被拒绝，各项一律按最新规则校验。
  绑定由 `validate_review.py` 总是要求，修改说明由 `--require-actionable` 要求。
  schema 2/3/4 的旧台账不再读取，按本版 SR 重新审查。
- 复审另有 `revision_impact_version`、`revision_digest` 和必需项的 `reverification`，见 [改版复审](revision-review.md)。
- `summary` / `release` 可省略，由校验器计算；填了必须一致。

### 功能判定（functions）

计划框架的问题可以改得更具体，但改后的问题仍要点名这块电路、它的器件或网络，不能换成“本节保留的已核方面”这类范围说明。
框架的成员行转给别的功能（`function_id` 指向别的功能）后仍是这块电路的行：成员行里有证据不足或不符合时，报告把这块电路
计为未定或不符合，并列出那一行所在的待办，不随转出变成“通过”。

以一个合成例子说明：反激控制器 U1 的 VCC 由辅助绕组经整流、源跟随管 Q2 供电，数字全部是编的，只为展示字段：

```json
{
  "id": "FN-BIAS", "circuit": "BIAS",
  "question": "最低输出档 5 V、−10..105 °C、辅助绕组取最低电压时，Q2 偏置路径能否让 U1 VCC 保持在 8.8 V 以上",
  "objects": {"refs": ["Q2", "D2", "D3", "D4", "C3"], "nets": ["AUX", "BIAS", "VCC"]},
  "states": ["STARTUP", "RUN", "LATCH"],
  "conditions": [
    {"id": "c1", "kind": "NUMERIC_LIMIT", "source": "evidence/ds/D2.txt", "locator": "p3 Table 7",
     "says": "VF ≤ 0.35 V @10 mA，≤ 0.45 V @100 mA（25 °C）", "limit": {"max": 0.45, "unit": "V"},
     "regime": "25 °C，10–100 mA", "use": "20 mA 在两点之间，VF 单调，取 0.45 V 作上界"},
    {"id": "c2", "kind": "NUMERIC_LIMIT", "source": "evidence/ds/Q2.txt", "locator": "p4 Table 4",
     "says": "VGS(th) 1.0–2.0 V @250 µA", "limit": {"min": 1.0, "max": 2.0, "unit": "V"},
     "regime": "25 °C，250 µA", "use": "20 mA 取 2.0 V + 0.5 V 工程余量"},
    {"id": "c3", "kind": "NUMERIC_LIMIT", "source": "evidence/ds/U1.txt", "locator": "p7 Table 7",
     "says": "VCC(off) max 8.8 V", "limit": {"max": 8.8, "unit": "V"}, "regime": "−10..105 °C", "use": "判据"},
    {"id": "c4", "kind": "MANDATORY_CLAUSE", "source": "evidence/ds/U1.txt", "locator": "p9 §7.3",
     "says": "VCC 引脚必须经外部电容去耦，UVLO 释放前不得由 HV 脚以外的路径反灌",
     "applies": "U1 由外部偏置供电时", "use": "偏置路径的连接要求"},
    {"id": "c5", "kind": "NETLIST_FACT", "source": "db.json", "locator": "net AUX", "nets": ["AUX"],
     "says": "AUX 网把辅助绕组整流接到 Q2 栅极", "use": "路径"}
  ],
  "calculation": {"claim_ids": ["BIAS-VCCMIN"], "inputs": ["v_aux_min", "vf_d2", "vgs_q2"], "result": "VCC_min = 9.6 V",
                  "margin": {"value": 0.8, "unit": "V", "against": "VCC(off) max 8.8 V", "states": ["LATCH"],
                             "basis": {"kind": "GUARANTEED_BOUND", "comparison": "GT", "limit": "c3", "conditions": ["c1", "c2"],
                                       "scope": "−10..105 °C，VF 与 VGS(th) 取保证上界", "regime": "−10..105 °C",
                                       "derivation": "GUARANTEED_LIMIT",
                                       "corners": [{"input": "vf_d2", "condition": "c1", "picked": "max", "why": "VF 越大 VCC 越低"},
                                                   {"input": "vgs_q2", "condition": "c2", "picked": "max", "why": "VGS(th) 越大 VCC 越低"}]}},
                  "assumptions": ["辅助绕组 −10%", "Na/Ns = 3"], "aspect": "变换器电压裕量"},
  "judgements": [{"aspect": "偏置路径连接", "conditions": ["c4", "c5"], "states": ["STARTUP", "RUN", "LATCH"],
                  "says": "C3 跨接 VCC 与地，AUX 只经 Q2 进入 VCC，无 HV 脚以外的反灌路径"}],
  "verdict": "OPEN",
  "open": [{
    "key": "AUX-5V-MIN", "kind": "DESIGN_VALUE",
    "what": "T1 辅助绕组在 5 V 空载时的最低峰值电压还没有定",
    "scope": "5 V 空载、−10..105 °C",
    "spec": "辅助绕组峰值 ≥ 13.5 V（= 8.8 + 2.5 + 0.45 + 1.5 + 0.25 V 余量）", "owner": "磁件设计",
    "undecided": [{"ref": "T1", "parameter": "辅助绕组峰值", "unit": "V"}],
    "closure": "磁件规格写明 5 V 空载最低峰值电压且 ≥ 13.5 V",
    "decides": [{"aspect": "变换器电压裕量", "states": ["STARTUP", "RUN"], "via": {"claim": "BIAS-VCCMIN", "input": "v_aux_min"},
                 "rationale": "启动和运行态 VCC 由辅助绕组经 Q2 供给，最低峰值未定，与 VCC(off) 的比较缺这一项"}],
    "severity": {"level": "P1", "class": "REQUIRED_FUNCTION", "affects": "U1 供电",
                 "consequence": "辅助电压低于规格时 U1 在 5 V 待机掉电重启"},
    "design_option": {"status": "NONE", "reason": "先定磁件规格；定不下来再改为有保证压差的受控偏置",
                      "evidence": [{"source": "evidence/ds/U1.txt", "locator": "p7 Table 7"}]}
  }],
  "fails": [],
  "handoffs": [{"receivers": ["样机试验"], "constraint": "5 V 空载、−10 °C 时 VCC ≥ 8.8 V", "verification": "实测 C3 电压"}],
  "evidence": [{"source": "evidence/ds/U1.txt", "locator": "p7 Table 7"}]
}
```

LATCH 态由 0.8 V 的保证最坏值余量判 PASS；STARTUP 和 RUN 由开放项的影响条目挡住，等磁件规格。

字段：

| 字段 | 含义 |
|---|---|
| `id` / `circuit` / `question` / `objects` / `states` | 计划框架给出；框架外的功能自己写，`id` 以 `FN-` 开头 |
| `conditions[]` | [判“证据不足”之前先定界](evidence-proportionality.md#判证据不足之前先定界)第 1 步“先用手册里已有的界限”：每条 `id`/`kind`/`source`/`locator`/`says`/`use`；只在可编程器件某个设置下成立的条件写 `setting{ref, group, value}`，该器件该组的 CFG-D01 结果行 `settings[{value, function}]` 须列出这个值，配置表缺口（DELIVERABLE_PENDING / CONFIGURATION_TABLE）只挡 CFG-D01 行和需求行；`use` 写怎么用（相邻测试点夹出界限、门限上限、温度系数）。`kind` 是下表五种之一 |
| `calculation` | 同节第 2 步“算出了余量就下结论”：`result`、`margin{value,unit,against,basis[,aspect,states,check_ids]}`（多个方面写成列表，各带 `aspect`；`against` 写含项目降额的限值）、`claim_ids`、`inputs`（计算的输入量名，影响条目的 `via.input` 从这里取）、`assumptions`；只针对一个方面时写 `aspect`。同一功能里 `value`、`unit`、`against` 都相同的余量只能有一条：一个缺陷落在证明它的那个方面，要落到别的方面须是另一个量、另一条余量。没有数值的功能写 `no_calculation_reason` |
| `judgements[]` | 没有数值的方面各写一条：`{aspect, conditions: [条件 id], says[, states, check_ids]}`，`says` 写这几条条件对本方面说明了什么（例如“无外置补偿网络，按拓扑无独立电压环”）。厂家参考电路也可以撑起判断：该 TYPICAL_REFERENCE 条件写 `reference_circuit{figure, connection, load}`——参考电路的图号或页、本板与它相同的接法、它的元件值与本板负载的对照（本板不重于它），报告依据写“厂家参考电路 + 图号”。行要判 PASS，本方面本状态必须有证明通过的余量或一条 judgement，不能借别的方面或别的状态的结论 |
| `verdict` | PASS / FAIL / OPEN，且与 `open`/`fails` 一致（有失败项即 FAIL，否则有开放项即 OPEN） |
| `open[]` | 开放项：`key`（全文件唯一）、`kind`、`what`、`scope`、`decides[影响条目]`、`severity{level,class,affects,consequence[,hazard_path,exclusion]}`、`closure`、`due_stage`（默认 design_iteration）、`design_option`，`title`/`why` 可选；各种 `kind` 另要的字段见下面“开放项的六种” |
| `fails[]` | 失败项：`key`、`finding_id`（指向 findings）、`what`、`decides`，可带 `conditions`（被违反的强制条款）、`title`/`why`/`due_stage`/`design_option`；依据三选一：余量证明不够（REACHABLE_CASE/EXACT_ENVELOPE）、违反强制条款、或 `outside_specified{condition, operating_point, curves_checked}`——器件工作在手册没规定的区域：`condition` 是本功能里给出手册规定区的条款，`operating_point` 写本机工作点，`curves_checked` 列查过的曲线和表，其中须有推荐工作条件或电气特性节，工作点是某个引脚的还须有引脚说明节；不要把“没规定”写成限值 0 去比较 |
| `handoffs[]` | 功能级移交，派生行时填进计划要求移交的行 |
| `verdict_history[]` | 改过结论时写 `{from, to, basis: [条件或 claim id], note}`，basis 不能为空 |
| `evidence` | 可定位的证据 |

**开放项的六种。** 归类看欠的是什么，不看向谁要：

| `kind` | 必写 | 不写 | 说明 |
|---|---|---|---|
| DESIGN_VALUE（设计还没定） | `spec`、`owner`；`undecided[{ref, parameter[, unit]}]` 列出没选的器件参数，或 `depends_on: <开项 key>` | 向厂家索取（`spec` 不许写成这样） | `undecided` 所列位号的 BOM 行已有“参数名 + 该单位的数”时拒收：这个量板上已定，按 BOM 行算。缺的量由本审查另一个开项决定时（例如保护阈值等厂家数据）写 `depends_on`，只挂一层，它挡的行在待办和报告里并到那个开项下计。有计算的功能里没有对应方面的余量时写 `no_margin_reason`（还没选定什么） |
| VENDOR_DATUM（只有厂家知道） | `checked`（条件 id）、`why_insufficient`、`acquisition`、`worst_case` | — | 先按公开资料界限算：`worst_case{bound{condition, value, basis: GUARANTEED_LIMIT/ADJACENT_TEST_POINT/TYPICAL_CURVE/PUBLISHED_TABLE/APPLICATION_NOTE}, result, margin{value,unit,against,basis}}`，这个余量按它的依据决定结论。确实没有公开界限时写 `worst_case{not_boundable_reason, curves_checked[{source, locator}], operating_point_specified}`：`true` 是手册写了这种用法只缺数值，另写 `specified_by` 指向写了这种用法的条件（不能是 `monotonic_tried.test_points` 里没覆盖工作点的测试点；可以是条款、应用说明或 `regime` 覆盖工作点的典型曲线），引典型曲线（`curve: true`）时另写 `typical_estimate{value, unit, against, basis: ESTIMATE 并引这条曲线}`，估算已经不够就是失败项（余量记 REACHABLE_CASE），资料不足按后果定级；`false` 是设计依赖手册未规定的工作区，记失败项，发现项给出回到规定区的改法，不向厂家要。目录器件的参数是这一种，不是交付物 |
| DELIVERABLE_PENDING（另一阶段欠的交付物） | `deliverable_kind`（CUSTOM_PART_DRAWING 定制件图纸 / FIRMWARE_CAPABILITY 固件应用能力 / CONFIGURATION_TABLE 配置表）、`scope`、`deliverable`、`owner`、`assumed`（本判定按什么假定算的）、`closure` | `acquisition`、`spec` | CUSTOM_PART_DRAWING 另写 `missing_parameters[{name[, unit]}]`，只列判定需要、BOM 规格没写的参数（饱和电流、Bmax、绝缘结构；资格认可这类没有数值的不写 unit）；写了 unit 的参数若 `deliverable`/`what` 点名位号的 BOM 行已有“参数名 + 该单位的数”则拒收，按 BOM 行引作 NUMERIC_LIMIT（见[常规器件下限](commodity-floors.md)） |
| USER_DEFERRED（用户暂缓） | `instruction` | — | — |
| REQUIREMENT（需求没定） | — | `severity` | 走[需求澄清](requirement-clarifications.md) |
| REVIEW_INCOMPLETE（审查没做完） | — | — | 本轮自己读算完；有这种开项时不打包 |

**条件的五种。** 每条条件先要能定位：`locator` 给页码、表号、图号、章节、手册的节名（电气特性、绝对最大、引脚说明……）、
需求或记录编号、位号，或点名的网络/引脚（“nets PGND/SGND”）；“相关位号所有物理脚”“## BIAS”不定位任何东西。再按它是什么写 `kind`：

| `kind` | 另要的字段 | 能用来做什么 |
|---|---|---|
| NUMERIC_LIMIT | `limit{min 和/或 max（有限数）, unit}`，`says` 引出这个数，`regime`（温度、波形或脉宽、模式、型号——限值成立的条件） | 余量比较的限值；不能写进判断句 |
| MANDATORY_CLAUSE | `says` 引出规范句（必须/不得/须/shall/must…），`applies`（本设计受它约束的前提）；不要数字；位置是典型应用、应用电路、参考设计的不算 | 判断、失败项的依据 |
| NETLIST_FACT | `nets` 和/或 `pins`（REF.PIN）；有网表时每个名字要在网表里，只写叶名而网表里有两个同叶名网络的要写全路径 | 判断的依据 |
| TYPICAL_REFERENCE | 能定位；典型曲线或特性图写 `curve: true`，应用说明的文字不写 | 参考，不能撑起保证最坏值 |
| ENGINEERING_ASSUMPTION | 无 | 估算，不能撑起保证最坏值或确会出现的工况 |

条款指能定位的 NUMERIC_LIMIT 或 MANDATORY_CLAUSE。

**余量的依据（`margin.basis`）。** 每个余量写 `basis{kind, comparison GE/GT, scope, conditions[, limit, regime, conversion]}`，说明这个数证明了什么：

| `basis.kind` | 证明什么 | 另要 |
|---|---|---|
| GUARANTEED_BOUND | 在要求范围内余量的下界：满足则 PASS，不满足只说明没证明（OPEN） | 不依赖 TYPICAL_REFERENCE 或 ENGINEERING_ASSUMPTION |
| REACHABLE_CASE | 一个确会出现的工况：不满足则 FAIL，满足不证明整个范围（OPEN） | `joint` 说明这些参数为什么会同时出现；不依赖 ENGINEERING_ASSUMPTION |
| EXACT_ENVELOPE | 完整的最坏包络：满足 PASS，不满足 FAIL | `model`、`domain`、`extremum`；同 GUARANTEED_BOUND 不依赖典型值或假设 |
| ESTIMATE | 什么都不决定；用于必需功能或性能且移交样机实测时，满足判 PASS（见下） | 判 PASS 时写 `consequence_class` 与 `handoff` |

估算判通过（SR 自查 2.1）：相似器件保证范围或典型 ±30% 这类估算在整个范围内结论不变时，`basis` 另写 `consequence_class`
（REQUIRED_FUNCTION 或 PERFORMANCE_OR_LIFE，估算错了的后果）和 `handoff`（本功能 `handoffs` 里样机实测那一条的序号，
那一条写全 receivers、constraint、verification），满足就判 PASS，派生行带上这条移交（`required: true`，OPEN）。
损坏、过热和保护类规则（DEV-C01、DEV-C04、PWR-C03、PWR-C06、PWR-C10、DRV-C01、全部 PRO）不走这条路，仍要保证值。
寿命行另有自己的估算路径（见 DEV-C02/DEV-C06）。

`comparison` 为 GE 时零余量算满足，GT 时不算。除 ESTIMATE 外，`limit` 指向被比较的 NUMERIC_LIMIT，`regime` 写算出量成立的条件；
与限值的 `regime` 不同时，`conversion` 要指向一条条件或 claim（换算或包络），否则跨条件比较被拒绝。

除 ESTIMATE 外，`basis` 还写这个界怎么来的：
- `derivation`：GUARANTEED_LIMIT（手册限值就在本工况成立）、ADJACENT_TEST_POINT 或 MONOTONIC（从测试点推过来，另写 `monotonic{curve: 本功能里说明单调形状的条件 id, side: FAVORABLE}`，实际工况须在有利一侧，不利一侧的测试点什么都定不了）、TEMPCO（经温度系数推，`tempco` 指向给出温度系数 min/max 的 NUMERIC_LIMIT）、PUBLISHED_TABLE（公开数表）；TYPICAL_CURVE 只能用于 REACHABLE_CASE（典型件已经不够）；按典型曲线读出的估算记 ESTIMATE，不写 `derivation`。
- `cell`、`method`、`formula`（任何种类的余量都可写）：按[工作点定界表](bounding-table.md)定的界写格和推法编号（须是这一格允许的推法）；
  推法带公式时写 `formula{name: bound_formulas 里的函数, inputs, value}`，门禁用同样的输入重算，差超过 0.5% 拒收。
- `corners[{input, condition, picked: min|max, why}]`：每个带公差的输入取了哪条 NUMERIC_LIMIT 的哪一端，以及为什么那一端不利；取的那一端必须是该条件给出的数。没有带公差的输入时写空列表加 `no_corners_reason`。

开放项判“定不出界”（`worst_case.not_boundable_reason`）时，先用数写 `monotonic_tried`（结果格式 6）：
- `side`：开着的是上界还是下界（UPPER 或 LOWER）；`quantity`：哪个量的界。
- `cell`：[工作点定界表](bounding-table.md)里这个参数的格（表里没有写 `NONE`）。格有开着的一侧时须与 `side` 相同；
  格落到 `BOUNDED`（总能定界）或 `OUTSIDE_SPECIFIED`（记失败项）时拒收；参数单调时，有利一侧给了这一侧限值的测试点就定了界，拒收。
- `operating_point{min, max, unit}`：本板上测试点所在那个变量的范围（如齐纳电流 0.06–1.3 mA）。
- `test_points[{condition, at{value, unit}}]`：手册给这个量或它斜率的测试点，条件须在 `checked` 里，单位与工作点相同（u、μ 按 µ 算）。
- `why_not`：这些测试点为什么给不出开着的那个界，不得照抄 `not_boundable_reason`。
- `other_side`：另一个界 DECIDED（本功能有同一方面的余量）或 NOT_DECISIVE（写 `other_side_reason`）。

工作点整段落在两个测试点之间时，门禁拒收“定不出界”，按相邻测试点定界（ADJACENT_TEST_POINT）；只有一部分在测试点之外时，
`open_range{min, max}` 写开着的那段（在工作点之内、不跨进测试点之间），测试点之间那段写成本功能同一方面的余量。
开放项的每条边写 `side`，与 `monotonic_tried.side` 相同。

计算类（规则方法 C）的方面判 PASS 必须有证明它的余量；一句判断只能收掉连接追踪（T）和条款核对（D）类方面，写明 `reference_circuit` 的厂家参考电路例外。

**影响条目（`decides[]`）。** 开放项和失败项的每个 `decides` 条目是一条边：`{aspect, states?, check_ids?, effect, via, rationale}`。
`effect` 默认 BLOCKS_PROOF（挡住该范围的证明），INFORMATION_ONLY 只登记不挡；`check_ids` 把边收窄到点名的行。
经需求文档条款的边（条件来自需求目录里的文档，`requirement_source` 及其同目录文件）只能挡绑定到该需求的行：该需求的 REQ-D01 行及其 `bound_checks`；挡别的行要经缺的数进入的那个比较——数值限值、计算输入，或手册、标准里的条款。
DESIGN_VALUE、VENDOR_DATUM、DELIVERABLE_PENDING 的每条边都写 `via`——缺的量进到哪里：`{condition: 本功能的条件 id}` 或
`{claim: 计算的 claim id[, input: calculation.inputs 里的输入名]}`——和 `rationale`（现有的界为什么决定不了这一项）。
一个缺口挡几个方面不限数，超过 3 个只出 WIDE_GAP 提示，供复看是否该拆开。

**范围要写明。** 余量、判断和边不写 `states` 时只覆盖不带状态的行（STATELESS），不覆盖所有状态；要覆盖几个状态就把它们列出来。

**退役字段。** `margin_not_decisive_reason`、`loose_bound`、`decides_reason` 写了会被拒绝：余量决不决定由余量依据说明，挡住什么由影响条目说明。

校验 F1–F12：F1 每个功能有问题、对象、结论，电路功能至少引用一条条款（被判断、余量依据、开放项、失败项或影响条目实际引用；只含 DOC 行的功能不要求）；
F2 DESIGN_VALUE 写规格与责任方，不向厂家要；F3 VENDOR_DATUM 写查过什么、为什么不够，以及公开资料界限下的最坏情况（界的条件、取值、依据和带余量依据的余量；没有界就列查过的曲线表），
公开资料界限下证明通过的余量说明这个量不缺，开放项要撤掉，证明不满足的要记失败项，ESTIMATE 可以保留开放；
F4 结论跟着余量的依据走：证明通过的余量与挡住同一范围的边并存被拒绝，证明不满足的余量要有失败项，同一范围既有通过又有失败的证据是 EVIDENCE_CONFLICT，
没被任何东西决定的 OPEN 余量要有开放项；失败项要么落在证明不满足的余量上，要么在 `conditions` 里引被违反的强制条款，指向的发现项带 `remediation`；
F5 行跟随功能（见下）；F6 改结论要引条款或数字；F7 缺口的每条影响条目写 `via` 和 `rationale`，`via` 指向本功能的条件或计算的 claim 与输入；
F8 功能已有计算时，DESIGN_VALUE 开放项要有对应方面的余量，或写明设计还没选定什么；
F9 判 PASS 的每个方面在该状态有证明通过的余量或 `judgements` 条目，每条 judgement 至少引一条 MANDATORY_CLAUSE、NETLIST_FACT 或写明 `reference_circuit` 的厂家参考电路，不引 NUMERIC_LIMIT
（数字限值在余量里比较，不在判断句里宣布满足），只说“不适用 / 无此问题 / 按拓扑无… / 不涉及”而不引 NETLIST_FACT 的判断被拒绝（改记 NA），
判断与挡住同一范围的边冲突，没人判过的方面不会默认通过；
F10 同一条不能定位的条件出现在两个以上功能里被拒绝（能定位的条款可以被几个功能共同引用；同一句 `assumptions` 抄进几个功能的计算同样拒绝，共用工况写进 intent 一次）；
同一句 `no_margin_reason`/`why_insufficient` 出现在几个开放项上只出 TEMPLATE_REASON 提示；
F11 框架功能的 `objects` 不超出 intent 电路声明的位号与网络（要扩大先改 intent 再重生成计划，不在判定里放宽），审查员自己绑定的行要是该功能对象上的行
（位号行的位号、网络行的网络在功能 `objects` 里，网络名不计图纸路径；感性负载行只看电感本身和它的开关节点，续流回路里别的器件只是上下文；需求行、全板行没有对应的器件或网络，不受此限）——一块电路的缺口不借绑定伸进另一块电路；
F12 计划带 `clamp_refs` 的连接器行（PRO-D03）必须绑定功能：钳位电压对被保护脚绝限是功能判定里的条款和判断，不手填 PASS。

**检查项标识。** `plan_review.py` 给每行写 `check_key`：规则、规则版本（目录条目与问题模板）、去掉 `circuit` 名称后的对象、判据四项的摘要。
装配状态按内容命名：计划的 `assemblies` 给 intent.assemblies 的每个名字一个由贴装表和跳线算出的键（`ASSEMBLY-…`），检查器行的 `state`/`states`
和装配检查的 `assembly` 用这个键进标识，所以两人给同一装配起不同的名字仍是同一项检查；电路行的 `state` 是工作态，不换。
检查器清单的摘要（`*_digest`）和句柄（`decoupling_group`、`power_switch`、`supervision` 等，见 `check_key.INVENTORY_FIELDS`）只是指回清单，不进标识。
校验器总是重算这个键，不信记录里存的值；同一项检查在计划里问了两次被拒绝。改电路名不改检查项，换规则模板或判据才改。
`scripts/compare_reviews.py` 先按这个键严格配对两份记录，再给出按电路的建议配对（见 [自动检查](automation.md#脚本分类)）。
电路级行的对象带 `circuit_key`（电路来自的候选编号，合并的用 `+` 连接）：有它时成员表、核心器件和网络不进标识，
两份记录接受了同一批候选，即使画法（成员、网络写法）不同，电路检查项也是同一项。

**所属对象。** 计划给每行写 `owner`：电路级行归它的电路（`{"kind": "CIRCUIT", "id": …}`）；
`catalog.SYSTEM_FUNCTIONS` 里的系统规则行归系统功能（`SYSTEM`，如 SYS-POWER）；关于器件的行归拥有这颗器件的电路
（多颗器件须同属一块）；其余归全板（`BOARD`）。计划的 `owners` 列出每块电路拥有的器件，`summary.owners` 是按所属的行数。
校验器按 `owners` 重算每行的所属，拒绝写错的行；审查员后加的拆分行可以不写。

**接口。** 计划的 `interfaces`（`scripts/interfaces.py`）列出所属对象之间的接口：一条网络连着两个所属对象的器件脚就是它们之间的接口网络，
同一对之间的网络合成一个接口；地网不是接口网络。四种：电路对 `IF-<A>~<B>`、链路 `LINK-<跨电路候选>`（带它自有的器件 `parts`）、
供电 `RAIL-<轨>`（带 `source` 与 `basis`）、对外 `EXT-<连接器>`（连接器全部脚）。编号用电路的候选编号，改电路名不改接口。
每个端点 `{owner, pin, role, basis, domain, supply}`：角色 DRIVER / RECEIVER / BIDIRECTIONAL / PASSIVE 按库引脚类型、器件类别、电源树和引脚名推，
推不出的进 `gaps`（`reason: role`），轨推不出源的也进 `gaps`（`reason: source`）。

**接口检查项。** 计划按 `catalog.INTERFACE_SUBJECTS` 逐接口生成行，对象带 `interface`：电路对问 SIG-T04 方向语义与 SIG-C07 电平，
链路问 SIG-C07（两端电平），两端 IC 供电轨或参考地分区不同的接口网络（`cross_supply`）另问 SIG-C08；连接器问 DEV-D03 对端定义、
DEV-C04 载流、PRO-D03 对外防护（对象 `{interface: EXT-<连接器>, ref}`）；供电轨在敏感电路（ANALOG、CLOCK、RF）取电时问 PWR-C14
（对象带 `loads`）。行的缺口取接口的角色缺口（`interface-role:<脚>`）、轨源缺口（`rail-source:<接口>`）和端点 IC 的资料。
电路对、链路和连接器各一个接口框架（`functions[]` 里带 `interface`、`interface_kind`，没有 `circuit`），成员是该接口的行；
供电接口只有行，不建框架。按声明的总线电路展开的同名规则仍问电路内部的链路。

**系统功能。** 有对象才生成：两个以上地网问 PWR-T06（`{system: SYS-GROUND, nets}`），两条以上电源轨问 RST-T03
（`{system: SYS-SEQUENCE, rails}`，全板一行），有可能是主控的 IC 问 SIG-D13（`{system: SYS-PINMAP, refs}`）；电源树与监控的行
（PWR-T01/C01/A01/A04、PWR-T04/A06）照旧生成。每个有行的系统功能一个框架（`functions[]` 里带 `system`），成员是归它的行。
**自有器件。** DEV-C01 应力、DEV-C02 电容、DEV-C03 精度每块电路对它拥有的器件一行（`{circuit, circuit_key, refs}`，
按器件类别取），没有电路拥有的器件全板一行（`{board: BOARD, refs}`）。
**覆盖审计。** 校验器另查两条：电路来自候选时，每颗贴装器件恰归一块电路（`row_owner.coverage_errors`），
或列在 REQ-Q08 的 `unassigned` 上（计划把没有电路拥有的贴装器件都列进去）；每个接口都有它该问的行（`interfaces.coverage_errors`），电路对、链路（有网络时）和连接器另有框架。
**报告分组。** 计划有树框架时，报告的功能表分系统功能、功能电路、接口和审查员另建的功能四组；每个发现项多一行“所属”，写它的行归哪个系统功能、电路、接口或全板。

**文档检查不是功能电路。** 功能回答一块电路的问题；DOC-* 行（输入版本、图纸卫生）不是电路。
文档错误直接在行上判 FAIL 并写 finding，不绑定功能（校验拒绝绑定了功能的 DOC FAIL 行）；这件待办由 finding 生成（`W-<finding id>`，含指向它的全部 DOC FAIL 行），不要改记证据不足。DOC 行证据不足时仍需一个开放项作入口，这种只含 DOC 行的功能不计入
“功能判定”计数，也不进报告的功能表。

隔离器件的工作资格（PRO-C03）和反馈稳定（PWR-C15）是功能的方面，不另设约定：
PRO-C03 在隔离功能里逐个列出变压器、光耦/数字隔离器、跨接电容的实际工作电压、重复峰值/频率和厂家资格条件
（短时耐压、目标绝缘类别、无直流跨接都不能独自关闭）；PWR-C15 在变换器功能里写反馈模型、补偿配置和角点稳定性
（无反馈环按拓扑 NA；内部补偿用厂家适用条件证明；Bode 实测是移交，不是开放项）。

**行跟随功能。** 绑定了功能的行（计划检查行，或审查员写了 `function_id` 的行——这样的行要是该功能对象上的行（F11）；同一组对象声明了两个功能电路时，
一个框架的检查行可以绑到另一框架的功能，条件是该功能的 `objects` 覆盖这一行的位号与网络，这样共用的检查项只判一次、不复制开放项；
框架行不能挂到审查员自建的功能上，也不能从自建功能取 `open_ref`/`fail_ref`：计划电路的缺口写成该电路功能（或拥有该器件的计划功能）的开放项或失败项，
缺口只写一次——跨电路的缺口写在拥有缺失量的框架里，开放项的 `decides` 另加影响条目，用 `check_ids` 点名另一电路受它挡住的行，
那些行的 `open_ref` 就指向这个开放项（没点名的行不能指向别的功能的开放项；失败项不跨功能，2026-10-24 定）；自建功能只装不属于任何框架的行，如器件、检查器和全板行，
它的位号若全在某个电路框架里，校验拒收并提示写进那个框架；计划漏了电路时在 `intent.circuit_decisions` 登记 add 决定后重生成计划）：功能 PASS → 行 PASS；
功能 FAIL → `fails[].decides` 命中的（方面，状态）FAIL 并带 `fail_ref`/`finding_id`；功能 OPEN →
`open[].decides` 命中的行 INSUFFICIENT 并带 `open_ref: "FN-ID/KEY"`；其余的行只有本方面本状态有证明通过的余量或 `judgements` 条目才 PASS，
否则 `derive_rows.py` 报“judges no …”而不生成该行。`rationale` 写“见功能判定 FN-X（方面，状态）：”加本方面自己的结论和余量，或 judgement 的内容和条款。
`derive_rows.py` 生成这些行；手填的行只对账不覆盖。校验强制：INSUFFICIENT 必有 `open_ref` 且其 `decides` 覆盖本行的方面和状态；
绑定的行的 `aspect` 等于计划的方面；每个有已审成员的框架都有功能判定。

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
不因没有实测或全温曲线继续索取参数。通用说明不再准确时（拓扑专用、部分范围、NA 等），在结果行
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
缺口，也不能解除输入完整性失败带来的全板 NO_GO。输入资格缺口只影响确实依赖该事实的行：
某器件缺功能名只影响该器件自身引脚角色，不改变网络连通，其他器件去耦组的电容、回流与边界照常审结；
不能把同一缺口复制成每个去耦行的 INS（见 [执行一致性](execution-consistency.md#2-局部-pass-不扩展为路径或系统-pass)）。
受影响的行引用原生导出逐端点比对；局部电气结论还须具体用途、原厂条款、状态及参数证明，不能仅从 XML 推断合格。
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
`severity.consequence` 是否写了这个缺口在什么工况下导致什么后果。然后逐行用实际对象上下文对照手填行的 `rationale` 及关联待办：

- 对每条需求，将原文与本行 criterion 中并列的功能、工况前提、交付和范围排除分别列为分项要求，
  在现有 evidence 定位每项实际证据、相关检查 ID 与状态。明确排除认证、实测或某种使用状态，
  只证明该排除分项要求；不能据此让同条需求中的电气实现或保证前提一起 PASS。必要时按上文
  “拆分实例的命名”补查分项要求，保留自动原项及完整覆盖关系。
- 需求整项只有全部适用分项要求已 PASS（或有来源证明 NA）时才能 PASS。分项要求有确认 FAIL 时
  整项按真实违反给 FAIL；没有确认 FAIL 但仍有必需证据不足时整项为 INSUFFICIENT，写明具体
  开放项、未知和关闭条件，是否写 `"blocking": false` 按该要求现有准出依赖判断。最高潜在级仅引用实际相关
  分项要求的可信物理后果与条件，确认缺陷和潜在风险分开；复用既有唯一根因任务，不重复计缺陷。
  纯范围排除项可独立 PASS，不能因为全板其他项未闭就自动传染 INSUFFICIENT；相反，复合项不能
  用范围 PASS 掩盖它明确依赖的器件自身的要求。资料缺口不是需求待决，不改成 REQUIREMENT_OPEN。

- 将文字中的每个位号、物理脚、网络与本行对象/状态核对。额外对象只能作为有定位的供电、返回、保护或
  共同证明路径出现，说明其与本行的关系；从其他行继承而无因果关系的前缀、脚名、数值须删除或重写。
  旁路、储能等器件清单按本行所核电源脚及实际贴装变体的连接路径列出，避免把全板清单带入局部判据。
- 用“本行要判断的内容→已核路径/条款→剩余未知→补证或修改→复验判据”核闭环。接口防护的缺口须对应
  该接口的实际外接边界；另一个接口的浪涌、旁路或源许可不能独自关闭本行。无源触点的候选排除说明须
  引用其真实角色，不能借相邻 IC 的旁路说明代替。
- 共享的是可定位的证明，不是整段结论。确实共用同一路径/工况的对象可引用同一证据，分别说明它覆盖的
  范围；状态、对端、故障路径或关闭资料不同的项分别写。不要以禁止共享文字的机械规则制造重复工作。
- 修改理由或关联关系后重新核父项、澄清项和任务；已完成的板级窄判据与真实外部未知分别留记录。
- 运行态与掉电态分别核取证。正常运行接口项引用运行供电、输入电平/共模和对端边界；Ioff、掉电泄漏、
  UVLO/关断条件只支持其实际适用的状态与判据。某个字段写错状态时修正该字段及关联任务，仍保留
  本行真实未闭合的外部共模等缺口，不用掉电补证替代运行态证明，也不把整行自动改为 NA。
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

证据不足的行只指向功能判定里决定它的开放项（缺口文字写在开放项上，行不重复）：

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
（DESIGN_VALUE→DESIGN_OPEN，VENDOR_DATUM→EXTERNAL_DATA，REQUIREMENT→REQUIREMENT_OPEN，DELIVERABLE_PENDING 与其余同名），写了会被拒绝。

由校验器推出、不写进台账的字段（写了会被拒绝）：
- `blocking`：FAIL/INSUFFICIENT 默认阻塞。只有阶段允许暂留的 P2/P3 才写 `"blocking": false`。
- `evidence_confidence`：PASS/FAIL 默认 B，INSUFFICIENT 为 C。只有声称 A 级证据时才写 `"A"`。
- `disposition`：默认 OPEN。只写 FIXED_VERIFIED、ACCEPTED、RETRACTED。
- 行级潜在等级是 `open_ref` 指向的开放项的 `severity.level`；一行只指向一个开放项。

- `binding.object`/`binding.criterion` 是实际已审范围，与同 ID 计划的 object/criterion 完全一致；
  `evidence` 和 `rationale` 只支持这个对象、配置、工况和判据。复用结论前核对物理脚、网络及要求，
  不能因 ID 相似、同一 IC 或同一功能组就移用。
- 所有结果含非空 `rationale` 与可定位 `evidence`。INSUFFICIENT 必须有 `open_ref`（REQ-H02 历史处置除外）；非 FAIL 不填 `severity`（行级字段只属于 FAIL）。
- 每个开放项（REQUIREMENT 除外）给 `scope` 和完整的 `severity`（`level`、`class`、`affects`、`consequence`），校验始终强制；
  内容按 [危险度分类原则](verdicts-and-release.md#证据不足的危险度分类原则) 逐项判定；非空字段不等于危险度可靠。
  `consequence` 同时是定级理由：写清这个缺口在什么工况下导致什么后果，不写跨开放项通用的套话（`TEMPLATED_SEVERITY_REASON`）。
- **独立审查**：结果顶层写 `history_inputs`（本轮能看到的旧审查目录或文件路径，没有就写空数组）。除 REQ-H02 上一版问题复验行外，任何检查的 evidence 引用这些路径都会被 `validate_review.py` 拒绝；未声明却引用某次审查的结论/校验/报告文件（`review-results.json`、`review-gate.json`、`审查报告.md`）会进质量筛查候选。报告结论里写明本轮可见的旧审查材料（只显示目录名）。首审（`review_mode: first`）可以看到旧材料，但结论按当前资料重新得出、不引用旧结论，也不逐条登记上一版问题的处理结果，报告照此说明；要逐条登记（已修、保留、撤回），用改版复审（REQ-H02）。
- `severity.class` 是后果类别，类别决定潜在等级（见[后果类别](verdicts-and-release.md#后果类别severityclass)）；
  P0 类别另给 `severity.hazard_path`，只会坏一个器件而不打开危险路径的写 `COMPONENT_DAMAGE`（P1）；
  P0 类别降为 P1 时给 `severity.exclusion` 写出独立保护。
- 每个 REQ-D01（需求状态 OPEN/DEFERRED 与 NA 除外）给 `requirement_clauses`，
  把需求原文按顺序完整拆成条款（拼接后等于原文），逐条标类别：

  | 条款形式 | kind | 结论 |
  |---|---|---|
  | 规定本设计应达到的量值、功能或状态（=、≤、≥、±、须、不得、支持、保持、可靠进入） | OBLIGATION | `result` 取 PASS/FAIL/INSUFFICIENT/NA，可附 `check_ids` |
  | 工况与前提（允许…、输入…范围、给定的器件参数）、审查方法与输入取值（按…审查、公差取…、先读…再登记、移交下游）、范围说明 | PREMISE | 不带结论；作用于所有相关行 |

  格式：`[{"text": "原文片段", "kind": "OBLIGATION", "result": "PASS", "check_ids": [...]}, {"text": "原文片段", "kind": "PREMISE"}]`。
  行结论 = 要求条款中最差的结论（FAIL > INSUFFICIENT > PASS > NA），校验强制。前提条款里的要求由相关器件/电路行执行，
  其他行发现的缺陷不连带本行；需求原文把该缺陷写成要求（如“各连续受电元件不得超出持续功率额定”）时才在本行判。
- 证据不足的原因是开放项的 `kind`：DESIGN_VALUE、VENDOR_DATUM、DELIVERABLE_PENDING、REQUIREMENT、REVIEW_INCOMPLETE、USER_DEFERRED，
  含义见 [复核每条证据不足](evidence-proportionality.md#复核每条证据不足)。纯下游项不是 INSUFFICIENT，用阶段 NA。
  `scope` 写缺口要覆盖的电压/负载/状态/温度范围，不是标题或 `what` 的复述（`REQUEST_SCOPE_ECHOES_TASK` 提示，报告也不显示只复述的范围）；
  `acquisition` 以“已读 X 第 N 页，缺 Y”开头时，报告把“已读”部分单列为“已查过”。
  `closure` 写设计者能核的边界和条件（手册限值、标准条款、工况），不写审查员算例的中间值；
  位号与数值之间留空格或标点（“R12 100°C”，不写“R12100°C”）。
- 计划行带 `proposal.result = PASS` 而结论为 FAIL/INSUFFICIENT 时，须给 `proposal_override`（code 与 reason），
  code 的封闭清单见 [通用件最弱档基准](commodity-floors.md#计划预判dev-c01-逐颗行)。
- `bom_constraint`：常规器件（电阻、电容、电感、二极管）超出最弱档、或需求的特殊要求（寿命、精度、宽温等）落到这颗器件时，
  在 PASS 行上写 BOM 必须写明的要求，不建开放项、不记证据不足（规则见 [通用件最弱档基准](commodity-floors.md#常规器件只排查风险)）：
  `{refs, requirement, basis, consequence_class, level, status, hazard_path?, written_at?}`。`requirement` 写最低值（“额定功率 ≥ 0.09 W”
  “耐久 ≥ 10000 h @105 ℃”）；`basis` 写算出它的计算或需求编号；`consequence_class`/`level` 按
  [BOM 约束怎么定级](commodity-floors.md#bom-约束怎么定级)，等级由类别决定；`status` 为 TO_WRITE（冻结阶段阻断）或
  WRITTEN（`written_at` 指向 BOM 上写明它的那一行）。报告单列“BOM 要写明的额定与规格”一节。
  校验拒收：开放项（DESIGN_VALUE / VENDOR_DATUM）挡住的行全是常规器件的 DEV-C01/DEV-C02 行，或挡住全板 BOM 行（DEV-D04）而文字只点名常规器件时，应改写成 `bom_constraint`。
  需求有寿命参数（`lifetime`）时，计划按 `mission_profile` 给每颗电解、固态或超级电容一行 `DEV-C02.LIFE.<位号>`（带移交热设计），
  给每颗耗损件一行 `DEV-C06.<类别>.<位号>`（按次数核而次数没给的直接 NA）；寿命行可凭估算余量（`ESTIMATE`）判 PASS，
  这时须写 `bom_constraint` 且 `requirement` 写明“估算”和所设热点；寿命行不开 VENDOR_DATUM，见
  [寿命与耗损件](commodity-floors.md#寿命与耗损件)。
- 光耦输出接在控制器的反馈脚（FB/VFB/COMP）上时，计划给这个脚一行 `PRO-C01.FEEDBACK-OPEN.<位号-脚>`：反馈断开（光耦或串阻开路、副边控制失效）后控制器按开环送能，按手册的保护检测延时算到保护动作为止输出侧电压的上界，对照输出侧器件耐压；这一单一故障不看审查员是否想到。
- 其他常见单一故障也按网表特征派固定行（2026-10-23），行只问问题、不预设结论，没有特征就不派：
  - 开关管一端接连接器、该端不给任何 IC 供电，另一端是变换器或稳压器输出（声明的电源轨，或能追到来源且有对地大电容）、本身不接连接器：`DRV-C02.PORT-SHORT`，端口硬短路时储能经开关释放，核 SOA、I²t 与关断尖峰；
  - NTC 两端都不接 IC、旁边有整流桥、二极管、保险或连接器（限浪涌用）：`PWR-C13.NTC-HOT`，热态重接入时整流桥、保险与输入电容承受的浪涌；
  - 开关节点（有 MOS 漏极和变压器或电感）经二极管到一个没有对地大电容的节点，该节点上的电阻和电容另一端接同一网：每颗电阻一行 `DRV-C01.RCD`，钳位电阻功率与耐压；
  - IC 的信号脚和 LED 或光耦 LED 的一端在同一网（不经晶体管、不是地网）：`DEV-C05.PIN-LED`，按第 5 条四档核该脚的电流；
  - 光耦输出接到 IC 的使能或关断脚（EN、SHDN、DIS、INH、STBY、ON/OFF、RUN 等）：`SIG-C09.ENABLE-LINK`，上电先后、使能门限与光耦延时、掉电后能否恢复。
- 器件行（DEV-D01 身份、DEV-D05 引脚处置、DEV-C05 工况）对晶体管、光耦、稳压/TVS 二极管、整流桥、变压器和 part/value 写明 CUSTOM 的电感固定生成，不靠 `intent.devices` 声明；普通二极管和普通电感是常规件，声明了才生成。
- 脚电流行（`DEV-C01.PIN.*`）的串阻读不出阻值、计划没算出脚电流时，判 PASS 须附 `manual_verification`，在 `method` 里写出自己的脚电流计算。
- 阶段 NA：`review_result: NA` + `na_reason: OUTSIDE_SCHEMATIC_STAGE`，`applicability` 保持 APPLICABLE，
  `handoff.product_requirement_status: PENDING_VERIFICATION`，不建开放项；完整写法见 [纯下游验证项](verdicts-and-release.md#纯下游验证项)。
  复合要求不能整体 NA；测试要求条款写 `result: NA`、`na_reason: OUTSIDE_SCHEMATIC_STAGE`，
  `check_ids` 链接独立阶段 NA 检查，不得只改条款结果让测试消失。
- 普通 NA 必须 NOT_APPLICABLE；修改自动计划的适用性需 `applicability_evidence`。计划行带 `requires`（网表上找到了它问的机制）
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
  同一对象（只差状态）的几行可写相同文字，报告会合并显示；不同对象写同一段 `method` 会被拒绝，每行写清核对了哪些位号、节点和数值。只能用在工具确实拦了的行上；
  这类行不算 REVIEW_INCOMPLETE、不建开放项，gate 把工具限制列入 `sr_improvements`，不影响准出。
  资料或设计本身没给出的数值不是工具限制，仍按 EXTERNAL_DATA / DESIGN_OPEN 处理。
  工具提示的 `required_inputs` 指向 `intent:` 字段（如 `supervision.rail_requirements` 逐轨 `required=false` / `internal_monitor`，
  `optocouplers[].internal_pullup`）时，是声明缺失不是工具限制：先补 intent、重生成计划再判，不写 `manual_verification`。
  校验按阻断的缺口代码强制这一条：`intent`、`evidence`、`requirements`、`firmware`、`population`、`datasheet*`、`unverified-device-pinout`、
  `official-full-pinout`、`rail-requirement`、`level-standard` 开头的缺口是审查者可补的输入，`manual_verification` 覆盖不了；
  其余（拓扑或模型识别不了，如 `pin-role-or-model:`）才算工具限制，报告“对 SR 的反馈”按缺口代码列出。

### 示例：一个功能的两个开放项决定两行

合成例子：反激变换器的功能判定缺两样：T1 的磁件参数（本设计要定，DESIGN_VALUE）挡住环路模型（PWR-C15）和最小关断时间（PWR-C04），
输出电容的低温 ESR（厂家才知道，VENDOR_DATUM）只挡住 PWR-C04。两行都由 `derive_rows.py` 从功能派生。

```json
{
  "functions": [{
    "id": "FN-QR", "circuit": "QR", "question": "90–264 Vac、5–12 V、空载至 3 A 时反激各输出档是否稳定且关断时间不低于 tOFF(min)",
    "objects": {"refs": ["U1", "Q1", "T1", "C5"], "nets": ["BULK", "VOUT"]}, "states": ["RUN"],
    "conditions": [
      {"id": "c1", "kind": "MANDATORY_CLAUSE", "source": "evidence/ds/U1.txt", "locator": "p13 Feedback, p21 补偿网络",
       "says": "使用内部补偿时，功率级增益和输出电容零点须在规定范围内", "applies": "FB 不外接补偿时", "use": "FB 外接与条件一致"},
      {"id": "c2", "kind": "NUMERIC_LIMIT", "source": "evidence/ds/U1.txt", "locator": "p8 Table 6",
       "says": "tOFF(min) ≤ 1.2 µs（−40..125 °C）", "limit": {"max": 1.2, "unit": "µs"}, "regime": "−40..125 °C",
       "use": "判据：关断时间不小于 1.2 µs"},
      {"id": "c3", "kind": "NUMERIC_LIMIT", "source": "evidence/ds/C5.txt", "locator": "p1 特性表",
       "says": "ESR ≤ 50 mΩ @20 °C、100 kHz", "limit": {"max": 50, "unit": "mΩ"}, "regime": "20 °C，100 kHz",
       "use": "低温 ESR 未给"},
      {"id": "c4", "kind": "NUMERIC_LIMIT", "source": "evidence/ds/C5.txt", "locator": "p1 规格表",
       "says": "使用温度范围 −40..+105 °C", "limit": {"min": -40, "max": 105, "unit": "°C"}, "regime": "全系列",
       "use": "−20 °C 在规定使用范围内"}
    ],
    "no_calculation_reason": "功率级增益和关断时间都要 Lp 与匝比，规格未定",
    "verdict": "OPEN",
    "open": [
      {"key": "T1-SPEC", "kind": "DESIGN_VALUE", "what": "T1 的 Lp、匝比与漏感还没有定",
       "scope": "90–264 Vac、5–12 V 输出、空载至 3 A",
       "spec": "Lp 公差、Np:Ns:Na 与漏感上限，使 264 Vac/12 V/0.3 A 下关断时间 ≥ tOFF(min) 且各档穿越频率在内部补偿适用范围内",
       "owner": "磁件设计", "closure": "按 Lp 下限算出的关断时间不小于 tOFF(min)；各输出档满足内部补偿适用条件",
       "undecided": [{"ref": "T1", "parameter": "Lp", "unit": "µH"}, {"ref": "T1", "parameter": "匝比"},
                     {"ref": "T1", "parameter": "漏感", "unit": "µH"}],
       "decides": [{"aspect": "反馈模型与补偿资格", "via": {"condition": "c1"},
                    "rationale": "功率级增益由 Lp 与匝比决定，没有它判断不了是否在内部补偿的适用范围内"},
                   {"aspect": "变换器时序与输出电容条件", "via": {"condition": "c2"},
                    "rationale": "关断时间由 Lp 下限和匝比算出，规格未定时无法和 tOFF(min) 比较"}],
       "severity": {"level": "P1", "class": "REQUIRED_FUNCTION", "affects": "反激输出调节",
                    "consequence": "功率级模型未知时无法证明各输出档在全输入范围内稳定；关断时间低于下限时轻载跳周期"},
       "design_option": {"status": "NONE", "reason": "磁件参数是设计输入，改图不能代替规格",
                         "evidence": [{"source": "evidence/ds/U1.txt", "locator": "p8 Table 6"}]}},
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
    {"id": "PWR-C15.QR-RUN.U1", "review_result": "INSUFFICIENT", "function_id": "FN-QR",
     "aspect": "反馈模型与补偿资格", "open_ref": "FN-QR/T1-SPEC", "…": "…"},
    {"id": "PWR-C04.QR-RUN.U1", "review_result": "INSUFFICIENT", "function_id": "FN-QR",
     "aspect": "变换器时序与输出电容条件", "open_ref": "FN-QR/T1-SPEC", "…": "…"}
  ]
}
```

- 一行只指向一个开放项：PWR-C04 同时受两个开放项影响时，`derive_rows.py` 取 `open[]` 里先写的那个；
  两个开放项各派生一件待办（W-T1-SPEC、W-C5-ESR），待办的 `check_ids` 是指向它的行。
- 共享的是开放项，不是结论：两行各自的方面写在 `decides` 里，等级和 `scope` 写在开放项上。
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

## 四、校验与门禁输出

    python3 scripts/validate_review.py review-plan.json review-results.json --db db.json --lint lint-cold.json --lint lint-hot.json --require-actionable --json review-gate.json

- 退出 0 表示台账有效（结论 NO_GO 也可正常交付）；2 表示台账有错。冻结门加 `--require-release`，NO_GO 也退出 2。
- 校验只证明记录一致，不验证来源文字真实、计算合理或判据穷尽。空计划、遗漏对象、C 写 PASS、NA 冲突、
  无位置/改法、虚假汇总、陈旧规则指纹均被拒绝。
- **自动扫描发现即计划检查**：冷检每条 FINDING/CANDIDATE 在计划里自成一行（id 形如
  `PWR-A01.AUX-DC-b17ec0`，判据为“规则名：发现原文”），像其他检查一样写结论；INFO 进计划
  `diagnostics`（`LINT_INFO`），不计疑点。两次 `--lint` 提供两次扫描的 JSON，
  校验核对每条发现都有计划行；结果不再写 `lint_reviews`。仅 PDF 模式明确 NA 并留依据。
- **输出**：`summary`（检查结果计数、唯一缺陷及 P0–P3）、`categorized_summary`（当前/历史检查、唯一缺陷、
  唯一任务、必需移交及其状态）、`insufficient_by_cause`、`requirement_clarification_summary`、`workflow`、
  `release`/`blockers`、`remediation_validation`、`binding_validation`。
- **quality_screening** 提示理由/影响跨范围复用、位号与声明范围不相交，以及补证对象和接口模式错配。
  影响描述逐字段核对，不以正确的理由或证据位置替代因果核验；原样回显绑定对象/判据不能证明分析成立。
  PWR-C10 的 `qualification_refs` 指向实际已贴电容，连接器身份不能替代电容额定证明；USB 方向分析不能只复用 UART/SPI 的角色。
  仅作提示，不增添缺陷、不改变 release；共享依赖可明确加入对象范围并核对，零提示不证明审完。

## 五、规则指纹与重新审查

计划写入 `review_engine`：SKILL.md、`references/` 与 `scripts/` 的逐文件 SHA256 及总摘要（含未提交修改，
排除测试、缓存、隐藏文件、`.pyc` 和 `~` 备份）。任何规则文字修改都会改变指纹。

- 指纹变化后以当前输入重新生成计划并完整审查；旧 PASS、旧缺口列表不能代替本轮判断。
- 两次扫描的结果合并只接受同一指纹；CLI 校验要求当前指纹。
- 原始 datasheet、已验证模型和计算数据可复用，但先复核型号/版本、工况、保证条件和当前判据。

显式 `intent.devices` 中的关键器件按逐器件身份、工作条件与特殊脚检查展开，不能因位号不是 U/M 而遗漏；连接器仍走其专属检查，不重复生成未用脚项。声明只补覆盖，不替代身份、资料与结果审核。


### 保护时序审查附注

对以关断/响应时间不足为依据的结论，在本项证据或共享记录中给出故障后果、允许窗口、实际响应界、裕量、温度范围及关闭阶段。
可在结果行用可选`timing_assessment`对象记录上述同名英文字段（见最小充分证据）；或用`timing_assessment.evidence`
列出包含完整分析的共享文档定位。它是审查者工程证据，不替代缺口的 `severity`、HANDOFF或风险接受。
质量筛查的`TIMING_BLOCK_WITHOUT_WINDOW`只是需复核提示；补充一个字段不会使设计自动通过。
