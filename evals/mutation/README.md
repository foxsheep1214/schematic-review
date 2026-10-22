# 变异门：注入具名缺陷，单元测试必须杀死

[run.py](run.py) 把仓库复制到临时目录（不带 `.git`/`.claude`/`runs`），按 [mutations.json](mutations.json)
逐条把一段实现改坏，跑单元测试，记录 KILLED（有测试失败）/ SURVIVED（全部通过）。源仓库不改。

```sh
python3 evals/mutation/run.py                 # 全部变异 × 单元层与合同层，结果写 RESULTS.md
python3 evals/mutation/run.py --only M4       # 只跑某几条
python3 evals/mutation/run.py --tier unit     # 只跑单元层（门槛）
```

- **单元层**：`pytest scripts/tests -x`，去掉典型电路、种子基准与 KiCad 回放三块板级基准。
- **合同层**：同上加 `-m contract`（规则合同、校验器不变量、解析器），只报告，不设门槛。
- **门槛**：每条变异都必须被单元层杀死；有存活或模式没唯一命中时退出 1。
- **基线**：先跑一份未变异的副本，单元层不通过就退出 1 并打印首个失败——副本里缺文件（例如台账点名的训练轮产物）会让每条变异都“被杀死”，那不是守住了判据。
  副本只去掉 `.git`/缓存、顶层 `runs/` 和训练轮里的冷跑/基准产物（`reviews/`、`seeded/`、`replay/`、`critic/`、`*.log`）。

## 变异清单

M1–M8 来自 2026-10-19 的审计：板级基准（42 块典型板、种子基准、KiCad 回放）只杀死其中 2 条，
单元测试杀死 7 条，存活的是 M4（DEV-E02 只核上限、不核下限）。补了
`test_electrical_safety.py::test_operating_range_fails_when_the_rail_minimum_is_below_the_recommended_minimum`
和 DEV-E02 合同后 M4 被杀死。M9–M12 删掉建合同前从未被测试点名的四条 A 规则（NET-A03、PWR-A04、RST-A01、
REQ-A01）的报出，只有规则合同能杀死它们。
M13–M18（2026-10-20）守功能判定机制：F2（设计值不向厂家要）、F4（正余量必须下结论）、框架科目行绑定、
`derive_rows.py` 按开放项派生、问题禁止句检查、计划生成功能框架，各由 `test_review_functions.py`、
`test_derive_rows.py`、`test_catalog.py`、`test_plan_review.py` 的一条测试杀死。
M19（2026-10-20）把与工作态无关的审查科目（`catalog.STATE_INVARIANT`）重新按状态展开，由
`test_plan_review.py` 的科目行计数测试杀死（首个失败是 `ReviewPlanTests::test_level_shift_name_hit_is_candidate_until_circuit_is_declared`，
`FunctionFrameTests::test_state_invariant_rules_get_one_row_per_circuit` 同样失败）。
M23–M24（2026-10-20，训练第 1 轮裁决）守两条放宽：IC 双向脚的单节点网降 CANDIDATE（`test_board_scans.py::SingleNodeNetTest`）、
驱动脚经最多 3 级电阻可达的栅极降 CANDIDATE（`test_power_switch.py::ChainedDriverTest`）。
M25–M26（2026-10-20，热审试点）守台账两条放宽：同对象框架的行只能绑到覆盖该行对象的功能（`test_review_functions.py::SharedObjectFrameTests`）、
`review_scope` 只免范围外的行（`ScopedReviewTests`）。
M27–M32（2026-10-20）守开放项的四条收紧：VENDOR_DATUM 的 `worst_case` 必须给公开界（M27）、公开界下的正余量就是结论（M28）、
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

## 维护

- 改规则或检查器时，为新判据加一条变异：`old` 是实现里唯一出现的一段原文，`new` 是“判据失效”的改法。
  `old` 不唯一时运行器报 ERROR，不会悄悄改错位置。
- 某条变异存活 = 有一条判据没有任何测试守着；先补触发板/近似板或单元测试，再提交。
- 实现重写导致 `old` 找不到时，按新实现改写该条变异，不要删掉。
