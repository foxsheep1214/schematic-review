# I²C 连接覆盖清单

维护范围：从现有 `db.json` 发现 I²C 端点、上拉、串阻路径和边界，并生成逐状态审查计划。
不是 KiCad 解析器、I²C 电气求解器或准出结果。无需安装额外依赖。

## 输入与装配证据

不提供配置时，也会按 SDA/SCL 引脚名、网名生成候选清单，但名称只是线索。
`SCLK` 不独立触发 I²C；不能把未识别的接口判 NA。
不传 `--intent` 可以使用此候选模式；显式传入的 intent 文件根值必须是 object，
`null`/数组等会报输入错误，不会悄悄丢弃配置。畸形 db 容器也在入口拒绝。

确认连接范围时，在 `intent.json` 增加 `i2c_topology`。示例全部为合成条件：

```json
{
  "i2c_topology": {
    "schema_version": 1,
    "db_sha256": "填写当前 db_fingerprint(db) 的 64 位哈希",
    "states": [{
      "id": "run-option-A",
      "citation": "装配 BOM Rev.B 选项 A；跳线配置表 Rev.C 第 2 行",
      "population": {"U1": true, "JP1": true, "R1": true, "R2": true},
      "jumpers": {"JP1": "closed"}
    }],
    "buses": [{
      "id": "CONTROL",
      "sda": ["U1.5"],
      "scl": ["U1.6"],
      "citation": "已核对的 U1 物理脚表与原理图页 2"
    }],
    "components": {
      "U1": {"kind": "endpoint", "citation": "U1 接口角色核对记录"},
      "JP1": {"kind": "jumper", "citation": "JP1 两脚跳线定义"}
    },
    "rails": {"VCC_3V3": "本版电源树节点 A"}
  }
}
```

- `db_sha256` 使用 `electrical_contract.db_fingerprint(db)`；不允许将旧状态声明静默用于新网表。
  命令示例：`python3 scripts/electrical_contract.py db.json`，取其输出的 `db_sha256`。
- `states`：1–32 个唯一状态，每项必须有 `id/citation`。`population` 是本状态的实际装配，
  值仅为 JSON `true/false`；缺项表示未知，不以 `nc=false` 推定已贴装。
  经过核对的状态声明可以覆盖解析器的 `nc` 标记，输出保留原标记，必须在 citation 中说明变体依据。
- `jumpers`：按位号填写 `closed/open/unknown`，且跳线需 `population=true` 才能导通。
  未知状态、库名 `Bridged` 或焊盘默认图形都不能当作实际闭合证明。
- `buses`：每组唯一 `id`，`sda/scl` 各为非空、去重的物理节点数组和角色证据 `citation`。
  可包含同一逻辑总线不同侧的已核对端点；输入仍不会把隔离或有源器件两侧短接。
  不熟悉的引脚命名用显式物理节点补齐。直接把不明节点加进数组不能替代查引脚功能。
- `components`：可选类型声明，含 `kind/citation`。支持 `resistor/jumper/endpoint/connector/`
  `level_shifter/isolator/switch`。R、JP、J/P/CN 前缀只提供相应候选类型；其他无源位号需显式声明。
  导通边只支持恰好两个网表物理脚的电阻/跳线，不支持把多脚电阻阵列或 IC 当两脚桥接。
- `rails`：按网络名声明已核对的供电域及出处；只确认身份，不提供轨压、耐压或供电能力证据。
  轨名推断的供电域仍保留 `rail-identity` 缺口。

电平转换器、隔离器或开关的类型声明可增加 `ports`：

```json
{
  "U3": {
    "kind": "level_shifter",
    "citation": "U3 本型号物理脚及两侧接口核对记录",
    "ports": [
      {"sda": "U3.1", "scl": "U3.2"},
      {"sda": "U3.3", "scl": "U3.4"}
    ]
  }
}
```

每对 ports 单独提供 SDA/SCL 种子。端口未映射时列 `boundary-port-map` 缺口；不猜测另一侧引脚。
各侧永远单独追踪。内部传输、EN/RESET、方向、掉电及漏电行为留给电气检查，不由连接发现器建模。

## 执行与产物

常规 `lint.py` / `plan_review.py` 会重新生成清单并嵌入 `review-plan.json.i2c_topology`，
不读取旧清单作为事实。需要单独保存时，在原命令增加：

```sh
--i2c-topology-json i2c-topology.json
```

也可以只生成清单，不执行 Lint：

```sh
python3 scripts/i2c_topology.py db.json --intent intent.json --json i2c-topology.json
```

清单中每个 `states[]` 分别记录：

| 字段 | 含义 |
|---|---|
| `buses` | 声明/端口/名称候选，以及 SDA/SCL 所属连接区域 |
| `regions` | 仅通过已确认导通的两脚无源器件可到达的网络集合，不跨有源器件 |
| `regions[].edges` | 原位号、物理脚、两端网、串阻值/公差、装配与模型出处 |
| `regions[].segments` | 仅由 0Ω/闭合跳线相连的拓扑段；非零串阻两侧仍是不同段 |
| `regions[].pullups` | 每只已确认贴装上拉只出现一次，含供电域、阻值及可复现路径 |
| `path_origin_net` / `pullups[].path` | 路径起点网及依序经过的边位号；不是电压传递模型 |
| `endpoints` / `boundaries` | 物理端点、串联断点、未知器件、有源器件或外接端口 |
| `gaps` | 未核装配/角色/供电域、未映射边界、未知外接模块、输入错误或追踪上限 |
| `coverage` | `DISCOVERED` 或 `INCOMPLETE`，二者都不是电气 PASS |

有限串阻允许追踪到远端上拉，但不进行理想短接或跨串阻直接并联。
断开/不贴的选件不会连接两个区域；工具继续列出两侧的潜在覆盖，未确认的远端归属仍待核。
连接器后的外部上拉一律未知；需取得模块/线缆网表，形成并核验完整索引或另留专家证据。
发现器不枚举任意 IC 内部路径，也不声称覆盖未提供的外部电路。

追踪用去重队列处理环路；每状态最多 1024 个候选网络，达到上限明确记录缺口及
`unvisited_seed_nets/unvisited_frontier_nets`，不能视为完整。
`segments` 是连接分组，不证明真实 0Ω/跳线无压降或无限带宽。

## 计划与证据门槛

每状态、每连接区域新增 1 项连接覆盖检查及 3 项现有 I²C 判据：灌电流/上升时间、
电压域/掉电、地址/复用/装配状态。有限串阻各段须保留节点做关联分析；有源器件两侧另查传输条件。
名称未确认、外接模块未知等缺口必须补齐或保持 `INSUFFICIENT`，不能由“有一只上拉”生成 PASS。
电气检查初始始终 `WAITING_EVIDENCE`，需专家提供适用规格、工况计算及逐项结论。

新增项目与原有 Rule-09 直接连接/直接并联计算并存，不扩大后者的模型，也不自动将本清单
或 state population 注入热跑。对不同装配变体执行原有热检查时，仍需给对应实际装配的 db 和
绑定该 db/状态的 evidence；不能拿基础版 `nc` 与另一个变体的上拉结果混算。

清单含当前网表、完整声明上下文与内容摘要；计划对象绑定区域、状态、网络和清单摘要。
装配、跳线、端点或清单改变时，同版旧计划的自动合并也会拒绝，需逐项复核后迁移人工项。
最终校验传入 `--db`，重建并对比清单、检查新增覆盖；含连接缺口的区域不能写 PASS。
摘要只绑定被审输入，不验证引用文字真实，也不替代工程审查。
