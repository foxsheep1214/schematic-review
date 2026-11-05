# 任务：对一块真实电路板跑完整 SR 审查并逐条归因（板 `{{BOARD_ID}}`，流水线 {{LANE}}）

你在 schematic-review（SR）技能的一个 git 工作树里。本次只处理一块板：`{{BOARD_ID}}`。细致优先于速度。

## 先读
- `评测集/公开真实板/README.md`（回路的六步、`findings.json` 的格式、流水线不能做的事——照它做）。
- `评测集/公开真实板/catalog.json` 里 `{{BOARD_ID}}` 那一项（repo、commit、schematic、license、types）。
- `评测集/公开真实板/_lanes/{{LANE}}/memo.md`（前面板子留下的经验；没有就跳过）。
- `SKILL.md`（SR 的审查流程 ①–⑧ 与命令）、`references/check-catalog.md`（规则总表）、`references/shared/guideline-criteria.md`（设计准则怎么用）、`docs/proposals/criteria-top50-examples-2026-11-02.md`（50 条准则的正反例，漏报核对用）。

## 做
1. `python3 -B evals/boards_tools/fetch_board.py {{BOARD_ID}} --cache ~/.cache/sr-boards`，得到 `~/.cache/sr-boards/{{BOARD_ID}}/db.json`（它拉源仓库、`kicad-cli` 导网表、`scripts/parse_kicad.py` 解析）。失败就在 `评测集/公开真实板/{{BOARD_ID}}/round-report.md` 写明原因（KiCad 版本、库缺失、许可证），`findings.json` 的 `run.gate` 写 `not_run`，结束。
2. 在 `~/.cache/sr-boards/{{BOARD_ID}}/review/` 里按 `SKILL.md` 走 SR 流程到能走的最远处：冷扫 → `intent.json`（板子用途从源仓库 README/文件名推断，写明“推断”；产品基线 `industrial_telecom`；电路类型按 catalog 的 `types` 声明，再按候选补）→ `circuit_decisions.py` → 带候选重扫 → 合并扫描出最终计划 → 逐项判计划项：能从网表、BOM（有则 `read_bom.py`）、HardwareWiki（`~/Documents/知识库/HardwareWiki/`，只读，`scripts/find_parts.py` 可检索手册）独立判定的写 `review-results.json`，依据写清；不能判的标 `needs_human` → `validate_review.py` → `render_report.py`。报告复制为 `评测集/公开真实板/{{BOARD_ID}}/审查报告.md`。门禁 FAIL 不要硬改成 PASS，如实记。
3. 逐条归因报告里的每条发现（五类，证据到位号/网络/数值/手册页或条款），按 README 的格式写 `评测集/公开真实板/{{BOARD_ID}}/findings.json`。`false_alarm` 要写出检查器应该怎么判才对、依据是什么。
4. 漏报核对：按本板触发的电路类型，用 Top 50 正反例逐条对照网表，找 SR 该报没报的，写进 `misses`，每条给应报的 SR 规则、准则、证据。
5. 为 `false_alarm`/漏报写 `proposed_fix`，为 `true_defect`/可网表表达的漏报写 `seed`；没有写 `null`。
6. 写 `评测集/公开真实板/{{BOARD_ID}}/round-report.md`（数字表 + 最重要 3 条观察 + SR 用法上的坑，不超过一页）；在 `评测集/公开真实板/_lanes/{{LANE}}/memo.md` 末尾追加 3–5 行给下一块板的经验。

## 不做
- 不改 `scripts/`、`references/`、`evals/seeded_bench/`、`docs/`、`SKILL.md`；不写 HardwareWiki；不往仓库复制第三方电路文件；不 `git commit`、不 push（驱动脚本会提交）。
- 不为了让门禁过而编造 results；不把"拿不准"写成 `false_alarm` 或 `true_defect`。

## 结束时
用中文给一段不超过 15 行的汇报：板子类型、计划项数、发现数、五类各几、漏报几、最值得合并步先做的一件事。
