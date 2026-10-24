# SR 整体自查：矛盾、过时与可精简之处（2026-10-24）

状态：只查不改。用户原话：“你先整体看看SR技能有没有逻辑、代码、文档，有没有自相矛盾，能不能再简洁明确一些”。

做法：文档约 65 万字符、代码约 150 万字符，分四片由只读子代理通读，分别是证据与定界、台账与报告、读入与计划、代码本身。每条都对照了两边原文或实际分支，重点条目由主会话复核。去重后共 70 余条，分成五组：

| 组 | 内容 | 条数 | 要不要你定 |
|---|---|---|---|
| 一 | 照着文档做会直接跑错或被拒收 | 14 | 不用，按现行规则改文档或代码 |
| 二 | 规则本身两套说法，要你定口径 | 9 | 要 |
| 三 | 代码里同一概念几套判法 | 7 | 不用（行为统一到一处），个别要你点头 |
| 四 | 过时文字 | 13 | 不用 |
| 五 | 可精简的地方 | 8 | 第 5.8 条要（属架构） |

---

## 一、照着文档做会直接跑错或被拒收

| # | 问题 | 位置 | 改法 |
|---|---|---|---|
| 1.1 | 示例命令缺 `--candidates`：只要 intent 里有 `circuit_decisions`，`lint.py` 不带它就直接 FATAL | SKILL.md:232；revision-review.md:23–31；reviewed-declarations.md:43；代码 lint.py:736 | 命令块都补上 `--candidates record/circuit-candidates.json` |
| 1.2 | SKILL.md 让人看“计划提示 CIRCUIT_TYPE_MISFIT”“未声明电压的轨”，但这些只有 `plan_review.py` 打印，入口 `lint.py` 不打印 | SKILL.md:202、206；plan_review.py:760 | 让 `lint.py` 也打印计划诊断（推荐），或改成“看计划 JSON 的 `diagnostics`” |
| 1.3 | 第 2 步的候选命令用到第 3、4 步才产生的 `datasheet-audit.json`；“之后的两次扫描”指哪两次说不清 | SKILL.md:173–178、211、231 | 第 1–4 步改成一条带命令的编号序列：读入 → 冷扫 → 取证核类别 → 候选 → 决定 → 带候选冷扫 → 资料请求 → 合并扫描 |
| 1.4 | 文档里三个 JSON 示例按现行门禁都通不过（缺 `derivation`/`corners`、`kind`、`monotonic_tried`、`via`/`rationale`，`design_option` NONE 缺 `evidence`；intent 示例手写 `circuits` 和 `features` APPLICABLE） | plan-and-results.md:24–60、305–353、744–798 | 按现行格式补全，并加一条测试让示例过门禁 |
| 1.5 | “TYPICAL_CURVE 只能出 ESTIMATE”：3b 后代码只允许它配 REACHABLE_CASE（是我 3b 漏改的） | plan-and-results.md:398；review_functions.py:475 | 改成“derivation 为 TYPICAL_CURVE 时只能是 REACHABLE_CASE；典型曲线的估算写 ESTIMATE，不写 derivation” |
| 1.6 | 有 8 个单调格（ZENER-VZ-LOWER、TVS-LEAK-HOT、DIODE-VF-COLD、DIODE-IR-HOT、DIODE-SURGE、MOS-RDS-HOT、MLCC-EFFECTIVE-C、IND-ISAT）门禁要求按 G2 定界，表里却不许用 G2，写 `method: G2` 会被拒收（是我 3d 的错） | catalog.BOUNDS；review_functions `_cell_errors`/`_formula_errors` | 这 8 格的推法补上 G2 |
| 1.7 | G10 写“负载不重于本板”，方向反了：应是本板负载不重于参考电路 | catalog.py:983；bounding-table.md:43；evidence-proportionality.md:408 | 三处改成“本板负载不重于参考电路” |
| 1.8 | “跨电路缺口写在拥有它的框架里，其他框架的行用 `open_ref` 指向它”做不到：`open_ref` 必须在行自己的 `function_id` 下；唯一办法是把行改绑到对方功能，且对方 `objects` 覆盖这一行 | SKILL.md:248–249；plan-and-results.md:496–498；results_model.py:105；review_functions `delegated` | 文档改成实际做法（改绑 + 覆盖条件）；两块电路对象不重叠时怎么办，见 2.6 |
| 1.9 | SKILL.md:263“框架外的功能（intent 没有声明的电路）自己加”是手画电路时代的说法，与 8a–8c 相反 | SKILL.md:263 对 :251 | 改成“框架外的行（器件、检查器、全板行）可自建功能；要新电路写 add 决定” |
| 1.10 | 候选漏了器件：一处说记 REQ-Q08、改规则，一处说写 add 决定 | SKILL.md:189 对 :251 | 合成一句：未归属器件写 add 决定，或留在 REQ-Q08 清单上写原因 |
| 1.11 | intent 一节标题写 schema_version 3（实际 4），SKILL.md、automation.md 的链接也指过去 | plan-and-results.md:18 | 改成 4 |
| 1.12 | 还在用已被拒收的 `intent.materials.datasheets.available` | datasheets.md:57–58；plan_review.py:164 | 改成按 `path` 是否存在、有审计文件时按逐位号状态 |
| 1.13 | 文档提到的 5 个自检提示代码在代码里不存在（ACQUISITION_WITHOUT_LOOKUP 等） | verdicts-and-release.md:178；report-and-remediation.md:136、139；evidence-proportionality.md:408 | 删掉，清单改成“见 review_quality.py” |
| 1.14 | 报告结构描述的是 `render_report.py` 不生成的内容：需求说明一段、“仍待确认 M 件”、处理清单表、潜在等级之和等于资料不足数；节名节序与实际不一致 | report-and-remediation.md:6、123–208；verdicts-and-release.md:354 | 删掉旧结构，只留“每节怎么写”表并与实际逐节对齐（需求澄清是否要进报告见 2.5） |

## 二、规则本身两套说法，要你定口径

| # | 问题 | 两边 | 我的建议 |
|---|---|---|---|
| 2.1 | **估算能不能判通过**。文档和判据多处写“典型曲线 / 典型 ±30% / 相似器件 / 转移曲线，结论在范围内不变就判 PASS(B)”（含 P1 并移交样机）；门禁里 ESTIMATE 什么都不判，只有寿命行例外 | evidence-proportionality.md:208、242、248、280；wca-formulas.md:5；DEV-C05、DRV-C02、DRV-E01 判据，对 review_functions `margin_verdict` | 定一条：估算不判通过，留开放项；例外只有寿命行和 G10 参考电路。这样 F 那次定的“P1 可用并移交样机”要改回去。也可以反过来给门禁开一条“估算 + 样机移交 → PASS”的路。两种都会动已定口径，需要你选 |
| 2.2 | **潜在 P0 的资料不足能不能“接受”放行**。文档说 P0 不能接受放行；代码只拦已确认的 P0 失败，潜在 P0 的资料不足填齐接受字段就变成有条件准出 | verdicts-and-release.md:39、292、361 对 validate_review blocker | 潜在 P0 也不可接受放行，代码补拦 |
| 2.3 | **打包是否强制“报告只从台账生成”**（不变的决定第 6 条）。`pack_review.py` 不读门禁 `valid`、不读 `review_scope`，也不核报告是否由当前台账重新生成，只记一个哈希；文档却写“手改打包失败”“不打包” | plan-and-results.md:290；report-and-remediation.md:56 对 pack_review.py | 打包时重新渲染比对报告，并要求门禁 valid（属架构，需你确认） |
| 2.4 | 应用说明能不能当“写了这种用法”的依据。应用说明多半只能记成典型参考，而典型参考一律要求典型曲线的 `regime` 和 `typical_estimate` | evidence-proportionality.md:408 对 review_functions.py:775 | 只对“曲线”要求 `typical_estimate`，应用说明文字不要求 |
| 2.5 | 需求澄清项要不要进报告正文。现在只在“定稿还差”里计一个数 | report-and-remediation.md:145 对 render_report | 进报告，单列一节 |
| 2.6 | 一个缺口跨两块对象不重叠的电路时，只能各写一份开项，与“缺口只写一次”相反 | 见 1.8 | 允许另一块电路的行用 `open_ref` 指向别的功能的开项（放宽 shape 检查），条件是开项的 `decides` 写了那一行的方面 |
| 2.7 | 门禁里多处“缺这个键就整段跳过”的宽松默认（`require_candidates`、`require_bindings`、`dependency_version`、`review_engine` 等），真实计划都带这些键，缺了反而放行 | plan_review.py:106、288；validate_review.py:277–279；review_engine.py:13；review_workflow.py:59 | 改成必填，宽松默认只留在测试夹具 |
| 2.8 | intent 校验对未知字段不报错（顶层拼错的 `power_rail` 也放行），缺 `schema_version` 也放行；计划、结果和各段都是严格的 | plan_review.validate_intent | intent 也改成字段白名单 + 版本必填 |
| 2.9 | 两个出计划入口（`plan_review.py` 和 `lint.py`）的 main 已经分叉 | plan_review.py:686–780 对 lint.py:695–842 | 删 `plan_review.main`，只留 `lint.py`（属“增删入口”，需你点头） |

## 三、代码里同一概念几套判法

| # | 问题 | 位置 | 改法 |
|---|---|---|---|
| 3.1 | 地网 / 电源轨有 6 套判法，结论不同：VSS 在 netgraph 不是地，在 plan_circuits、i2c、lint 是地；SGND、GND_SENSE、0V、+5V、V3P3 各处不一 | netgraph.py:14–18、265；plan_circuits.py:45；i2c_topology.py:24；lint.py:79；solve_dividers.py:33；passive_stress.py:74 | 全部走 netgraph 一处 |
| 3.2 | 电解 / 极性电容 4 套判法，钽一处排除一处纳入 | plan_circuits.py:104–110；board_scans.py:26；input_filter.py:23；decoupling.py:36 | 一个共用判法 |
| 3.3 | NTC、压敏、LED 识别各处正则不同；plan_circuits 里两个一模一样的 `NTC` 正则 | plan_circuits.py:120、137；circuit_candidates.py:42；board_scans.py:16 | 词表集中一处 |
| 3.4 | BOM 耐压三种读法（`10uF/16V/25V` 一处取 16 V，一处算没写） | board_scans.py:38；passive_stress.py:504；solve_dividers | 一个 `rated_voltage` |
| 3.5 | 有限数判断约 12 份，3 份遇超大整数抛 OverflowError，`calc.py` 不捕获（已复现） | review_functions.py:120；requirement_parameters.py:24；design_preflight.py:18 等 | 全部改用 electrical_contract.finite |
| 3.6 | 空白压缩、µ 归一 4 种写法，µ 的规范字一处是 U+00B5、一处是 u | plan_review.py:66；validate_review.py:42；review_functions.py:304；audit_datasheets.py:58 | 一个 `squeeze` |
| 3.7 | 储能电容门槛 1 µF 与 10 µF 并存；无装配声明时两种降级方式；汇总的“已写明”计数不带类别校验、门禁带 | plan_circuits.py:139 对 circuit_candidates.py:32；states.py:17 对 i2c_topology.py:459；review_summary.py:69 对 validate_review.py:236 | 门槛若有意不同就写明原因；其余统一 |

## 四、过时文字（直接改）

- `check-catalog.md` 手写的头部：计划和 intent 版本写 3、“证据 2”、`input-manifest.json`、“证据计算”“审查科目”，阶段表没有候选与决定（catalog.py 生成部分）。
- `catalog.py` 功能电路说明还是“intent 声明 circuits / features 使其适用”。
- REQ-Q08 判据少了“未归属器件、被 reject 候选的成员”这一半职责。
- PRO-E01 的关闭条件还写“乘寿命系数”，与 F 定的“本行不要求寿命系数”矛盾。
- automation.md：候选 schema 1、规则版本 2026-10-21.1，与同节的 schema 2 互相矛盾；函数位置写在 plan_review；没提 `passive_stress`。
- inputs-and-coverage.md 一处说 KiCad 解析器已随附，一处说只随附 Cadence；小节编号嵌套重复；还把设计方材料写成“待核材料”，与四类输入的决定冲突。
- 定界表的“出处”列指向技能外的方案文档（“定界表方案 3.1”“1-A”），还有 5 格指向不存在的小节。
- 代码注释和报错里的 schema 3/4，`review_quality` 的字段名指向已禁用的 `gaps[]`，`review-ledger.json`，`skill_identity` 排除表里不存在的文件和旧章节名。
- verdicts-and-release.md 的“`gap_cause: DOWNSTREAM_VERIFICATION` 已取消”：`gap_cause` 整个字段都不能写了；“版本 2 新增”一类版本沿革。
- execution-consistency.md 的结果值 CONDITIONAL（不存在）；plan-and-results.md:362–363 悬空的“第 1 步 / 第 2 步”。
- “自动计划不预填任何 HANDOFF”，但寿命行会预填热设计移交。
- REQ-Q07 并非“各行有结论就写 PASS”：绑定行全为 NA 时要手填。
- “审查审查要点”错字（review-charter.md:1、catalog 生成的两处）；同一东西叫“审查纲要 / 七项审查要点 / 审查要点”三个名字。

## 五、可精简的地方

| # | 内容 | 估计 |
|---|---|---|
| 5.1 | SKILL.md 第 5 步第 1 小步 25 行（其中一句 600 多字、五层括号），与 plan-and-results 字段表重复大半：留 6–8 行要点加链接 | 省约 17 行 |
| 5.2 | `plan-and-results.md` open[] 一个单元格约 3000 字：拆成“通用字段 + 每种开项一张短表（必填 / 禁填 / 可选）”，代码对不同开项要求本来就不同 | 不省字，但能读 |
| 5.3 | 每条规则只留一个权威位置，其余一句加链接：独立性边界（6 处）、rule_gaps（10 处）、电路候选流程（2 处）、缺厂家数据四档（4 处）、齐纳低电流（5 处）、需求行 NA（4 处）、manual_verification（3 处）、`valid` 语义（4 处）、通用件 50% / 25%（6 处） | 省约 100 行，也免得越改越分叉 |
| 5.4 | report-and-remediation.md 旧报告结构（约 85 行，见 1.14） | 省约 70 行 |
| 5.5 | 历史数字和版本沿革：SKILL.md:348 的 2026-10-21 基线、plan-and-results 里“6 版起 / 7 版起”、2026-10-21 对比叙述；历史都已在 architecture.md 决定表里 | 省约 20 行 |
| 5.6 | evidence-proportionality.md 定界五步后的逐项条目，大半已是定界表的格；并进 bounding-table.md，只留五步摘要 | 省约 40 行 |
| 5.7 | 死代码：`run_regression.py` 对着已不可读的旧记录空转（实测两块板都 SKIPPED 却报 PASS）；`solve_dividers.py` 除电阻解析外的分压求解器、`linear_feedback_window`、CLI 只有测试在用；十来个无人调用的常量和导入 | 省约 700 行代码和 300 行测试（`solve_dividers` 瘦身前要你点头，wca-formulas 提到它） |
| 5.8 | `results_model.expand` 仍把功能判定展开成旧的行级形状（`gap_cause`、`work_items` 等）给校验和报告读，是第三组和第四组好几条的根源；脚本的环归属和实际导入方向也有十来处逆向。都属架构，单独出方案 | — |

## 不是问题的

- F1–F12 编号连续，没有缺号或重号。`function_errors` 说明里写的 “F1–F10” 是它自己那一批，只是漏写了 F5 在别处，改一下说明即可。
- SKILL.md 和 references 里所有命令参数都存在于脚本；所有 md 链接和锚点都能解析；四个格式版本号与代码一致；`check-catalog.md` 和 `bounding-table.md` 的生成部分与 catalog 一致。

## 确认（2026-10-24）

用户原话：“先改1、3、4、5组，同时请询问我第2组的口径应该怎么写，给建议，我来做选择题。” 第二组逐题选择如下（选项原文）：

| # | 用户的选择 | 与建议 |
|---|---|---|
| 2.1 | “估算 + 样机移交可判通过”：门禁开一条路，余量是 ESTIMATE、功能是必需功能或性能（不含损坏、过热、保护）、写了样机实测移交时行判 PASS | 与建议不同 |
| 2.2 | “可以接受放行”：代码不动，文档改成已确认 P0 不能接受、潜在 P0 可由用户书面接受，准出为有条件 | 与建议不同 |
| 2.3 | “重新渲染比对 + 要求 valid” | 同建议（架构，已确认） |
| 2.4 | “曲线标出来，只有曲线要估算”：典型参考加 `curve: true` | 同建议 |
| 2.5 | “单列一节”：报告加需求要说清楚的地方 | 同建议 |
| 2.6 | “允许指向别的功能的开项”：开项的 decides 写了这一行的方面 | 同建议 |
| 2.7 | “改成必填” | 同建议 |
| 2.8 | “字段白名单 + 版本必填” | 同建议 |
| 2.9 | “删 plan_review.main”：只留 lint.py，plan_review.py 改归为库 | 同建议（架构，已确认） |
| 5.7 | “两个都删”：删 run_regression.py；solve_dividers.py 只留电阻解析 | 同建议（架构，已确认） |
| 5.8 | “这次不动，另出方案” | 同建议 |

实施顺序：第一组 → 第四组 → 第三组 → 第二组 → 第五组，每组一个提交；5.8 另写两份方案。
