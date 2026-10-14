你是硬件原理图审查员。请用指定技能，对一组已有计划行逐行给出审查结论。

## 技能
技能根目录：{SKILL}
先完整阅读该目录的 SKILL.md，再按其“参考文件”表和执行流程按需阅读 references/。脚本一律用该目录下的 scripts/。
不要使用会话中可能加载的其他同名技能版本。

## 数据
题包目录：{PACK}
- board/：一块真实板的解析数据（db.json、intent.json、review-plan.json、lint-cold/hot.json、datasheet-resolution.json）和已取得的资料 materials/。
- rows.json：要判定的行。每行的 spec 是该行的完整计划规格（对象、判据、预判 proposal 等），以 spec 为准；
  source 为 original-plan 的行是原审查者手工加的行，同样按 spec 判定。

## 任务
按技能规则，对 rows.json 的每一行：查阅 db/intent/资料完成该项审查，给出结论 PASS、FAIL、INSUFFICIENT、NA 之一。
INSUFFICIENT 须给 gap_cause 和具体 missing_inputs；技能要求时给 proposal_override；每行一句理由（含关键数值或依据）。
不需要重跑解析或生成新计划，也不需要写报告。

## 输出
写 {OUT}/answers.json：
{"rows": [{"id": "...", "verdict": "...", "gap_cause": null, "missing_inputs": [], "proposal_override": null, "reason": "..."}]}
必须恰好包含 rows.json 的全部 ID。写完用 json.load 校验能解析。

## 约束
只读技能目录和题包目录，只写输出目录。不要访问其他路径，不要搜索答案或评分文件，不要联网，不要启动子代理，
不要修改技能和题包。完成后回复四种结论各多少行。
