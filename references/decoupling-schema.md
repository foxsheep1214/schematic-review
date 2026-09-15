# 去耦覆盖清单与逐项审查

从现有 `db.json` 生成逐器件、物理电源脚、直接供电/返回网络、装配状态和电容清单。
只做原理图连接覆盖与审查计划联动，不是 KiCad 解析器、PDN 求解器或去耦合格判定。

## 候选发现与执行

不传 intent 时按物理脚名称/类型发现候选，也纳入符号声明但未连的脚；名称只是线索。
未核器件另列 `unverified_device_refs`，不能因没有常见 VDD/VCC 名称便判不适用。
官方脚表中网表完全不存在的电源脚也会生成候选，不能只检查网表实有脚。

常规 `plan_review.py` / `lint.py` 自动生成 `review-plan.json.decoupling`，可另存：

```sh
--decoupling-json decoupling-inventory.json
```

单独生成候选清单并取得绑定哈希：

```sh
python3 scripts/decoupling.py db.json --json decoupling-candidates.json
python3 scripts/decoupling.py db.json --intent intent.json --json decoupling-inventory.json
```

第二条命令用于已补好声明的 intent。`input_sha256` 取第一条输出中的同名字段，
它包含已有电气指纹及 declared_pinname/declared_pintype、伪网、输入完整性/导出状态。
旧的 `db_sha256` 单独不足以绑定符号未连接脚。本模块不会修改 db、BOM 或任何电路。

## 输入声明

在 intent 增加 `decoupling`；以下全部是合成格式示例，不是真实器件规格：

```json
{
  "decoupling": {
    "schema_version": 1,
    "input_sha256": "替换为候选清单的 input_sha256",
    "states": [{
      "id": "run-option-A",
      "citation": "装配 BOM Rev.B 选项 A 与运行工况表第 2 行",
      "population": {"U1": true, "C1": true, "C2": false}
    }],
    "devices": {
      "U1": {
        "mpn": "TEST-IC-EXACT",
        "package": "TEST-PKG-3",
        "identity_citation": "BOM 订货码/封装与官方订货表对应行核对记录",
        "citation": "准确型号完整物理脚表 Rev.A 第 3 页",
        "pinout_complete": true,
        "pins": {
          "1": {"name": "VDD", "role": "power"},
          "2": {"name": "VSS", "role": "return"},
          "3": {"name": "IO", "role": "other"}
        }
      }
    },
    "components": {
      "C1": {"kind": "capacitor", "citation": "BOM/符号确认 C1 为两脚电容"},
      "C2": {"kind": "capacitor", "citation": "BOM/符号确认 C2 为两脚电容"}
    },
    "groups": [{
      "id": "U1-VDD",
      "ref": "U1",
      "supply_nodes": ["U1.1"],
      "return_nodes": ["U1.2"],
      "citation": "准确器件电源分组与返回节点要求 Rev.A 第 8 页",
      "requirements": [{
        "id": "VDD-CONNECTION", "kind": "connection",
        "criterion": "填写本组实际适用的电容接法条款，不用通用每脚一颗规则",
        "citation": "官方适用条款版本/页码/表号"
      }]
    }]
  }
}
```

- `states` 为 1–32 个唯一状态，必须给装配/工况出处。`population` 只接受 true/false，
  缺项是未知，`nc=false` 不证明已贴。经核对的变体可覆盖解析 nc，原标记仍保留。
- `devices` 给准确 MPN/封装、身份解释、完整官方物理脚表及出处。`pins` 包含全部物理脚，
  角色仅 `power/return/other`；脚号是字符串，支持 BGA/EP。`pinout_complete=false` 保持缺口。
  这是有出处的人工声明，脚本不会读取 PDF 验证真实性，也不因字段齐全而自动判通过。
- 官方脚表与符号/网表脚表做双向差集。官方多出的脚、符号多出的脚分别记录；
  官方 power 脚未入 group 时自动列候选。不得为消除缺口把缺失电源脚改成 other。
- `groups` 按器件具体条款划分，不要求每个电源脚单独一颗电容。节点必须属于该器件的
  对应官方角色，供电脚不能重复分组；本版每组只支持一个直接供电网和一个明确返回网。
  跨网分组不合并，保持缺口，须按实际供电段和条款拆分。普通去耦范围之外的飞跨/
  bootstrap/补偿电容按专用条款另审，不从“连到电容”推断属于本组。
- `components` 支持 capacitor/resistor/ferrite/inductor/jumper/switch/other，声明都要有出处。
  C/R/L/FB/JP 前缀仅为候选类型；计入确认容量前需核 C 的类型和装配。不规则位号用显式类型。
  `other` 是有证据的类别/范围排除，不是规避官方电源脚审查的通用开关。
- `requirements` 按独立条款填写唯一 id、kind、criterion、citation；kind 为
  connection/capacitance/rating。每条单独入计划；缺某类时生成对应待核项，不默认为 NA。
  当前数组对声明的全部 states 适用，状态不同的要求须在条款中写清条件，不能复用不适用限值。

## 输出与容量口径

每个状态有唯一位号电容登记表 `capacitors`，记录两端物理脚/网络、原值、标称容量、
贴装状态、候选类型及 `matched_groups`。共享电容可以关联多个组，物理登记仍只有一条。
各组均保留供电脚与返回脚数组；没有电容仍保留组和零数量记录。

| 字段 | 含义 |
|---|---|
| `groups[].capacitors` | 两端直接匹配本组供电/返回网络的电容，含不贴/未知候选 |
| `fitted_capacitors/fitted_count` | 类型、两脚连接和本状态贴装均确认的唯一位号/数量 |
| `known_nominal_subtotal_f` | 上述已贴电容中可解析标称值的已知小计，可为部分数据 |
| `nominal_total_f` | 仅组连接/覆盖/装配及容量均无缺口时给出，否则 null；不是有效容量 |
| `rejected_capacitors` | 供电侧接到的电容，但不匹配本组明确的两端连接 |
| `boundaries` | 供电网边缘的电阻/磁珠/电感/跳线/开关；始终 crossed=false |
| `gaps/capacitance_gaps` | 身份/脚表/连接/装配缺口，与容量解析缺口分别记录 |
| `coverage` | DISCOVERED/INCOMPLETE，仅表示清单状态，不是电气 PASS |

所有串联元件均不跨越，包括 0Ω 和闭合跳线；上游储能电容不直接计入下游本段。
不同地网不因名字相近而合并。同网共享电容不是每颗 IC 本地去耦充分的证据；各组容量
不能相加成为整板总量。实际距离、回路、ESL/PDN/布局须由 PCB 阶段验证。

标称值只解析有明确单位的首项，如 100nF、4.7u/10%/16V、4n7、1e-6F；不猜 104
等裸编码。无法解析的已贴电容保留数量与缺口，不当作 0，不丢弃，也不猜耐压/介质。
不把 nominal_total 当成 MLCC 偏压/温度/公差后的有效容量，不自动估算 ESR 或降容系数。

## 审查计划和再验证

新增清单完整性项；逐状态逐组新增连接覆盖项，随后分开审查接法、数量/容量以及额定值。
显式 requirements 每条独立展开；所有电气项初始 WAITING_EVIDENCE，仍需逐项提供
真实条款、器件参数、状态计算、证据和结论。清单中有电容不触发自动通过。

电气行的 `required_material_refs` 列出目标器件和本组已确认贴装的电容，供 ER1 按需将
关键电容加入 `audit_datasheets.py --require-ref C1`；未确认类型/装配的候选先解决清单缺口。
参数需绑定准确电容订货码/规格，不能用一般 datasheets.available 替代逐料号证据。
接法行独立形成 PCB HANDOFF，最终应据真实条款补齐具体约束与接收记录。

网表、符号脚、装配、分组或条款改变后重新生成；同版旧计划也不会自动合并不同清单。
旧结果不迁移。`validate_review.py --db` 重新生成清单与检查，拒绝被删检查、改写判据、
被篡改小计/缺口或旧绑定。存在对应清单/条款缺口时不能填 PASS；容量缺口不自动
否定另一个已证实的窄连接结论。NA 仍需适用性排除证据，失败/未知保持原状态。
不含本功能标记的旧计划兼容读取，不代表经过新去耦门；重新生成计划才能使用本功能。
