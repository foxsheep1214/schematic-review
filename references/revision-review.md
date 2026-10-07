# 改版复审

复审比较前一版本的网表、计划与历史意见，沿变更的供电/控制/保护依赖扩大复验范围。
旧基线（`--old-db`、`--old-plan`）必须是按当前规则总表生成的计划；规则指纹变化时整板完整重审。

## 一、改版影响与逐项复验

用途：在结构 Diff 之外，将新旧设计/装配/条件/资料变化关联到本轮检查项。
这是复验范围与证据交接，不是电气求解器，也不生成修复通过、严重度或准出结论。
结构修改断言按下文“网表 Diff 与历史意见断言”执行；断言 PASS 不能
代替电平、时序、额定、保护和上下游影响的复验。

### 输入与操作

数据契约版本为 `dependency_version: 1`，计划保存 `review_inputs`、`check_dependencies`。
`review_inputs` 包含完整当前 db 的规范化摘要、intent、evidence、datasheet-audit 和本地
文档的实际内容哈希；自身也有 digest。它是项目内的审查记录，不放入公共仓库。
旧版最终计划作为 `--old-plan`；本版冷跑计划才是 `--merge-plan`，二者不能混用。

复审冷/热跑均传同一前版基线，热跑额外传本版证据、资料审计及 merge-plan：

```sh
python3 scripts/lint.py db.json --intent intent.json \
  --review-mode revision --old-db old-db.json --old-plan old-review-plan.json \
  --claims review-claims.json --plan-json review-plan-cold.json --json lint-cold.json

python3 scripts/lint.py db.json --intent intent.json \
  --review-mode revision --old-db old-db.json --old-plan old-review-plan.json \
  --claims review-claims.json --evidence evidence.json --datasheet-audit datasheet-audit.json \
  --merge-plan review-plan-cold.json --plan-json review-plan.json --json lint-hot.json \
  --revision-impact-json revision-impact.json
```

`plan_review.py` 同样支持 `--old-db`、`--old-plan`、`--revision-impact-json`。
提供旧基线且未显式指定模式时使用 revision；显式 first 与旧基线冲突则拒绝。
`--claims` 仍是历史断言材料的准备度输入，不代表已经执行或通过断言。

### 依赖清单

`check_dependencies` 按完整检查 ID 索引，包含：

- `check_digest`：本项定义的规范化摘要，含对象、状态、判据、适用性和 HANDOFF 等。
- `refs/nodes/nets/states`：来自明确对象、物理脚、电路组与声明的依赖。
- `check_ids`：其他检查的明确依赖边；使用完整 ID 传播，环不会导致无限遍历。
- `evidence_ids/sources`：该项热证据 ID 和已登记的本地文档路径。
- `scope`：GLOBAL / PARTIAL / DECLARED；`gaps` 与 `citation` 解释范围。

对象引用和同网变化提供候选关联，不证明完整供电/控制/保护依赖。
默认窄检查为 PARTIAL；覆盖审计项、全板项（对象含 `board`）和按功能包展开的项（对象含 `package`）
为 GLOBAL。只有工程人员核对完整依赖后，
才在 `intent.review_dependencies` 声明已确认范围；自动结果不会自行把 PARTIAL 改成完整。

合成格式示例；两个摘要须分别取当前 `review_inputs.db_digest` 和该项 `check_digest`：

```json
{
  "review_dependencies": {
    "EXACT-CHECK-ID": {
      "complete": true,
      "citation": "本版依赖审查记录 DEP-01；已逐跳核对上下游、返回路径和异常状态",
      "db_digest": "<当前完整db的64位摘要>",
      "check_digest": "<当前检查定义的64位摘要>",
      "refs": ["U1", "R1", "R2"],
      "nodes": ["U1.3", "R1.1", "R1.2"],
      "nets": ["SDA", "VCC_3V3"],
      "states": ["run", "external-on"],
      "check_ids": []
    }
  }
}
```

先生成草案取得准确 ID 与摘要，核对后填声明并重建计划。声明只能追加依赖，不能删掉
自动发现的对象；不存在的引用、未知检查 ID、摘要过期仍留缺口。未匹配的声明 ID 单列
`dependency_unmatched`，不能静默忽略。`complete:false` 可先登记已知依赖。
完整性声明是有出处的工程主张，机器不能证明其语义真实；不能为了缩小复验范围而批量签完整。

### 文件与条件变化

资料审计中 `document.path` 的本地文件自动按实际字节重算哈希，不仅比较文件名/版本号，
也不依赖文件大小或 mtime 缓存。旧计划保留旧哈希，不用今天的文件替换历史记录。
其他作为判据的需求、BOM、模型、库文件或日志可登记为 `intent.review_sources`：

```json
{
  "review_sources": [{
    "id": "REQ-A", "path": "/absolute/project/requirements.pdf",
    "citation": "受控需求 Rev.B section 3", "refs": ["U1"]
  }]
}
```

path 必须为本地绝对路径；不下载 URL，不跟踪未登记的任意外部文件。refs 为空的文件变化
按全局影响处理。此登记只绑定文件内容，不证明型号/条款/工况正确。不可读文件留阻断缺口。
上下游或多个电路共同使用的文档应登记完整引用范围，无法界定就用空 refs 全局处理。
引用字符串没有对应文件或输入内容时，工具不能发现引用背后的文件被替换。

所有实际值变化均保留，包括极小数值差、贴装、物理脚定义、网名/成员和符号声明脚变化。
不按百分比过滤放行，不把 R1 当作 R10，不假设改网名无电气影响。
intent 实际条件或 evidence/audit 内容变化仍保守触发全量复验。不将
`db.export_meta` 中 source/date/tool 及 `db.pin_name_coverage`（派生统计）、`intent.input_sha256/review_phase/review_mode/review_dependencies` 的变化
单独视为电气变化；输入/文档指纹仍验证，实际结构、原生引脚类型、参数和 integrity 仍比较，不能借此隐藏变化。
未标策略版本的历史计划保留 v1 的全局退回逻辑。

### 影响结果与缺口

复审计划增加 `revision_impact_version: 1` 和 `revision_impact`；另存 JSON 与内嵌清单一致。

- `baseline`：旧 db 和旧完整计划的摘要。新旧对象分别使用自己的基线，不按相似 ID 猜配。
- `current`：当前 db、输入快照、检查定义集合摘要；`digest` 绑定完整影响清单。
- `changes`：精确变化记录，含 old/new、定位、关联 refs/nodes/nets 和全局范围标记。
- `entries`：每项的 check_id、required、原因、change_ids、check_digest。
- `strategy=EXACT_DEPENDENCIES`：在已声明范围内关联；`NO_RECORDED_CHANGE` 不等于电气 PASS，
  也不允许脚本自动继承旧结果。
- `strategy=MIXED_REVIEW`：有变化时，旧/新局部依赖不完整的项标记
  `incomplete-local-dependencies` 并复验；沿显式 check_ids 传递至依赖它的检查。
  已完整声明且确实不受影响的其他项无需重复全部人工工作。
- `strategy=FULL_REVIEW`：未知全局变化、缺失基线、不可读文件等阻断缺口时全量复验；
  不能用候选路径或“未匹配到变化”声明依赖不完整的项不受影响。
- `blocking_gaps`：旧基线/快照缺失、文件不可读、未匹配依赖声明等未决项。
  `revision-impact-coverage` 必须保持 INSUFFICIENT；先恢复材料、重建并重审，再清除缺口。

部分依赖本身不永久阻止交付：按影响清单执行扩大后的复验，逐项记录本轮结果，并由 coverage
项说明实际范围。但这不消除真实缺证，不自动解除任何其他检查或 HANDOFF。
旧检查在新计划消失时新增独立 `revision-removed-check`，保留 prior_check 与旧 ID；人工
核对删除/替代、复发/撤回及连带影响。该历史记录在后续版本继续保留，结果每轮独立填写。
同一历史 ID 同时经“旧项消失”和“保留历史记录”生成时仅保留一个；不同 prior_check 定义
保存在 `prior_checks` 数组，主 `prior_check` 优先保留最近基线定义。历史检查身份/判据冲突仍报错，
不会丢弃记录或自动沿用关闭状态。

### 结果与最终闸门

结果顶层新增 `revision_impact_version: 1`、`revision_digest`。全部 required 项还需：

```json
{
  "reverification": {
    "revision_digest": "<本轮影响清单digest>",
    "inputs_digest": "<本轮review_inputs.digest>",
    "check_digest": "<本项check_digest>",
    "method": "本轮实际核对/计算的方法、状态与接受条件；未完成则具体记录缺口",
    "evidence": [{"source": "本版计算或核对记录", "locator": "确切章节/行/条件"}]
  }
}
```

PASS/FAIL/NA/INSUFFICIENT 的原有证据规则不变；reverification 不替代 evidence、rationale
或 binding。INSUFFICIENT 记录本轮缺失事实，不伪造已做计算。新版复审强制对象/判据绑定。

```sh
python3 scripts/validate_review.py review-plan.json review-results.json \
  --db db.json --old-db old-db.json --old-plan old-review-plan.json \
  --lint lint-cold.json --lint lint-hot.json \
  --require-bindings --require-actionable --require-revision-impact --json review-gate.json
```

校验从当前 db、保存的输入、仍可读的文件及明确旧基线重建依赖/影响，核对必需项、旧项
消失记录与自动检查；删条目、篡改变化、换基线、旧复验摘要不能靠更新 plan_digest 绕过。
冷跑暂缺、热跑恢复的旧状态检查，其暂缺/恢复处置记录也保留，不能破坏冷/热台账交接。
它验证的是记录一致性，不识别伪造的工程主张；单纯复制所有新摘要不会使旧计算变正确。
输入快照是本轮已声明版本；未提供的新需求/装配不能被工具凭空发现，输入版本仍须人工确认。

旧计划用于新复审时若没有历史输入快照，不能按当前文件补造历史。只能用前版真实冻结
资料重建并记录依据，否则按缺失基线处理。首审不额外强制 revision 结果字段。

### 受控复用

每项带 `reuse_candidate`。仅无复验原因、旧/新依赖均无缺口时为 true；
它是证据复用候选，不是自动 PASS。所有项仍在最终计划和结果中各保留一次。
审查者核对对象/物理脚、精确 MPN、装配、工况、判据、模型及资料版本后，才可在当前
`evidence/rationale` 引用原受控计算，说明适用性复核范围和结论；不要求重复计算相同输入。
required 项仍必须填写本轮 reverification，复用不能免除已经命中的受影响部分。

完整依赖声明仍绑定当前 db_digest；看过真实差异并确认上下游范围后才能续签，不能脚本
批量替换摘要。全板 BOM/资料缺少可验证的对象关联时，文件变化仍可能触发全量检查。
本策略不承诺任何修改都能缩小范围，也不基于文字相似度缓存电气结论。

计划还记录 review_engine 内容指纹；规则变化时完整重审，不沿用旧结论（见 [计划与结果台账](plan-and-results.md#五规则指纹与重新审查)）。

### 模型变化也是设计输入变化

用 `review_dependencies.check_ids` 记录“供电电压模型 → 驱动电压 → 栅极电荷预算 → 损耗”这类依赖，
而不只登记本条位号。可选 `source_ids` 指向 `intent.review_sources[].id`，把计算模型/条件说明直接绑定到检查：

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

模型来源须有真实绝对路径和定位引用；内容变化即使没有网表差异也触发依赖检查，再沿 `check_ids` 传播。
未知 source ID 保持不完整依赖，不能声称可安全复用；不要伪造完整依赖来缩小复验范围。

### 用户要求从头审查时

以当前需求、设计方案及最终设计文件建立全新首审基线，不导入旧计划、结论、缺陷计数、整改状态或旧审查脚本。
设计文件中的旧审查结论不作证据；原厂原始资料可重新核对后使用，派生计算重新建立。
此模式不生成旧意见继承项，按当前规则完成全量审查。

## 二、网表 Diff 与历史意见断言

按 [SKILL.md](../SKILL.md) 的复审步骤解析旧/新网表并运行 Diff。输出器件新增/删除/字段变化、
引脚换网和网络成员变化；伪网络不参与成员 Diff，但引脚从伪 NC 转入真实网络仍保留变化记录。

### 闭环断言格式

claim id 唯一；ref/node/net/field 等定位字段完整。器件字段仅允许 part、value、jedec、prim、nc；
nc 的期望值为布尔值，其余为字符串。结构不合法时直接退出，不进入判定。

下例全部为合成设定：U3.9 已由引脚表核实为地，旧上拉 R40 停贴；R41 以 10K 1% 贴装，
两端分别连接 U3.8 与 U3.9。实际项目须用当前数据库的准确值字符串和装配 BOM，并核查全部支路。

```json
{
  "schema_version": 1,
  "claims": [{
    "id": "F-07",
    "description": "旧上拉 R40 停贴，R41 的贴装、阻值及下拉两端符合指定修改",
    "expect": [
      {"kind": "part_field_equals", "ref": "R40", "field": "nc", "value": true},
      {"kind": "part_field_equals", "ref": "R41", "field": "nc", "value": false},
      {"kind": "part_field_equals", "ref": "R41", "field": "value", "value": "10K 1%"},
      {"kind": "pins_connected", "nodes": ["U3.8", "R41.1"]},
      {"kind": "pins_connected", "nodes": ["R41.2", "U3.9"]},
      {"kind": "pins_disconnected", "nodes": ["R41.1", "R41.2"]}
    ]
  }]
}
```

最后一条仅排除跨 R41 的同网/已贴 0Ω 旁路，不能排除任意阻性或有源支路。
上述断言证明指定编辑的结构状态；仍须复算内部拉阻、漏电、全部外部支路、采样门限和时序，
将专项 ER 复验证据关联 F-07 后才可关闭功能问题，不能从网名或换线推断低电平已保证。

### 支持的断言及边界

- `part_added` / `part_removed`：核对指定器件新增或删除。
- `part_field_changed` / `part_field_equals`：核对字段变化或期望值。
- `pin_net_changed` / `pin_net_equals`：核对物理脚换网或指定网络归属，不证明该网的电气作用。
- `net_membership_changed`：核对网络成员变化。
- `pins_connected` / `pins_disconnected`：`nodes` 必须是两个物理脚，只比较同网或已贴 0Ω
  通路；不跨非零电阻、二极管、开关或电容。目标缺失/处于伪网不能证明断开。
- `net_members_equal`：给 net 和完整 nodes 列表，核对准确成员。

全部断言通过才报告该 claim 的 PASS；否则输出 REQ-H01 FINDING。仅含字段/换网/成员变化的
claim 为 INSUFFICIENT，并在 `--fail-on-open-claims` 时阻断；必须补期望状态断言。
Diff 的 PASS 只覆盖声明的状态，不代替额定、方向、时序和其他受影响电路的工程复验。

具体复验范围由计划的 [改版影响清单](revision-review.md) 关联并校验；原有结构
Diff/断言仍独立保留。未发现结构差异不能排除装配意图、判据或资料内容变化。
