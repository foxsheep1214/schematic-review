# schematic-review

**一套网表驱动的电路原理图系统性审查方法论，打包成 AI Agent 可直接调用的 skill。**

用于原理图冻结/进入 PCB Layout 前首审、改版 diff 复审和历史意见闭环核验——以
EDA 导出网表为第一数据源，用确定性规则解决覆盖率，用分层专家审查解决正确性。
本 skill 不签署已布 PCB、SI/PI、EMC、热、DFM 或生产准出。

---

## 核心思想

原理图的电气本质是**网络表**，图形只是可视化。所以审查不依赖 EDA 软件：把导出网表解析成结构化索引，然后分两层执行——

| 层 | 解决什么 | 怎么做 |
|---|---|---|
| **AC0 Automated Check（自动检查）** | **覆盖率与适用性发现** | 首轮生成逐项执行计划；Lint 执行确定性规则；改版 Diff 另执行 Rule-17 |
| **ER1–ER7 Expert Review（专家审查）** | **正确性与风险** | datasheet/身份 → 供电 → 链路 → WCA → 平台原理图规则 → 图形 → 器件身份/封装 |

关键纪律：**AC0 的输出是疑似清单，不是判决。** 合法结构（Bob-Smith 终端、DNP 选项、工具生成的伪网络）由执行 agent 逐条排除并留痕——实践中 AC0 命中数百条而真问题为零是常态，真问题往往来自需要判断的 ER3/ER4/ER5。

分层判据不是「能不能自动化」，而是**结论是「算出来的」还是「推出来的」**——算出来的（可复现、零幻觉、可穷举）交给脚本，推出来的（需语义理解或外部证据）交给 agent。全流程由 agent 驱动时这条线更要紧：AC0 的价值不是省人力，而是**把 LLM 不可靠的地方交给代码**（逐个核对 357 个电源球的驱动，脚本可追踪覆盖；让 agent 自己数，必漏）。

AC0 先做 **Applicability Discovery**：把网表特征、设计意图和材料可用性合并成
逐项 `review-plan.json`，标出每项的适用性、准备度、执行阶段和缺失输入。随后按输入
依赖分三档跑：**冷跑**（只吃网表）→ **冷跑·参数化**（加意图清单）→ ER1 →
**热跑**（加结构化 evidence.json）。冷跑除了 `FINDING`，还产出 `CANDIDATE`——
待 ER1 定夺的优先级清单，**直接决定优先读哪几份 datasheet**，而不是盲读几十份。
每趟末尾显式列出未执行的规则及原因：**扫出 0 条与根本没扫，绝不能长得一样。**

## V1.6 电路检查改进

按电路和工作状态展开检查，取消隐含公差和“有上拉即电平通过”。分压遇到未建模支路返回未判定；源追踪不把 TVS/电感/连接器当发电源；I2C 检查等效上拉；TVS 区分工作、击穿及钳位电压。
热跑必须绑定当前网表及已核实文档，缺资料的依赖项保持 INSUFFICIENT。旧 evidence 可读取，但需按 [证据 schema](references/datasheet-evidence-schema.md) 补齐才能得到 PASS。

## 三条铁律

1. **datasheet 原文 > 网表实测 > 页面注释。** 注释只是"待验证声明"（真实案例：图上标 V1=20V，实贴电阻算出 18.39V）
2. **历史评审意见只作线索，必须独立复核。** "回复已修改"不构成闭环证据，逐条对网表验证——假闭环是高频事件
3. **每条结论必须有证据链**：refdes + 网络名 + datasheet 条款/页码 + 置信度。没有证据链的发现不进报告

## 置信度与严重度

| 置信度 | 含义 | 处置 |
|---|---|---|
| **A** | 网表实证（断网、参数不符） | 可直接整改 |
| **B** | datasheet/规范已核 | 可直接整改 |
| **C** | 证据来源不充分或未核实 | 仅用于 `evidence_confidence`，**严禁臆测** |

严重度分 BLOCKER / Warning / Info / 观察。每个检查项独立记录
`PASS / FAIL / INSUFFICIENT / NA`；`INSUFFICIENT` 表示本项适用但材料不足。
`HANDOFF` 是独立的下游动作字段，不是第五种结果，可与 PASS、FAIL 或
INSUFFICIENT 并存。所有逐项记录完成后，再聚合出原理图准出结论。

---

## 目录

```
SKILL.md                          # 主干：三条铁律、分级标准、0→10 步流程、20 条高频错误自查表
scripts/                          # 可直接运行，无第三方依赖
  parse_netlist.py                #   三件套 → 结构化索引；自带自检闸门与伪网络识别
  audit_datasheets.py             #   逐物料覆盖审计 → agent 联网补取/用户提示任务
  plan_review.py                  #   AC0 适用性发现 → 逐项执行计划
  lint.py                         #   AC0 冷跑 + ER1 证据热跑 + PINUSE/ERC
  diff_netlists.py                #   新旧网表 Diff + Rule-17 历史闭环断言
  solve_dividers.py               #   串/并联分压 + min/typ/max 公差窗口
  tests/                           #   标准库 unittest 回归测试
references/
  scope-boundary.md               # 原理图可判定、HANDOFF 与范围外矩阵
  review-plan-schema.md           # AC0 intent 输入与逐项计划输出契约
  datasheet-resolution-schema.md  # 资料包审计、agent 补取与 FOUND/NOT_FOUND 写回
  datasheet-evidence-schema.md    # ER1 热跑输入格式
  diff-claims-schema.md           # 复审闭环断言格式
  methodology-v1.0.md             # 方法论完整长文档（AC0/ER1–ER7 各章细节、平台规则库构建方法、迁移指南）
  netlist-parsing.md              # 网表解析规范：三件套格式、pinname 两种布局、渲染读图与旋转页坐标换算；其他 EDA 适配
  lint-rules.md                   # AC0/改版 Diff 规则身份与运行依赖
  review-checklist.md             # 按电路域的通用检查表（电源/时钟/复位/接口/防护/监控/无源/连接器/热/文档）
  wca-formulas.md                 # 参数验算公式库：FB 分压、UVLO/OVLO、限流、钳位、ADC 分压、RC 复位、MLCC 偏压…
  report-template.md              # 报告骨架 + ECO 级发现项格式
examples/
  worked-example-industrial-gateway.md   # 一份完整的合成范例报告（虚构板卡）
```

## 审查流程

**检查标识表示主执行顺序；身份核实先于参数代入。** AC0 是唯一的自动检查层，ER1–ER7 是需要工程判断的专家审查层；流程步骤、检查标识与 Rule 编号相互独立。

```
0. 意图对齐（设计意图问卷）        5. ER3 关键链路逐条追踪
1. 数据解析（网表→结构化索引）     6. ER4 参数与边界验算（WCA）
2. AC0 适用性发现 + Lint 冷跑       7. ER5 平台原理图规则扫描
3. ER1 datasheet 核实 + AC0 热跑     8. ER6 图形化系统目检
4. ER2 供电系统审计（建电源树）     9. ER7 器件身份与封装一致性
                                  10. 输出分级报告 + 修复-复验闭环
```

**贯穿全程（不排队）**：文本层不可靠时立即渲染目检。等排到 ER6 再读图，
前面的结论已经写错了。

顺序有依据：先有 datasheet 才谈得上"违反"（ER1 供给 Rule-16 与 ER5 的判定依据、
供给 ER4 的公式常量）；先有电源树才有地图可走链路（ER2 → ER3）；
先走通链路才知道该算哪些点（ER3 → ER4）。

---

> **检查标识迁移（V1.2）**：`AC0` = Automated Check（原 `L0`），`ER1`～`ER7` = Expert Review（原 `L1`～`L7`）。迁移期可写成 `AC0（原 L0）`、`ER1（原 L1）`，换算表见 `references/methodology-v1.0.md` §0.2.1。
> **三个编号体系解耦**：步骤 0～10 表示工作流位置，AC0/ER1–ER7 表示检查模块，`Rule-01`～`Rule-20` 表示规则身份。
> **结果模型迁移（V1.4）**：材料不足统一写 `INSUFFICIENT`；A/B/C 只表示证据置信度；`HANDOFF` 从结果状态中拆出，作为可与审查结果并存的独立字段。
> **Datasheet 闭环（V1.5）**：逐物料审计资料包；MISSING 由 agent 联网补取；NOT_FOUND 逐颗提示用户；review_result 为 INSUFFICIENT，evidence_confidence 单独记录。

## 安装

作为 Claude Code / Claude Desktop 的个人 skill：

```bash
git clone https://github.com/foxsheep1214/schematic-review.git ~/.claude/skills/schematic-review
```

其他 agent 平台把仓库放进对应的 skills 目录即可。**本 skill 不含任何二进制依赖**，只需要环境具备：

- 文件读取
- Python 3 执行（解析网表）
- `pdftotext` / `pdftoppm`（poppler-utils，读图与渲染 datasheet）

## 使用

交给 agent：

```
按 schematic-review 审查 <项目路径> 的原理图
```

或手工跑确定性步骤：

```bash
python3 scripts/parse_netlist.py <项目>/allegro -o db.json
python3 scripts/audit_datasheets.py db.json \
       --datasheet-dir <项目>/datasheets --json datasheet-audit.json
python3 scripts/plan_review.py db.json --intent intent.json \
       --datasheet-audit datasheet-audit.json --json review-plan.json
python3 scripts/lint.py db.json --log <项目>/allegro/netlist.log \
       --intent intent.json --datasheet-audit datasheet-audit.json \
       --plan-json review-plan.json --json lint-cold.json
python3 scripts/lint.py db.json --intent intent.json \
       --datasheet-audit datasheet-audit.json \
       --evidence evidence.json --json lint-hot.json
python3 scripts/solve_dividers.py db.json --vfb U1=0.815 U2=0.6 \
       --vfb-tol 0.02 --json wca.json
python3 scripts/diff_netlists.py old-db.json db.json \
       --claims review-claims.json --json diff.json --fail-on-open-claims
python3 -m unittest discover -s scripts/tests -v
```

准备一个包含以下内容的目录：

| 输入 | 必需 | 说明 |
|---|---|---|
| 网表 | ✅ | 随附解析器支持 Cadence/OrCAD 三件套；其他 EDA 需项目适配器先生成同契约 db.json |
| 原理图 PDF | ✅ | 用于读图复核与版本比对 |
| intent.json | 建议 | 声明功能适用性、材料可用性与关键器件期望；缺失项保持 `UNDETERMINED`，不自动写 NA |
| datasheet 包 | ✅ | 关键器件必须齐全，否则相关检查项标为 `INSUFFICIENT`，不得写 PASS |
| datasheet-audit.json | ✅ | 逐物料 AVAILABLE/MISSING/NOT_FOUND 与 agent_requests |
| datasheet-resolution.json | 缺料时必需 | Agent 联网补取后的 FOUND/NOT_FOUND 写回 |
| evidence.json | 热跑必需 | ER1 从 datasheet 提取的结构化检查证据 |
| 旧版 db.json + 历史断言 | 复审必需 | 用于 Rule-17 真/假闭环 |
| 需求/规格书 | 建议 | 缺失时报告会声明"规格符合性判定受限" |

只要能从工具链拿到 `{nets, parts, pin2net}` 三个索引，AC0/ER1–ER7 全部流程原样适用。

---

## 这套方法能接住什么

方法论的价值不只在"找到什么"，更在**挡住误报**。以下都是实际发生过、被流程接住的：

- 按单颗电阻算分压，得出"供电 5.38V 会烧模组"——追到底发现下臂是两颗**串联**，实际 3.83V
  （该板 15 处分压**全部**含串联臂，所以这不是小概率事件；`solve_dividers.py` 就是为此存在）
- 网表里一张挂 357 个引脚、名为 `NC` 的网络，看似隔离栅被短接——两路独立证据证明是导出工具的**伪网络**
- 按"可调阈值"算监控点得出异常值——渲染 datasheet 订购表目检后发现该变体是**工厂固定档**

对应到规则上，就是 `SKILL.md` 里那张 20 条高频错误模式自查表，每轮强制过一遍；
能自动化的部分已固化进 `scripts/`——包括那条最要命的**静默失败**：
引脚功能名提取失败时，依赖它的两条规则会安静地扫出 0 条并被当成"全部通过"，
所以 `parse_netlist.py` 在覆盖率过低时**直接报错退出**，宁可中断也不交出残缺索引。

## 关于平台规则库

`references/methodology-v1.0.md` 第 7 章只提供**构建方法与空模板**，不附任何具体厂商的规则内容——各 SoC 原厂/平台方的设计指南受其自身授权条款约束且版本更新频繁，请以你手上的官方文档版本为准自行生成。

## 关于范例报告

`examples/` 中的范例为**合成内容**，板卡、位号、参数均为虚构，仅用于演示报告结构与详略程度。

---

## License

MIT — 见 [LICENSE](LICENSE)。
