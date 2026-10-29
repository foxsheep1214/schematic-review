# 原理图审查报告

## 结论

**可以定稿。** 电路和文档都没有发现错误。有 1 条设计约束由 SR 算出、交给后续设计，按约束判合格，见附录“交给后续环节的要求”。

功能 1 个：合格 1，不合格 0，未定 0；检查 10 条，资料不足 0 条；交给后续环节 3 条。

## 各功能的判断

所有功能都合格。

<details>
<summary>合格的 1 个功能</summary>

| 功能 | 问题 | 结论 | 余量或依据 | 错误或待办编号 |
|---|---|---|---|---|
| FN-BIAS | 默认 5 V 输出、−10..105 °C、辅助绕组取最低电压时，Q2 偏置路径能否让 U1 VCC 保持在 8.8 V 以上 | 合格 | 余量 0.8 V 对 VCC(off) max 8.8 V | — |

</details>

## 附录

<details>
<summary>交给后续环节的要求</summary>

下面这些要求在原理图上做不了，要在 PCB、热设计、测试等后续环节落实，不算原理图的错误，也不影响原理图定稿。原理图交出时把对应的表交给负责方即可。

#### 磁件设计（1 条）

| 涉及位号/网络 | 要落实的要求 | 怎么验证 |
|---|---|---|
| Q2 | T1 辅助绕组 5 V 空载最低峰值 ≥ 13.5 V | 磁件规格写明 5 V 空载最低峰值电压且 ≥ 13.5 V |

</details>

<details>
<summary>数字一览</summary>

| 项目 | 数量 |
|---|---|
| 功能判定 合格 / 不合格 / 未定 | 1 / 0 / 0 |
| 检查总数 | 10 |
| 合格 / 不合格 / 资料不足无法判断 | 10 / 0 / 0 |
| 与本产品无关（NA） | 0 |
| 原理图阶段不判、交给后续环节 | 0 |
| 发现的错误，按严重程度 P0 / P1 / P2 / P3 | 0 / 0 / 0 / 0 |
| 其中文档错误 | 0 |
| 待办（同一原因合并） | 0 件 |
| 资料不足的检查，可能的严重程度 P0 / P1 / P2 / P3 | 0 / 0 / 0 / 0 |
| 交给后续环节的要求 | 1 |
| 审查记录自检提示（不计入结论，分类见“对 SR 的反馈”） | 4 |
| 上一版问题的处理记录（不计入上面各行） | 0 |

</details>

## 对 SR 的反馈（设计者不用处理）

<details>
<summary>展开（给 SR 维护者）</summary>

### 审查记录自检提示

4 条，只要求复核写法和依据，不改变结论：CONDITION_REF_OUTSIDE_FUNCTION 2、TEMPLATED_HANDOFF 2。明细在 record/review-gate.json 的 quality_screening。

</details>

## 索引

| 内容 | 文件 |
|---|---|
| 每条检查的结论、依据、缺的资料和修改条件 | [review-results.json](record/review-results.json) |
| 检查计划：全部检查项和覆盖范围 | [review-plan.json](record/review-plan.json) |
| 校验结果：各项计数、定稿条件和自检提示明细 | [review-gate.json](record/review-gate.json) |
| 从原理图导出的网表数据 | [db.json](record/db.json) |
| 审查依据：需求、电源轨、装配和器件声明 | [intent.json](record/intent.json) |
| 自动检查输出（只用网表） | [lint-cold.json](record/lint-cold.json) |
| 自动检查输出（加上器件资料） | [lint-hot.json](record/lint-hot.json) |
| 引用的资料摘录、计算和图片 | [evidence/](record/evidence/) |
