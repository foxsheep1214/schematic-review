# 当前规则审查、计算预检查与范围迁移

## SR 自身变化时先重新审查

`plan_review.py` 将 `review_engine` 写进计划：SKILL.md、references 和运行脚本的
逐文件 SHA256 及总摘要，包含尚未 commit 的修改，排除测试/缓存。它是规则内容身份，
不是仅比较 Git 版本号。规则文字修正也会保守触发重审。

1. 以当前需求、原理图、网表、BOM 和原始资料重新生成当前计划。
2. 旧计划缺指纹或与当前指纹不同：`revision_impact.fresh_review_required=true`，
   全部条目 `REVERIFY`；不得用旧 PASS、旧缺口列表或旧检查覆盖代替本轮判断。
   旧报告用于定位改动、历史发现及范围迁移。历史问题不能凭升级自动消失。
3. 每项 `reverification` 保留原有 method/evidence/输入与判据绑定，并增加
   `evaluation_origin: "CURRENT_REVIEW"`、`engine_digest: <当前 review_engine.digest>`。
   应实际读当前判据、重新核查证据和计算；复制旧解释再填指纹不构成重审。
4. 原始 datasheet、已验证模型及计算数据可以复用，但先复核型号/版本、使用工况、
   保证条件和当前判据；旧审查结论不能作为这些前提的证明。
5. 冷/热跑 `--merge` 仅接受同一规则指纹。规则升级后重新生成，必要时用 `--old-plan`
   追踪历史；逐条评估旧手工检查是否仍适用，再按当前判据创建。

`validate_review.py` CLI 默认检查当前指纹。陈旧/无指纹计划不能准出；
`--archive-only` 仅供历史记录结构检查，输出 `NOT_EVALUATED`，不能与
`--require-release` 合用。库函数为旧调用保留结构检查兼容；当前交付调用须传
`require_current_engine=True`，或使用 CLI。历史 schema/依赖结构不兼容时仍会报告结构错误。
结构校验不能证明审查者确实重新阅读了资料；最终证据质量仍须工程复核。

## 模型变化也是设计输入变化

复用现有 `review_dependencies.check_ids` 记录“供电电压模型 → 驱动电压 →
栅极电荷预算 → 损耗”的依赖，而不只登记本条位号。增加可选 `source_ids`，
指向 `intent.review_sources[].id`，将计算模型/条件说明直接绑定到检查：

```json
{
  "complete": true,
  "citation": "本版偏置供电模型及适用工况已复核",
  "db_digest": "<当前 db digest>",
  "check_digest": "<当前 check_spec digest>",
  "source_ids": ["BIAS_MODEL"],
  "check_ids": ["PWR-C01.BIAS"]
}
```

模型来源必须有真实绝对路径和定位引用；内容变化即使没有网表差异，也触发依赖检查，
再沿 `check_ids` 传播。未知 source ID 保持不完整依赖，不能声称可安全复用。
输入状态/保证条件改变仍按现有保守规则扩大检查；不要伪造完整依赖来缩小范围。

## 修改建议先核算前提

当前计划的 actionable findings 使用 `remediation_version: 2`，每项 remediation
给 `calculation_preflight`。其 calculations 合同与 ASG 的 `design_preflight.py` 相同，
格式见 [计算预检查](calculation-preflight.md)。READY 必须有适用条件下成立的计算；
参数通过 `calculation_ids` 关联依据，不能将候选值写成保证修复。
纯文档、恢复受控连接/贴装等无需数值推导的窄判据，可声明 `applicable:false`，
同时给 reason 与可定位 evidence；不能以此跳过实际需要的应力/供电计算。

## 不让历史计数代替当前覆盖

门禁增加 `categorized_summary`：current、history（REQ-H02）、unique_findings、
unique_work_items、work_item_check_links、required_handoffs、handoffs_by_state。
旧 summary 保持兼容，但正文优先展示新分项。HANDOFF 与检查可重叠，不相加成检查总数；
多条检查不等于多个根因。ACCEPTED 只表示约束/责任已接收，VERIFIED 才是有验证记录。

旧热判据若混合电气损耗与实际温升，移至 REQ-H02 的历史处置，并用 `scope_migration`
记录 `kind:"SPLIT"`、`replacement_check_ids`、reason、evidence；本版另立电气检查，
历史项保留 required HANDOFF。只有纯下游验证才用 `kind:"DOWNSTREAM_ONLY"` 和空替代列表。
历史混合判据改为 NA/NOT_APPLICABLE 表示拆分/退役，不代表电气通过；替代项照常审查，
可保持 FAIL/INSUFFICIENT。原有 handoff 接收/验证约束不变。
