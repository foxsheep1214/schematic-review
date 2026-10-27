# 原理图审查报告

## 数字一览

| 项目 | 数量 |
|---|---|
| 功能判定 合格 / 不合格 / 未定 | 0 / 0 / 1 |
| 检查总数 | 7 |
| 合格 / 不合格 / 资料不足无法判断 | 6 / 0 / 1 |
| 与本产品无关（NA） | 0 |
| 原理图阶段不判、交给后续环节 | 0 |
| 发现的错误，按严重程度 P0 / P1 / P2 / P3 | 0 / 0 / 0 / 0 |
| 其中文档错误 | 0 |
| 待办（同一原因合并） | 1 件 |
| 资料不足的检查，可能的严重程度 P0 / P1 / P2 / P3 | 0 / 1 / 0 / 0 |
| 资料不足的原因：缺资料 / 已暂缓 | 1 / 0 |
| 资料不足细分：按公开资料界限算不够 / 按公开资料界限算够，但不是保证值 / 公开资料定不出界限 | 0 / 0 / 1 |
| 资料不足的可能后果：损坏或危险 / 核心链路断开 / 器件损坏（不致危险） / 必需功能 / 性能或寿命 / 局部或资料 / 可选优化 | 0 / 0 / 0 / 1 / 0 / 0 / 0 |
| 交给后续环节的要求 | 0 |
| 审查记录自检提示（不计入结论，分类见“对 SR 的反馈”） | 0 |
| 上一版问题的处理记录（不计入上面各行） | 0 |

## 结论

**还不能定稿。** 电路和文档都没有发现错误。另有 1 件事因为缺资料，现在还判断不了。

**最先要解决的一件事：**
1. Synthetic task（P1，缺资料；待办 W-1）

这是设计中途的检查，“还不能定稿”说的是离定稿还差上面这些，不是否定设计。

## 各功能的判断

| 功能 | 问题 | 结论 | 余量或依据 | 待办编号 |
|---|---|---|---|---|
| FN-W-1 | Synthetic task | 未定 | synthetic fixture | W-1 |

## 待办

严重程度：P0 可能损坏器件或危及安全；P1 必需功能可能不达标；P2 局部或次要问题；P3 可选优化。

### W-1　Synthetic task

类型：缺资料（公开资料定不出界限）　可能后果：必需功能可能不达标（P1）　涉及 1 条检查

- **缺什么**：startup load current envelope；适用范围：Peak amperes, pulse seconds and repetition at the specified supply limits
- **为什么要紧**：Synthetic independent input
- **这个缺口影响哪些判断**：使能极性与耐压：Synthetic: W-1 leaves 使能极性与耐压 undecided（出处 synthetic-fixture.json p1 Table 1 (stipulated clause)）
- **还要做**：System engineer derives controlled bound from installed loads and their startup data
- **怎样算通过**：Recompute current-limit margin and startup voltage; compare with required rails

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
