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

## 维护

- 改规则或检查器时，为新判据加一条变异：`old` 是实现里唯一出现的一段原文，`new` 是“判据失效”的改法。
  `old` 不唯一时运行器报 ERROR，不会悄悄改错位置。
- 某条变异存活 = 有一条判据没有任何测试守着；先补触发板/近似板或单元测试，再提交。
- 实现重写导致 `old` 找不到时，按新实现改写该条变异，不要删掉。
