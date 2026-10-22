# 变异门：注入具名缺陷，单元测试必须杀死

[run.py](run.py) 把仓库复制到临时目录（不带 `.git`/`.claude`/`runs`），按 [mutations.json](mutations.json)
逐条把一段实现改坏，跑单元测试，记录 KILLED（有测试失败）/ SURVIVED（全部通过）。源仓库不改。

```sh
python3 evals/mutation/run.py                 # 全部变异 × 单元层与约定测试，结果写 RESULTS.md
python3 evals/mutation/run.py --only M4       # 只跑某几条
python3 evals/mutation/run.py --tier unit     # 只跑单元层（门槛）
```

- **单元层**：`pytest scripts/tests -x`，去掉典型电路、种子基准与 KiCad 回放三块板级基准。
- **约定测试**：同上加 `-m contract`（规则约定、校验器不变量、解析器），只报告，不设门槛。
- **门槛**：每条变异都必须被单元层杀死；有存活或模式没唯一命中时退出 1。
- **基线**：先跑一份未变异的副本，单元层不通过就退出 1 并打印首个失败——副本里缺文件（例如台账点名的训练轮产物）会让每条变异都“被杀死”，那不是守住了判据。
  副本只去掉 `.git`/缓存、顶层 `runs/` 和训练轮里的网表扫描/基准产物（`reviews/`、`seeded/`、`replay/`、`critic/`、`*.log`）。

## 变异清单

M1–M8 来自 2026-10-19 的审计：板级基准（42 块典型板、种子基准、KiCad 回放）只杀死其中 2 条，
单元测试杀死 7 条，存活的是 M4（DEV-E02 只核上限、不核下限）。补了
`test_electrical_safety.py::test_operating_range_fails_when_the_rail_minimum_is_below_the_recommended_minimum`
和 DEV-E02 约定后 M4 被杀死。M9–M12 删掉建约定前从未被测试点名的四条 A 规则（NET-A03、PWR-A04、RST-A01、
REQ-A01）的报出，只有规则约定能杀死它们。
M13–M18（2026-10-20）守功能判定机制：F2（设计值不向厂家要）、F4（正余量必须下结论）、框架检查行绑定、
`derive_rows.py` 按开放项派生、问题禁止句检查、计划生成功能框架，各由 `test_review_functions.py`、
`test_derive_rows.py`、`test_catalog.py`、`test_plan_review.py` 的一条测试杀死。
M19（2026-10-20）把与工作态无关的电路检查项（`catalog.STATE_INVARIANT`）重新按状态展开，由
`test_plan_review.py` 的检查行计数测试杀死（首个失败是 `ReviewPlanTests::test_level_shift_name_hit_is_candidate_until_circuit_is_declared`，
`FunctionFrameTests::test_state_invariant_rules_get_one_row_per_circuit` 同样失败）。
M23–M24（2026-10-20，训练第 1 轮裁决）守两条放宽：IC 双向脚的单节点网降 CANDIDATE（`test_board_scans.py::SingleNodeNetTest`）、
驱动脚经最多 3 级电阻可达的栅极降 CANDIDATE（`test_power_switch.py::ChainedDriverTest`）。
M25–M26（2026-10-20，热审试点）守台账两条放宽：同对象框架的行只能绑到覆盖该行对象的功能（`test_review_functions.py::SharedObjectFrameTests`）、
`review_scope` 只免范围外的行（`ScopedReviewTests`）。
M27–M32（2026-10-20）守开放项的四条收紧：VENDOR_DATUM 的 `worst_case` 必须给公开资料界限（M27）、公开资料界限下的正余量就是结论（M28）、
亏欠保留开放要点名取松的条款（M29）、DELIVERABLE_PENDING 要写交付物/责任方/假定（M30）、亏欠的失败项要带改法（M31）、
称“无法定界”要列查过的曲线表（M32），都由 `test_review_functions.py::PublicBoundTests` / `DeliverablePendingTests` 杀死。
M33–M43（2026-10-20，架构收紧）守“没人判过的方面不默认通过、出口有类型且看得见”：交付物要写 `deliverable_kind`（M33）、
`scope` 必填（M34）、报告显示 `assumed`（M35）、派生行不把没判过的方面判 PASS（M36）、校验拒绝没判过方面的 PASS 行（M37）、
`judgements` 要引条款（M38）、手工核对覆盖不了缺输入的工具缺口（M39）、不同对象不共用一段核对方法（M40）、
手册未规定的工作点不当缺资料（M41）、报告显示为什么不按余量下结论（M42）、同一句假定不抄进几个功能（M43），
由 `test_derive_rows.py`、`test_review_functions.py`、`test_render_and_pack.py` 的对应测试杀死。
M44–M51（2026-10-21，两名审查员同板记录对比）守七条让记录趋同的护栏：功能至少一条能定位、带数字的条款（M44）、
判断至少引一条能定位的条件（M45）、DESIGN_VALUE/VENDOR_DATUM 写了理由也不许超过 3 个方面（M46）、同一句理由不抄到几个开放项（M47）、
框架功能的对象不越出 intent 电路（M48）、审查员绑定的行要在功能对象上（M49）、带 clamp_refs 的连接器行不手填（M50）、
需求行不整行阶段 NA（M51），由 `test_review_functions.py::ReviewerAgreementTests` 和 `test_review_stage_scope.py` 杀死。
M52–M55（2026-10-21，电路候选步 1–2）守 IC 角色与参考地分区：没核验角色的 U/M 位号不登记 DEV-D02 缺口（M52，`test_ic_kinds.py::PlannerGapTests`）、
泛称 ic 的原文写明角色仍通过（M53，`QuoteVerificationTests`）、推导参考地分区时电容导通（M54，`test_domains.py::DomainTests`）、
截止网络的一跳规则穿过地（M55，`RailStopTests`）。
M56–M61（2026-10-21，电路候选步 3–7）守候选生成与决定：走线穿过跨域器件（M56，`test_circuit_candidates.py`）、同距离的共享件只给第一个候选（M57）、
没有决定的候选通过（M58，`test_circuit_decisions.py`）、拆分漏下成员（M59）、手画电路与决定不一致仍通过（M60）、
有电路的记录没有候选文件也能打包（M61，`test_render_and_pack.py`）。
M62–M72（2026-10-21，Codex 合并方案 §3–§5）守影响条目、证据依据和检查项标识：GT 比较把零裕量当通过（M62）、没写 states 的证据覆盖全部状态（M63）、同一范围的通过与失败不报 EVIDENCE_CONFLICT（M64）、跨 regime 比较不写换算（M65）、典型应用当作强制条款（M66）、失败项既无已证缺口也无强制条款（M67）、保证最坏值建在典型值上（M68），由 `test_review_functions.py::EvidenceBasisTests` 和 `FunctionShapeTests` 杀死；电路名进入检查项标识（M69）、同一项检查问两次（M70）、没有定位引用的别名算作配对（M71），由 `test_compare_reviews.py::StrictIdentityTests` 和 `test_validate_review.py` 杀死；证明通过的裕量与阻断同一范围的缺口并存（M72）。
同一批改指向：F7 的 3 个方面上限和 decides_reason 退役后，M46 改守"缺口的每条影响条目都要写 via"；F10 的理由模板降为提示后，M47 改守"判断句不许引数字限值"。M14、M20、M21、M28、M29、M37、M38、M42、M44、M45 跟着新代码换了注入位置，守的行为不变（M42 从"不显示裕量为何不决定"改为"不显示缺口影响哪些判断"）。
M73–M79（2026-10-21，功能电路树第 1 步：器件归属唯一）守认领次序与归属：链路成员与隔离带同级（M73）、电路成员不强于链路成员（M74）、打平的器件归每个打平者（M75），由 `test_circuit_candidates.py::OwnershipTests` 杀死；没有 own 决定的打平被接受（M76）、own 决定没有定位引用（M77）、候选文件里一颗器件两个所属（M78）、手写的 owned 与决定不符（M79），由 `test_circuit_decisions.py::OwnershipTests` 杀死。M57 改指向归属一步生成的共享清单（原先的共享清单代码已删除）。

M80–M84（2026-10-21，功能电路树第 2 步：行归属与电路行身份）守所属与身份：电路级行的成员表和网络留在身份里（M80）、按电路展开的系统规则行归到系统功能（M81）、器件归每个列出它的电路而不是所属电路（M82）、校验器接受与所属表不符的 owner（M83）、电路行按显示名而非候选编号作键（M84），都由 `test_row_owner.py` 杀死。

M85–M90（2026-10-21，功能电路树第 3 步：接口识别）守接口推导：地网成为接口网络（M85）、碰到链路自有器件的网络又进电路对接口（M86）、只凭像电源轨的名字就生成供电接口（M87）、手册库类型为输入的引脚被当作轨的源（M88）、接口编号用电路显示名（M89）、推不出角色的端点不记缺口（M90），都由 `test_interfaces.py` 杀死。

M91–M97（2026-10-22，功能电路树第 4 步：接口检查项）守接口行：SIG-C08 在每条接口网络上都问（M91）、连接器不问载流（M92）、每条轨都问纹波噪声（M93）、接口行归全板（M94）、供电接口也建框架（M95）、接口规则的扫描行落在接口网络上仍归全板（M96）、连接器上的网络先归电路对（M97）；M95 由 `test_circuit_decisions.py` 的框架用例杀死，其余由 `test_interface_rows.py` 杀死。

M98–M103（2026-10-22，功能电路树第 5 步：系统功能与自有器件）守触发与归位：只有一个地网也问 PWR-T06（M98）、只有一条轨也问 RST-T03（M99）、全部 IC 都核验为非主控也问 SIG-D13（M100）、DEV-C02 取电路的全部器件而非电容（M101）、没有电路拥有的器件不问（M102）、有行的系统功能不建框架（M103）；M98/M99 由规则约定板杀死，M101 由全板规则用例、M102 由生成判据用例、其余由 `test_system_functions.py` 杀死。
M104–M110（2026-10-22，功能电路树第 6 步：树上的覆盖与报告）守两条覆盖审计和报告分组：器件归属审计不跑（M104）、一颗器件归两块电路也放过（M105）、没有电路拥有的贴装器件只按候选文件的清单进 REQ-Q08（M106）、缺接口行（M107）或缺接口框架（M108）也放过、报告功能表不按树分组（M109）、发现项不写“所属”（M110）；全部由 `test_tree_coverage.py` 杀死。
M111–M115（2026-10-22，功能电路树第 7 步：拆分计划生成、拒收旧记录）守旧记录的界线：缺所属表（M111）或缺接口（M112）的计划被放行、校验器（M113）、合并（M114）和改版比对（M115）连带读 5 版计划；全部由 `test_tree_modules.py` 杀死。同步把代码搬到 `plan_circuits.py`、`plan_system.py`、`plan_board.py`、`interfaces.py` 的 15 条变异改指新文件，全量重跑；M81 自第 5 步（RST-T03 不再按电路展开）起只剩直接调用 `row_owner.owner` 能触发，由 `test_row_owner.py` 新加的用例杀死。
M116–M122（2026-10-22，配对补缺：装配状态按内容命名）守检查项标识：检查器行仍带审查员起的装配名（M116）、清单句柄（M117）或清单摘要（M118）进标识、电路行的工作态被当成装配（M119）、装配键不看跳线（M120）、校验器放行没有装配表的计划（M121）、`compare_reviews.py` 不用装配表算键（M122）；全部由 `test_assembly_identity.py` 杀死。
M123–M130（2026-10-22，去耦行收紧：固定要求种类、返回脚由脚表推出）守：只按写了条款的种类出行（M123）、审查员条款当成行的判据进标识（M124）、返回脚只取一个（M125）、`return_net` 不参与取脚（M126）、返回脚跨网却不写 `return_net`（M127）或只有一个返回网也写（M128）被放行、同一类两条条款被放行（M129）、无电容组的 NA 行把条款出处写进判据（M130）；M123 由 `test_decoupling.py`、其余由 `test_decoupling_fixed_kinds.py` 杀死。
M131–M138（2026-10-22，需求固化第 1 步：需求由工具抄录）守：只抄第一列（M131）、首列不是编号的表也当需求表（M132）、重复编号放行（M133）、需求文档改了仍照读（M134）、intent 里手写原文或出处放行（M135）、文档里的需求在 intent 里缺项（M136）或 intent 里有文档没有的编号（M137）放行、需求条款按判据而不按原文拼接（M138）；M131、M138 由 `test_requirement_clauses.py`、其余由 `test_requirement_source.py` 杀死。

## 维护

- 改规则或检查器时，为新判据加一条变异：`old` 是实现里唯一出现的一段原文，`new` 是“判据失效”的改法。
  `old` 不唯一时运行器报 ERROR，不会悄悄改错位置。
- 某条变异存活 = 有一条判据没有任何测试守着；先补触发板/近似板或单元测试，再提交。
- 实现重写导致 `old` 找不到时，按新实现改写该条变异，不要删掉。
