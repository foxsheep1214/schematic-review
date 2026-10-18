# 保存并复用审查者核对的分组

适用：AI 已对照当前网表、图面和原厂资料核对器件角色及供电/返回分组，希望下次自动检查直接读取。
记录的是已核对的结构事实和条款，不是电气 PASS；不能把名称候选或旧报告结论直接转成声明。

## 录入一次，后续验证复用

1. 保留不带 `reviewed_declarations` 的基础 `intent.json`。按本次真实阅读/追踪写 `declaration-draft.json`：

```json
{
  "reviewer": {"kind": "AI", "method": "对照原厂引脚表与本版网表逐端核对供电、返回及本组电容"},
  "sources": [
    {"path": "/绝对路径/原厂资料.pdf", "locator": "第3页物理脚表及第9页应用电路"},
    {"path": "/绝对路径/本版原理图.kicad_sch", "locator": "U1、C1和GND连接"}
  ],
  "declarations": {
    "devices": {},
    "decoupling": {
      "schema_version": 2,
      "components": {},
      "groups": []
    }
  }
}
```

`devices` 仅补已核定的准确脚表，可省略；已有脚表冲突时报错，不能覆盖。`decoupling` 沿用
[去耦格式](automation.md#去耦覆盖decoupling)：组内写准确物理供电脚、返回脚、用途、适用条款与出处。
各声明的 citation 指向 sources 中的具体依据；sources 应覆盖实际用到的原始文件，而不只引用旧总结。

桥式整流器、定制变压器经核对后，可在 `components` 分别写
`{"kind":"bridge_rectifier","citation":"准确文件和定位"}` 或 `{"kind":"transformer","citation":"准确设计单及绕组定位"}`。
这只说明它们不是需要 IC 旁路的对象；不关闭极性、绕组、额定、磁件、保护或绝缘检查。
普通 R/C 等仍用已有种类；没有依据时不填 `other` 来消除提示。

2. 保存及应用（脚本核格式和一致性，不代替步骤1的核对）：

```sh
python3 scripts/reviewed_declarations.py capture db.json intent.json declaration-draft.json -o reviewed-declarations.json
python3 scripts/reviewed_declarations.py apply db.json intent.json reviewed-declarations.json -o intent-reviewed.json
python3 scripts/reviewed_declarations.py status db.json intent-reviewed.json
python3 scripts/lint.py db.json --intent intent-reviewed.json --plan-json review-plan.json --json lint.json
```

生成的 `reviewed-declarations.json` 可随审查记录保存，`apply` 将其嵌入工作用 intent。
脚本不修改基础 intent，也不把有效声明转换成审查通过。检查计划仍保留条款、容量、额定和动态能力的判断。
后续同输入用保存的 intent 直接重跑，无需重新录入分组。

## 输入变化后的行为

声明保存网表/符号/料号/导出完整性指纹、基础 intent 指纹、全部引用文件 SHA-256，以及声明自身摘要。
基础 intent 包含装配、工作电压、需求、器件脚表和已有分组；引用文件使用绝对路径，失联也不能复用。
每次建清单、生成计划和验证已有台账都重新比对，且重读引用文件；任一不符返回 `REVIEW_REQUIRED`，
拒绝使用旧声明，不静默更新摘要或沿用旧 PASS。仅刷新顶层 `input_sha256` 不能解除失效。

审查者应检查变化的引脚、连接、装配、工况及原文，更新基础 intent/声明草稿，再执行 capture/apply。
脚本只能触发复核，不能自行完成资料语义复核。当前采用整组保守失效；即使只改其他器件，也须先确认声明仍适用。

## 核对者身份

`reviewer.kind` 必须如实写 AI 或 HUMAN；HUMAN 只用于实际人员参与且有记录的核对。
未记录身份时，不从旧字段名 `manual_*` 推断为人员核对。它们为兼容旧格式保留，表示自动检查之外的独立核对。
报告中的 `manual_verification` 可用 `reviewer_kind: "AI"` 明示身份；已解决的工具限制不继续列为待改进项。
