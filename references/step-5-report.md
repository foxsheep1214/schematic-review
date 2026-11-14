# ⑤ 出报告

> 读者：审查员。

做本步前读 SKILL.md 和本文件；五个步骤的总览见 [SKILL.md 的执行流程](../SKILL.md#执行流程)。

## 5.1 渲染报告与白话说明

- 进报告的文字（任务、finding、handoff、notes）用白话，不用 [写法要求](report-and-remediation.md) 列出的词；
  `pack_review.py` 会检查。
- 报告由脚本从台账生成，agent 只在 `notes.json` 里补白话说明（格式见 [报告与修改说明](report-and-remediation.md)）：

      python3 scripts/render_report.py review-plan.json review-results.json review-gate.json --notes notes.json -o <审查目录>/审查报告.md   # 同时写出 审查报告.html

  默认简洁报告保留全部缺陷、任务、通过标准及计数，逐项依据链接到台账；需逐条展开时加 `--detail full`，不手改报告或删检查来缩短输出。
- 合格但有风险的检查由门禁的 `risks` 渲染成附录里折叠的“风险清单”，按风险类型分组（功能、格、只靠估算的角点、怎么估、余量、怎么改进、样机要测、涉及检查），
  结论段和数字一览各带一句；风险不限制定稿。寿命检查项凭估算判通过的不列风险，只列它的 BOM 约束和热设计移交；
  器件类别词表或定界表没覆盖的（`sr_improvements` 的 NEW_DEVICE_KIND / NEW_BOUND_CELL）渲染在“对 SR 的反馈”下“器件类别与定界表要扩的”，只告诉 SR 维护者要扩表。
- 按设计约束判合格的检查项由门禁 `design_constraints` 汇总，结论段带一句，约束本身列在“交给后续环节的要求”；不限制定稿。

- 渲染取舍（只写决定性余量、长 result 只取第一句等）由 `render_report.py` 实现，见 [报告与修改说明](report-and-remediation.md)；待办标题超过 60 字出 TASK_TITLE_LONG 提示，summary 不复述检查计数。
做完的标志：`notes.json` 的 summary、items、sr_feedback 用白话且都进了报告（summary 不带检查计数）；报告里的相对链接都能打开；
TASK_TITLE_LONG 提示每条处置过；报告里没有"每只、每只"串接、图说不重复。

## 5.2 打包与交付

- **交付只有三样**：项目审查目录顶层只放 `审查报告.md`、`审查报告.html`（同一内容，图直接显示）和 `record/`，其余中间文件留在工作目录。

      python3 scripts/pack_review.py <审查目录> --review-plan … --review-results … --review-gate … --db … --intent … \
        --circuit-candidates record/circuit-candidates.json --knowledge-checklist knowledge-checklist.json --notes notes.json --lint-cold … --lint-hot … --evidence-root <工作目录> --input schematic=<工程> --input requirements=<需求> …

  `pack_review.py` 拒绝打包的情形：重新渲染的报告与 `审查报告.md` 不同（手改过或台账改了没重出；渲染用了 `--title`、`--detail` 的打包时同样传）、门禁不 valid、门禁之后计划/结果/db/lint 又改过、结果声明了 `review_scope`、顶层有其他文件、引用的证据找不到或越界（`..`、符号链接）。它只复制结论引用的证据，原理图工程、手册、需求、旧审查按路径和 SHA-256 记入 `record/manifest.json`；本轮证据用 `--evidence-root` 内的相对路径。不另写 README 或说明文档。冻结与后续补充按 [留档](inputs-and-coverage.md#留档)。
  公开仓库只放脱敏合成用例。
- 证据只放摘录：引用台账文件的证据指向 `record/`，不复制；引用 SR 自己的 references 按 `skill_version` 解析，不声明为输入；
  手册和标准声明为输入（`--input datasheets=<原厂资料目录>`）按路径加页码引用，引用了 `ds/*.txt` 抽取而没有含 PDF 的输入打包失败；
  单个证据超过 300 KB 打包给 NOTE，处置是改为按输入引用或裁成摘录。

做完的标志：`pack_review.py` 打包成功（无拒绝），审查目录顶层只有 `审查报告.md`、`审查报告.html`、`record/`；
`record/evidence/` 里没有台账副本，输入里没有 SR 自身文档，打包的每条 NOTE 处置过（改引用或留下理由）。
