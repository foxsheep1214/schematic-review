# intent.json 格式

> 读者：审查员。

审查数据分四份文档：[intent 格式](intent-format.md)（`intent.json`，按需求和设计结果写，不抄设计方的意图文件）、[计划格式](plan-format.md)（`review-plan.json`）、[结果格式](results-format.md)（`review-results.json`）、[校验与重新审查](gate-and-rerun.md)（门禁输出与规则指纹）。计划只决定每项的规则、适用性和准备度，不提前制造 PASS/FAIL；结果另存，由 `validate_review.py` 对账。常规命令见 [SKILL.md](../SKILL.md)。

## 一、intent.json（schema_version 5）

合成示例（数值仅说明结构）：

```json
{
  "schema_version": 5,
  "review_mode": "first",
  "review_phase": "design_iteration",
  "input_sha256": "填写 decoupling.py 候选清单里的 input_sha256",
  "assemblies": [{
    "id": "run-option-A", "citation": "装配 BOM Rev.B 选项 A；跳线表 Rev.C 第 2 行",
    "population": {"U1": true, "C1": true, "C2": false}, "jumpers": {"JP1": "closed"}
  }],
  "devices": {
    "U1": {
      "mpn": "REG-X-ADJ", "package": "SOT-23-3",
      "identity_citation": "BOM 订货码与官方订货表对应行",
      "citation": "REG-X datasheet Rev.A 第 3 页完整脚表", "pinout_complete": true,
      "pins": {"1": {"name": "VIN", "role": "power"}, "2": {"name": "GND", "role": "return"}, "3": {"name": "VOUT", "role": "power"}}
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
     "states_add": ["standby"], "state_requirements": {"standby": "REQ-STANDBY"}, "citation": "Requirements v1.2 section 4.1"},
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

任务书给了几份需求文档，`requirement_source` 就写成列表 `[{"path", "sha256"}, …]`（每份文件各自的 sha256，一个 id 只在一份文档里出现）；只有一份时写成上面的单个对象也行。

- `schema_version` 必写（5）；顶层只认本节列出的字段和各检查器的段（`plan_review.INTENT_FIELDS`），拼错或多写的字段被拒收并提示最接近的字段名。
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
  没有的资料不写，依赖它的检查项等资料。
- `rail_exclusions`：网表上像电源（有 IC 从它取电，或 ≥1 µF 电容到地）而名字不像轨的网，每条都要在 `power_rails`
  声明成轨或在这里写它不是轨的依据，否则拒收；只能排除这类网，且不能同时声明。计划的 `rail_candidates` 列出每条这类网
  及其确认方式（`name` 名字像轨、`declared`、`excluded`）。名字像轨的网照旧按名字识别。
- `rule_gaps`：审查员认为该查、计划里没有的检查。每条写 `id`、`rule`（按总表哪条规则判，不能是 REQ-D01：需求检查项由需求文档生成）、
  `object`（非空；位号须在网表里）、`criterion`、`missing`（工具缺什么规则或推导）和 `basis`（依据）。计划工具写成一项
  `origin: REVIEWER_ADDED` 的检查（`rule_gap` 记缺口编号、`missing`、`basis`），照常判；计划 `summary.reviewer_added` 计数，
  两份记录比较时这些检查项单独列出、不计入配对率；门禁结果 `rule_gaps` 列出每条缺口与结论，报告在“对 SR 的反馈”里列出，
  每条记进改进台账，变成工具生成的规则。
- `assemblies`（1–32 个，各带 `id` 与 `citation`）是全部检查器共用的装配状态；`devices` 是按位号的官方脚表。
  `pinout_complete: true` 的脚表要含封装名说出的每个脚号（QFN-16 → 1..16，SOT-23-3 → 1..3；带原厂代号 `SOT-23-3 (DBZ)` 照读；
  封装跳过的脚号写进脚表并给角色 `absent`——NCP1343 CASE 751BP 的物理脚是 1–8 和 10，`"9": {"name": "ABSENT", "role": "absent"}`，脚差集和脚处置都不算它；
  BGA、模组、SOT-23 这类读不出脚数的不查），缺的脚号列出来拒绝，多出的 EP/PAD 放行；U/M 位号抄全了却没有 power 和 return 脚的，
  计划打 `DEVICE_PINS_NO_SUPPLY` 诊断（去耦组按这两种脚推，没有就整颗没有去耦组），不拒绝——分流基准等确无供电脚的器件不用改；核验类别为光耦、继电器、变压器、整流桥、晶体的不问。
  声明二者或任一检查器段时须带顶层 `input_sha256`，过期即拒绝。
- `devices.<位号>.set_points`：器件选出的输出档位，每组 `{id, citation, points[]}`（`id` 大写，`citation` 是列出档位的手册章节）；
  计划每组给一项 `PWR-C02.SET-POINT-<id>.<位号>` 逐档核输出精度。可编程器件的配置不审（2026-10-26 起）：手册声明的能力判为可达，
  `configurable` 已取消，写了即拒收。计划另有 `GATE_BIAS_ZENER` 诊断：
  接在源跟随器栅极与地之间的齐纳是偏置基准、正常就导通，不派 PRO-C02 两侧窗口，由器件检查项和电路判定核。
- `mission_profile`：所有寿命检查项共用的一份任务剖面
  `{requirement, phases[{name, share, load, ambient_c, citation[, requirement]}], events[{event, count, citation[, refs, requirement]}]}`。
  `requirement` 是给出设计寿命（`lifetime` 参数）的需求；`share` 是这一段占设计寿命时间的比例，各段合计为 1；`load` 是负载占额定的
  比例（0–1）；`ambient_c` 是环境温度；`event` 取 `catalog.LIFE_EVENTS`（开关机、浪涌、故障动作、动作、插拔、充放电循环、擦写），
  `count` 是设计寿命内的总次数，`refs` 只给点名的器件；每个 `citation` 须是所引需求原文里的一段。规则见
  [寿命与耗损件](commodity-floors.md#寿命与耗损件)。
- 需求不手抄：`python3 scripts/requirements_extract.py 需求.md --json record/requirements.json` 逐字抄录需求表
  （首列表头为 ID/编号/需求编号/工程ID 的表格行——首格可以是"编号 标题"，编号取第一个词、标题留作该列的文字——或 `- <编号>：<文字>` 列表项，
  `A.2.2.1/A.2.3：…` 这样斜杠连的编号各算一条、同一段文字；表头不是编号列的表（议题、版本……）不是需求表），每条各列分开、带所在章节与 `文件:行号`，并给文件 sha256。
  `requirement_source` 写文件路径和这个 sha256（任务书给了几份需求文档就写几项，列表 `[{path, sha256}, …]`，逐文件抄录，
  REQ ID 跨文件唯一，两份文档给同一个 id 拒绝；`locator` 带各自的文件名），`requirements[]` 每项只写 `id`、`categories`、`interpretation`
  和 `status`，不写 `text`、`citation`、`criterion`。`categories` 从 [规则总表](check-catalog.md#需求类别与审查方面)
  的需求类别表选一个或几个（表有“怎么选”一列；拿不准就多选，少选是漏查）。分解的单位是需求里的量：带参数的方面由
  `parameters` 里有没有这个参数决定，有就问，不管选了哪些类别；不带参数的方面由类别决定；一个参数都没写的需求才按类别问全部方面，
  计划同时列出原文里没读进参数的带单位数字（`REQUIREMENT_NUMBERS_UNREAD`，扫描时打印；每个数后面列出按单位和类别能收它的参数名，没有参数能收的说明写进 interpretation 或登记 rule_gaps；任务剖面引用的需求不列，剖面就是它的读数）。计划按（需求，方面）各生成一项 REQ-D01，判据取方面模板。
  `interpretation` 写这条需求要在原理图上落实什么（不抄原文），挂在每一项上，不进检查标识；
  不适用的方面在结果里判 NA 并给依据，不从类别里删方面。需求文档里每个编号都要有一项（优化目标、明确排除也一样），
  文档里没有的编号被拒收；文档改了 sha256 就变，重新抄录并复看改过的需求。源不是表格时先整理成同格式的需求表并存档。
  计划的 REQ-D01 项带 `source_text`（出处、章节、各列原文），每个方面检查项结果的 `requirement_clauses` 按顺序拼接都须等于这段原文。
- `requirements[].parameters`：从原文读出的数字，每项 `{name, min, max, unit, condition}`；`name` 与 `unit` 取
  [规则总表](check-catalog.md#需求类别与审查方面)的需求参数表，至少给 `min`、`max` 之一，每个数字须在该条原文里出现
  （`±5%` 同时给出 −5 和 5；数字后紧跟的短横是范围，不是负号），`condition` 须是原文里的一段（如“3 A 线缆时”）。
  参数按规范单位换算后挂在该需求的每一项上（`parameters`，不进检查标识）。计划使用这些数字：
  `power_rails.<网>.voltage_v` 可以只写 `{"requirement": "<需求编号>"}`（该需求同时有输入和输出电压时加 `parameter`），
  窗口取那条需求电压参数的上下限；输入电压、频率写进 SYS-POWER 框架的 `requirement_windows` 和问题；需求给了待机功耗或静态电流（`standby_power` / `quiescent_current`）时 SYS-POWER 多一项 PWR-C16（待机与空载输入功耗上界），需求检查项的 STANDBY_POWER 方面绑它；
  工作环境温度（DEV-C01/C02/C05）和设计寿命（DEV-C02/C06）作为 `conditions` 挂在器件应力检查项上，计划顶层 `conditions` 列出各条来源。
- `requirements[].owners`，**承接电路**：落实这条需求的功能电路、系统功能或接口的 id。规则总表给每个审查方面列出承担它的检查和可承接的电路类型；
  计划替每个需求检查项找出**可承接的电路**，写在 `owner_candidates`（拥有承担该方面的检查项的所属里，电路类型、系统功能、接口种类在该方面那一格里的那些；表外的不算）。
  **有可承接的电路的需求必须写 owners**（DEFERRED 的除外），没写的计划拒绝生成并打印它们；审查员认定没有承接电路时写 `owners: []`
  加能定位的 `no_owner_reason`，需求检查项自判（检查项记 `self_judged: DECLARED`，“审查员认定没有承接电路”）；没有可承接的电路的不要求写，需求检查项自判
  （`self_judged: NO_OWNER_CANDIDATE`，“没有可承接的电路”）。写了可承接之外的 id 允许，计划打诊断 `REQUIREMENT_OWNER_OUTSIDE_CANDIDATES` 供复核。
  只有一个可承接的电路也要手写，不自动填。
  计划把需求检查项绑定到这些规则中 `owners` 拥有的检查项，没写 `owners` 时全板方面（器件温度等级、按温度降额、寿命）绑定全板这些规则的检查项，
  写在需求检查项的 `bound_checks`（不进检查标识，校验时重算，点名的 id 必须拥有计划里的检查项）。有绑定检查项判过（不算 NA）的需求检查项不再另判：
  读取时取绑定检查项中最差的结论派生（`derived_from`；FAIL 带上该发现项并把需求检查项加进它的 `check_ids`，INSUFFICIENT 带上 `open_ref`），
  手填的需求检查项只对账不覆盖；校验要求结论等于绑定检查项中最差者，这种检查项不要求条款。没有绑定检查项、或绑定检查项全是 NA 的方面由需求检查项自己判，照常拆条款。
  有参数的方面（如 TEMPERATURE_GRADE 的 °C）只从经需求条款或经该参数单位的限值的失败边继承 FAIL（`requirement_bindings.fail_counts`）：
  绑定检查项因别的量失败（齐纳低电流 VZ）时失败留在该检查项，需求检查项写明不继承；INSUFFICIENT 照旧继承。
- `requirements[].status`：已确认（CONFIRMED）或暂缓（DEFERRED，用户明确暂缓，不生成检查项，报告列在“本次不审的范围”）。
  先按 [需求原文到审查要求](requirement-clarifications.md#需求原文到审查要求) 分清确实待用户决定的需求；
  没说清的不留“未定”或“提案”状态，当场问用户，问题和答复写 `clarifications`。
- `clarifications`：问用户的需求问题和答复（字段与规则见 [需求澄清](requirement-clarifications.md)）。
  答复 DECIDED / ADOPTED_PROPOSAL 的澄清编号成为一条需求，`requirements` 加同编号的一项、`status: CONFIRMED`，原文就是答复的文字；
  DEFERRED 把点名的需求改为暂缓。有问题没答复时，候选、带候选的扫描和门禁都拒绝往下做（审查停在第①步）。
- `power_rails` 支撑 PWR-C01 与 DEV-C05：给电压/最大负载、源端最弱保证可供电流和条件；READY 不等于 PASS。
  片内稳压输出（如 MCU 的 1.1 V 内核轨）、仅板内使用的中间轨同样要声明电压：阻容预判按同簇器件的全部供电轨定界，缺一条就整簇不出预判。计划命令末尾会列出“未声明电压的轨”及受阻检查项数，能从稳压器手册或需求定出时补齐后重跑。
  隔离或多地设计给各轨与各地写 `domain`（如 PRI/SEC），地写 `voltage_v: {min: 0, max: 0}`；栅极/检测节点可按计算声明窗口。
  窗口由审查者独立定界：取需求输入范围、稳压器/钳位/保护门限的保证值和故障上限，逐条写 `citation`；不取设计方计算的数值。
  合并扫描前 `power_rails` 仍为空却有 DEV-C01/PWR-C10 项，属审查准备未完成，先补齐再录结论。
- 条件导通另可声明 `power_sources`（某状态的供入节点）与 `power_paths`（某状态可导通的方向，不是理想短路或载流声明），
  不得把未上电的稳压器或端口标成 source 来消除告警。
- 各检查器的 intent 段（`i2c_topology`、`decoupling`、`device_kinds` 等）见 [自动检查](automation.md)。
  `device_kinds` 也覆盖集成电路：每颗 IC 声明手册标题给出的角色（角色登记表 `catalog.DEVICE_ROLES`，见
  [检查目录·器件角色](check-catalog.md#器件角色)；标题没有任何登记角色的写泛称 ic，计划列成 `DEVICE_KIND_GENERIC` 诊断），
  没有核验过的角色是 DEV-D02 的缺口；角色决定电路候选的核心器件和它生成的电路类型。
- 计划顶层 `domains`（参考地分区、跨域器件、核心器件、截止网络，由 `checkers/domains.py` 按地的直流连通推导）见同文。
- **电路不手画**：`circuits` 由 `record/circuit-candidates.json`（`scripts/circuit_candidates.py` 从网表、已核实的器件类别和检查器库存生成，见[自动检查](automation.md)）与 `circuit_decisions` 推出，
  `python3 scripts/circuit_decisions.py intent.json record/circuit-candidates.json --db db.json --write` 写入 `circuits` 和 `circuit_candidates_sha256`；
  lint/计划对声明电路的 intent 必须带 `--candidates`，手写的电路列表与决定推出的不相等即拒绝（类型、成员集合、工作态、候选编号逐个比较）。
  `circuit_decisions[]` 每条对一个候选做一种决定，每个候选恰有一条：
  - `accept`：原样接受，可给名称 `id`；加工作态写 `states_add`，并在 `state_requirements` 里给每个加的态点名一条需求（`{state: REQ id}`），
    那条需求的原文要说到这个态（待机/空载、掉电、热插拔、短路、突发/轻载……，`catalog.STATE_WORDS`），`citation` 仍要可定位；
    一句泛引文不能给每块电路都加态。候选的态是类型的固定表。
  - `merge`：`candidate` 列几个候选，`id` 必填，`citation` 引一条把它们描述成一个流程的条款；电路候选不与跨电路候选（ISOLATION、STARTUP、保护链）合并。
  - `split`：`into: [{id, members}]`，每部分成员是该候选成员的子集，所有成员都要有去处，`citation` 可定位。
  - `reject`：`reason` 为 OUTSIDE_SCOPE / NOT_A_CIRCUIT / DUPLICATE_OF（后者带 `of: <已推出的电路>`，成员须都在它里面），`citation` 可定位；被拒候选的成员进 REQ-Q08 复核，已被接受、合并、拆分或 add 的电路持有的除外。
    拒绝一颗没有候选的器件写 `{"decision": "reject", "ref", "reason"（OUTSIDE_SCOPE / NOT_A_CIRCUIT）, "citation"}`：它不再进 REQ-Q08 清单，原因随记录。
  - `add`：生成器没找到的功能，`id`、`type`（规则总表的包名）、`members` 只能收 `unassigned` 中的器件、`via` 为每颗写它所在的网，`citation` 可定位。
    `id` 若是前面决定已推出的电路，器件并入那块电路（`type` 须一致），不另起电路——驱动变换器开关的门极驱动、使能驱动管都这样归位。
  - 未归属的有源件（候选文件 `unassigned` 里 kind 为 mosfet / bjt / opto / ic 的）必须有 add 或 reject 决定，留在 REQ-Q08 清单上校验不过；两端件照旧留在 REQ-Q08。
    候选走线从电路自己的网走到小信号三极管的门极/基极时把它收进电路并从漏极/集电极继续（成员 role `driven_switch`），所以多数驱动管不会落到未归属。
  - `own`：`ref`、`candidate`、`citation`（可定位）：同一级认领打平的器件归 `candidate` 所在的电路。只裁定打平，不改已有的归属；每颗至多一条。
  推出的电路带 `id`、`type`、`refs`、`owned`、`nets`、`states`、`citation`、`candidate_ids`、`cross_cutting`、`anchors`。
  `refs` 是电路持有的全部器件，`owned` 是其中归它所有的：每颗被持有的器件恰好在一块电路的 `owned` 里，其余持有它的电路只引用它
  （可在条件与计算里引用，计划不为它生成检查项）。归属在决定后保留的电路之间按认领强弱判定：电路的核心器件 > 电路成员 >
  电路里的端点类角色（端口的 PD 控制器）> 链路成员（启动链、保护链）> 隔离带 > 链路的核心器件与端点；被拒或判为重复的候选让出的器件
  由下一个认领者拥有，打平的要 own 决定。一颗非核心器件最多被两块电路持有。
  审查员认为候选漏了器件，不往电路里手加：那是规则或网表的缺口，记在 REQ-Q08（候选生成没有归属的器件逐颗列出）并改规则。
