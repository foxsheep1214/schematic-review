# 报告与修改说明

报告正文只写结论和需要处理的事项，详细台账与计算放可定位的附录；无内容不设空节。
结果字段以 [计划与结果台账](plan-and-results.md) 为准，分级与准出以 [结论与准出](verdicts-and-release.md) 为准。

**报告由 `scripts/render_report.py` 从台账生成**，顺序固定：数字一览（各类计数，每类一行）→ 结论（第一段用白话回答能否定稿、电路和文档各有几处错误、还有几件事因为什么判断不了及其中 P0 数；接着审查员 `summary`；“最先要解决的”列后果最重的三件待办，标题在前、待办编号在后；“定稿还差”只列错误和待办以外的定稿条件；最后一段说明审查阶段和是否看过上一版审查。检查条数和自检提示不上结论）→
电路错误 → 待办（一个列表，按可能后果从重到轻）→ 交给后续环节的要求（随图交出，不卡定稿）→
对 SR 的反馈（设计者不用处理，默认折叠：工具判断不了、已手工核对的检查 `sr_improvements`，审查员的 `notes.sr_feedback`，自检提示按代码分类）→ 索引（`record/` 里每个文件装什么）。
结构和数字只来自台账，不手改报告；要改内容就改台账（任务的 title/root_cause/reason/next_action、检查的 gaps、
finding 的 remediation、handoff）后重新生成。下文各节规定这些字段写什么。agent 只通过 `notes.json` 补白话：

```json
{"summary": "1–3 句：和上一版比变了什么、设计者现在先做什么，写给硬件工程师",
 "items": {"<任务或 finding ID>": "一两句白话：这件事是什么、为什么要做（待办里以“审查员补充”一条列出，不另起段落）"},
 "sr_feedback": [{"kind": "false_alarm", "rules": ["SIG-T01"], "instance": "本板实例：哪个对象、SR 怎么判、实际是什么",
                  "suggestion": "SR 该怎么改（规则、别名、模型或说明）"}]}
```

`summary`、`items` 只说这块板：SR 自身的误报、提示数量、改进效果一律写进 `sr_feedback`，
渲染脚本遇到这类文字会拒绝出报告。打包时的白话检查跳过“数字一览”（标签由脚本固定），到“对 SR 的反馈”为止；
这一节和索引是给 SR 维护者的，允许出现规则名和术语。

`sr_feedback` 记录审查中发现的 SR 自身问题，按 `kind` 分类：`false_alarm`（误报）、`over_strict`（规则过严或关闭
条件不合理）、`missed`（漏报：问题是审查者自己找到的）、`unclear`（说明不清或互相矛盾）。每条必须点名规则编号、
本板实例和建议；格式不对时 `render_report.py` 报错退出，不静默丢弃。它和工具拦住、审查者已手工判定的检查（`manual_verification`）一起渲染在“对 SR 的反馈”一节，分小节列出。

程序错误用 `software_bug`，自动化模型或输入格式不足用 `coverage_gap`，不要把专家流程已发现的错误说成整轮漏检。
首页先回答能否定稿，再说已确认的电路/文档错误、判断不了的事项及其潜在 P0 数和最先要解决的待办；提示数量只出现在“数字一览”，代码名只出现在“对 SR 的反馈”；
检查行计数只在“数字一览”展示，同一原因跨多规则/状态展开不重复计成多件问题。
工具维护反馈与逐项规则解释默认放在可展开的 `<details>` 中，完整依据、关闭条件和原始台账照常保留。
简洁不通过删除未解决项、降低等级或截断唯一关闭条件来实现。

notes 不能改结论或计数，不写内部代码名（gap_cause、documented 等），不重复任务字段已有的内容。
任务按上面的五行显示，标题直接点名器件或环路。
字段都在开放项上：`what` 写具体缺口，`why` 只补实际影响；`scope` 写适用器件与工况；
`spec`+`owner`（设计要定的量）或 `acquisition`（厂家资料）写具体动作及资料取得方法；`closure` 写可复核的通过标准。
不用“隔离资格、独立关闭义务、角点闭合”等说法；分别写器件允许的工作条件、需要补的具体内容、各输入/负载/温度组合怎样才算通过。
不同工作条件重复索取同一资料时合并，保留所有不同的通过标准；不能只显示前三条而隐藏其余要求。
同一动作、同一范围、同一通过标准才合并任务；仅资料来源相同可以合并取资料动作，不能合并不同电源环路的判定。
优先复用审查时已取得的资料和计算，仅整理报告时不增加检查、试验、填表或补资料要求。

任务的 title / root_cause / reason / next_action、gaps 和 handoff 按写给硬件工程师的白话写：
用器件位号、网络名和物理量说事，不写 SR 内部的规则号、字段名、工具名或“伪填”“签 PASS”这类审查行话；
一个字段一两句，细节放检查行的 rationale。finding 的 title / observed / impact / recommendation / verification
和 remediation 的 purpose / steps 同样原样进报告。

- 这些词读者看不懂，进报告的文字不能出现：冻结、闸门、原生、下游、移交、接收方、闭合、绑定、本行、证据不足、
  技能、remediation、handoff、fit。分别改说：定稿、KiCad 导出的、后续环节、交给、负责方、解决/算完、对应、
  （写出位号）、资料不足、（不写）、修改方案、交给后续环节的要求、装配/要装。`pack_review.py` 检查报告正文，
  出现就打包失败，改记录或 notes 后重新生成。
- handoff 的 `constraint` / `verification` 要能脱离检查行单独读懂：写出具体位号、网络和数值，不写“本行”“本项”。
  只写本设计算出来的要求；“回路尽量短、去耦就近、注意散热”这类通用布板常识不写（见
  [HANDOFF](verdicts-and-release.md#4-handoff-与集成约束)）。
  报告按负责方合并这些要求，并自动列出涉及的位号；同一负责方下的要求写法一致时只显示一次。
审查目录只有 `审查报告.md` 与 `record/`（见 [留档](inputs-and-coverage.md#留档)），不另写 README、说明或 HTML。

## 每节怎么写

每节只回答一个问题；一句话只说一件事，前面说过的后面不再说。

| 节 | 回答什么 | 谁写 | 怎么写 | 不写 |
|---|---|---|---|---|
| 数字一览 | 各类有多少 | 脚本 | 第一行是功能判定的通过/没通过/未定；每类一行，为 0 也写 | — |
| 结论第一句 | 能不能定稿；错在哪；几件事判断不了、为什么 | 脚本 | — | — |
| 结论第二段 `summary` | 和上一版比变了什么；设计者现在先做什么 | 审查员 | 1–3 句，写位号和具体决定 | 能否定稿、错误数（第一句已说）；审查过程（用哪版 SR、重新导出、逐页读图、复算）；SR 自身问题 |
| 最先要解决的 3 件事 | 先做哪几件 | 脚本 | 标题在前，等级和待办编号在后 | — |
| 各功能的判断 | 每个功能能不能用、差多少 | 脚本（功能判定） | 一行一个功能：问题、结论（通过/没通过/未定）、计算结果与余量、待办编号 | 检查条数、规则号 |
| 发现的错误 | 每处错在哪、怎么改 | 审查员（finding） | 问题写看到的事实和资料页；后果写对这块板的影响；怎么改写改哪个位号、改成什么 | 规则号、审查行话 |
| 待办 | 每件缺什么、怎么补 | 审查员（work item 与缺口） | 固定五行，见下 | 同一句套在几件待办上 |
| 交给后续环节的要求 | 交给谁、做什么、怎么验 | 审查员（handoff） | 一件要求一行；只差位号的要求合成一行，位号列在“涉及位号”，验证写“每只” | 通用布板常识；“本行”“本项” |
| 对 SR 的反馈 | SR 哪里不对、该怎么改 | 审查员（sr_feedback、manual_verification） | 每条点名规则、本板实例、建议 | 板子本身的问题 |
| 索引 | 每个记录文件装什么 | 脚本 | — | — |

待办固定五行，每行只装一种内容：

- **缺什么**（开放项的 `what` + `scope`）：哪个器件缺哪个数或哪项设计没定，适用哪些工况。
- **为什么要紧**（`why`，无则 `severity.consequence`）：缺了它判断不了什么、可能出什么事。只复述“缺什么”的句子不显示；三件以上共用的句子也不显示。
- **已查过**（`acquisition` 开头的“已读……”）：读过哪份资料哪几页、查到了什么。几处写的同一份资料只显示一次。
- **还要做**（其余部分：DESIGN_VALUE 是“由 {owner} 确定：{spec}”，VENDOR_DATUM 是 `acquisition`，失败项是“按发现项 … 的改法处理”）：向谁取得什么、算什么、改什么。
- **怎样算通过**（`closure`）：可以复核的数值或条件。

`notes.items` 写成“审查员补充”，只写以上五行里没有的取舍或先后，不复述。

## 一、报告结构

### 1. 结论与范围

- 写明板卡/原理图版本、装配配置和首审/复审基线，链接输入清单，说明 PDF/网表同版核对结果。
- 按阶段给结论：非冻结阶段说明已证实功能、真实缺陷、仍影响本体判断的疑点和集成约束，以及本轮先做什么；
  申请冻结时给出可冻结、有条件冻结或不可冻结及主要原因，有条件冻结须有实际接受记录。
- 设计迭代阶段的首段按“唯一根因”写：确认缺陷数、潜在 P0 根因数、本轮设计任务数（`current_work_items`）、
  移交到样机的任务数，再给每个本轮任务一句话。检查行数放在下面的计数表，不写进标题或首句；
  一个根因按多个状态/规则展开出的几十行是同一件事，不说成“还有几百项没过”。
- 质量提示（`quality_screening`）中有 TEMPLATED_SEVERITY_REASON / UNIFORM_SEVERITY_WITHIN_RULE 时，先重新定级再出报告；
  来不及时在结论里写明“等级尚未逐行复核”，不把模板等级当结论展示。
- BOILERPLATE_ACQUISITION / TEMPLATED_DESIGN_OPTION_REASON / TEMPLATED_WORK_ITEM_REASON 表示多件待办共用同一句“怎么拿资料”、同一句“为什么不改图”或同一句 `reason`；逐件写出真实来源（文件、供应商联系、测量）、不改图的具体理由或该件为什么在这个阶段、为什么这些检查归一件，或提出改法。三件以上共用的 `reason` 报告不显示。报告结论里的自检行只报数量，不改结论。
- MARGIN_COMPUTED_BUT_OPEN 表示记录里已经算出了“X > 限值”之类的余量，检查却仍是证据不足：余量够就判 PASS（B）并写明假设和样机实测移交，不够就判 FAIL 或风险并给改法。DESIGN_VALUE_ASKED_OF_VENDOR 表示设计没定的量写成了向厂家索取：反算允许范围写成设计规格，见 [判“证据不足”之前先定界](evidence-proportionality.md#判证据不足之前先定界)。
- FIRMWARE_IMAGE_RECORDED_AS_DESIGN_GAP 表示把烧录镜像/读回/量产校准记成了阻塞冻结的设计缺口；改成判原理图前提 + 阶段 NA 移交固件。CALCULATION_RECORDED_AS_DATA_GAP 表示资料已读只差计算；本轮算完或交 ASG。DUPLICATE_WORK_ITEMS 表示同一方法套在几个对象上被拆成了几件；合并成一件多位号。
- PORT_OVERVOLTAGE_GRADED_BELOW_P0 表示后果写的是端口/负载过压，类别却藏起了这条路径；按危险度表改类别，锁定式 OVP 是降级理由时写进 exclusion。REQUEST_SCOPE_ECHOES_TASK / TEMPLATED_HANDOFF 是写法问题：适用范围写工况不写标题，移交表逐条写要做要测的事。
- WORK_ITEM_MIXES_LEVELS / WORK_ITEM_MIXES_HAZARD_PATHS 表示一件 P0 待办夹带了 P1 分支或两条危险路径；拆成各自的待办，或在 reason 里写明为何同根因。REF_GLUED_TO_VALUE / OVERPRECISE_CLOSURE_VALUE / ACQUISITION_WITHOUT_LOOKUP 是写法问题：分开位号和数值、通过条件不写算例中间值、缺资料先写查过哪页。
- 结论里“N 件待办阻塞定稿”只计阻塞项，“仍待确认 M 件”计全部待办，二者可以不等；“交给后续环节”表按检查逐行列出，便于接收方逐条销项。
- `release` 是冻结闸门，非冻结阶段不能当作总判定，也不能反过来把真实电气阻断项改成 PASS；
  `valid=true` 只表示记录可对账，不作“审查通过”展示。
- 审查未完成时写明“审查进行中”，只交进度和剩余工作；仍有 REVIEW_INCOMPLETE 行时 `pack_review.py` 拒绝打包。仅 PDF、外部缺证等限制直接说明影响，不写长篇免责声明。
- 复审概括本轮新增、修复、撤回和仍开放的事项，历史数量不混入当前缺陷。
- 有开放的需求澄清时，结论里单列“需求说明问题”一段，直接说明：本轮有 N 项证据不足是需求说明不明确造成的，不是电路缺陷，也不是缺器件资料。逐个澄清项写：需求原文（或“未提及”）→ 不明确在哪里 → 建议补入需求说明的条文 → 关联几项检查、未定前的冻结影响。N 取 `requirement_clarification_summary.insufficient_from_requirements`。

默认 `--detail compact`：正文列全部唯一缺陷、任务及各自通过标准，逐项依据链接到保存的台账；
`--detail full` 另展开逐条说明。两种模式使用同一结果和计数，不省略未决项、不替换结论。
待办的等级、补证要求和改法都来自它派生自的开放项，不传播同一功能里其他开放项的等级。

报告开头的“数字一览”由脚本从 gate 生成，每类一行，为 0 也写出；报告正文用中文标签，不出现内部代码名。口径如下：

| 计数类别 | 取值 | 来源 |
|---|---|---|
| 检查结果 通过（PASS）/ 不符合（FAIL）/ 证据不足（INSUFFICIENT）/ 不适用（NA）/ 本阶段不判，移交下游（NA_OUTSIDE_STAGE） | 当前检查行数 | `review-gate.json` 的 `categorized_summary.current.results`；复审另列 `history`（REQ-H02 历史处置），不混入当前 |
| 确认缺陷 P0 / P1 / P2 / P3 | 唯一缺陷数 | `summary.by_severity` |
| 证据不足项潜在等级 P0 / P1 / P2 / P3 / 需求未定（不定级） | 当前 INSUFFICIENT 行数 | `review-results.json` 中 INSUFFICIENT 行的潜在等级（各缺口 `severity.level` 中最高的一级）；`gap_cause` 为 REQUIREMENT_OPEN 的行不定级，计入“需求未定”，各项之和等于当前 INSUFFICIENT 数 |
| 证据不足原因 REQUIREMENT_OPEN / EXTERNAL_DATA / DESIGN_OPEN / REVIEW_INCOMPLETE / USER_DEFERRED | INSUFFICIENT 行数 | `insufficient_by_cause`（未填原因的计为 UNSPECIFIED，应补填） |
| 影响分级依据完整 / 未完整、冻结阻断 | 当前证据不足行数 | `categorized_summary.insufficient_impact` 的 documented / undocumented / blocking；有等级无依据的行仍计入未完整 |
| 电路改进建议 PROPOSED / NONE | 唯一任务数 | `workflow.design_options`；只统计带 `design_option` 的任务 |
| 移交状态 OPEN / ACCEPTED / VERIFIED | 必需移交的检查数 | `categorized_summary.handoffs_by_state`；只统计 `required: true`，集成约束（`required: false`）不计入 |
| 需求澄清 开放 / 其中阻断 / 其中已覆盖 / 已解决 / 已撤回 | 唯一澄清项数 | `requirement_clarification_summary` 的 open / blocking_open / covered_open / resolved / retracted |
| 需求说明不明确导致的证据不足 | 当前 INSUFFICIENT 行数 | `requirement_clarification_summary.insufficient_from_requirements`（即 gap_cause 为 REQUIREMENT_OPEN 的行） |

工具输出省略的类别按 0 补齐。检查行数、唯一缺陷数、移交数和澄清项数口径不同，不相加。

### 2. 处理清单

按紧迫性列全部需处理事项。同一根因或独立决定一行，用“类别”区分：电气缺陷、需求澄清、
证据/设计缺口、审查待完成、下游移交、集成约束、可选改善。
阶段 NA 单列为“本阶段不判，移交下游”（结果计数键 `NA_OUTSIDE_STAGE`），与普通 NA 分开，不计入设计缺证；
需求追溯表中 `stage_scope.requirements_pending_downstream` 的需求行标“待下游验证”，不写“不适用”。
EXTERNAL_DATA / DESIGN_OPEN 项展示开放项的补证要求（spec/owner 或 acquisition）及复审关闭条件（closure）。

| ID / 类别 | 位置、问题及依据 | 影响 / 冻结影响 | 建议及下一步 | 关闭条件 / 时点 / 状态 |
|---|---|---|---|---|

- **电气缺陷**标 P0–P3，写清不满足的判据、工况和影响，链接证据与计算，按下文“修改说明”给改法。
- **需求澄清**写需求原文（或“未提及”）、已核输入、建议补入的需求条文、责任方和关闭依据，见 [需求澄清项](requirement-clarifications.md)；不套缺陷等级。
- **证据不足**写已知什么、具体缺什么、影响哪个判断、如何关闭；先完成现有资料支持的分析，同一补证动作只列一次。
  潜在 P0–P3 按 [危险度分类原则](verdicts-and-release.md#证据不足的危险度分类原则)，写实际后果路径、独立保护/排除依据及调整等级的条件；
  与冻结影响分别展示，不把补证难度或 C 置信度当危险度，也不称潜在等级为已确认缺陷等级。
  任务有电路改进建议时，在“建议及下一步”栏先写改法要点，再写“改后可规避”的问题和关闭的检查，
  最后写补证路径；详细改法放下文第三部分。
- **下游移交/集成约束**写接收角色、定量约束、验证方法与阶段，引用真实接收记录。
- 待核请求和共享任务逐检查列出本对象的器件、供电/返回域、工况、所缺事实与关闭证据；先区分脚号/功能/连通、参数保证与实物效果。接口速率、电平或固件仲裁不能证明缺失的接触编号；另一接口或去耦组的资料不能关闭本条。已有资料支持的窄连接判断独立结论，保留其余适用电气缺口。
  共享任务的摘要、每个操作步骤、前提、影响、复验与逐项关闭证据均须匹配这个范围。跨组动作明确为独立依赖，不能把别组条款写成本组必做改法；按现有任务字段复核，不新增填表要求。
  移交只列本装配实际适用的物理义务；无适用负载、虚设脚或未贴组不沿用通用强制任务，可选装配另列前提。同对象的其他适用布局义务仍独立保留。
- 同一问题关联多个检查只统计一次并保留关联 ID；不把检查行数或质量提示数称为缺陷数。

交付前确认每条不通过或待关闭事项都有明确建议与关闭条件；不能用“不通过/待验证/参考手册”代替动作。

### 3. 证据与追溯附录

“逐项检查说明”只展开没通过和资料不足的检查：给出盲区、关闭条件和常见误报，并保留本次结论依据，
正好告诉设计者要补什么；不适用的只写一句理由；通过项不展开，避免淹没真正的待办。
结果行只改了某个字段时，该字段标“本次对象说明”，其余沿用计划通用说明。
通用盲区不称为已发现问题。写法见 [每项检查的盲区与关闭条件](plan-and-results.md#每项检查的盲区与关闭条件)；
历史计划缺说明时不从当前规则自动补写。


可直接链接已有持久化文件，不必再造同内容表格：

- 输入版本/哈希、需求、装配与规则指纹；PDF 页码/页名/网表路径映射，未知标 UNKNOWN。
- 全量检查台账：对象、判据、结果、证据、计算，以及关联的 finding/澄清/任务/移交；冷热候选处置和覆盖统计。
- 实际计算、图面记录和修改明细；相似器件参数、反算要求与本器件事实分清。
- 复审的 Diff、历史 ID 到本轮结论的映射、关闭/撤回依据及复验证据；未执行的复验不能关闭。
- `review-gate.json`。质量提示的核查结果记在相应证据中，不另建“语义审查报告”。

## 二、修改说明（让硬件新手能执行）

目标是让读者能根据原理图定位并完成编辑，知道哪些参数已有依据、哪些仍要确定、用什么结果验收。
指导编辑不等于授权代改设计。真实位号/物理脚来自当前版本；新器件写“建议新增，位号待分配”，不伪称已有空闲位号。
证据不足/待决项同样给补证或设计动作和关闭条件，但不冒充已确认缺陷。

### 修改准备度

| readiness | 报告中文 | 适用条件 |
|---|---|---|
| READY | 可直接修改 | 连接、规格和前提已齐；无未决选型/输入 |
| CONDITIONAL | 条件满足后修改 | 拓扑方案已明确，参数或资料前提未齐；给取得及判断方法 |
| DESIGN_REQUIRED | 需要重新设计 | 架构、模式、控制脚或接口方案未定；先列设计步骤和选择依据 |

准备度与严重度、置信度、关闭状态彼此独立。READY 不表示可以直接上电或修改已验证。
不得用 CONDITIONAL/DESIGN_REQUIRED 逃避现有资料可完成的计算、连接核对和具体操作。

### 每项应说清的内容

1. **定位和目的**：PDF 实际页/页名、位号.物理脚、网络；用一句普通话解释应恢复的行为，
   例如“上拉电阻使控制脚在主控接管前保持高电平”，再说明该高电平对应开还是关。
2. **前后状态**：旧→新值/装配/网络；换源时先写断开哪条旧连接，再写新路径，路径写成
   `源物理脚 → 网 → 已贴器件.脚 → 网 → 接收物理脚`。仅加同名标签可能合并所有同名端，须列受影响成员。
3. **顺序操作**：定位 → 断旧/改件 → 连新 → 更新 BOM/装配 → 检查；只写实际必要步骤，不猜 EDA 菜单。
   分压、多级开关、二极管方向等需图形才能说清的给小图或连接表，标清脚号。
4. **规格与依据**：被动件给值/精度及相关功率、耐压、封装、贴装；保护/有源件给所需范围与物理脚定义，
   精确 MPN 须有原厂依据。给公式、实际输入、公差/温度边界、结果与验收窗；未知项说明取得处和选择方法，
   如“取得最大输入电压后按 P=V²/R 计算，再按温度降额曲线选额定”，不能只写“重算”。
5. **联动及验收**：指出需要一起解决的 ID 和改后受影响状态；每条验证写方法、测点/工况、预期结果。
   区分网表/计算验收与 PCB、固件、实物验证，不把待做测试写成已通过。

不能只写“接到合适 GPIO”“加 ESD”“参考典型应用”“复算环路”“加 10k 上拉”这样的终点句；
没有取得某颗 IC 的实际脚表就写清缺口，不为显得具体而编造脚号。选项较多时给推荐方案及选择条件。

### 三种修改的尺度（合成示例，数值不可复用）

**连接/装配已有唯一依据**：p2 的 R10 为已确认的 10 kΩ 上拉，`R10.1→3V3；R10.2→U2.4` 已接对，但装配为 DNP。
将 R10 改为贴装、导出 BOM 数量恢复为 1、阻值保持；规格 1%/0402/≥0.063 W，最坏 3.465 V、−1% 阻值时功耗约 1.22 mW。
验收：新网表/BOM 中 R10 为已贴，两端分别在 3V3 和 U2.4 所在网。

**方向明确但参数未定**：输出泄放。先画清 `VOUT → R_new → GND` 的并联支路；从受控要求取得
Vmax、Cmax、Vsafe、tmax、温度，按 `R ≤ tmax/[Cmax·ln(Vmax/Vsafe)]` 计算，再核 `Pmax = Vmax²/Rmin`、
公差及功率降额。只有条件算例时标“候选，不能据此定版”，并写明取得哪些输入后可改为已选。

**需要重新设计**：默认关断链。先列输入电源与控制电源有/无、主控复位/高阻/运行时的目标输出；
核 EN 极性与门限、内部默认拉阻、掉电耐受；推荐能覆盖状态表的拓扑，标出接入点，给电平/电流不等式和选型方法。
主控脚未分配时须取得 pinmux 表，不能臆造“空闲 GPIO”，也不能以“找专业人员处理”代替设计说明。

### 结构化字段

`--require-actionable` 时每个 finding 带 `remediation`（写了也一律校验）：

```json
{
  "remediation": {
    "readiness": "READY",
    "purpose": "使主控复位期间输入保持规定的高电平。",
    "prerequisites": [],
    "steps": [{
      "kind": "ASSEMBLY",
      "target": "PDF p2 R10",
      "before": "DNP，不贴装",
      "after": "贴装，BOM数量1；阻值10kΩ保持",
      "instruction": "在当前配置中启用R10贴装，并同步BOM装配选项。"
    }],
    "parameters": [{
      "target": "R10",
      "specification": "10kΩ，1%，0402，额定≥0.063W，贴装",
      "status": "SELECTED",
      "basis": [{"source": "synthetic-requirements.md", "locator": "SYN-R1 and power calculation"}]
    }],
    "related_findings": [],
    "impact_review": "核3V3存在而主控复位的默认态；输出灌电流按已列规格核算。",
    "verification": [{
      "stage": "NETLIST",
      "method": "导出本配置网表和BOM，逐端检查R10。",
      "expected": "R10已贴；R10.1在3V3，R10.2与U2.4同网。"
    }],
    "calculation_preflight": {"applicable": false, "reason": "恢复受控贴装，无数值推导", "evidence": [{"source": "synthetic-requirements.md", "locator": "SYN-R1"}]}
  }
}
```

- `steps` 按顺序执行，至少一项；`kind` 为 CONNECT / COMPONENT / ASSEMBLY / DOCUMENT / DESIGN，每步 target/before/after/instruction 非空。
  CONNECT 另给 `remove_connections`/`add_connections`（`{"from":"R1.2","to":"U1.3"}`），至少一侧非空。
- `parameters` 每条 target/specification/status/basis 非空；status 为 SELECTED / CANDIDATE / TBD，后两者另给 needed_input 和 selection_method。
  COMPONENT/ASSEMBLY 步骤至少有一条规格记录。
- `prerequisites` 每项含 input/reason/how_to_obtain/acceptance；READY 必须为空且不含候选参数或 DESIGN 步骤，其他准备度至少一项。
- `related_findings` 指向同报告其他 finding；`impact_review` 非空。
- `verification` 至少一项，stage 为 NETLIST / CALCULATION / DOCUMENT / BENCH / PCB，且至少一项属于前三类。
- `calculation_preflight`：有数值推导时给 calculations（合同见 [计算条件合同](calculation-preflight.md)），参数用 `calculation_ids` 关联依据；
  READY 必须有适用条件下成立的计算，不能依赖窄条件之外的保证值、典型值或未关闭假设。
  纯文档、恢复受控连接/贴装等无数值推导的修改可声明 `applicable: false`，给 reason 与可定位 evidence。

校验加 `--require-actionable`。校验器只检查结构和准备度矛盾，不能证明操作语义或计算正确；
交付前按这些步骤对照真实输入逐项演算一次。

## 三、证据不足项的电路改进建议

证据不足项不是缺陷，但很多缺口可以靠改图直接消除，比等资料更快、更确定。凡任务关联了 EXTERNAL_DATA
或 DESIGN_OPEN 的证据不足项，都要回答“改图能不能消除它”（判断方法见
[能否用电路修改消除缺口](evidence-proportionality.md#能否用电路修改消除缺口)）。

报告里每条建议写清四件事：

1. **改法**：与上文修改说明同样具体，定位、旧→新、规格和依据、顺序操作。
2. **改后可规避的问题**：按改后电路说明原来的风险为什么不再存在，例如“改后最低供电只取决于
   VRAW 下限和二极管 VF 最大值，不再依赖亚 mA 齐纳电压，DEV-C05.U701 等 15 项可按保证值判定”。
   写清哪些检查因此可以闭合；只是缩小缺口的，写剩下什么。
3. **代价与新风险**：成本、体积、损耗、热、绝缘、需要修改的已确认规格；新引入的风险同样列出，
   不能只写好处。
4. **推荐顺序**：先改图还是先补证，理由是什么。原厂不会提供的保证（器件在测试条件外）推荐先改图。

建议不改变本轮结论和计数：该项仍是 INSUFFICIENT，改图后经复审才能关闭。需要改已确认规格的建议，
写成待用户决定的前提。

结构化字段写在任务的 `design_option`：

```json
{
  "design_option": {
    "status": "PROPOSED",
    "summary": "SR 控制器供电改为经肖特基取自输出，去掉低电流齐纳偏置",
    "preference": "DESIGN_FIRST",
    "preference_reason": "齐纳在测试电流以下的电压原厂不保证，补证路径基本不可得",
    "remediation": { "...": "与 finding 的 remediation 相同结构，含 calculation_preflight" },
    "avoids": [{
      "problem": "5 V 输出时最低供电依赖无保证的亚 mA 齐纳电压",
      "after_change": "最低供电 = VRAW 下限 − 肖特基 VF 最大值，全部来自手册保证值",
      "check_ids": ["<实际检查ID>"]
    }],
    "tradeoffs": ["21 V 输出时控制器内部箝位损耗上升，热约束移交 PCB", "需修改已确认规格 BLK-xx 的下限"]
  }
}
```

- `status`：`PROPOSED`（有改法）或 `NONE`（无法靠改图消除，另给 `reason` 与可定位 `evidence`）。
- `PROPOSED` 必填 `summary`、`preference`（DESIGN_FIRST / EVIDENCE_FIRST / EITHER）与 `preference_reason`、
  `remediation`（按上文结构校验）、`avoids`（每条含 problem、after_change 和关联的未关闭检查）、`tradeoffs`。
- 合成示例的数值和位号不可复用；实际建议必须引用本设计的器件、网络和手册条件。
